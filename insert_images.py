
from openai import OpenAI

def call_gpt_for_prompt(paragraph):
    system = "당신은 콘텐츠 디자이너입니다. 주어진 문단에 어울리는 '자료화면 스타일의 이미지' 프롬프트를 한 문장으로 생성하세요."
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
        return res.choices[0].message.content
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
