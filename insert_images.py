
from openai import OpenAI

client = OpenAI()

def extract_key_paragraphs(body):
    system = (
        "다음은 정치 칼럼 본문이다. 전체 문단 중에서 핵심 주장을 가장 잘 드러내는 문단 2개를 골라줘. "
        "각 문단에 대해 그 내용을 상징적으로 시각화할 수 있는 간단한 프롬프트도 함께 생성해줘. "
        "정치인 실명, 얼굴, 사진, 조직명은 포함하지 말고, 상징적·중립적 표현으로만 구성할 것. "
        "JSON 형식으로 반환해: [{'paragraph': '...', 'prompt': '...'}, ...]"
    )
    try:
        res = client.chat.completions.create(
            model="gpt-4",
            temperature=0.7,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": body}
            ]
        )
        import json
        return json.loads(res.choices[0].message.content.strip())
    except Exception as e:
        print(f"[핵심 문단 추출 실패] {e}")
        return []

def dalle_image_url(prompt):
    try:
        res = client.images.generate(
            model="dall-e-3",
            prompt=prompt,
            n=1,
            size="1024x1024"
        )
        return res.data[0].url
    except Exception as e:
        print(f"[이미지 생성 실패] 프롬프트: {prompt} → 오류: {e}")
        return None

def insert_images_into_body(body):
    key_data = extract_key_paragraphs(body)
    html = ""
    for item in key_data:
        para = item.get("paragraph", "").strip()
        prompt = item.get("prompt", "").strip()
        html += f"<p>{para}</p>\n"
        if prompt:
            img_url = dalle_image_url(prompt)
            if img_url:
                html += f"<img src='{img_url}' style='max-width:100%; height:auto;'/><br/>\n"
            else:
                html += f"<!-- 이미지 생성 실패 (URL 없음) -->\n"
        else:
            html += f"<!-- 이미지 프롬프트 없음 -->\n"
    return html
