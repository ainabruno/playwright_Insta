import asyncio
from playwright.async_api import async_playwright
import json

async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, slow_mo=100)
        context = await browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        await page.goto("https://www.facebook.com/login", timeout=90000)

        print("🟡 Connecte-toi à Facebook manuellement dans la fenêtre...")
        await page.wait_for_timeout(90000)  # 60 sec pour se connecter

        # Vérifie que l'utilisateur est bien connecté
        if "login" not in page.url:
            cookies = await context.cookies()
            with open("facebook_cookies.json", "w") as f:
                json.dump(cookies, f, indent=2)
                print("✅ Cookies Facebook sauvegardés dans facebook_cookies.json")
        else:
            print("❌ Connexion échouée. Vérifie tes identifiants.")

        await browser.close()

asyncio.run(run())
