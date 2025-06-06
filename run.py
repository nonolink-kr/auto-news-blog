"""
Auto-blogging script – Claude Sonnet 4 기본 사용
"""
import os, sys, random, time, requests, feedparser
from requests.auth import HTTPBasicAuth

# 0. 랜덤 대기(스케줄 실행 시)
if os.getenv("GITHUB_EVENT_NAME") == "schedule":
    wait = random.randint(0, 1800)
    print(f"[CRON] sleep {wait}s")
    time.sleep(wait)
else:
    print("[Manual] run immediately")

def need(name: str) -> str:
    v = os.getenv(name, "").strip()
    if not v:
        sys.exit(f"❌ ENV {name} is missing.")
    return v

WP_USERNAME       = need("WP_USERNAME")
WP_APP_PASSWORD   = need("WP_APP_PASSWORD")
WP_SITE_URL       = need("WP_SITE_URL").rstrip("/")
ANTHROPIC_API_KEY = need("ANTHROPIC_API_KEY")
OPENAI_API_KEY    = need("OPENAI_API_KEY")

cat_raw = os.getenv("WP_CATEGORY_ID", "").strip()
CATEGORY_ID = int(cat_raw) if cat_raw.isdigit() else 4
WP_POST_API = f"{WP_SITE_URL}/wp-json/wp/v2/posts"

# 1. 최신 정치 기사
entry = feedparser.parse("https://rss.donga.com/politics.xml").entries[0]
news_title, news_link = entry.title, entry.link

html = requests.get(news_link, headers={"User-Agent":"Mozilla/5.0"}).text
try:
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "lxml")
    news_body = "\n".join(p.get_text(" ", strip=True) for p in soup.find_all("p")[:40])
except ImportError:
    news_body = entry.summary

# 2. Claude Sonnet 4 요약/의견
from anthropic import Anthropic
with open("claude_prompt.txt", encoding="utf-8") as fp:
    tmpl = fp.read()

model_name = os.getenv("CLAUDE_MODEL", "claude-3-sonnet-20260408")
print(f"▶ Anthropic model = {model_name}")

anthropic = Anthropic(api_key=ANTHROPIC_API_KEY)
resp = anthropic.messages.create(
    model=model_name,
    max_tokens=900,
    temperature=0.7,
    messages=[{"role":"user","content":tmpl.format(title=news_title, body=news_body)}],
)
blog_text = resp.content[0].text
print("✔ Claude Sonnet 4 완료")

# 3. GPT-4 이미지 프롬프트
from openai import OpenAI
openai = OpenAI(api_key=OPENAI_API_KEY)
img_resp = openai.chat.completions.create(
    model="gpt-4o-mini",
    temperature=0.7,
    messages=[
        {"role":"system","content":"아래 글을 시각화할 사진 프롬프트 3줄 작성"},
        {"role":"user","content":blog_text},
    ],
)
prompts = [l.strip("- ").strip() for l in img_resp.choices[0].message.content.splitlines() if l.strip()]
img_html = "".join(f"<p><em>이미지 프롬프트: {p}</em></p>" for p in prompts)

# 4. 최종 본문
full_body = f"""<p><a href="{news_link}" target="_blank">원문 기사 보기</a></p>
{img_html}
<div>{blog_text}</div>
"""

# 5. 워드프레스 발행
payload = {
    "title": news_title,
    "content": full_body,
    "status": "publish",
    "categories": [CATEGORY_ID],
}
r = requests.post(WP_POST_API, json=payload,
                  auth=HTTPBasicAuth(WP_USERNAME, WP_APP_PASSWORD))
print("WP response:", r.status_code)
print(r.text[:400])
