import requests
import time
from typing import Dict, Any, Generator, List
from youtubesearchpython import VideosSearch

# ================== TWITTER CONFIG ==================
TWITTER_API_KEY = "new1_c4a4317b0a7f4669b7a0baf181eb4861"
TWITTER_API_URL = "https://api.twitterapi.io/twitter/tweet/advanced_search"


class TwitterAPIClient:

    def build_query(self, params: Dict[str, Any]) -> str:
        parts = []
        if params.get("keyword"):
            parts.append(params["keyword"])
        if params.get("lang") and params["lang"] != "Tout":
            parts.append(f"lang:{params['lang']}")
        return " ".join(parts)

    def fetch_tweets_generator(
        self,
        params: Dict[str, Any],
        limit: int = 50
    ) -> Generator[Dict, None, None]:

        headers = {"X-API-Key": TWITTER_API_KEY}
        query = self.build_query(params)

        all_tweets = []
        next_cursor = None
        start_time = time.time()

        while len(all_tweets) < limit:
            payload = {"query": query, "limit": 20}
            if next_cursor:
                payload["cursor"] = next_cursor

            response = requests.get(
                TWITTER_API_URL,
                params=payload,
                headers=headers
            )

            if response.status_code != 200:
                yield {"error": "Erreur API Twitter"}
                break

            data = response.json()
            tweets = data.get("tweets", [])

            if not tweets:
                break

            for t in tweets:
                all_tweets.append({
                    "platform": "Twitter",
                    "date": t.get("createdAt"),
                    "text": t.get("text"),
                    "author": t.get("author", {}).get("userName"),
                    "url": t.get("url")
                })

            yield {
                "current": len(all_tweets),
                "data": all_tweets,
                "finished": False,
                "duration": round(time.time() - start_time, 2)
            }

            next_cursor = data.get("next_cursor")
            if not next_cursor:
                break

            time.sleep(6)

        yield {
            "current": len(all_tweets),
            "data": all_tweets[:limit],
            "finished": True,
            "duration": round(time.time() - start_time, 2)
        }


# ================== YOUTUBE CLIENT ==================
class YouTubeClient:

    def fetch_videos(self, keyword: str, limit: int = 20) -> List[Dict]:

        search = VideosSearch(keyword, limit=limit)
        results = search.result().get("result", [])

        videos = []
        for v in results:
            videos.append({
                "platform": "YouTube",
                "date": v.get("publishedTime"),
                "text": v.get("title"),
                "author": v.get("channel", {}).get("name"),
                "url": v.get("link")
            })

        return videos
