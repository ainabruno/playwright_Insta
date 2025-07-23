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
from playwright.async_api import async_playwright, Page
import random # Import for random delays

MESSAGE_TEXT_TEMPLATE = "Bonjour 👋, j'ai découvert votre profil via le hashtag #{hashtag} et j'ai trouvé votre contenu très intéressant. 😊"


MAX_FOLLOWS_PER_DAY = 100 # max 150, but safer to be conservative 
MAX_DMS_PER_DAY = 30    # max 50, but safer to be conservative 

current_follows_today = 0
current_dms_today = 0

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

# --- Fonction pour extraire email et numéro de téléphone depuis une biographie ---
def extract_email_and_phone(biography: str):
    # Regex email plus robuste
    email_pattern = r"([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)"
    # Regex téléphone : accepte formats +33, 0033, espaces, tirets, parenthèses
    phone_pattern = r"(\+?\d{1,4}[\s.-]?)?(\(?\d{2,4}\)?[\s.-]?){2,5}\d{2,4}"

    email_matches = re.findall(email_pattern, biography)
    phone_matches = re.findall(phone_pattern, biography)

    email = email_matches[0] if email_matches else ""
    phone = "".join(phone_matches[0]) if phone_matches else ""

    return email, phone

# --- Nouvelle fonction: Suivre un utilisateur ---
async def follow_user(page: Page, username: str) -> bool:
    global current_follows_today

    if current_follows_today >= MAX_FOLLOWS_PER_DAY:
        print(f"⚠️ Limite quotidienne de follow ({MAX_FOLLOWS_PER_DAY}) atteinte. Impossible de suivre {username}.")
        return False

    print(f"Attempting to follow {username}...")
    try:
        profile_url = f"https://www.instagram.com/{username}/"
        current_url = page.url
        if profile_url not in current_url:
            await page.goto(profile_url, wait_until="domcontentloaded", timeout=15000)
            await page.wait_for_timeout(random.randint(1000, 3000))

        # --- MODIFICATION ICI : Sélecteur du bouton "Follow" amélioré ---
        follow_button = page.locator("button:has-text('Follow'), button:has-text('Suivre')").first
        
        following_button = page.locator("button:has-text('Following'), button:has-text('Abonné')").first
        
        # Wait for either follow or following button to be visible
        # This combined wait is crucial for robustness
        await page.wait_for_selector(
            "button:has-text('Follow'), button:has-text('Suivre'), button:has-text('Following'), button:has-text('Abonné')",
            state='visible',
            timeout=7000
        )

        if await following_button.is_visible():
            print(f"ℹ️ Vous suivez déjà {username}.")
            return True # Already following, so consider it a success for the purpose of DM
        elif await follow_button.is_visible():
            await follow_button.click(timeout=5000)
            current_follows_today += 1
            print(f"✅ Suivi de {username} effectué. ({current_follows_today}/{MAX_FOLLOWS_PER_DAY} aujourd'hui)")
            await page.wait_for_timeout(random.randint(500, 1500))
            return True
        else:
            print(f"❌ Bouton 'Follow' ou 'Following' non trouvé pour {username}.")
            return False
    except Exception as e:
        print(f"❌ Erreur lors du suivi de {username}: {e}")
        return False

# async def follow_user(page: Page, username: str) -> bool:
#     global current_follows_today

#     if current_follows_today >= MAX_FOLLOWS_PER_DAY:
#         print(f"⚠️ Limite quotidienne de follow ({MAX_FOLLOWS_PER_DAY}) atteinte. Impossible de suivre {username}.")
#         return False

#     print(f"🔍 Tentative de suivre {username}...")

#     try:
#         profile_url = f"https://www.instagram.com/{username}/"
#         await page.goto(profile_url, wait_until="domcontentloaded", timeout=30000)
#         await page.wait_for_timeout(random.randint(10000, 30000))

#         follow_btn = page.locator("button:has-text('Follow'), button:has-text('Suivre')")
#         following_btn = page.locator("button:has-text('Following'), button:has-text('Abonné')")

#         # Attente de la présence d'un des deux boutons
#         await page.wait_for_selector("button:has-text('Follow'), button:has-text('Suivre'), button:has-text('Following'), button:has-text('Abonné')", timeout=30000)

#         if await following_btn.is_visible():
#             print(f"ℹ️ Déjà abonné à {username}.")
#             return True

