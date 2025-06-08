import openai
import os

def call_gpt_for_prompt(paragraph):
    system = "당신은 콘텐츠 디자이너입니다. 주어진 문단에 어울리는 '자료화면 스타일의 이미지' 프롬프트를 한 문장으로 생성하세요."
    user = f"문단: {paragraph}"
    res = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user}
        ],
        temperature=0.7
    )
    return res['choices'][0]['message']['content'].strip()

def dalle_image_url(prompt):
    res = openai.Image.create(
        prompt=prompt,
        model="dall-e-3",
        n=1,
        size="1024x1024"
    )
    return res['data'][0]['url']

def insert_images_into_body(body):
    paragraphs = body.split('\n\n')
    html = ""
    for para in paragraphs:
        html += f"<p>{para}</p>\n"
        try:
            img_prompt = call_gpt_for_prompt(para)
            img_url = dalle_image_url(img_prompt)
            html += f"<img src='{img_url}' style='max-width:100%; height:auto;'/><br/>\n"
        except Exception as e:
            print(f"[이미지 생성 실패] 문단 내용: {para[:100]}... → 오류: {e}")
        html += f"<!-- 이미지 생성 실패: {e} -->\n"
    return html
