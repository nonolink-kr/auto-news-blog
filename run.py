import os, sys, random, time, re, json, requests, feedparser
from requests.auth import HTTPBasicAuth
import anthropic
from openai import OpenAI, RateLimitError
from insert_images_logged import insert_images_into_body  # 이미지 삽입용 함수 추가

# 0. 랜덤 대기 (스케줄 실행 시)
if os.getenv("GITHUB_EVENT_NAME") == "schedule":
    delay = random.randint(0, 1800)
    print(f"[CRON] sleep {delay}s")
    time.sleep(delay)
else:
    print("[Manual] run immediately")

# 1. ENV 변수 로드
def need(k: str) -> str:
    v = os.getenv(k, "").strip()
    if not v:
        sys.exit(f"❌ ENV {k} is missing.")
    return v

WP_USERNAME       = need("WP_USERNAME")
WP_APP_PASSWORD   = need("WP_APP_PASSWORD")
WP_SITE_URL       = need("WP_SITE_URL").rstrip("/")
if not WP_SITE_URL.startswith(("http://", "https://")):
    WP_SITE_URL = "https://" + WP_SITE_URL
ANTHROPIC_API_KEY = need("ANTHROPIC_API_KEY")
OPENAI_API_KEY    = os.getenv("OPENAI_API_KEY", "").strip()
CATEGORY_ID = int(os.getenv("WP_CATEGORY_ID", "4") or 4)
WP_POST_API = f"{WP_SITE_URL}/wp-json/wp/v2/posts"

# 2. 최신 정치 기사 크롤링
rss_entry = feedparser.parse("https://rss.donga.com/politics.xml").entries[0]
news_title, news_link = rss_entry.title, rss_entry.link

article_html = requests.get(news_link, headers={"User-Agent": "Mozilla/5.0"}).text
try:
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(article_html, "lxml")
    news_body = "\n".join(p.get_text(" ", strip=True) for p in soup.find_all("p")[:40])
except ImportError:
    news_body = rss_entry.summary

# 3. Claude 프롬프트
with open("claude_prompt.txt", encoding="utf-8") as fp:
    prompt_template = fp.read()
length_hint = random.choice(["2300자 내외", "2400자 내외", "2500자 내외"])
prompt = (prompt_template
          .replace("{length_hint}", length_hint)
          .replace("{title}", news_title)
          .replace("{body}", news_body))

def unescape(s: str) -> str:
    s = s.replace("\\", "\\\\")
    s = s.replace('"', '\\"')
    s = s.replace("\n", "\\n")
    s = s.replace("\r", "")
    return json.loads(f'"{s}"')

def try_extract_json_block(text):
    match = re.search(r'\{.*\}', text, re.S)
    return match.group(0) if match else text


def try_parse_claude_response(text, model_used):
    if model_used == "claude-3-haiku-20240307":
        lines = text.strip().splitlines()
        if len(lines) >= 2:
            return {
                "title": lines[0].strip(),
                "body": "\n".join(line.strip() for line in lines[1:])
            }
        else:
            sys.exit("❌ Haiku 응답 포맷 해석 실패")

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        candidate = try_extract_json_block(text)
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            t_m = re.search(r'"title"\s*:\s*"((?:[^"\\]|\\.)*)"', candidate, re.S)
            b_m = re.search(r'"body"\s*:\s*"((?:[^"\\]|\\.)*)"', candidate, re.S)
            if not (t_m and b_m):
                print("Claude raw ▶", text[:400])
                sys.exit("❌ Claude JSON 파싱 실패(3단계)")
            return {
                "title": unescape(t_m.group(1)),
                "body": unescape(b_m.group(1))
            }


primary_model = os.getenv("CLAUDE_MODEL", "claude-3-sonnet-20240601").strip()
backup_model  = "claude-3-haiku-20240307"
client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
def claude_call(model):
    response = client.messages.create(
        model=model,
        max_tokens=1000,
        temperature=0.7,
        messages=[{"role": "user", "content": prompt}],
    )
    return response, model
try:
    resp, model_used = claude_call(primary_model)
except anthropic.NotFoundError:
    print(f"⚠️ {primary_model} unavailable → fallback {backup_model}")
    resp, model_used = claude_call(backup_model)

raw_text = resp.content[0].text
content_json = try_parse_claude_response(raw_text, model_used)

post_title = content_json.get("title", "제목 없음")[:90]
post_body  = content_json.get("body", "")

# 4. 이미지 프롬프트 (선택)
img_html = ""
if OPENAI_API_KEY:
    openai = OpenAI(api_key=OPENAI_API_KEY)
    try:
        _ = openai.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0.7,
            messages=[
                {"role": "system", "content": "아래 글을 시각화할 사진 프롬프트 3줄 작성"},
                {"role": "user", "content": post_body},
            ],
        )
    except RateLimitError:
        print("⚠️ OpenAI quota 초과 – 이미지 프롬프트 스킵")

# 5. 최종 본문 (이미지 삽입 포함)
body_with_images = insert_images_into_body(post_body)
html_content = (
    "<p><a href='" + news_link + "' target='_blank'>원문 기사 보기</a></p>
" + body_with_images
)

html_content = (
    "<p><a href='" + news_link + "' target='_blank'>원문 기사 보기</a></p>
" + body_with_images
)

# 6. 워드프레스 업로드
payload = {
    "title": post_title,
    "content": html_content,
    "status": "publish",
    "categories": [CATEGORY_ID],
}
r = requests.post(WP_POST_API, json=payload, auth=HTTPBasicAuth(WP_USERNAME, WP_APP_PASSWORD))
print("WP response:", r.status_code)
print(r.text[:400])