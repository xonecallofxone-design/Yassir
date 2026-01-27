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

# Importation des clients API
from api_client import TwitterAPIClient, YoutubeAPIClient

nest_asyncio.apply()

st.set_page_config(page_title="Système d'Analyse Avancé", layout="wide")

st.markdown("""
<style>
    .stButton>button { width: 100%; background-color: #1DA1F2; color: white; border: none; font-weight: bold; }
    .stButton>button:hover { background-color: #0d8ddb; color: white; }
    .metric-card { background-color: #f0f2f6; padding: 20px; border-radius: 10px; }
</style>
""", unsafe_allow_html=True)

COLOR_MAP = {'Positif': '#00CC96', 'Négatif': '#EF553B', 'Neutre': '#7f7f7f'}

# --- BARRE LATERALE ---
with st.sidebar:
    st.header("Configuration de Recherche")
    
    # --- CHOIX DE LA SOURCE ---
    source = st.radio("Source de données", ["Twitter (X)", "YouTube"], index=0)
    st.divider()

    with st.form("api_form"):
        st.subheader("1. Critères Sémantiques")
        all_words = st.text_input("Mots-clés", placeholder="ex: Crise Banque")
        exact_phrase = st.text_input("Phrase exacte")
        
        # Options spécifiques à Twitter
        hashtags = ""
        lang = "Tout"
        min_faves = 0
        from_accts = ""
        since_date = datetime.now() - timedelta(days=30)
        until_date = datetime.now()

        if source == "Twitter (X)":
            hashtags = st.text_input("Hashtags", placeholder="#Finance")
            lang = st.selectbox("Langue", ["Tout", "fr", "en", "ar"], index=1)

            st.subheader("2. Filtres Techniques")
            with st.expander("Options Avancées"):
                st.info("Astuce : Élargissez les dates pour plus de résultats.")
                c1, c2 = st.columns(2)
                since_date = c1.date_input("Début", datetime.now() - timedelta(days=30))
                until_date = c2.date_input("Fin", datetime.now())
                min_faves = st.number_input("Min J'aime", 0)
                from_accts = st.text_input("Depuis ces comptes")
        else:
            st.info("YouTube : La recherche se fait sur les vidéos les plus pertinentes.")

        limit = st.number_input("Nombre de résultats", 10, 2000, 50)
        
        submitted = st.form_submit_button(f"Lancer l'Extraction {source}")

    if submitted:
        # Sélection du Client Dynamique
        if source == "Twitter (X)":
            client = TwitterAPIClient()
            params = {
                "all_words": all_words, "exact_phrase": exact_phrase,
                "hashtags": hashtags, "lang": lang,
                "min_faves": min_faves, "from_accounts": from_accts,
                "since": since_date.strftime("%Y-%m-%d"),
                "until": until_date.strftime("%Y-%m-%d")
            }
        else:
            client = YoutubeAPIClient()
            params = {
                "all_words": all_words, "exact_phrase": exact_phrase
            }

        # --- MISE À JOUR DYNAMIQUE ---
        with st.status("Initialisation...", expanded=True) as status:
            final_data = []
            
            # Note: J'ai renommé la méthode dans api_client en fetch_data_generator pour être générique
            # Assurez-vous d'utiliser le code api_client.py fourni ci-dessus
            generator = client.fetch_data_generator(params, limit)
            
            for progress in generator:
                
                if "error" in progress:
                    status.update(label="Erreur survenue", state="error")
                    st.error(progress["error"])
                    break
                
                curr = progress['current_count']
                tgt = progress['target']
                
                status.update(label=f"Traitement en cours ({curr}/{tgt}) - Veuillez patienter...", state="running")
                
                final_data = progress['data']
                
                if progress.get('finished'):
                    status.update(label="Extraction terminée !", state="complete", expanded=False)

            if final_data:
                st.success(f"Terminé : {len(final_data)} éléments archivés via {source}.")
                with open("api_data.json", "w", encoding="utf-8") as f:
                    json.dump(final_data, f, ensure_ascii=False)
                st.cache_data.clear()
                st.rerun()
            else:
                st.warning("Aucune donnée trouvée.")

