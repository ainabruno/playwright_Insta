import streamlit as st
from playwright.sync_api import sync_playwright
import pandas as pd
import json
import os
import time

COOKIE_FILE = "cookies_ig.json"

def save_cookies(context):
    cookies = context.cookies()
    with open(COOKIE_FILE, "w") as f:
        json.dump(cookies, f)

def load_cookies(context):
    if os.path.exists(COOKIE_FILE):
        with open(COOKIE_FILE, "r") as f:
            cookies = json.load(f)
        context.add_cookies(cookies)

def extract_post_data(page, url):
    page.goto(url, timeout=60000)
    time.sleep(2)
    try:
        username = page.query_selector("header a").inner_text()
    except:
        username = ""
    try:
        caption_elem = page.query_selector("div[data-testid='post-comment-root']")
        caption = caption_elem.inner_text() if caption_elem else ""
    except:
        caption = ""
    try:
        likes_elem = page.query_selector("section span span")
        likes = likes_elem.inner_text() if likes_elem else "0"
    except:
        likes = "0"
    try:
        date_elem = page.query_selector("time")
        date = date_elem.get_attribute("datetime") if date_elem else ""
    except:
        date = ""
    try:
        comments = page.query_selector_all("ul > ul")
        nb_comments = len(comments)
    except:
        nb_comments = 0

    return {
        "user": username,
        "text": caption,
        "likes": likes,
        "comments": nb_comments,
        "date": date,
        "url": url
    }

def main():
    st.title("📸 Instagram Hashtag Scraper (avec cookies)")
    hashtag = st.text_input("Entrez un hashtag (sans #):", "hairstylistantwerp")
    max_posts = st.number_input("Nombre de posts à extraire :", min_value=1, max_value=100, value=10)

    if st.button("Scraper"):
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context()
            
            if os.path.exists(COOKIE_FILE):
                load_cookies(context)
            else:
                page = context.new_page()
                st.info("Connexion manuelle requise (1 seule fois)...")
                page.goto("https://www.instagram.com/accounts/login/", timeout=60000)
                st.warning("Veuillez vous connecter manuellement puis fermer l'onglet.")
                page.wait_for_timeout(60000)  # 60 secondes pour te connecter manuellement
                save_cookies(context)
                st.success("Cookies enregistrés.")

            page = context.new_page()
            hashtag_url = f"https://www.instagram.com/explore/tags/{hashtag}/"
            page.goto(hashtag_url, timeout=60000)
            page.wait_for_selector("article")

            post_links = set()
            while len(post_links) < max_posts:
                page.mouse.wheel(0, 2000)
                time.sleep(1.5)
                anchors = page.query_selector_all("article a")
                for a in anchors:
                    href = a.get_attribute("href")
                    if href and href.startswith("/p/"):
                        post_links.add("https://www.instagram.com" + href)
                        if len(post_links) >= max_posts:
                            break

            data = []
            for link in list(post_links)[:max_posts]:
                try:
                    data.append(extract_post_data(page, link))
                except Exception as e:
                    st.error(f"Erreur sur {link} : {e}")

            df = pd.DataFrame(data)
            st.dataframe(df)

            csv = df.to_csv(index=False).encode("utf-8")
            st.download_button("📥 Télécharger CSV", data=csv, file_name=f"{hashtag}_posts.csv", mime="text/csv")

            browser.close()

if _name_ == "_main_":
    main()