#         elif await follow_btn.is_visible():
#             await follow_btn.click()
#             print("⏳ Attente du changement 'Follow' -> 'Following'...")
#             try:
#                 await following_btn.wait_for(state="visible", timeout=80000)
#                 print(f"✅ Suivi de {username} confirmé.")
#                 current_follows_today += 1
#                 return True
#             except:
#                 print("⚠️ Le bouton n’a pas changé vers 'Following'.")
#                 return False

#         else:
#             print(f"❌ Bouton 'Follow' ou 'Following' introuvable pour {username}.")
#             return False

#     except Exception as e:
#         print(f"❌ Erreur lors du suivi de {username}: {e}")
#         return False


# 📩 Fonction mise à jour avec meilleure gestion des erreurs et debug
async def get_user_biography_and_send_dm(page: Page, username: str, hashtag: str) -> dict:
    global current_dms_today

    dm_sent = False
    dm_status = "Échec"
    profile_url = f"https://www.instagram.com/{username}/"

    print(f"➡️ Navigation vers le profil: {profile_url}")

    try:
        await page.goto(profile_url, wait_until="domcontentloaded", timeout=20000)
        print("📍 URL après navigation :", page.url)

        # Vérification redirection
        if "challenge" in page.url or "login" in page.url:
            print("⚠️ Redirection détectée. Session probablement invalide.")
            return {"dm_sent": False, "dm_status": "Échec (Session invalide)"}

        # Évite d’attendre indéfiniment
        # await page.wait_for_load_state("networkidle")  # désactivé
        await page.wait_for_timeout(random.randint(1000, 3000))

        print(f"Strategie 'Follow-First' pour {username}...")
        followed_successfully = await follow_user(page, username)

        if not followed_successfully:
            print(f"Impossible de suivre {username}. Saut du DM.")
            return {"dm_sent": False, "dm_status": "Échec (Follow impossible)"}

        wait_seconds = random.randint(5, 10)
        print(f"⏳ Attente de {wait_seconds} secondes avant DM...")
        await page.wait_for_timeout(wait_seconds * 1000)

        if current_dms_today >= MAX_DMS_PER_DAY:
            print(f"⚠️ Limite quotidienne DM atteinte ({MAX_DMS_PER_DAY}).")
            return {"dm_sent": False, "dm_status": "Échec (Limite DM atteinte)"}

        final_message_text = MESSAGE_TEXT_TEMPLATE.format(hashtag=hashtag)

        # 1. Ouvrir la boîte de message
        # # ▶️ Clic sur le bouton "Message"
        # try:
        #     message_button = page.locator("div[role='button']", has_text="Message")
        #     await message_button.click()
        #     print("📩 Clic sur le bouton 'Message' effectué.")
        #     await page.wait_for_timeout(random.randint(1500, 3000))
        try:
            # Meilleur sélecteur pour bouton 'Message'
            message_button = page.locator("button:has-text('Message'), div[role='button']:has-text('Message')").first
            await message_button.wait_for(state="visible", timeout=10000)

            if await message_button.is_visible():
                await message_button.click()
                print("📩 Bouton 'Message' cliqué.")
                await page.wait_for_timeout(random.randint(1500, 3000))
            else:
                print(f"🚫 Bouton 'Message' non visible pour {username}.")
                return {"dm_sent": False, "dm_status": "DM indisponible (non visible)"}

        except Exception as e:
            print(f"❌ Erreur bouton 'Message' : {e}")
            os.makedirs("screenshots", exist_ok=True)
            await page.screenshot(path=f"screenshots/error_message_button_{username}.png", full_page=True)
            return {"dm_sent": False, "dm_status": "Échec (Message non cliquable)"}

        # 2. Saisir et envoyer le message
        try:

            message_input = page.locator("div[aria-label='Message'][contenteditable='true']")
            await message_input.wait_for(state="visible", timeout=5000)

            # Remplir et envoyer le message
            await message_input.fill("")  # clear input
            await message_input.type(final_message_text, delay=random.randint(30, 70))

            print(f"💬 Message inséré : {final_message_text}")
            await message_input.press("Enter")
            await page.wait_for_timeout(random.randint(1000, 3000))

            def clean_text(text):
                # Supprime les emojis et les sauts de ligne
                text = re.sub(r"[^\w\s#,@'.!?-]", '', text)  # Conserve hashtags, ponctuations
                text = re.sub(r"\s+", " ", text).strip()
                return text.lower()

            try:
                await page.wait_for_selector("div[dir='auto']", timeout=10000)
                elements = await page.query_selector_all("div[dir='auto']")
                if not elements:
                    raise Exception("Aucun message détecté.")
                last = elements[-1]
                text = await last.inner_text()
                print("🕵️ Message détecté :", text)

                # Nettoyage du message attendu et reçu
                clean_detected = clean_text(text)
                clean_expected = clean_text(final_message_text)

                print("🔍 Comparaison nettoyée :")
                print(" - attendu :", clean_expected)
                print(" - détecté :", clean_detected)

                # Compare 80% du message sans emoji
                if clean_expected[:50] in clean_detected or clean_expected in clean_detected:
                    print("✅ Message envoyé et confirmé.")
                    dm_sent = True
                    dm_status = "OK"
                    current_dms_today += 1
                else:
                    print("⚠️ Le message ne correspond pas suffisamment.")
                    dm_status = "Échec (texte partiel)"

            except Exception as e:
                print(f"❌ Impossible de confirmer le message : {e}")
                await page.screenshot(path=f"screenshots/confirm_message_error_{username}.png")
                dm_status = "Échec (Confirmation)"

        except Exception as e:
            print(f"❌ Échec envoi du message : {e}")
            os.makedirs("screenshots", exist_ok=True)
            await page.screenshot(path=f"screenshots/error_dm_input_{username}.png", full_page=True)
            dm_status = "Échec (Saisie/envoi)"


    except Exception as e:
        print(f"❌ Erreur générale pour {username} : {e}")
        os.makedirs("screenshots", exist_ok=True)
        await page.screenshot(path=f"screenshots/error_general_{username}.png", full_page=True)
        dm_status = "Échec (Exception générale)"

    return {"dm_sent": dm_sent, "dm_status": dm_status}

