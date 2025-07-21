# --- Correctif Windows pour Playwright (sous-processus) --------------------
import sys
import asyncio
if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
# ---------------------------------------------------------------------------

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import re
import json
import os
from playwright.async_api import async_playwright, Page # <--- ADDED 'Page' IMPORT HERE

# 📂 Charger les cookies depuis un fichier JSON
def load_cookies(path="cookies.json"):
    """Loads cookies from a JSON file."""
    if not os.path.exists(path):
        st.warning(f"🍪 Fichier de cookies non trouvé à l'emplacement : {path}. Veuillez vous assurer d'être connecté.")
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        st.error(f"❌ Erreur de lecture du fichier cookies.json. Assurez-vous qu'il s'agit d'un JSON valide.")
        return []

## Fonction d'Extraction de la Biographie Utilisateur
async def get_user_biography(page: Page, username: str) -> str:
    """
    Navigates to a user's Instagram profile page and extracts their biography.
    """
    biography = "N/A"
    profile_url = f"https://www.instagram.com/{username}/"
    
    print(f" ➡️ Navigation vers le profil: {profile_url}")
    try:
        # Increased timeout for navigation for robustness
        await page.goto(profile_url, wait_until="domcontentloaded", timeout=10000) 
        
        biography_locator = page.locator("span._ap3a._aaco._aacu._aacx._aad7._aade[dir='auto']").first
        
        await biography_locator.wait_for(state='visible', timeout=5000) # Increased timeout

        if await biography_locator.is_visible():
            biography_full = await biography_locator.text_content()
            biography = biography_full.strip()
            # Clean up common "more" or "plus" text in bio, for cleaner data
            biography = re.sub(r'\s*(Voir plus|See more|...plus)\s*$', '', biography, flags=re.IGNORECASE).strip()
            print(f" 📝 Biographie de '{username}': {biography[:150]}...")
        else:
            print(f" ⚠️ Biographie non trouvée pour '{username}' sur le profil: {profile_url}")

    except Exception as e:
        print(f" ❌ Erreur lors de l'extraction de la biographie pour '{username}': {e}")
        biography = "Extraction Error"
    
    return biography

## Fonction Principale de Scraping Instagram

