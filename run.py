"""
auto-news-blog · click-bait title & 반말 + 비문 / 기존 패치 유지
"""
import os, sys, random, time, json, requests, feedparser
from requests.auth import HTTPBasicAuth
import anthropic
from openai import OpenAI, RateLimitError

# ── 0. 랜덤 대기(스케줄 실행 시) ────────────────────────────────
if os.getenv("GITHUB_EVENT_NAME") == "schedule":
    delay = random.randint(0, 1800)
    print(f"[CRON] sleep {delay}s")
    time.sleep(delay)
else:
    print("[Manual] run immediately")

# ── 1. ENV 로드 & 검증 ─────────────────────────────────────────
def need(k: str) -> str:
    v = os.getenv(k, "").strip()
    if not v:
        sys.exit(f"❌ ENV {k} is missing.")
    return v

WP_USERNAME       = need("WP_USERNAME")
WP_APP_PASSWORD   = need("WP_APP_PASSWORD")
WP_SITE_URL       = need("WP_SITE_URL").rstrip("/")
if not WP_SITE_URL.startswith(("http://", "https://")):
    WP_SITE_URL = "https://" + WP_SITE_URL  # 스킴 자동 보정

ANTHROPIC_API_KEY = need("ANTHROPIC_API_KEY")
OPENAI_API_KEY    = os.getenv("OPENAI_API_KEY", "").strip()  # 없어도 동작

CATEGORY_ID = int(os.getenv("WP_CATEGORY_ID", "4") or 4)
WP_POST_API = f"{WP_SITE_URL}/wp-json/wp/v2/posts"

# ── 2. 최신 정치 기사 스크랩 ──────────────────────────────────
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

# ── 3. Claude: 클릭유도 제목 + 반말 본문(JSON) ────────────────
with open("claude_prompt.txt", encoding="utf-8") as fp:
    prompt = fp.read().format(title=news_title, body=news_body)

primary_model = os.getenv("CLAUDE_MODEL", "claude-3-sonnet-20240229").strip()
backup_model  = "claude-3-haiku-20240307"

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
def call_claude(model):
    return client.messages.create(
        model=model,
        max_tokens=1000,
        temperature=0.7,
        messages=[{"role": "user", "content": prompt}],
    )

try:
    resp = call_claude(primary_model)
except anthropic.NotFoundError:
    print(f"⚠️ {primary_model} unavailable → fallback {backup_model}")
    resp = call_claude(backup_model)

try:
    content_json = json.loads(resp.content[0].text)
    post_title = content_json["title"][:90]   # 제목 안전 길이
    post_body  = content_json["body"]
except (KeyError, json.JSONDecodeError):
    sys.exit("❌ Claude JSON 파싱 실패")

# ── 4. 이미지 프롬프트 (Quota 초과 시 완전 생략) ────────────────
img_html = ""
if OPENAI_API_KEY:
    openai = OpenAI(api_key=OPENAI_API_KEY)
    try:
        img_resp = openai.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0.7,
            messages=[
                {"role": "system",
                 "content": "아래 글을 시각화할 사진 프롬프트 3줄 작성"},
                {"role": "user", "content": post_body},
            ],
        )
        # 프롬프트를 사용해도 본문에는 넣지 않음(SEO·가독성 유지)
    except RateLimitError:
        print("⚠️ OpenAI quota 초과 – 이미지 프롬프트 스킵")

# ── 5. 최종 본문(프롬프트·오류 문구 비노출) ────────────────────
html_content = (
    f"<p><a href='{news_link}' target='_blank'>원문 기사 보기</a></p>\n"
    f"<div>{post_body}</div>"
)

# ── 6. 워드프레스 발행 ─────────────────────────────────────────
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