# --- CHARGEMENT ET TRAITEMENT (IDENTIQUE) ---

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

    # Si c'est YouTube, les 'likes' contiennent les Vues.
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

# --- TABLEAU DE BORD ---

st.title("War Room : Analyse de Crise")

if not df_raw.empty:
    
    # Petit indicateur de source
    source_used = df_raw['source_type'].iloc[0] if 'source_type' in df_raw.columns else "Inconnu"
    st.caption(f"Données chargées depuis : **{source_used}**")

    # 1. Filtre Post-Extraction
    st.markdown("### Filtres d'Affichage")
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

    # 2. KPIs
    k1, k2, k3 = st.columns(3)
    k1.metric("Volume Affiché", len(df))
    
    engagement_label = "Vues Totales (Est.)" if source_used == "YouTube" else "Engagement Total"
    k2.metric(engagement_label, int(df['engagement'].sum()))
    
    if 'sentiment_cat' in df.columns:
        neg_count = len(df[df['sentiment_cat'] == 'Négatif'])
        k3.metric("Contenus Négatifs", neg_count, delta_color="inverse")

        # 3. Graphiques
        c1, c2 = st.columns([1, 2])
        
        with c1:
            st.subheader("Répartition")
            if not df.empty:
                st.plotly_chart(
                    px.pie(df, names='sentiment_cat', color='sentiment_cat', color_discrete_map=COLOR_MAP), 
                    use_container_width=True
                )

        with c2:
            st.subheader("Impact vs Sentiment")
            if not df.empty:
                st.plotly_chart(
                    px.scatter(df, x="engagement", y="sentiment_score", 
                               color="sentiment_cat", color_discrete_map=COLOR_MAP, 
                               hover_data=['text', 'handle'], size_max=40), 
                    use_container_width=True
                )

        st.divider()
        
        # --- 4. SOLDE NET ---
        st.subheader("Solde Net de Sentiment")
        
        if 'date' in df.columns and not df.empty:
            df_polar = df[df['sentiment_cat'] != 'Neutre'].copy()
            
            if not df_polar.empty:
                # Groupement par 4H
                df_agg = df_polar.groupby([pd.Grouper(key='date', freq='4H'), 'sentiment_cat']).size().unstack(fill_value=0)
                
                if 'Positif' not in df_agg.columns: df_agg['Positif'] = 0
                if 'Négatif' not in df_agg.columns: df_agg['Négatif'] = 0
                
                df_agg['net_score'] = df_agg['Positif'] - df_agg['Négatif']
                df_agg['color_label'] = df_agg['net_score'].apply(lambda x: 'Positif' if x >= 0 else 'Négatif')
                
                df_final = df_agg.reset_index()

                fig_bar = px.bar(
                    df_final, x="date", y="net_score", color="color_label", 
                    color_discrete_map=COLOR_MAP,
                    title="Solde = [Positifs] - [Négatifs]",
                    labels={"date": "Temps", "net_score": "Solde Net"}
                )
                fig_bar.add_hline(y=0, line_color="white", opacity=0.8)
                fig_bar.update_layout(showlegend=False)
                st.plotly_chart(fig_bar, use_container_width=True)
            else:
                st.info("Pas assez de données polarisées pour calculer le solde.")

        # 5. Données
        st.subheader("Détail du Flux")
        st.dataframe(
            df[['date', 'handle', 'text', 'engagement', 'sentiment_cat']], 
            use_container_width=True
        )
    else:
        st.info("Données textuelles non disponibles pour l'analyse.")

else:
    st.info("Configurez la recherche à gauche et cliquez sur 'Lancer l'Extraction'.")