async def scrape_instagram(hashtag: str, limit: int = 5):
    """
    Scrapes Instagram posts for a given hashtag, including user biographies.
    """
    cookies = load_cookies()
    if not cookies:
        st.error("❌ Impossible de démarrer le scraping sans cookies valides. Assurez-vous d'être connecté à Instagram.")
        return []

    posts = []
    # This dictionary will store biographies so we don't fetch them repeatedly for the same user
    user_biographies_cache = {} # <--- ADDED: Cache for user biographies
    # Using a set to store processed post hrefs to avoid duplicates more efficiently
    processed_hrefs = set() # <--- ADDED: Set to track processed post links

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True) # Mettez headless=False pour voir le navigateur
        context = await browser.new_context()
        if cookies:
            await context.add_cookies(cookies)
        
        page = await context.new_page() 

        url = f"https://www.instagram.com/explore/tags/{hashtag}/"
        print(f"🌐 Navigation vers la page de hashtag: {url}")
        try:
            await page.goto(url, timeout=60000)
            await page.wait_for_selector("a[href^='/p/']", timeout=20000) 
            print("✅ Page de hashtag chargée et posts détectés.")
        except Exception as e:
            print(f"❌ Erreur lors de la navigation vers la page de hashtag ou du sélecteur initial: {e}")
            await browser.close()
            return posts

        print("⏬ Défilement pour charger plus de posts...")
        scroll_attempts = max(2, int(limit / 5)) # Example: 2 scrolls for limit=1-9, 4 for 10-19, etc.
        scroll_attempts = min(scroll_attempts, 5) # Cap max scrolls to avoid excessive waits
        wait_time_per_scroll = max(1000, min(900, int(limit * 10))) # Adjusted calculation
        
        for _ in range(scroll_attempts):
            await page.evaluate("window.scrollBy(0, document.body.scrollHeight)")
            await page.wait_for_timeout(wait_time_per_scroll)

        links = await page.locator("a[href^='/p/']").all()
        hrefs = []
        for l in links:
            href = await l.get_attribute("href")
            if href and href.startswith("/p/") and href not in processed_hrefs: # <--- CHANGED: Use processed_hrefs
                hrefs.append(href)
                processed_hrefs.add(href) # <--- ADDED: Add to set
            if len(hrefs) >= limit:
                break
        print(f"🔗 Trouvé {len(hrefs)} liens de posts à scraper.")

        for i, href in enumerate(hrefs):
            if len(posts) >= limit:
                break

            post_url = f"https://www.instagram.com{href}"
            print(f"\n✨ Scraping du post {i+1}/{len(hrefs)}: {post_url}")
            
            # Store the current post URL to navigate back to it later
            current_post_url = post_url # <--- ADDED: Store current post URL

            try:
                await page.goto(post_url, timeout=20000) # <--- CHANGED: Increased timeout
                await page.wait_for_selector("time[datetime]", timeout=10000) # <--- CHANGED: Increased timeout
                print("✅ Page de post chargée.")

                # --- Extraction du nom d'utilisateur du post ---
                username = "N/A" # <--- ADDED: Initialize username
                user_biography = "N/A" # <--- ADDED: Initialize user_biography
                try:
                    # Using the more specific username locator
                    username_locator = page.locator("span._ap3a._aaco._aacw._aacx._aad7._aade[dir='auto']").first

                    if await username_locator.is_visible():
                        username = (await username_locator.text_content()).strip()
                        print(f" 👤 Utilisateur: {username}")
                       
                        user_biography = await get_user_biography(page, username)
                        user_biographies_cache[username] = user_biography # Store in cache
                            
                        # Navigate back to the original post page after getting the bio
                        # This is crucial for subsequent extractions on the post page
                        await page.goto(current_post_url, wait_until="domcontentloaded", timeout=10000) # <--- ADDED: Navigate back
                        await page.wait_for_selector("time[datetime]", timeout=5000) # <--- ADDED: Wait for post elements
                        print(f" ✅ Retourné à la page du post: {current_post_url}")

                    else:
                        print(" ⚠️ Le sélecteur du nom d'utilisateur est visible mais le texte est vide ou non trouvé.")
                        user_biography = "N/A" # Set biography to N/A if username not found
                        

                except Exception as e:
                    print(f" ⚠️ Impossible de trouver le nom d'utilisateur ou d'extraire la biographie: {e}")
                    username = "N/A" # Ensure username is "N/A" if extraction fails
                    user_biography = "Extraction Error (Username/Bio)" # Indicate error
                    
                # --- Extraction de la légende (caption) du post ---
                caption = ""
                try:
                    caption_locator = page.locator("span.x193iq5w.xeuugli.x13faqbe.x1vvkbs.xt0psk2.x1i0vuye.xvs91rp.xo1l8bm.x5n08af.x10wh9bi.xpm28yp.x8viiok.x1o7cslx.x126k92a[style*='line-height: 18px;']").first

                    if await caption_locator.is_visible():
                        caption_full = await caption_locator.text_content()
                        
                        caption = caption_full.strip()
                        # Added cleanup for "more" or "plus" text in caption
                        caption = re.sub(r'\s*(more|plus|...plus)\s*$', '', caption, flags=re.IGNORECASE).strip()
                            
                        print(f" 📝 Légende complète: {caption[:100]}...") # Display up to 100 chars for clarity
                    else:
                        print(" ℹ️ La légende n'est pas visible ou n'a pas été trouvée en utilisant le sélecteur exact.")

                except Exception as e:
                    print(f" ⚠️ Une erreur est survenue lors de l'extraction de la légende: {e}")

                # --- Récupérer le nombre de likes ---
                num_likes = 0
                try:
                    likes_locator = page.locator("a[href*='/liked_by/'] span[class*='html-span']").first
                    # CORRECTED: Await the text_content() call
                    likes_text = await likes_locator.text_content() if await likes_locator.is_visible() else "0"
                    num_likes = int("".join(filter(str.isdigit, likes_text)))
                    print(f"  ❤️ Likes: {num_likes}")
                except Exception as e:
                    print(f"  ⚠️ Impossible de trouver le nombre de likes: {e}")

                # --- Date de publication et Statut du post ---
                date = ""
                status = "Unknown" # Initialize status
                try:
                    date_locator = page.locator("time[datetime]").first
                    
                    raw_date_str = await date_locator.get_attribute("datetime") if await date_locator.is_visible() else ""
                    
                    if raw_date_str:
                        dt_object = datetime.strptime(raw_date_str, '%Y-%m-%dT%H:%M:%S.%fZ')
                        date = dt_object.strftime('%d-%m-%Y %H:%M')
                        
                        current_date = datetime.now()
                        new_post_threshold = timedelta(days=30) 
                        
                        if current_date - dt_object <= new_post_threshold:
                            status = "New"
                        else:
                            status = "Old"
                            
                    else:
                        date = "N/A" 
                        status = "No Date Found" 
                            
                    print(f" 📅 Date: {date}")
                    print(f" ⏳ Statut du post: {status}")

                except ValueError as ve:
                    print(f" ⚠️ Erreur de format de date: {ve}")
                    date = "N/A"
                    status = "Date Parsing Error"
                except Exception as e:
                    print(f" ⚠️ Impossible de trouver la date ou erreur inattendue: {e}")
                    date = "N/A"
                    status = "Error"

                # --- Extraction des commentaires ---
                comments = []
                print("  💬 Extraction des commentaires...")
                
                try:
                    # Made comment button locator more robust for multiple languages
                    view_more_comments_button = page.locator("button[role='button']").filter(
                        has_text=re.compile(r'(Voir plus de commentaires|Load more comments|View all \d+ comments)', re.IGNORECASE)
                    ).first
                    if await view_more_comments_button.is_visible():
                        await view_more_comments_button.click()
                        await page.wait_for_timeout(2000)
                        print("    ➡️ Cliqué sur 'Voir plus de commentaires'.")
                except Exception:
                    pass

                comment_containers = await page.locator("div[class*='x1iyjqo2'][class*='x2lwn1j'][class*='xeuugli']").all()

                for comment_elem in comment_containers:
                    comment_username = "N/A"
                    comment_text = "N/A"
                    
                    try:
                        user_locator = comment_elem.locator("a[href*='/'][class*='_a6hd']").first
                        # CORRECTED: Await the text_content() call
                        comment_username = await user_locator.text_content() if await user_locator.is_visible() else "N/A"
                        
                        all_spans_in_comment = await comment_elem.locator("span[dir='auto']").all()
                        
                        for s_idx, s_elem in enumerate(all_spans_in_comment):
                            text_content = await s_elem.text_content()
                            is_link = await s_elem.locator("a").count() > 0
                            
                            # Filter out common non-comment text like "Reply", empty strings, and @mentions that are links
                            if text_content and text_content.strip() not in ["Reply", ""] and not (is_link and text_content.strip().startswith("@")):
                                comment_text = text_content.strip()
                                break
                            elif text_content and text_content.strip() == comment_username: # Skip if the text content is just the username again
                                continue

                        if comment_username != "N/A" or comment_text != "N/A":
                            # Filter out "See translation" or empty comments
                            if comment_text.strip().lower() == "see translation" or not comment_text.strip():
                                continue
                            
                            comments.append({
                                "comment_username": comment_username.strip(),
                                "comment_text": comment_text.strip()
                            })
                    except Exception as e:
                        # Continue to next comment if one fails, without crashing
                        continue

                print(f"  💬 Commentaires extraits: {len(comments)}")

                
                posts.append({
                    "username": username,
                    "biography": user_biography,
                    "caption": caption,
                    "post_url": post_url,
                    "likes": num_likes,
                    "comments": len(comments),
                    "date": date,
                    "status": status
                })

            except Exception as e:
                print(f"  ❌ Erreur majeure lors de l'extraction du post {post_url}")
                continue # Continue to the next post even if one fails

        await browser.close()
    return posts

