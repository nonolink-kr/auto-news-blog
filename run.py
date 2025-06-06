
import os
import random
import time
import requests
from requests.auth import HTTPBasicAuth
import feedparser
from anthropic import Anthropic

# 수동 실행이면 즉시, 스케줄이면 랜덤 대기
event_name = os.getenv("GITHUB_EVENT_NAME")
if event_name == "schedule":
    wait_minutes = random.randint(0, 30)
    print(f"[CRON 실행] {wait_minutes}분 대기 후 실행됩니다.")
    time.sleep(wait_minutes * 60)
else:
    print("[수동 실행 또는 기타 이벤트] 즉시 실행합니다.")

# 환경 변수 불러오기
anthropic_api_key = os.getenv("CLAUDE_API_KEY")
wp_user = os.getenv("WP_USERNAME")
wp_password = os.getenv("WP_APP_PASSWORD")
wp_url_base = os.getenv("WP_SITE_URL")
category_id = os.getenv("WP_CATEGORY_ID", "4")  # 기본값 4

wp_url = f"{wp_url_base}/wp-json/wp/v2/posts"

# 1. RSS에서 뉴스 불러오기
rss_url = "https://rss.donga.com/politics.xml"
feed = feedparser.parse(rss_url)
first_entry = feed.entries[0]
news_title = first_entry.title
news_body = first_entry.summary

# 2. Claude 프롬프트 템플릿 적용
with open("claude_prompt.txt", "r", encoding="utf-8") as f:
    prompt_template = f.read()

final_prompt = prompt_template.format(title=news_title, body=news_body)

# 3. Claude API 호출
client = Anthropic(api_key=anthropic_api_key)
response = client.messages.create(
    model="claude-3-haiku-20240307",
    max_tokens=1000,
    temperature=0.7,
    messages=[{"role": "user", "content": final_prompt}]
)
claude_content = response.content[0].text

# 4. GPT로 이미지 프롬프트 생성
from openai import OpenAI

openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
image_prompts = []

image_prompt_response = openai_client.chat.completions.create(
    model="gpt-4",
    messages=[
        {"role": "system", "content": "다음 글의 주요 장면을 시각화할 수 있는 프롬프트 5개를 만들어줘. 각 프롬프트는 한 문장으로 요약해야 하며, 장면을 사진처럼 상상할 수 있게 구성해."},
        {"role": "user", "content": claude_content}
    ]
)

prompt_lines = image_prompt_response.choices[0].message.content.strip().split("\n")
for line in prompt_lines:
    if line.strip():
        image_prompts.append(line.strip())

# 5. 본문용 이미지 HTML 구성
image_html = ""
for prompt in image_prompts:
    image_html += f"<p><em>이미지 생성 프롬프트: {prompt}</em></p>\n"

# 6. 최종 HTML 콘텐츠 조립
full_content = f"{image_html}<hr>{claude_content}"

# 7. 워드프레스에 글 발행
data = {
    "title": news_title,
    "content": full_content,
    "status": "publish",
    "categories": [int(category_id)]
}

res = requests.post(wp_url, json=data, auth=HTTPBasicAuth(wp_user, wp_password))
print("Response status:", res.status_code)
print("Response body:", res.text)
