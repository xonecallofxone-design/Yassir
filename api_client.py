import requests
import time
from datetime import datetime
from typing import Dict, Any, Generator
from youtubesearchpython import VideosSearch

# --- CONFIGURATION API TWITTER ---
API_KEY = "new1_c4a4317b0a7f4669b7a0baf181eb4861" 
API_URL = "https://api.twitterapi.io/twitter/tweet/advanced_search"

class TwitterAPIClient:
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
    def fetch_data_generator(self, params: Dict[str, Any], limit: int = 50) -> Generator[Dict, None, None]:
        # Construction intelligente de la requête pour YouTube
        search_terms = []
        if params.get('all_words'): search_terms.append(params['all_words'])
        if params.get('exact_phrase'): search_terms.append(f'"{params["exact_phrase"]}"')
        if params.get('hashtags'): search_terms.append(params['hashtags'])
        
        # Hack pour la langue
        lang_map = {'fr': 'français', 'en': 'english', 'ar': 'arabic'}
        if params.get('lang') and params['lang'] != 'Tout':
            search_terms.append(lang_map.get(params['lang'], params['lang']))

        final_query = " ".join(search_terms)
        if not final_query.strip():
            final_query = "news" # Fallback si vide
        
        min_views_needed = int(params.get('min_faves', 0))

        # Initialisation de la recherche
        try:
            videos_search = VideosSearch(final_query, limit=limit)
        except Exception as e:
            yield {"error": f"Erreur Init YouTube: {str(e)}"}
            return

        all_videos = []
        
        try:
            results = videos_search.result()
            
            while len(all_videos) < limit:
                if not results or 'result' not in results: break
                    
                batch = results['result']
                if not batch: break

                for v in batch:
                    if len(all_videos) >= limit: break
                    
                    # Nettoyage Vues
                    view_text = v.get('viewCount', {'text': '0'})
                    if isinstance(view_text, dict): view_text = view_text.get('text', '0')
                    # Extraction des chiffres uniquement
                    views_str = ''.join(filter(str.isdigit, str(view_text)))
                    views = int(views_str) if views_str else 0

                    # FILTRE TECHNIQUE : Si vues < min demandé, on ignore
                    if views < min_views_needed:
                        continue

                    all_videos.append({
                        "id": v.get('id'),
                        "date_iso": datetime.utcnow().isoformat() + "Z",
                        "text": f"{v.get('title', '')} \n {v.get('descriptionSnippet', '')}",
                        "handle": v.get('channel', {}).get('name', 'Inconnu'),
                        "url": v.get('link', ''),
                        "source_type": "YouTube",
                        "metrics": {
                            "likes": views,
                            "retweets": 0,
                            "replies": 0
                        }
                    })

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
                    time.sleep(1) 
                except: break

        except Exception as e:
            yield {"error": f"Erreur YouTube: {str(e)}"}

        yield {
            "current_count": len(all_videos),
            "target": limit,
            "data": all_videos,
            "finished": True
        }