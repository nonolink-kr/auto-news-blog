import os
import requests
from anthropic import Anthropic
from requests.auth import HTTPBasicAuth

# Claude API 설정
client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

# 뉴스 기사 제목과 본문 예시 (여기엔 실제 RSS 파싱 결과가 들어가야 함)
news_title = "예시 기사 제목"
news_body = "여기에 뉴스 기사 본문이 들어갑니다."

# 프롬프트 템플릿 불러오기
with open("claude_prompt.txt", "r", encoding="utf-8") as f:
    prompt_template = f.read()

final_prompt = prompt_template.format(title=news_title, body=news_body)

# Claude API 호출
response = client.messages.create(
    model="claude-3-opus-20240229",
    max_tokens=2048,
    temperature=0.7,
    messages=[
        {"role": "user", "content": final_prompt}
    ]
)

generated_content = response.content[0].text

# 워드프레스 설정
wp_user = os.getenv("WP_USERNAME")
wp_password = os.getenv("WP_APP_PASSWORD")
wp_url = os.getenv("WP_SITE_URL").rstrip("/") + "/wp-json/wp/v2/posts"

# 이미지, 카테고리 ID 등은 정적 설정
thumbnail_url = "https://source.unsplash.com/random/800x400?politics"
category_id = 4

data = {
    "title": news_title,
    "content": f"<img src='{thumbnail_url}' /><br>{generated_content}",
    "status": "publish",
    "categories": [category_id]
}

res = requests.post(wp_url, json=data, auth=HTTPBasicAuth(wp_user, wp_password))

print("Response status:", res.status_code)
print("Response body:", res.text)
