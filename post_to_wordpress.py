import requests
from requests.auth import HTTPBasicAuth
import os

def publish_post(title, content):
    wp_url = os.getenv("WP_SITE_URL") + "/wp-json/wp/v2/posts"
    wp_user = os.getenv("WP_USERNAME")
    wp_pass = os.getenv("WP_APP_PASSWORD")

    data = {
        'title': title,
        'content': content,
        'status': 'publish',
        'categories': [4]  # 'ntpt' 카테고리 ID
    }

    res = requests.post(wp_url, json=data, auth=HTTPBasicAuth(wp_user, wp_pass))
    print(res.status_code, res.text)
