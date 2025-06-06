"""
auto-news-blog · click-bait title + 반말 + 비문
  - Claude JSON 파싱 보강 버전
"""
import os, sys, random, time, re, json, requests, feedparser
from requests.auth import HTTPBasicAuth
import anthropic
from openai import OpenAI, RateLimitError

# ────────────────────────────────────────────────────────────────
# 0. 랜덤 대기 (스케줄 실행 시)
if os.getenv("GITHUB_EVENT_NAME") == "schedule":
    delay = random.randint(0, 1800)
    print(f"[CRON] sleep {delay}s")
    time.sleep(delay)
else:
    print("[Manual] run immediately")

# ────────────────────────────────────────────────────────────────
# 1. ENV 변수 로드
def need(k: str) -> str:
    v = os.getenv(k, "").strip()
    if not v:
        sys.exit(f"❌ ENV {k} is missing.")
    return v

WP_USERNAME       = need("WP_USERNAME")
WP_APP_PASSWORD   = need("WP_APP_PASSWORD")
WP_SITE_URL       = need("WP_SITE_URL").rstrip("/")
if not WP_SITE_URL.startswith(("http://", "https://")):   # 스킴 자동 보정
    WP_SITE_URL = "https://" + WP_SITE_URL
ANTHROPIC_API_KEY = need("ANTHROPIC_API_KEY")
OPENAI_API_KEY    = os.getenv("OPENAI_API_KEY", "").strip()

CATEGORY_ID = int(os.getenv("WP_CATEGORY_ID", "4") or 4)
WP_POST_API = f"{WP_SITE_URL}/wp-json/wp/v2/posts"

# ────────────────────────────────────────────────────────────────
# 2. 최신 정치 기사 크롤링
rss_entry = feedparser.parse("https://rss.donga.com/politics.xml").entries[0]
news_title, news_link = rss_entry.title, rss_entry.link

article_html = requests.get(news_link, headers={"User-Agent": "Mozilla/5.0"}).text
try:
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(article_html, "lxml")
    news_body = "\n".join(p.get_text(" ", strip=True)
                          for p in soup.find_all("p")[:40])
except ImportError:
    news_body = rss_entry.summary

# ────────────────────────────────────────────────────────────────
# 3. Claude: 클릭베이트 제목 + 반말 본문(JSON)
with open("claude_prompt.txt", encoding="utf-8") as fp:
    prompt_template = fp.read()
length_hint = random.choice([
    "2300자 내외", "2400자 내외", "2500자 내외"
])
prompt = prompt_template.replace("{length_hint}", length_hint)
prompt = (prompt_template
          .replace("{title}", news_title)
          .replace("{body}",  news_body))

primary_model = os.getenv("CLAUDE_MODEL", "claude-3-sonnet-20240229").strip()
backup_model  = "claude-3-haiku-20240307"
client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

def claude_call(model):
    return client.messages.create(
        model=model,
        max_tokens=1000,
        temperature=0.7,
        messages=[{"role": "user", "content": prompt}],
    )

try:
    resp = claude_call(primary_model)
except anthropic.NotFoundError:
    print(f"⚠️ {primary_model} unavailable → fallback {backup_model}")
    resp = claude_call(backup_model)

# ─── Claude 응답(JSON) 파싱 ────────────────────────────────
raw_text = resp.content[0].text

# ① 직접 json.loads 시도
try:
    content_json = json.loads(raw_text)
except json.JSONDecodeError:
    # ② 첫 { … } 블록 추출 후 재시도
    blk = re.search(r'\{.*?\}', raw_text, re.S)
    candidate = blk.group(0) if blk else ""
    try:
        content_json = json.loads(candidate)
    except json.JSONDecodeError:
        # ---------- 단계 ③ 수동 추출 ----------
        t_m = re.search(r'"title"\s*:\s*"((?:[^"\\]|\\.)*)"', candidate, re.S)
        b_m = re.search(r'"body"\s*:\s*"((?:[^"\\]|\\.)*)"', candidate, re.S)
        if not (t_m and b_m):
            print("Claude raw ▶", raw_text[:400])
            sys.exit("❌ Claude JSON 파싱 실패(3단계)")
        content_json = {
            "title": unescape(t_m.group(1)),
            "body": unescape(b_m.group(1))
        }
def unescape(s: str) -> str:
    return json.loads(f'"{s}"')   # "..." 를 다시 JSON 으로 파싱

content_json = {
    "title": unescape(t_m.group(1)),
    "body":  unescape(b_m.group(1))
}
# --------------------------------------------------------------

post_title = content_json.get("title", "제목 없음")[:90]
post_body  = content_json.get("body", "")
# ────────────────────────────────────────────────────────────────
# 4. 이미지 프롬프트 (OpenAI 키 없으면 생략)
img_html = ""
if OPENAI_API_KEY:
    openai = OpenAI(api_key=OPENAI_API_KEY)
    try:
        _ = openai.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0.7,
            messages=[
                {"role": "system",
                 "content": "아래 글을 시각화할 사진 프롬프트 3줄 작성"},
                {"role": "user", "content": post_body},
            ],
        )
        # 프롬프트 자체는 본문에 넣지 않음 (SEO·가독성 유지)
    except RateLimitError:
        print("⚠️ OpenAI quota 초과 – 이미지 프롬프트 스킵")

# ────────────────────────────────────────────────────────────────
# 5. 최종 본문
html_content = (
    f"<p><a href='{news_link}' target='_blank'>원문 기사 보기</a></p>\n"
    f"<div>{post_body}</div>"
)

# ────────────────────────────────────────────────────────────────
# 6. 워드프레스 발행
payload = {
    "title": post_title,
    "content": html_content,
    "status": "publish",
    "categories": [CATEGORY_ID],
}

r = requests.post(WP_POST_API, json=payload,
                  auth=HTTPBasicAuth(WP_USERNAME, WP_APP_PASSWORD))
print("WP response:", r.status_code)
print(r.text[:400])