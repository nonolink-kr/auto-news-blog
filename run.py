import os
import requests
from anthropic import Anthropic
from requests.auth import HTTPBasicAuth
import openai
import re

# Claude API 설정
claude_client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

# OpenAI API 설정 (DALL·E 이미지 생성용)
openai.api_key = os.getenv("OPENAI_API_KEY")

# 뉴스 기사 제목과 본문 예시
news_title = "예시 기사 제목"
news_body = "여기에 뉴스 기사 본문이 들어갑니다."

# Claude 프롬프트 불러오기
with open("claude_prompt.txt", "r", encoding="utf-8") as f:
    prompt_template = f.read()

final_prompt = prompt_template.format(title=news_title, body=news_body)

# Claude 응답 생성
response = claude_client.messages.create(
    model="claude-3-opus-20240229",
    max_tokens=2048,
    temperature=0.7,
    messages=[
        {"role": "user", "content": final_prompt}
    ]
)

generated_text = response.content[0].text

# 괄호 속 이미지 프롬프트 추출
matches = re.findall(r"\((.*?)\)", generated_text)

# 문단 나누기
paragraphs = re.split(r"\n\n+", generated_text)

# 이미지 생성 및 삽입
content_with_images = ""
image_index = 0

for para in paragraphs:
    if not para.strip():
        continue
    content_with_images += f"<p>{para.strip()}</p>\n"

    # 해당 문단 뒤에 이미지 삽입 (있을 경우)
    if image_index < len(matches):
        prompt = matches[image_index]
        print("이미지 생성 프롬프트:", prompt)

        # OpenAI DALL·E 이미지 생성
        try:
            image_res = openai.Image.create(
                prompt=prompt,
                n=1,
                size="1024x1024"
            )
            image_url = image_res["data"][0]["url"]
            content_with_images += f"<img src='{image_url}' alt='{prompt}' /><br>\n"
        except Exception as e:
            content_with_images += f"<p>(이미지 생성 실패: {prompt})</p>\n"

        image_index += 1

# 워드프레스 포스팅 설정
wp_user = os.getenv("WP_USERNAME")
wp_password = os.getenv("WP_APP_PASSWORD")
wp_url = os.getenv("WP_SITE_URL").rstrip("/") + "/wp-json/wp/v2/posts"
category_id = 4

data = {
    "title": news_title,
    "content": content_with_images,
    "status": "publish",
    "categories": [category_id]
}

res = requests.post(wp_url, json=data, auth=HTTPBasicAuth(wp_user, wp_password))

print("Response status:", res.status_code)
print("Response body:", res.text)
