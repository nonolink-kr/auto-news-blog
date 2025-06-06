
import os
import random
import time
import requests
from requests.auth import HTTPBasicAuth
from bs4 import BeautifulSoup
import feedparser
from anthropic import Anthropic
from openai import OpenAI

# ───────────────────────────────────────────
# 1) 스케줄 실행일 때만 0‑30분 랜덤 대기
# ───────────────────────────────────────────
if os.getenv("GITHUB_EVENT_NAME") == "schedule":
    wait = random.randint(0, 1800)
    print(f"[CRON] {wait}초 대기 후 실행합니다.")
    time.sleep(wait)
else:
    print("[수동 실행] 즉시 실행합니다.")

# ───────────────────────────────────────────
# 2) 필수 환경변수
# ───────────────────────────────────────────
wp_user       = os.environ["WP_USERNAME"]
wp_password   = os.environ["WP_APP_PASSWORD"]
wp_site       = os.environ["WP_SITE_URL"].rstrip("/")
category_id   = int(os.getenv("WP_CATEGORY_ID", "4"))
anthropic_key = os.environ["CLAUDE_API_KEY"]
openai_key    = os.environ["OPENAI_API_KEY"]

wp_api_url = f"{wp_site}/wp-json/wp/v2/posts"

# ───────────────────────────────────────────
# 3) 최신 정치 기사 가져오기 (RSS)
# ───────────────────────────────────────────
rss_url = "https://rss.donga.com/politics.xml"
feed = feedparser.parse(rss_url)
entry = feed.entries[0]
news_title = entry.title
news_link  = entry.link

article_html = requests.get(news_link, headers={"User-Agent": "Mozilla/5.0"}).text
soup = BeautifulSoup(article_html, "html.parser")
paragraphs = [p.get_text(strip=True) for p in soup.select("p") if p.get_text(strip=True)]
news_body = "\n".join(paragraphs)[:4000]  # Claude 프롬프트 길이 제한

# ───────────────────────────────────────────
# 4) Claude 프롬프트 구성 & 호출
# ───────────────────────────────────────────
with open("claude_prompt.txt", encoding="utf-8") as f:
    tmpl = f.read()

claude_prompt = tmpl.format(title=news_title, body=news_body)

anthropic = Anthropic(api_key=anthropic_key)
claude_resp = anthropic.messages.create(
    model="claude-3-sonnet-20240229",
    max_tokens=1000,
    temperature=0.7,
    messages=[{"role": "user", "content": claude_prompt}]
)
blog_text = claude_resp.content[0].text

# ───────────────────────────────────────────
# 5) GPT‑4로 이미지 프롬프트 3개 생성
# ───────────────────────────────────────────
openai = OpenAI(api_key=openai_key)
img_prompt_resp = openai.chat.completions.create(
    model="gpt-4o-mini",
    temperature=0.7,
    messages=[
        {"role": "system", "content": "다음 글의 와닿는 장면을 사진처럼 묘사한 프롬프트 3개를 한 줄씩 만들어줘."},
        {"role": "user",   "content": blog_text}
    ]
)
img_prompts = [l.strip("- ").strip() for l in img_prompt_resp.choices[0].message.content.splitlines() if l.strip()]

image_html = "".join(f"<p><em>이미지 프롬프트: {p}</em></p>" for p in img_prompts)

# ───────────────────────────────────────────
# 6) 최종 본문 HTML
# ───────────────────────────────────────────
full_body = f"""<p><a href='{news_link}' target='_blank'>원문 기사 보기</a></p>
{image_html}
<div>{blog_text}</div>"""

# ───────────────────────────────────────────
# 7) 워드프레스 포스팅
# ───────────────────────────────────────────
payload = {
    "title": news_title,
    "content": full_body,
    "status": "publish",
    "categories": [category_id]
}

resp = requests.post(wp_api_url, json=payload,
                     auth=HTTPBasicAuth(wp_user, wp_password))
print("WP response:", resp.status_code)
print(resp.text)
