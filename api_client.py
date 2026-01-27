import requests
import time
from typing import Dict, Any, Generator
from youtubesearchpython import VideosSearch

# --- CONFIGURATION ET AUTHENTIFICATION ---
API_KEY = "new1_c4a4317b0a7f4669b7a0baf181eb4861"
API_URL = "https://api.twitterapi.io/twitter/tweet/advanced_search"


# ================== TWITTER ==================
class TwitterAPIClient:

    def build_query(self, p: Dict[str, Any]) -> str:
        parts = []
        if p.get('all_words'): parts.append(p['all_words'])
        if p.get('exact_phrase'): parts.append(f'"{p["exact_phrase"]}"')
        if p.get('any_words'):
            words = p['any_words'].split()
            parts.append(f"({' OR '.join(words)})" if len(words) > 1 else p['any_words'])
        if p.get('none_words'):
            for w in p['none_words'].split(): parts.append(f"-{w}")
        if p.get('hashtags'): parts.append(p['hashtags'])
        if p.get('lang') and p['lang'] != "Tout": parts.append(f"lang:{p['lang']}")
        if p.get('from_accounts'): parts.append(f"from:{p['from_accounts'].replace('@', '')}")
        if p.get('since'): parts.append(f"since:{p['since']}")
        if p.get('until'): parts.append(f"until:{p['until']}")
        return " ".join(parts)

    def fetch_tweets_generator(self, params: Dict[str, Any], limit: int = 50):

        query_string = self.build_query(params)
        headers = {"X-API-Key": API_KEY}

        all_tweets = []
        next_cursor = None
        start_time = time.time()

        while len(all_tweets) < limit:

            payload = {"query": query_string, "limit": 20}
            if next_cursor:
                payload["cursor"] = next_cursor

            response = requests.get(API_URL, params=payload, headers=headers)

            if response.status_code != 200:
                break

            data = response.json()
            batch = data.get("tweets", [])

            if not batch:
                break

            for t in batch:
                if any(x["id"] == t.get("id") for x in all_tweets):
                    continue

                author = t.get("author") or {}
                all_tweets.append({
                    "platform": "twitter",
                    "id": t.get("id"),
                    "date": t.get("createdAt"),
                    "text": t.get("text"),
                    "author": author.get("userName"),
                    "url": t.get("url")
                })

            yield {
                "platform": "twitter",
                "data": all_tweets,
                "finished": False
            }

            next_cursor = data.get("next_cursor")
            if not next_cursor:
                break

            time.sleep(6)

        yield {
            "platform": "twitter",
            "data": all_tweets[:limit],
            "finished": True
        }


# ================== YOUTUBE ==================
class YouTubeScraperClient:

    def fetch_videos(self, query: str, limit: int = 20):

        search = VideosSearch(query, limit=limit)
        results = search.result().get("result", [])

        videos = []
        for v in results:
            videos.append({
                "platform": "youtube",
                "title": v.get("title"),
                "channel": v.get("channel", {}).get("name"),
                "published": v.get("publishedTime"),
                "url": v.get("link")
            })

        return videos


# ================== MAIN ==================
if __name__ == "__main__":

    twitter = TwitterAPIClient()
    youtube = YouTubeScraperClient()

    QUERY = "bad buzz marque"

    print("\n====== TWITTER ======\n")
    tweets = []
    for update in twitter.fetch_tweets_generator(
        {"all_words": QUERY, "lang": "fr"},
        limit=20
    ):
        if update.get("finished"):
            tweets = update["data"]

    for t in tweets:
        print("🐦", t["text"])
        print("   ", t["url"])

    print("\n====== YOUTUBE ======\n")
    videos = youtube.fetch_videos(QUERY, limit=10)
    for v in videos:
        print("▶", v["title"])
        print("   ", v["url"])
