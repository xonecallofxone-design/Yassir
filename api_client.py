import requests
import time
from datetime import datetime
from typing import Dict, Any, Generator
from youtubesearchpython import VideosSearch

# --- CONFIGURATION ET AUTHENTIFICATION ---
API_KEY = "new1_c4a4317b0a7f4669b7a0baf181eb4861" 
API_URL = "https://api.twitterapi.io/twitter/tweet/advanced_search"

class TwitterAPIClient:
    """
    Client Twitter original (inchangé).
    """
    def build_query(self, p: Dict[str, Any]) -> str:
        parts = []
        if p.get('all_words'): parts.append(p['all_words'])
        if p.get('exact_phrase'): parts.append(f'"{p["exact_phrase"]}"')
        if p.get('hashtags'): parts.append(p['hashtags'])
        if p.get('lang') and p['lang'] != "Tout": parts.append(f"lang:{p['lang']}")
        if p.get('from_accounts'): parts.append(f"from:{p['from_accounts'].replace('@', '')}")
        if p.get('since'): parts.append(f"since:{p['since']}")
        if p.get('until'): parts.append(f"until:{p['until']}")
        return " ".join(parts)

    def fetch_data_generator(self, params: Dict[str, Any], limit: int = 50) -> Generator[Dict, None, None]:
        query_string = self.build_query(params)
        headers = {"X-API-Key": API_KEY}
        all_tweets = []
        next_cursor = None
        start_time = time.time()
        
        while len(all_tweets) < limit:
            payload = {"query": query_string, "limit": 20}
            if next_cursor: payload["cursor"] = next_cursor

            try:
                response = requests.get(API_URL, params=payload, headers=headers)
                if response.status_code == 429:
                    time.sleep(10)
                    continue 
                if response.status_code != 200:
                    yield {"error": f"Erreur API: {response.status_code}"}
                    break

                data = response.json()
                batch = data.get('tweets', [])
                if not batch: break 

                for t in batch:
                    if any(existing['id'] == t.get('id') for existing in all_tweets): continue
                    author = t.get('author') or {}
                    all_tweets.append({
                        "id": t.get('id'),
                        "date_iso": t.get('createdAt'),
                        "text": t.get('text', ""),
                        "handle": author.get('userName', 'Inconnu'),
                        "url": t.get('url') or t.get('twitterUrl', ""),
                        "source_type": "Twitter",
                        "metrics": {
                            "likes": t.get('likeCount', 0),
                            "retweets": t.get('retweetCount', 0),
                            "replies": t.get('replyCount', 0)
                        }
                    })

                duration = time.time() - start_time
                yield {
                    "current_count": len(all_tweets),
                    "target": limit,
                    "data": all_tweets,
                    "finished": False
                }

                next_cursor = data.get('next_cursor')
                if not next_cursor or not data.get('has_next_page'): break
                time.sleep(6)

            except Exception as e:
                yield {"error": str(e)}
                break

        yield {
            "current_count": len(all_tweets),
            "target": limit,
            "data": all_tweets[:limit],
            "finished": True
        }

class YoutubeAPIClient:
    """
    Nouveau Client pour YouTube.
    Scrape les résultats de recherche et les formate comme des tweets
    pour que le dashboard fonctionne sans modification.
    """
    def fetch_data_generator(self, params: Dict[str, Any], limit: int = 50) -> Generator[Dict, None, None]:
        search_query = params.get('all_words', '')
        if params.get('exact_phrase'):
            search_query += f' "{params.get("exact_phrase")}"'
            
        videos_search = VideosSearch(search_query, limit=limit)
        all_videos = []
        start_time = time.time()
        
        try:
            # Récupération en une fois ou par lots (la lib gère la pagination interne, mais on simplifie ici)
            results = videos_search.result()
            
            while len(all_videos) < limit:
                if not results or 'result' not in results:
                    break
                    
                batch = results['result']
                
                for v in batch:
                    if len(all_videos) >= limit: break
                    
                    # Normalisation des vues (ex: "1.2M views" -> nombre approximatif ou 0)
                    view_text = v.get('viewCount', {'text': '0'})
                    if isinstance(view_text, dict): view_text = view_text.get('text', '0')
                    views = ''.join(filter(str.isdigit, view_text))
                    views = int(views) if views else 0

                    all_videos.append({
                        "id": v.get('id'),
                        # On utilise l'heure actuelle car YouTube Search donne des dates relatives ("2 days ago")
                        # ce qui casserait le graphique temporel.
                        "date_iso": datetime.utcnow().isoformat() + "Z", 
                        "text": f"{v.get('title', '')} \n {v.get('descriptionSnippet', '')}",
                        "handle": v.get('channel', {}).get('name', 'Inconnu'),
                        "url": v.get('link', ''),
                        "source_type": "YouTube",
                        "metrics": {
                            "likes": views, # On map les Vues vers Likes pour le calcul d'engagement
                            "retweets": 0,
                            "replies": 0
                        }
                    })

                duration = time.time() - start_time
                yield {
                    "current_count": len(all_videos),
                    "target": limit,
                    "data": all_videos,
                    "finished": False
                }
                
                if len(all_videos) >= limit: break
                
                try:
                    videos_search.next()
                    results = videos_search.result()
                    time.sleep(2) 
                except:
                    break # Plus de résultats

        except Exception as e:
            yield {"error": f"Erreur YouTube: {str(e)}"}

        yield {
            "current_count": len(all_videos),
            "target": limit,
            "data": all_videos,
            "finished": True
        }