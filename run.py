import os, random, time, requests, feedparser
from requests.auth import HTTPBasicAuth
from anthropic import Anthropic
from openai import OpenAI
from bs4 import BeautifulSoup

# ── 1. 스케줄 실행이면 무작위 0–30분 대기 ─────────────────────────────
if os.getenv("GITHUB_EVENT_NAME") == "schedule":
    wait = random.randint(0, 1800)
    print(f"[CRON] {wait}초 대기 후 실행")
    time.sleep(wait)
else:
    print("[수동 실행] 즉시 실행")

# ── 2. 필수 ENV ───────────────────────────────────────────────────
wp_user       = os.environ["WP_USERNAME"]
wp_password   = os.environ["WP_APP_PASSWORD"]
wp_site       = os.environ["WP_SITE_URL"].rstrip("/")
wp_api_url    = f"{wp_site}/wp-json/wp/v2/posts"

#   카테고리 ID: 비어 있으면 4 사용
category_id   = int(os.getenv("WP_CATEGORY_ID") or "4")

anthropic_key = os.environ["CLAUDE_API_KEY"]
openai_key    = os.environ["OPENAI_API_KEY"]

# ── 3. 최신 정치 기사 가져오기 ────────────────────────────────────
rss_url = "https://rss.donga.com/politics.xml"
entry   = feedparser.parse(rss_url).entries[0]
news_title, news_link = entry.title, entry.link

html = requests.get(news_link, headers={"User-Agent": "Mozilla/5.0"}).text
soup = BeautifulSoup(html, "html.parser")
news_body = "\n".join(p.get_text(strip=True) for p in soup.select("p")[:40])

# ── 4. Claude 요약/의견 생성 ──────────────────────────────────────
with open("claude_prompt.txt", encoding="utf-8") as f:
    prompt_tmpl = f.read()

anthropic = Anthropic(api_key=anthropic_key)
claude = anthropic.messages.create(
    model="claude-3-sonnet-20240229",
    max_tokens=900,
    temperature=0.7,
    messages=[{"role": "user", "content": prompt_tmpl.format(title=news_title, body=news_body)}],
)
blog_text = claude.content[0].text

# ── 5. GPT-4로 이미지 프롬프트 3개 추출 ───────────────────────────
openai = OpenAI(api_key=openai_key)
img_resp = openai.chat.completions.create(
    model="gpt-4o-mini",
    temperature=0.7,
    messages=[
        {"role": "system", "content": "다음 글을 바탕으로 사진처럼 상상할 수 있는 프롬프트 3개를 한 줄씩 출력하세요."},
        {"role": "user", "content": blog_text}
    ],
)
prompts = [l.strip("- ").strip() for l in img_resp.choices[0].message.content.splitlines() if l.strip()]
img_html = "".join(f"<p><em>이미지 프롬프트: {p}</em></p>" for p in prompts)

# ── 6. 최종 본문 HTML ────────────────────────────────────────────
full_body = f"""<p><a href="{news_link}" target="_blank">원문 기사 보기</a></p>
{img_html}
<div>{blog_text}</div>
"""

# ── 7. 워드프레스 발행 ────────────────────────────────────────────
payload = {
    "title": news_title,
    "content": full_body,
    "status": "publish",
    "categories": [category_id]
}
resp = requests.post(wp_api_url, json=payload, auth=HTTPBasicAuth(wp_user, wp_password))
print("WP response:", resp.status_code)
print(resp.text)
