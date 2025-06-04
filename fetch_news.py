import feedparser

def get_latest_news():
    rss_url = open('news_sources.txt').read().strip()
    feed = feedparser.parse(rss_url)
    entry = feed.entries[0]
    return entry.title, entry.link, entry.summary
