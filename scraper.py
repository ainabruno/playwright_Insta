import asyncio
from playwright.async_api import async_playwright
import os
from dotenv import load_dotenv
import json

load_dotenv()

USERNAME = os.getenv("INSTAGRAM_USER")
SESSION_FILE = os.getenv("INSTAGRAM_SESSION")
HASHTAG = "hairstylistantwerp"
MAX_PROFILES = 5

async def auto_click_popups(page):
    # Accepter les cookies si la popup apparaît
    try:
        await page.click("text=Accepter", timeout=3000)
    except:
        pass
    # Refuser les notifications si la popup apparaît
    try:
        await page.click("text=Plus tard", timeout=3000)
    except:
        pass
    # Fermer toute autre popup générique
    try:
        await page.click("button:has-text('Fermer')", timeout=3000)
    except:
        pass

async def run(playwright):
    browser = await playwright.chromium.launch(headless=False)
    context = await browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    page = await context.new_page()

    # Charger les cookies de session si le fichier existe
    if SESSION_FILE and os.path.exists(SESSION_FILE):
        with open(SESSION_FILE, "r", encoding="utf-8") as f:
            cookies = json.load(f)
        await context.add_cookies(cookies)
        print("Cookies de session chargés.")
        await page.goto("https://www.instagram.com/", wait_until="domcontentloaded")
        await auto_click_popups(page)
    else:
        print("Fichier de session introuvable ou non spécifié.")
        await browser.close()
        return

    # Aller sur la page du hashtag
    await page.goto(f"https://www.instagram.com/explore/tags/{HASHTAG}/")
    await auto_click_popups(page)

    # Attendre que les posts chargent
    await page.wait_for_selector("article a")

    # Scroller pour charger plusieurs publications
    for _ in range(5):
        await page.evaluate("window.scrollBy(0, document.body.scrollHeight)")
        await asyncio.sleep(3)
        await auto_click_popups(page)

    # Récupérer les liens des publications
    posts = await page.query_selector_all("article a")
    profile_urls = set()

    for post in posts:
        href = await post.get_attribute("href")
        if href and "/p/" in href:
            await post.click()
            await asyncio.sleep(2)
            await auto_click_popups(page)

            # Extraire le profil auteur dans la popup
            profile_link_elem = await page.query_selector("header a")
            if profile_link_elem:
                profile_link = await profile_link_elem.get_attribute("href")
                if profile_link:
                    profile_urls.add(f"https://instagram.com{profile_link}")

            # Fermer la popup
            close_btn = await page.query_selector("div[role='dialog'] button")
            if close_btn:
                await close_btn.click()
            await asyncio.sleep(1)

            if len(profile_urls) >= MAX_PROFILES:
                break

    print(f"Profils extraits pour #{HASHTAG} :")
    for url in profile_urls:
        print(url)

    await browser.close()

async def main():
    async with async_playwright() as playwright:
        await run(playwright)

if __name__ == "__main__":
    asyncio.run(main())