# 🎨 Interface utilisateur Streamlit
st.set_page_config(page_title="Instagram Hashtag Downloader", layout="centered")
st.title("📸 Instagram Hashtag Downloader")

default_hashtag = "hairstylistantwerp"
hashtag = st.text_input("Entrez un hashtag (sans #)", value=default_hashtag, key="hashtag_input")
limit = st.slider("Nombre de posts à récupérer", min_value=1, max_value=200, value=5, key="limit_slider")

if st.button("📥 Scraper les posts"):
    hashtag = hashtag.strip().lstrip("#")
    if not os.path.exists("cookies.json"):
        st.error("❌ Le fichier cookies.json est manquant. Veuillez créer un fichier 'cookies.json' avec vos cookies de session Instagram.")
    else:
        with st.spinner("⏳ Scraping en cours... Cela peut prendre quelques instants..."):
            try:
                posts = asyncio.run(scrape_instagram(hashtag, limit))
            except Exception as e:
                st.error(f"❌ Erreur critique lors du scraping: {e}. Veuillez réessayer.")
                posts = []

        if not posts:
            st.warning("⚠️ Aucun post trouvé ou une erreur est survenue. Veuillez vérifier le hashtag et les cookies.")
        else:
            df = pd.DataFrame(posts)
            os.makedirs("exports", exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"exports/hashtag_{hashtag}_{timestamp}.xlsx"
            df.to_excel(filename, index=False)

            with open(filename, "rb") as f:
                st.success("✅ Scraping terminé avec succès ! 🎉")
                st.download_button(
                    "📂 Télécharger le fichier Excel",
                    data=f,
                    file_name=os.path.basename(filename),
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            
            st.markdown("---")
            st.subheader("Aperçu des données extraites")
            st.dataframe(df)