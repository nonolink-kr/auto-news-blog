
from openai import OpenAI

def call_gpt_for_prompt(paragraph):
    system = (
        "너는 콘텐츠 디자이너야. 아래 문단을 바탕으로 "
        "중립적이고 상징적인 자료화면 스타일 이미지를 만들어낼 수 있는 "
        "'짧은 설명문'을 생성해줘. "
        "절대 정치인 실명, 얼굴, 사진, 실제 인물, 실제 조직 이름을 포함하지 마. "
        "직접적인 묘사 대신 시각적 상징이나 풍경, 은유적 표현으로 바꿔줘."
    )
    user = f"문단: {paragraph}"

    try:
        client = OpenAI()
        res = client.chat.completions.create(
            model="gpt-4",
            temperature=0.7,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user}
            ]
        )
        return res.choices[0].message.content.strip()
    except Exception as e:
        print(f"[GPT 프롬프트 생성 실패] {e}")
        return None

def dalle_image_url(prompt):
    try:
        client = OpenAI()
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
    paragraphs = body.split('\n\n')
    html = ""
    for para in paragraphs:
        html += f"<p>{para}</p>\n"
        try:
            prompt = call_gpt_for_prompt(para)
            if not prompt:
                html += f"<!-- 프롬프트 생성 실패 -->\n"
                continue
            img_url = dalle_image_url(prompt)
            if img_url:
                html += f"<img src='{img_url}' style='max-width:100%; height:auto;'/><br/>\n"
            else:
                html += f"<!-- 이미지 URL 없음 -->\n"
        except Exception as e:
            print(f"[문단 처리 중 오류] {e}")
            html += f"<!-- 이미지 생성 실패: {e} -->\n"
    return html