# --- Fonction pour extraire le prénom de l'utilisateur ---

def extract_prenom(username: str) -> str:
    # Supprimer les caractères spéciaux
    cleaned = re.sub(r'[^a-zA-Z]', ' ', username)
    
    # Découper en mots
    mots = cleaned.split()

    # Heuristique : prendre le dernier mot non vide avec une majuscule
    for mot in reversed(mots):
        if mot and mot.isalpha():
            return mot.capitalize()

    return username.capitalize()

## Fonction principale simplifiée pour intégrer le message automatique uniquement
async def scrape_instagram(hashtag: str, limit: int = 5):
    global current_follows_today, current_dms_today
    current_follows_today = 0 # Reset counters for each run
    current_dms_today = 0     # In a real long-running bot, these should persist daily

    cookies = load_cookies()
    if not cookies:
        print("❌ Cookies manquants.")
        return []

    posts = []
    processed_hrefs = set() # To avoid processing the same post multiple times

    async with async_playwright() as p:
        # Launch browser in headless=False for debugging, switch to True for production
        browser = await p.chromium.launch(headless=True, slow_mo=100)
        context = await browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36"
        )

        # browser = await p.chromium.launch(headless=True) 
        # context = await browser.new_context()
        await context.add_cookies(cookies)
        page = await context.new_page()

        url = f"https://www.instagram.com/explore/tags/{hashtag}/"
        print(f"🌐 Navigation vers: {url}")

        try:
            await page.goto(url, timeout=60000)
            await page.wait_for_selector("a[href^='/p/']", timeout=20000)
            print("✅ Hashtag chargé.")
        except Exception as e:
            print(f"❌ Erreur chargement hashtag: {e}")
            await browser.close()
            return posts

        # Scroll pour charger les posts
        scroll_attempts = max(2, int(limit / 5))
        scroll_attempts = min(scroll_attempts, 5) # Cap max scroll attempts to avoid endless loops
        wait_time_per_scroll = random.randint(1000, 3000) # Randomize scroll wait time
        for _ in range(scroll_attempts):
            await page.evaluate("window.scrollBy(0, document.body.scrollHeight)")
            await page.wait_for_timeout(wait_time_per_scroll)

        links = await page.locator("a[href^='/p/']").all()
        hrefs = []
        for l in links:
            href = await l.get_attribute("href")
            # Only add post links (starting with /p/) and avoid duplicates
            if href and href.startswith("/p/") and href not in processed_hrefs:
                hrefs.append(href)
                processed_hrefs.add(href)
            if len(hrefs) >= limit:
                break
        print(f"🔗 {len(hrefs)} posts trouvés.")

        utilisateurs_deja_contactes = set()

        for i, href in enumerate(hrefs):
            # Check if daily DM limit or Follow limit reached before processing next post
            if current_dms_today >= MAX_DMS_PER_DAY or current_follows_today >= MAX_FOLLOWS_PER_DAY:
                print(f"⚠️ Limites quotidiennes de DM ({MAX_DMS_PER_DAY}) ou Follow ({MAX_FOLLOWS_PER_DAY}) atteintes. Arrêt du scraping.")
                break

            post_url = f"https://www.instagram.com{href}"
            print(f"\n✨ Scraping post {i+1}/{len(hrefs)}: {post_url}")

            statut_message = "Échec général"  # Default status

            try:
                await page.goto(post_url, timeout=20000)
                await page.wait_for_selector("time[datetime]", timeout=10000) # Wait for post to load
                await page.wait_for_timeout(random.randint(1000, 3000)) # Random delay after post load
                print("✅ Post chargé.")

                # Locate the username element (assuming it's consistent)
                username_locator = page.locator("span._ap3a._aaco._aacw._aacx._aad7._aade[dir='auto']").first

                if await username_locator.is_visible():
                    username = (await username_locator.text_content()).strip()
                    print(f"👤 Utilisateur: {username}")

                    if username in utilisateurs_deja_contactes:
                        print(f"⏩ Message déjà envoyé à {username} — on passe.")
                        statut_message = "Déjà contacté"
                    else:
                        # Call the combined function
                        result = await get_user_biography_and_send_dm(page, username, hashtag)
                        statut_message = result["dm_status"]
                        if result["dm_sent"]:
                            utilisateurs_deja_contactes.add(username)
                        
                        # Extract prénom for the report
                        prenom = extract_prenom(username)

                        posts.append({
                            "Prénom": prenom,
                            "Instagram Handle": username,
                            "Statut du message": statut_message
                        })
                else:
                    print(f"❌ Nom d'utilisateur non trouvé pour le post {post_url}.")
                    statut_message = "Échec (Nom d'utilisateur introuvable)"
                    posts.append({
                        "Prénom": "N/A",
                        "Instagram Handle": "N/A",
                        "Statut du message": statut_message
                    })

            except Exception as e:
                print(f"  ❌ Erreur majeure lors du traitement du post {post_url}: {e}")
                statut_message = f"Échec (Erreur traitement post: {e})"
                posts.append({
                    "Prénom": "N/A",
                    "Instagram Handle": "N/A",
                    "Statut du message": statut_message
                })
                continue 
        
        await browser.close() # Close browser after all posts are processed
    return posts

