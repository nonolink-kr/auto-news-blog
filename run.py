"""
Auto-blogging script (uses ANTHROPIC_API_KEY, robust category)
"""
import os, sys, random, time, requests, feedparser
from requests.auth import HTTPBasicAuth

# ── 0. 스케줄 실행이면 0-30분 랜덤 대기 ──────────────────────────
if os.getenv("GITHUB_EVENT_NAME") == "schedule":
    delay = random.randint(0, 1800)
    print(f"[CRON] sleep {delay}s")
    time.sleep(delay)
else:
    print("[Manual] run immediately")

# ── 1. 필수 ENV 로딩 + 검증 ────────────────────────────────────
def need(name: str) -> str:
    v = os.getenv(name, "").strip()
    if not v:
        sys.exit(f"❌ ENV {name} 가 비어 있습니다. GitHub Secrets 확인!")
    return v

WP_USERNAME       = need("WP_USERNAME")
WP_APP_PASSWORD   = need("WP_APP_PASSWORD")
WP_SITE_URL       = need("WP_SITE_URL").rstrip("/")
ANTHROPIC_API_KEY = need("ANTHROPIC_API_KEY")
OPENAI_API_KEY    = need("OPENAI_API_KEY")

# WP_CATEGORY_ID: 비어 있거나 숫자가 아니면 4
cat_env = os.getenv("WP_CATEGORY_ID", "").strip()
CATEGORY_ID = int(cat_env) if cat_env.isdigit() else 4

WP_POST_API = f"{WP_SITE_URL}/wp-json/wp/v2/posts"

# ── 2. 최신 정치 기사 추출 ─────────────────────────────────────
rss_url = "https://rss.donga.com/politics.xml"
entry   = feedparser.parse(rss_url).entries[0]
news_title, news_link = entry.title, entry.link

html = requests.get(news_link, headers={"User-Agent":"Mozilla/5.0"}).text
try:
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "lxml")
    news_body = "\n".join(p.get_text(" ", strip=True) for p in soup.find_all("p")[:40])
except ImportError:
    news_body = entry.summary

# ── 3. Claude 요약/의견 생성 ───────────────────────────────────
from anthropic import Anthropic
with open("claude_prompt.txt", encoding="utf-8") as fp:
    tmpl = fp.read()

anthropic = Anthropic(api_key=ANTHROPIC_API_KEY)
msg = anthropic.messages.create(
    model="claude-3-sonnet-20240620",
    max_tokens=900,
    temperature=0.7,
    messages=[{"role":"user","content":tmpl.format(title=news_title, body=news_body)}],
)
blog_text = msg.content[0].text
print("✔ Claude done")

# ── 4. GPT-4로 이미지 프롬프트 3개 생성 ─────────────────────────
from openai import OpenAI
openai = OpenAI(api_key=OPENAI_API_KEY)
img_resp = openai.chat.completions.create(
    model="gpt-4o-mini",
    temperature=0.7,
    messages=[
        {"role":"system","content":"아래 글을 사진처럼 시각화할 프롬프트 3줄 작성"},
        {"role":"user","content":blog_text},
    ],
)
prompts = [ln.strip("- ").strip() for ln in img_resp.choices[0].message.content.splitlines() if ln.strip()]
img_html = "".join(f"<p><em>이미지 프롬프트: {p}</em></p>" for p in prompts)

# ── 5. 최종 본문 HTML 구성 ─────────────────────────────────────
full_body = f"""<p><a href="{news_link}" target="_blank">원문 기사 보기</a></p>
{img_html}
<div>{blog_text}</div>
"""

# ── 6. 워드프레스 발행 ─────────────────────────────────────────
payload = {
    "title": news_title,
    "content": full_body,
    "status": "publish",
    "categories": [CATEGORY_ID],
}
resp = requests.post(WP_POST_API, json=payload,
                     auth=HTTPBasicAuth(WP_USERNAME, WP_APP_PASSWORD))
print("WP response:", resp.status_code)
print(resp.text[:400])
