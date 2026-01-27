import requests
import time
from datetime import datetime
from typing import Dict, Any, Generator
from youtubesearchpython import VideosSearch, Comments

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
        # 1. Construction de la requête pour trouver les VIDEOS
        search_terms = []
        if params.get('all_words'): search_terms.append(params['all_words'])
        if params.get('exact_phrase'): search_terms.append(f'"{params["exact_phrase"]}"')
        if params.get('hashtags'): search_terms.append(params['hashtags'])
        
        lang_map = {'fr': 'français', 'en': 'english', 'ar': 'arabic'}
        if params.get('lang') and params['lang'] != 'Tout':
            search_terms.append(lang_map.get(params['lang'], params['lang']))

        final_query = " ".join(search_terms)
        # Fallback pour éviter search vide
        if not final_query.strip(): final_query = "Maroc" 

        min_likes_needed = int(params.get('min_faves', 0))
        all_comments = []

        try:
            # On cherche d'abord les 15 vidéos les plus pertinentes
            videos_search = VideosSearch(final_query, limit=15)
            videos_result = videos_search.result()
        except Exception as e:
            yield {"error": f"Erreur Init YouTube: {str(e)}"}
            return

        if not videos_result or 'result' not in videos_result:
            yield {"current_count": 0, "target": limit, "data": [], "finished": True}
            return

        # 2. On boucle sur chaque vidéo pour récupérer les COMMENTAIRES
        for video in videos_result['result']:
            if len(all_comments) >= limit: break
            
            video_id = video.get('id')
            video_title = video.get('title', 'Titre Inconnu')
            video_link = video.get('link', '')

            try:
                # Appel API pour les commentaires de CETTE vidéo
                comments_fetcher = Comments(video_id)
                
                # Vérification de sécurité (si commentaires désactivés ou pas de résultat)
                if comments_fetcher.comments and 'result' in comments_fetcher.comments:
                    
                    for comm in comments_fetcher.comments['result']:
                        if len(all_comments) >= limit: break
                        
                        # Extraction robuste
                        content = comm.get('content', '')
                        author = comm.get('author', {}).get('name', 'Anonyme')
                        votes = comm.get('votes', {}).get('simpleText', '0')
                        published = comm.get('publishedTime', '')

                        # Conversion des "K" et "M" en chiffres
                        likes = 0
                        if 'K' in votes:
                            likes = int(float(votes.replace('K', '')) * 1000)
                        elif 'M' in votes:
                            likes = int(float(votes.replace('M', '')) * 1000000)
                        else:
                            digits = ''.join(filter(str.isdigit, votes))
                            likes = int(digits) if digits else 0

                        # Filtre Min Likes
                        if likes < min_likes_needed:
                            continue

                        # Construction de l'objet de données
                        all_comments.append({
                            "id": comm.get('id'),
                            "date_iso": datetime.utcnow().isoformat() + "Z", # Date technique
                            "text": content,
                            "handle": author,
                            "url": video_link,
                            "source_type": "YouTube Comments",
                            "metrics": {
                                "likes": likes,
                                "retweets": 0,
                                "replies": 0
                            },
                            "context": f"Source: {video_title} ({published})" # Important pour savoir d'où ça vient
                        })

                # Mise à jour progressive
                yield {
                    "current_count": len(all_comments),
                    "target": limit,
                    "data": all_comments,
                    "finished": False
                }
                
                time.sleep(0.5) # Pause pour éviter le blocage

            except Exception as e:
                # Erreur sur une vidéo spécifique (pas grave, on continue)
                continue

        # Envoi final
        yield {
            "current_count": len(all_comments),
            "target": limit,
            "data": all_comments,
            "finished": True
        }