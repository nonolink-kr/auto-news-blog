
import os
import random
import time
import requests
from requests.auth import HTTPBasicAuth
from bs4 import BeautifulSoup
import feedparser

# 환경 변수
wp_user = os.getenv("WP_USERNAME")
wp_password = os.getenv("WP_APP_PASSWORD")
wp_site_url = os.getenv("WP_SITE_URL")
wp_url = f"{wp_site_url}/wp-json/wp/v2/posts"
category_id = 4

# 실행 트리거에 따른 대기 시간 조절
event_name = os.getenv("GITHUB_EVENT_NAME")
if event_name == "schedule":
    wait_minutes = random.randint(0, 30)
    print(f"[CRON] {wait_minutes}분 대기 후 실행됩니다.")
    time.sleep(wait_minutes * 60)
else:
    print("[수동 실행] 즉시 실행합니다.")

# 정치 섹션 RSS 가져오기
rss_url = "https://rss.donga.com/politics.xml"
feed = feedparser.parse(rss_url)
entry = feed.entries[0]
news_title = entry.title
news_link = entry.link
news_response = requests.get(news_link)
soup = BeautifulSoup(news_response.content, "html.parser")
news_body = "\n".join(p.get_text() for p in soup.find_all("p"))

# Claude 프롬프트 로드
with open("claude_prompt.txt", "r", encoding="utf-8") as f:
    prompt_template = f.read()

final_prompt = prompt_template.format(title=news_title, body=news_body)

# Claude API 호출
import anthropic
client = anthropic.Anthropic(api_key=os.getenv("CLAUDE_API_KEY"))
message = client.messages.create(
    model="claude-3-sonnet-20240229",
    max_tokens=1000,
    temperature=0.7,
    system="뉴스 요약 및 개인 의견 작성",
    messages=[{"role": "user", "content": final_prompt}]
)
generated_content = message.content[0].text

# GPT 기반 이미지 생성 프롬프트 예시
image_prompts = [
    "국회 본회의장 전경, 오후 햇살이 비추는 풍경",
    "국회의사당 앞에서 1인 시위 중인 시민들",
    "텅 빈 국회 본회의장 좌석들",
    "여야 의원들이 고성을 지르며 대치하는 모습",
    "여야 대표가 회동하는 모습"
]

image_blocks = ["<p><strong>[이미지]</strong><br>{}</p>".format(p) for p in image_prompts]

# 최종 콘텐츠 구성
content_html = f"<p><strong>출처:</strong> <a href='{news_link}'>{news_title}</a></p>" +                "".join(image_blocks) +                f"<div>{generated_content}</div>"

# 워드프레스 포스팅
data = {
    "title": news_title,
    "content": content_html,
    "status": "publish",
    "categories": [category_id]
}

res = requests.post(wp_url, json=data, auth=HTTPBasicAuth(wp_user, wp_password))
print("Response status:", res.status_code)
print("Response body:", res.text)
