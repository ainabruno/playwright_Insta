# --- Correctif Windows pour Playwright --------------------
import sys
import asyncio
if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
# ------------------------------------------------------------

import streamlit as st
import pandas as pd
import json
import os
import random
import time
from playwright.async_api import async_playwright, Page

# --- Configuration ---
GROUP_URL = "https://www.facebook.com/groups/5901559153227055/members"
MESSAGE_TEMPLATE = "Bonjour {name} 👋,\n\nJe vous contacte depuis le groupe Facebook. 😊\n\nBonne journée !"
MAX_DMS_PER_RUN = 30
current_dms = 0

# --- Charger les cookies Facebook ---
def load_cookies(path="facebook_cookies.json"):
    if not os.path.exists(path):
        st.error(f"❌ Cookies non trouvés ({path}). Génère-les via script de connexion.")
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        st.error("❌ Erreur de lecture du fichier cookies JSON.")
        return []

# --- Fonction pour envoyer un message à un profil ---
async def send_facebook_message(page: Page, profile_url: str) -> bool:
    global current_dms
    if current_dms >= MAX_DMS_PER_RUN:
        print("⚠️ Limite de DMs atteinte.")
        return False

    try:
        await page.goto(profile_url, timeout=20000)
        await page.wait_for_timeout(random.randint(2000, 4000))

        # Clic sur bouton "Message"
        btn = page.locator("div[role='button'] span:has-text('Message')").first
        if not await btn.is_visible():
            print("🚫 Bouton 'Message' non visible.")
            return False
        
        await btn.click()
        await page.wait_for_timeout(2000)

        # Zone d’écriture du message
        input_box = page.locator("div[aria-label='Écrire un message'][contenteditable='true']")
        await input_box.wait_for(state="visible", timeout=10000)

        name = (await page.title()).split("|")[0].strip()
        message = MESSAGE_TEMPLATE.format(name=name)

        await input_box.fill(message)
        await input_box.press("Enter")
        await page.wait_for_timeout(random.randint(1000, 3000))

        current_dms += 1
        print(f"✅ Message envoyé à {profile_url}")

        close_btn = page.locator("div[aria-label='Fermer la discussion'][role='button']").first
        if await close_btn.is_visible():
            await close_btn.click()
            print("🔒 Modal de message fermé.")
            await page.wait_for_timeout(1500)
            
        return True

    except Exception as e:
        print("❌ Erreur DM ➜", e)
        return False


# --- Scrape membres + envoi de messages ---
async def run_bot(limit: int = 10):
    global current_dms
    current_dms = 0
    cookies = load_cookies()
    if not cookies:
        return []

    results = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, slow_mo=50)
        ctx = await browser.new_context()
        await ctx.add_cookies(cookies)
        page = await ctx.new_page()

        await page.goto(GROUP_URL, timeout=30000)
        await page.wait_for_timeout(5000)

        # Scrolling pour charger les membres
        members = []
        scrolls = 0
        while len(members) < limit and scrolls < 3:
            await page.mouse.wheel(0, 3000)
            await page.wait_for_timeout(3000)

            # Sélecteur amélioré d'après ton HTML
            elems = await page.query_selector_all("span.xjp7ctv > a[href^='/groups/']")

            for e in elems:
                href = await e.get_attribute("href")
                name = await e.text_content()
                if href and name:
                    # Construire URL complète
                    profile_url = "https://www.facebook.com" + href.split("?")[0]
                    if profile_url not in [m["profile_url"] for m in members]:
                        members.append({"name": name.strip(), "profile_url": profile_url})
                    if len(members) >= limit:
                        break
            scrolls += 1

        print(f"{len(members)} profils collectés.")

        for idx, member in enumerate(members, start=1):
            st.write(f"✉️ Envoi {idx}/{len(members)} ➜ {member['name']} ({member['profile_url']})")
            success = await send_facebook_message(page, member["profile_url"])
            results.append({"name": member["name"], "profile": member["profile_url"], "sent": success})
            await page.wait_for_timeout(random.randint(3000, 6000))

        await browser.close()
    return results


# --- Interface Streamlit ---
st.set_page_config(page_title="FB Group DM Bot", layout="centered")
st.title("🤖 Facebook Group DM Bot")

limit = st.number_input("Nombre de membres à contacter", min_value=1, max_value=50, value=10)
if st.button("🚀 Lancer le bot"):
    with st.spinner("Envoi des messages en cours..."):
        data = asyncio.run(run_bot(limit))
    if data:
        df = pd.DataFrame(data)
        st.success("✅ Envoi terminé")
        st.dataframe(df)
        # Export
        os.makedirs("exports", exist_ok=True)
        fname = f"exports/fb_group_dm_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        df.to_excel(fname, index=False)
        with open(fname, "rb") as f:
            st.download_button("📥 Télécharger les résultats", f, file_name=os.path.basename(fname))
    else:
        st.error("❌ Aucun message n'a été envoyé.")
