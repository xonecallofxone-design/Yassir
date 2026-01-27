import streamlit as st
from api_client import TwitterAPIClient, YouTubeClient

st.set_page_config(page_title="Social Media Monitor", layout="wide")

st.title("📊 Social Media Monitoring")

# -------- INPUTS --------
keyword = st.text_input("🔎 Mot-clé (ex: bad buzz marque)")

platforms = st.multiselect(
    "📡 اختر المنصات",
    ["Twitter", "YouTube"],
    default=["Twitter"]
)

limit = st.slider("📦 عدد النتائج", 10, 100, 30)

# -------- ACTION --------
if st.button("🚀 Lancer la recherche"):

    if not keyword:
        st.warning("⚠️ دخل كلمة البحث")
        st.stop()

    if not platforms:
        st.warning("⚠️ خاصك تختار Twitter ولا YouTube")
        st.stop()

    # -------- TWITTER --------
    if "Twitter" in platforms:
        st.subheader("🐦 Twitter")

        twitter = TwitterAPIClient()
        params = {
            "keyword": keyword,
            "lang": "fr"
        }

        tweets = []

        with st.spinner("⏳ استخراج Tweets..."):
            for update in twitter.fetch_tweets_generator(params, limit):
                if "error" in update:
                    st.error(update["error"])
                    break
                tweets = update["data"]

        for t in tweets:
            st.markdown(f"""
            **{t['author']}**  
            {t['text']}  
            🔗 [Lien]({t['url']})
            ---
            """)

    # -------- YOUTUBE --------
    if "YouTube" in platforms:
        st.subheader("📺 YouTube")

        yt = YouTubeClient()

        with st.spinner("⏳ استخراج Videos..."):
            videos = yt.fetch_videos(keyword, limit)

        for v in videos:
            st.markdown(f"""
            **{v['author']}**  
            {v['text']}  
            🔗 [Watch]({v['url']})
            ---
            """)