# 🎨 Interface utilisateur Streamlit
st.set_page_config(page_title="Instagram Hashtag Downloader", layout="centered")
st.title("📸 Instagram Hashtag Downloader & DM Sender") # Updated title

default_hashtag = "hairstylistantwerp"
hashtag = st.text_input("Entrez un hashtag (sans #)", value=default_hashtag, key="hashtag_input")
limit = st.slider("Nombre de posts à récupérer (affecte aussi le nombre de DM envoyés)", min_value=1, max_value=200, value=5, key="limit_slider")

if st.button("📥 Scraper les posts et envoyer les DMs"): # Updated button text
    hashtag = hashtag.strip().lstrip("#")
    if not os.path.exists("cookies.json"):
        st.error("❌ Le fichier cookies.json est manquant. Veuillez créer un fichier 'cookies.json' avec vos cookies de session Instagram.")
    else:
        with st.spinner("⏳ Scraping et envoi de DMs en cours... Cela peut prendre quelques instants..."):
            try:
                posts_and_dms_results = asyncio.run(scrape_instagram(hashtag, limit))
            except Exception as e:
                st.error(f"❌ Erreur critique lors du scraping et de l'envoi de DMs: {e}. Veuillez réessayer.")
                posts_and_dms_results = []

        if not posts_and_dms_results:
            st.warning("⚠️ Aucun post trouvé ou une erreur est survenue. Veuillez vérifier le hashtag et les cookies.")
        else:
            df = pd.DataFrame(posts_and_dms_results)
            os.makedirs("exports", exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"exports/hashtag_{hashtag}_{timestamp}.xlsx"
            df.to_excel(filename, index=False)

            with open(filename, "rb") as f:
                st.success("✅ Scraping et envoi de DMs terminés avec succès ! 🎉")
                st.download_button(
                    "📂 Télécharger le fichier Excel des résultats",
                    data=f,
                    file_name=os.path.basename(filename),
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            
            st.markdown("---")
            st.subheader("Aperçu des données et statuts de DM")
            st.dataframe(df)



# # --- Correctif Windows pour Playwright (sous-processus) --------------------
# import sys
# import asyncio
# if sys.platform.startswith("win"):
#     asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
# # ---------------------------------------------------------------------------

# import streamlit as st
# import pandas as pd
# from datetime import datetime, timedelta
# import re
# import json
# import os
# from playwright.async_api import async_playwright, Page # <--- ADDED 'Page' IMPORT HERE

# MESSAGE_TEXT = "Bonjour 👋, je viens de consulter votre profil et je suis intéressé par votre contenu. Discutons ! 😊"

# # 📂 Charger les cookies depuis un fichier JSON
# def load_cookies(path="cookies.json"):
#     """Loads cookies from a JSON file."""
#     if not os.path.exists(path):
#         st.warning(f"🍪 Fichier de cookies non trouvé à l'emplacement : {path}. Veuillez vous assurer d'être connecté.")
#         return []
#     try:
#         with open(path, "r", encoding="utf-8") as f:
#             return json.load(f)
#     except json.JSONDecodeError:
#         st.error(f"❌ Erreur de lecture du fichier cookies.json. Assurez-vous qu'il s'agit d'un JSON valide.")
#         return []
    
# # --- Fonction pour extraire email et numéro de téléphone depuis une biographie ---
# def extract_email_and_phone(biography: str):
#     # Regex email plus robuste
#     email_pattern = r"([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)"
#     # Regex téléphone : accepte formats +33, 0033, espaces, tirets, parenthèses
#     phone_pattern = r"(\+?\d{1,4}[\s.-]?)?(\(?\d{2,4}\)?[\s.-]?){2,5}\d{2,4}"

#     email_matches = re.findall(email_pattern, biography)
#     phone_matches = re.findall(phone_pattern, biography)

#     email = email_matches[0] if email_matches else ""
#     phone = "".join(phone_matches[0]) if phone_matches else ""

#     return email, phone


# # --- Fonction d'extraction de la biographie utilisateur ---
# async def get_user_biography_send_ms(page: Page, username: str) -> dict:
#     biography = "N/A"
#     email = ""
#     phone = ""
#     external_links = []

#     profile_url = f"https://www.instagram.com/{username}/"
#     print(f"➡️ Navigation vers le profil: {profile_url}")

#     try:
#         await page.goto(profile_url, wait_until="domcontentloaded", timeout=15000)

#         # Récupération de la biographie
#         biography_locator = page.locator("span._ap3a._aaco._aacu._aacx._aad7._aade[dir='auto']").first
#         await biography_locator.wait_for(state='visible', timeout=5000)

#         try:
#             more_button = page.locator("span:has-text('more'), span:has-text('Voir plus'), span:has-text('...plus')").first
#             if await more_button.is_visible():
#                 print("🔘 Bouton 'Voir plus' détecté, clic...")
#                 await more_button.click()
#                 await page.wait_for_timeout(500)
#         except Exception:
#             pass  # Pas de bouton 'Voir plus'

#         if await biography_locator.is_visible():
#             bio_text = await biography_locator.text_content()
#             biography = re.sub(r'\s*(Voir plus|See more|...more)\s*$', '', bio_text.strip(), flags=re.IGNORECASE).strip()
#             print(f"📝 Biographie: {biography[:120]}...")

#             email, phone = extract_email_and_phone(biography)

#         # Liens externes
#         try:
#             link_blocks = page.locator("div._ap3a._aaco._aacw._aacz._aada._aade[dir='auto']")
#             count = await link_blocks.count()

#             for i in range(count):
#                 text = await link_blocks.nth(i).text_content()
#                 links_found = re.findall(r'https?://\S+|www\.\S+', text or "")
#                 for link in links_found:
#                     cleaned = link.strip().split()[0].strip('.,)')
#                     if cleaned not in external_links:
#                         external_links.append(cleaned)
#             if external_links:
#                 print(f"🔗 Liens externes trouvés : {external_links}")
#         except Exception as e:
#             print(f"⚠️ Erreur liens externes : {e}")

#         # ▶️ Clic sur le bouton "Message"
#         try:
#             message_button = page.locator("div[role='button']", has_text="Message")
#             await message_button.click()
#             print("📩 Clic sur le bouton 'Message' effectué.")
#             await page.wait_for_timeout(2000)
#         except Exception as e:
#             print(f"❌ Erreur clic 'Message' : {e}")

#         # ✏️ Remplir le champ de message
#         try:
#             message_input = page.locator("div[aria-label='Message'][contenteditable='true']")
#             await message_input.wait_for(state='visible', timeout=5000)
#             await message_input.fill("")  # reset
#             await message_input.type(MESSAGE_TEXT, delay=50)
#             print(f"💬 Message inséré : {MESSAGE_TEXT}")
#         except Exception as e:
#             print(f"❌ Erreur saisie du message : {e}")

#     except Exception as e:
#         print(f"❌ Erreur générale: {e}")
#         biography = "Extraction Error"

#     return {
#         "biography": biography,
#         "email": email,
#         "phone": phone,
#         "external_links": external_links
#     }

# async def send_dm_direct(page: Page, username: str, message_text: str) -> bool:
#     try:
#         profile_url = f"https://www.instagram.com/{username}/"
#         await page.goto(profile_url, wait_until="domcontentloaded", timeout=15000)

#         # ▶️ Clic sur le bouton "Message"
#         try:
#             message_button = page.locator("div[role='button']", has_text="Message")
#             await message_button.click()
#             print("📩 Clic sur le bouton 'Message' effectué.")
#             await page.wait_for_timeout(2000)
#         except Exception as e:
#             print(f"❌ Erreur clic 'Message' : {e}")
#             return False

#         # ✏️ Remplir le champ de message
#         try:
#             message_input = page.locator("div[aria-label='Message'][contenteditable='true']")
#             await message_input.wait_for(state='visible', timeout=7000)
#             await message_input.click()
#             await message_input.fill("")
#             await message_input.type(message_text, delay=30)
#             print(f"💬 Message inséré : {message_text}")

#             # 📤 Envoyer (ENTER)
#             await message_input.press("Enter")
#             await page.wait_for_timeout(2000)

#             # ✅ Vérifier si le message apparaît dans l'historique (confirmation)
#             sent_message = page.locator(f"div:has-text('{message_text}')").last
#             if await sent_message.is_visible():
#                 print("✅ Message confirmé comme envoyé.")
#                 return True
#             else:
#                 print("⚠️ Message non confirmé.")
#                 return False

#         except Exception as e:
#             print(f"❌ Erreur lors de la saisie/envoi : {e}")
#             return False

#     except Exception as e:
#         print(f"❌ Erreur générale dans l'envoi : {e}")
#         return False

# def extract_prenom(username: str) -> str:
#     # Supprimer les caractères spéciaux
#     cleaned = re.sub(r'[^a-zA-Z]', ' ', username)
    
#     # Découper en mots
#     mots = cleaned.split()

#     # Heuristique : prendre le dernier mot non vide avec une majuscule
#     for mot in reversed(mots):
#         if mot and mot.isalpha():
#             return mot.capitalize()

#     return username.capitalize()

# ## Fonction principale simplifiée pour intégrer le message automatique uniquement
# async def scrape_instagram(hashtag: str, limit: int = 5):
#     cookies = load_cookies()
#     if not cookies:
#         print("❌ Cookies manquants.")
#         return []

#     posts = []
#     processed_hrefs = set()

#     async with async_playwright() as p:
#         browser = await p.chromium.launch(headless=True)
#         context = await browser.new_context()
#         await context.add_cookies(cookies)
#         page = await context.new_page()

#         url = f"https://www.instagram.com/explore/tags/{hashtag}/"
#         print(f"🌐 Navigation vers: {url}")

#         try:
#             await page.goto(url, timeout=60000)
#             await page.wait_for_selector("a[href^='/p/']", timeout=20000)
#             print("✅ Hashtag chargé.")
#         except Exception as e:
#             print(f"❌ Erreur chargement hashtag: {e}")
#             await browser.close()
#             return posts

#         # Scroll pour charger les posts
#         scroll_attempts = max(2, int(limit / 5))
#         scroll_attempts = min(scroll_attempts, 5)
#         wait_time_per_scroll = max(1000, min(900, int(limit * 10)))
#         for _ in range(scroll_attempts):
#             await page.evaluate("window.scrollBy(0, document.body.scrollHeight)")
#             await page.wait_for_timeout(wait_time_per_scroll)

#         links = await page.locator("a[href^='/p/']").all()
#         hrefs = []
#         for l in links:
#             href = await l.get_attribute("href")
#             if href and href.startswith("/p/") and href not in processed_hrefs:
#                 hrefs.append(href)
#                 processed_hrefs.add(href)
#             if len(hrefs) >= limit:
#                 break
#         print(f"🔗 {len(hrefs)} posts trouvés.")

#         utilisateurs_deja_contactes = set()

#         for i, href in enumerate(hrefs):
#             post_url = f"https://www.instagram.com{href}"
#             print(f"\n✨ Scraping post {i+1}/{len(hrefs)}: {post_url}")

#             statut_message = "Échec"  # Par défaut

#             try:
#                 await page.goto(post_url, timeout=20000)
#                 await page.wait_for_selector("time[datetime]", timeout=10000)
#                 print("✅ Post chargé.")

#                 username_locator = page.locator("span._ap3a._aaco._aacw._aacx._aad7._aade[dir='auto']").first

#                 if await username_locator.is_visible():
#                     username = (await username_locator.text_content()).strip()
#                     print(f"👤 Utilisateur: {username}")

#                     if username in utilisateurs_deja_contactes:
#                         print(f"⏩ Message déjà envoyé à {username} — on passe.")
#                         statut_message = "Déjà contacté"
#                     else:
#                         message_text = "Hello! I found your post on Instagram and would love to connect. Feel free to check out my profile too!"

#                         success = await send_dm_direct(page, username, message_text)
#                         statut_message = "OK" if success else "Échec"

#                         if success:
#                             utilisateurs_deja_contactes.add(username)

#                     # Extraire prénom 
#                     prenom = extract_prenom(username)

#                     posts.append({
#                         "Prénom": prenom,
#                         "Instagram Handle": username,
#                         "Statut du message": statut_message
#                     })

#             except Exception as e:
#                 print(f"  ❌ Erreur majeure lors de l'extraction du post {post_url}: {e}")
#                 continue  # Continue to the next post even if one fails
#                 await browser.close()
#     return posts

# # 🎨 Interface utilisateur Streamlit
# st.set_page_config(page_title="Instagram Hashtag Downloader", layout="centered")
# st.title("📸 Instagram Hashtag Downloader")

# default_hashtag = "hairstylistantwerp"
# hashtag = st.text_input("Entrez un hashtag (sans #)", value=default_hashtag, key="hashtag_input")
# limit = st.slider("Nombre de posts à récupérer", min_value=1, max_value=200, value=5, key="limit_slider")

# if st.button("📥 Scraper les posts"):
#     hashtag = hashtag.strip().lstrip("#")
#     if not os.path.exists("cookies.json"):
#         st.error("❌ Le fichier cookies.json est manquant. Veuillez créer un fichier 'cookies.json' avec vos cookies de session Instagram.")
#     else:
#         with st.spinner("⏳ Scraping en cours... Cela peut prendre quelques instants..."):
#             try:
#                 posts = asyncio.run(scrape_instagram(hashtag, limit))
#             except Exception as e:
#                 st.error(f"❌ Erreur critique lors du scraping: {e}. Veuillez réessayer.")
#                 posts = []

#         if not posts:
#             st.warning("⚠️ Aucun post trouvé ou une erreur est survenue. Veuillez vérifier le hashtag et les cookies.")
#         else:
#             df = pd.DataFrame(posts)
#             os.makedirs("exports", exist_ok=True)
#             timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
#             filename = f"exports/hashtag_{hashtag}_{timestamp}.xlsx"
#             df.to_excel(filename, index=False)

#             with open(filename, "rb") as f:
#                 st.success("✅ Scraping terminé avec succès ! 🎉")
#                 st.download_button(
#                     "📂 Télécharger le fichier Excel",
#                     data=f,
#                     file_name=os.path.basename(filename),
#                     mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
#                 )
            
#             st.markdown("---")
#             st.subheader("Aperçu des données extraites")
#             st.dataframe(df)