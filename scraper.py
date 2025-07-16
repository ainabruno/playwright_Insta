from playwright.sync_api import sync_playwright
import time

USERNAME = "randria1897"
PASSWORD = "Bruno17.com"
HASHTAG = "hairstylistantwerp"
MAX_PROFILES = 50

def run(playwright):
    browser = playwright.chromium.launch(headless=False)  # headless=True pour mode sans UI
    context = browser.new_context()
    page = context.new_page()

    # Aller sur la page de connexion Instagram
    page.goto("https://www.instagram.com/accounts/login/")

    # Attendre que le formulaire soit prêt
    page.wait_for_selector("input[name='username']")

    # Remplir login / mdp
    page.fill("input[name='username']", USERNAME)
    page.fill("input[name='password']", PASSWORD)

    # Cliquer sur se connecter
    page.click("button[type='submit']")

    # Attendre la navigation après login
    page.wait_for_load_state("networkidle")
    time.sleep(5)

    # Aller sur la page du hashtag
    page.goto(f"https://www.instagram.com/explore/tags/{HASHTAG}/")

    # Attendre que les posts chargent
    page.wait_for_selector("article a")

    # Scroller pour charger plusieurs publications
    for _ in range(5):
        page.evaluate("window.scrollBy(0, document.body.scrollHeight)")
        time.sleep(3)

    # Récupérer les liens des publications
    posts = page.query_selector_all("article a")
    profile_urls = set()

    for post in posts:
        href = post.get_attribute("href")
        if "/p/" in href:
            post.click()
            time.sleep(2)

            # Extraire le profil auteur dans la popup
            profile_link = page.query_selector("header a").get_attribute("href")
            profile_urls.add(f"https://instagram.com{profile_link}")

            # Fermer la popup
            close_btn = page.query_selector("div[role='dialog'] button")
            close_btn.click()
            time.sleep(1)

            if len(profile_urls) >= MAX_PROFILES:
                break

    print(f"Profils extraits pour #{HASHTAG} :")
    for url in profile_urls:
        print(url)

    browser.close()

with sync_playwright() as playwright:
    run(playwright)
