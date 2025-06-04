def format_claude_response(response_text):
    lines = response_text.strip().split('\n')
    title = lines[0].strip('# ').strip()
    body = '\n'.join(lines[1:]).strip()
    return title, body
