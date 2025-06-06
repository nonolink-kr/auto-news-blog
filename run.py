"""
Auto-blogging script with Anthropic fallback (module fixed)
"""
import os, sys, random, time, requests, feedparser
from requests.auth import HTTPBasicAuth
import anthropic      # ← 모듈 임포트

# 0. 랜덤 대기(스케줄 실행 시)
if os.getenv("GITHUB_EVENT_NAME") == "schedule":
    delay = random.randint(0, 1800)
    print(f"[CRON] sleep {delay}s")
    time.sleep(delay)
else:
    print("[Manual] run immediately")

def need(name: str) -> str:
    v = os.getenv(name, "").strip()
    if not v:
        sys.exit(f"ENV {name} is missing. Check Secrets.")
    return v

WP_USERNAME       = need("WP_USERNAME")
WP_APP_PASSWORD   = need("WP_APP_PASSWORD")
WP_SITE_URL       = need("WP_SITE_URL").rstrip("/")
ANTHROPIC_API_KEY = need("ANTHROPIC_API_KEY")
OPENAI_API_KEY    = need("OPENAI_API_KEY")

CATEGORY_ID = int(os.getenv("WP_CATEGORY_ID", "4") or 4)
WP_POST_API = f"{WP_SITE_URL}/wp-json/wp/v2/posts"

# 1. 최신 정치 기사
e = feedparser.parse("https://rss.donga.com/politics.xml").entries[0]
news_title, news_link = e.title, e.link

html = requests.get(news_link, headers={"User-Agent":"Mozilla/5.0"}).text
try:
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "lxml")
    news_body = "\n".join(p.get_text(" ", strip=True) for p in soup.find_all("p")[:40])
except ImportError:
    news_body = e.summary

# 2. Claude 요약/의견 (Sonnet→Haiku 백업)
with open("claude_prompt.txt", encoding="utf-8") as fp:
    tmpl = fp.read()

primary_model = os.getenv("CLAUDE_MODEL", "claude-3-sonnet-20240229").strip()
backup_model  = "claude-3-haiku-20240307"

print(f"▶ Primary model: {primary_model}")
client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

def call(model):
    return client.messages.create(
        model=model,
        max_tokens=900,
        temperature=0.7,
        messages=[{"role":"user",
                   "content": tmpl.format(title=news_title, body=news_body)}],
    )

try:
    resp = call(primary_model)
except anthropic.NotFoundError:
    print(f"⚠️ {primary_model} not found → fallback {backup_model}")
    resp = call(backup_model)

blog_text = resp.content[0].text
print("✔ Claude done")

# ── 3. GPT-4 이미지 프롬프트 (RateLimit 대비) ───────────────────
from openai import OpenAI, RateLimitError
openai = OpenAI(api_key=OPENAI_API_KEY)

try:
    img_resp = openai.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0.7,
        messages=[
            {"role": "system",
             "content": "아래 글을 시각화할 사진 프롬프트 3줄 작성"},
            {"role": "user", "content": blog_text},
        ],
    )
    prompts = [ln.strip("- ").strip()
               for ln in img_resp.choices[0].message.content.splitlines()
               if ln.strip()]
    img_html = "".join(
        f"<p><em>이미지 프롬프트: {p}</em></p>" for p in prompts
    )

except RateLimitError as e:
    print("⚠️ OpenAI quota 초과 – 이미지 프롬프트 생략")
    img_html = "<p><em>(이미지 프롬프트 생략: OpenAI quota 부족)</em></p>"

# 4. 본문 구성
full_body = (
    f"<p><a href='{news_link}' target='_blank'>원문 기사 보기</a></p>\n"
    f"{img_html}\n"
    f"<div>{blog_text}</div>"
)

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