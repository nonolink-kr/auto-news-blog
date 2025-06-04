import os
from fetch_news import get_latest_news
from generate_prompt import generate_prompt
from format_post import format_claude_response
from insert_images import insert_images_into_body
from post_to_wordpress import publish_post
import anthropic

def claude_api_call(prompt):
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    response = client.messages.create(
        model="claude-3-haiku-20240307",
        max_tokens=1500,
        temperature=0.7,
        messages=[{"role": "user", "content": prompt}]
    )
    return response.content[0].text

def main():
    title, link, summary = get_latest_news()
    prompt = generate_prompt(title, summary)
    response_text = claude_api_call(prompt)
    blog_title, blog_body = format_claude_response(response_text)
    html_with_images = insert_images_into_body(blog_body)
    publish_post(blog_title, html_with_images)

if __name__ == "__main__":
    main()
