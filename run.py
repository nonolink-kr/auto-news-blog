"""
Auto-blogging script
• 스케줄(cron)로 실행되면 0-30분 랜덤 대기
• 수동(workflow_dispatch) 실행은 즉시
• 정치 RSS → Claude 요약/의견 → GPT-4 이미지 프롬프트 → 워드프레스 발행
"""
import os, random, time, sys, requests, feedparser
from requests.auth import HTTPBasicAuth

# ── 0. 스케줄 실행 시 랜덤 대기 ───────────────────────────────
if os.getenv("GITHUB_EVENT_NAME") == "schedule":
    wait = random.randint(0, 1800)
    print(f"[CRON] waiting {wait} s")
    time.sleep(wait)
else:
    print("[Manual] run immediately")

# ── 1. 환경변수 로딩 + 검증 ──────────────────────────────────
def need(name: str) -> str:
    val = os.getenv(name, "").strip()
    if not val:
        sys.exit(f"❌ 환경변수 {name} 가 비어 있습니다. GitHub Secrets 확인!")
    return val

WP_USERNAME      = need("WP_USERNAME")
WP_APP_PASSWORD  = need("WP_APP_PASSWORD")
WP_SITE_URL      = need("WP_SITE_URL").rstrip("/")
CLAUDE_API_KEY   = need("CLAUDE_API_KEY")
OPENAI_API_KEY   = need("OPENAI_API_KEY")

CATEGORY_ID      = int(os.getenv("WP_CATEGORY_ID") or "4")
WP_POST_API      = f"{WP_SITE_URL}/wp-json/wp/v2/posts"

# ── 2. 정치 뉴스 RSS 파싱 ──────────────────────────────────
rss_url = "https://rss.donga.com/politics.xml"
entry   = feedparser.parse(rss_url).entries[0]
news_title, news_link = entry.title, entry.link

# 원문 간단 추출
html = requests.get(news_link, headers={"User-Agent": "Mozilla/5.0"}).text
try:
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "lxml")
    news_body = "\n".join(p.get_text(" ", strip=True) for p in soup.find_all("p")[:40])
except ImportError:
    news_body = entry.summary

# ── 3. Claude 요약 및 의견 생성 ─────────────────────────────
from anthropic import Anthropic
with open("claude_prompt.txt", encoding="utf-8") as fp:
    tmpl = fp.read()

claude_client = Anthropic(api_key=CLAUDE_API_KEY)
claude_resp = claude_client.messages.create(
    model="claude-3-sonnet-20240620",
    max_tokens=900,
    temperature=0.7,
    messages=[{"role": "user", "content": tmpl.format(title=news_title, body=news_body)}],
)
blog_text = claude_resp.content[0].text
print("✔ Claude 완료")

# ── 4. GPT-4로 이미지 프롬프트 3개 생성 ────────────────────
from openai import OpenAI
openai_client = OpenAI(api_key=OPENAI_API_KEY)
img_prompts_resp = openai_client.chat.completions.create(
    model="gpt-4o-mini",
    temperature=0.7,
    messages=[
        {"role": "system", "content": "아래 글을 사진처럼 상상할 수 있는 프롬프트 3줄을 만들어줘."},
        {"role": "user", "content": blog_text}
    ],
)
prompts = [ln.strip("- ").strip() for ln in img_prompts_resp.choices[0].message.content.splitlines() if ln.strip()]
img_html = "".join(f"<p><em>이미지 프롬프트: {p}</em></p>" for p in prompts)

# ── 5. 최종 본문 HTML ───────────────────────────────────────
full_body = f"""<p><a href="{news_link}" target="_blank">원문 기사 보기</a></p>
{img_html}
<div>{blog_text}</div>
"""

# ── 6. 워드프레스 발행 ───────────────────────────────────────
payload = {
    "title": news_title,
    "content": full_body,
    "status": "publish",
    "categories": [CATEGORY_ID],
}

resp = requests.post(WP_POST_API, json=payload,
                     auth=HTTPBasicAuth(WP_USERNAME, WP_APP_PASSWORD))
print("WP response:", resp.status_code)
print(resp.text[:500])
