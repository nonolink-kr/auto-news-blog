import os
import random
import time
import requests
from requests.auth import HTTPBasicAuth
from bs4 import BeautifulSoup
from datetime import datetime
import feedparser

# CRON으로 실행될 때만 랜덤 대기 (0~30분)
if os.getenv("GITHUB_EVENT_NAME") == "schedule":
    wait_time = random.randint(0, 1800)
    print(f"Scheduled run detected. Sleeping for {wait_time} seconds...")
    time.sleep(wait_time)
else:
    print("Manual run detected. Executing immediately.")

# --- 환경변수로부터 인증 정보 불러오기 ---
wp_user = os.environ["WP_USERNAME"]
wp_password = os.environ["WP_APP_PASSWORD"]
wp_url = os.environ["WP_SITE_URL"].rstrip("/") + "/wp-json/wp/v2/posts"
category_id = os.environ.get("WP_CATEGORY_ID", "1")

# --- Claude 프롬프트 템플릿 불러오기 ---
with open("claude_prompt.txt", "r", encoding="utf-8") as f:
    prompt_template = f.read()

# --- 정치 섹션 RSS에서 뉴스 하나 파싱 ---
rss_url = "https://www.hani.co.kr/rss/politics/"  # 예: 한겨레 정치
feed = feedparser.parse(rss_url)
entry = feed.entries[0]
news_title = entry.title
news_url = entry.link

# 뉴스 내용 가져오기
res = requests.get(news_url, headers={"User-Agent": "Mozilla/5.0"})
soup = BeautifulSoup(res.text, "html.parser")
article = soup.find("div", class_="article-text")
news_body = article.get_text(strip=True) if article else "본문 추출 실패"

# Claude 프롬프트 생성
final_prompt = prompt_template.format(title=news_title, body=news_body)

# Claude API 호출
from anthropic import Anthropic
anthropic_client = Anthropic(api_key=os.environ["CLAUDE_API_KEY"])
completion = anthropic_client.messages.create(
    model="claude-3-sonnet-20240229",
    max_tokens=1200,
    temperature=0.6,
    system="너는 40대 초반 좌파 성향의 남성 블로거야.",
    messages=[{"role": "user", "content": final_prompt}]
)
blog_text = completion.content[0].text

# 이미지 생성 프롬프트 추출용 GPT 호출
from openai import OpenAI
openai_client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
img_prompts_response = openai_client.chat.completions.create(
    model="gpt-4",
    temperature=0.7,
    messages=[
        {"role": "system", "content": "다음 글을 바탕으로, 문단별 자료화면 느낌의 이미지 프롬프트를 5개 생성해줘. 각 프롬프트는 한 줄짜리 묘사로 구성돼야 해."},
        {"role": "user", "content": blog_text}
    ]
)
img_prompts = img_prompts_response.choices[0].message.content.splitlines()

# 이미지 생성 (예: 첫 번째 프롬프트만)
image_urls = []
for prompt in img_prompts[:1]:
    img_res = openai_client.images.generate(
        model="dall-e-3",
        prompt=prompt,
        size="1024x1024",
        n=1
    )
    image_url = img_res.data[0].url
    image_urls.append(image_url)

# 이미지 HTML 구성
image_html = ''.join(f'<img src="{url}" style="max-width:100%;"/>' for url in image_urls)

# 최종 글 구성
full_body = f"<p><a href='{news_url}' target='_blank'>원문 기사 보기</a></p>
{image_html}
<pre>{blog_text}</pre>"

# 워드프레스 업로드
data = {
    "title": news_title,
    "content": full_body,
    "status": "publish",
    "categories": [int(category_id)]
}

res = requests.post(wp_url, json=data, auth=HTTPBasicAuth(wp_user, wp_password))
print("Response status:", res.status_code)
print("Response body:", res.text)
