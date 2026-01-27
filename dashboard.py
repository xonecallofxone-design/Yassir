import sys
import asyncio

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

import streamlit as st
import pandas as pd
import plotly.express as px
import json
import os
import nest_asyncio
from textblob import TextBlob 
from datetime import datetime, timedelta
from api_client import TwitterAPIClient, YoutubeAPIClient

nest_asyncio.apply()

st.set_page_config(page_title="Système d'Analyse Bad Buzz", layout="wide")

st.markdown("""
<style>
    .stButton>button { width: 100%; background-color: #C2185B; color: white; border: none; font-weight: bold; }
    .stButton>button:hover { background-color: #880E4F; color: white; }
    .metric-card { background-color: #f0f2f6; padding: 20px; border-radius: 10px; }
</style>
""", unsafe_allow_html=True)

COLOR_MAP = {'Positif': '#00CC96', 'Négatif': '#EF553B', 'Neutre': '#7f7f7f'}

# --- BARRE LATERALE ---
with st.sidebar:
    st.header("Paramètres de Scan")
    
    source = st.radio("Cible", ["Twitter (X)", "YouTube"], index=0)
    st.divider()

    with st.form("api_form"):
        st.subheader("1. Mots-clés (Sujet)")
        all_words = st.text_input("Mots-clés Principaux", placeholder="ex: Boycott, Scandale")
        exact_phrase = st.text_input("Phrase exacte")
        
        # Hashtags dispo pour les deux
        hashtags = st.text_input("Hashtags", placeholder="#Maroc #Danger")
        
        lang = st.selectbox("Langue", ["Tout", "fr", "en", "ar"], index=1)

        st.subheader("2. Filtres Techniques")
        with st.expander("Options Avancées"):
            if source == "Twitter (X)":
                lbl_min = "Min Likes (Tweet)"
                lbl_accts = "Comptes Ciblés"
            else:
                lbl_min = "Min Likes (Commentaire)"
                lbl_accts = "Chaîne Spécifique (Optionnel)"
            
            c1, c2 = st.columns(2)
            since_date = c1.date_input("Début", datetime.now() - timedelta(days=30))
            until_date = c2.date_input("Fin", datetime.now())
            
            min_faves = st.number_input(lbl_min, 0, step=10)
            from_accts = st.text_input(lbl_accts)

        limit = st.number_input("Volume à analyser", 10, 2000, 50)
        
        submitted = st.form_submit_button(f"Lancer l'Analyse {source}")

    if submitted:
        if source == "Twitter (X)":
            client = TwitterAPIClient()
        else:
            client = YoutubeAPIClient()
            
        params = {
            "all_words": all_words, "exact_phrase": exact_phrase,
            "hashtags": hashtags, "lang": lang,
            "min_faves": min_faves, "from_accounts": from_accts,
            "since": since_date.strftime("%Y-%m-%d"),
            "until": until_date.strftime("%Y-%m-%d")
        }

        with st.status("Traitement en cours...", expanded=True) as status:
            final_data = []
            
            for progress in client.fetch_data_generator(params, limit):
                
                if "error" in progress:
                    status.update(label="Erreur détectée", state="error")
                    st.error(progress["error"])
                    break
                
                curr = progress['current_count']
                tgt = progress['target']
                
                msg_type = "Tweets" if source == "Twitter (X)" else "Commentaires"
                status.update(label=f"Collecte des {msg_type}: {curr}/{tgt}...", state="running")
                
                final_data = progress['data']
                
                if progress.get('finished'):
                    status.update(label="Analyse Terminée !", state="complete", expanded=False)

            if final_data:
                st.success(f"Terminé : {len(final_data)} réactions collectées.")
                with open("api_data.json", "w", encoding="utf-8") as f:
                    json.dump(final_data, f, ensure_ascii=False)
                st.cache_data.clear()
                st.rerun()
            else:
                st.warning("Aucune donnée trouvée. Vérifiez vos mots-clés.")

# --- CHARGEMENT ET TRAITEMENT ---

@st.cache_data
def load_and_process_data():
    if not os.path.exists("api_data.json"): return pd.DataFrame()
    try:
        with open("api_data.json", "r", encoding="utf-8") as f:
            data = json.load(f)
    except: return pd.DataFrame()
            
    if not data: return pd.DataFrame()
    
    df = pd.json_normalize(data)
    df['date'] = pd.to_datetime(df['date_iso'], errors='coerce')
    
    for col in ['metrics.likes', 'metrics.retweets', 'metrics.replies']:
        if col not in df.columns: df[col] = 0

    df['engagement'] = df['metrics.likes'] + df['metrics.retweets']

    def get_sentiment(text):
        if not isinstance(text, str): return 0.0, 'Neutre'
        s = TextBlob(text).sentiment.polarity
        if s > 0.1: return s, 'Positif'
        elif s < -0.1: return s, 'Négatif'
        else: return s, 'Neutre'
    
    if 'text' in df.columns:
        df[['sentiment_score', 'sentiment_cat']] = df['text'].apply(lambda x: pd.Series(get_sentiment(x)))
    
    return df

df_raw = load_and_process_data()

st.title("War Room : Détection de Bad Buzz")

if not df_raw.empty:
    source_used = df_raw['source_type'].iloc[0] if 'source_type' in df_raw.columns else "Inconnu"
    st.caption(f"Source des données : **{source_used}**")

    # Filtres interactifs
    col_filter, _ = st.columns([1, 2])
    with col_filter:
        selected_sentiments = st.multiselect(
            "Filtrer par sentiment :",
            options=["Positif", "Négatif", "Neutre"],
            default=["Positif", "Négatif", "Neutre"]
        )
    
    if 'sentiment_cat' in df_raw.columns:
        df = df_raw[df_raw['sentiment_cat'].isin(selected_sentiments)]
    else:
        df = df_raw

    st.divider()

    # Section KPIs
    k1, k2, k3 = st.columns(3)
    k1.metric("Volume Analysé", len(df))
    
    # Label dynamique
    eng_text = "Somme des Likes"
    k2.metric(eng_text, int(df['engagement'].sum()))
    
    if 'sentiment_cat' in df.columns:
        neg_count = len(df[df['sentiment_cat'] == 'Négatif'])
        k3.metric("Réactions Négatives", neg_count, delta_color="inverse")

        c1, c2 = st.columns([1, 2])
        with c1:
            st.subheader("Répartition des Avis")
            st.plotly_chart(px.pie(df, names='sentiment_cat', color='sentiment_cat', color_discrete_map=COLOR_MAP), use_container_width=True)

        with c2:
            st.subheader("Impact vs Sentiment")
            st.plotly_chart(px.scatter(df, x="engagement", y="sentiment_score", color="sentiment_cat", color_discrete_map=COLOR_MAP, hover_data=['text', 'handle'], size_max=40), use_container_width=True)

        st.divider()
        st.subheader("Flux des Messages (Raw Feed)")
        
        # Colonnes intelligentes
        display_cols = ['date', 'handle', 'text', 'engagement', 'sentiment_cat']
        if 'context' in df.columns:
            display_cols.append('context')
            
        st.dataframe(df[display_cols], use_container_width=True)
else:
    st.info("Utilisez le menu à gauche pour configurer et lancer l'analyse.")
