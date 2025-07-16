import streamlit as st
from instaloader import Instaloader, Hashtag
import os
import time
from dotenv import load_dotenv

load_dotenv()
username = os.getenv("INSTAGRAM_USER")
session = os.getenv("INSTAGRAM_SESSION")

st.title("Instagram Hashtag Downloader")
tag = st.text_input("Voer hashtag in (zonder #):", "hairstylistantwerp")
max_count = st.slider("Aantal posts", 1, 20, 5)

if st.button("Download posts"):
    loader = Instaloader()
    loader.load_session_from_file(username, session)
    h = Hashtag.from_name(loader.context, tag)

    for post in h.get_posts():
        loader.download_post(post, target=tag)
        time.sleep(15)
        st.success(f"Post van @{post.owner_username} gedownload.")
        max_count -= 1
        if max_count == 0:
            break
