
import os
import requests
from requests.auth import HTTPBasicAuth
import feedparser
import random
import time

# 환경 변수 가져오기
wp_user = os.getenv("WP_USERNAME")
wp_password = os.getenv("WP_APP_PASSWORD")
wp_site = os.getenv("WP_SITE_URL")

if not wp_site:
    raise ValueError("환경변수 'WP_SITE_URL'이 설정되지 않았습니다.")

wp_url = f"https://{wp_site}/wp-json/wp/v2/posts"
print(f"▶ wp_url: {wp_url}")

# 정치 뉴스 RSS 피드
rss_url = "https://rss.donga.com/politics.xml"

# RSS 피드 파싱
feed = feedparser.parse(rss_url)
if not feed.entries:
    raise ValueError("RSS 피드에서 기사를 불러오지 못했습니다.")

# 최신 기사 선택
entry = feed.entries[0]
news_title = entry.title
news_body = entry.summary

# Claude 프롬프트 로딩
with open("claude_prompt.txt", "r", encoding="utf-8") as f:
    prompt_template = f.read()

# Claude 프롬프트 완성
try:
    final_prompt = prompt_template.format(title=news_title, body=news_body)
except KeyError as e:
    raise ValueError(f"Claude 프롬프트 템플릿에 필요한 키가 없습니다: {e}")

# Claude API 요청
import anthropic
client = anthropic.Anthropic(api_key=os.getenv("CLAUDE_API_KEY"))

response = client.messages.create(
    model="claude-3-opus-20240229",
    max_tokens=1024,
    temperature=0.7,
    messages=[
        {"role": "user", "content": final_prompt}
    ]
)

generated_content = response.content[0].text
print("Claude 응답 생성 완료")

# ChatGPT로 이미지 생성 프롬프트 요청
image_prompts = [
    "국회 본회의장 전경, 오후 햇살이 비추는 풍경",
    "국회의사당 앞에서 1인 시위 중인 시민들",
    "텅 빈 국회 본회의장 좌석들",
    "여야 의원들이 고성을 지르며 대치하는 모습",
    "여야 대표가 회동하는 모습",
    "일몰녘 국회의사당 전경"
]

# 이미지 삽입 (임시로 프롬프트 리스트 활용)
image_html = ""
for prompt in image_prompts:
    image_html += f"<p><strong>이미지 생성 프롬프트:</strong> {prompt}</p>"

# 최종 포스트 내용
content = f"{image_html}\n\n{generated_content}"

# 포스팅할 데이터
data = {
    "title": news_title,
    "content": content,
    "status": "publish",
    "categories": [4]  # 지정된 카테고리 ID
}

# 워드프레스에 POST 요청
res = requests.post(wp_url, json=data, auth=HTTPBasicAuth(wp_user, wp_password))
print(f"Response status: {res.status_code}")
print(f"Response body: {res.text}")
