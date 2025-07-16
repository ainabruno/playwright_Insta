import streamlit as st
import instaloader
from instaloader.exceptions import ProfileNotExistsException, ConnectionException

# Configurer l'affichage de la page
st.set_page_config(page_title="Instagram Scraper", layout="centered")

st.title("📸 Instagram Scraper avec Session Instagram")

# Nom d'utilisateur à scraper
username_input = st.text_input("🔍 Entrez un nom d'utilisateur Instagram :", "")

# Utilisateur connecté à Instagram (pour charger la session)
login_user = "ton_nom_utilisateur"  # <-- Remplace par ton identifiant Instagram

if username_input:
    try:
        # Créer une instance Instaloader
        L = instaloader.Instaloader()

        # Charger une session Instagram sauvegardée
        try:
            L.load_session_from_file(login_user)
            st.info(f"✅ Session Instagram chargée pour {login_user}")
        except FileNotFoundError:
            st.error(f"❌ Session non trouvée. Lance d'abord dans le terminal :\n`instaloader --login={login_user}`")
            st.stop()

        # Charger le profil demandé
        profile = instaloader.Profile.from_username(L.context, username_input)

        st.success(f"👤 Profil trouvé : {profile.username}")
        st.write(f"Nom complet : {profile.full_name}")
        st.write(f"Bio : {profile.biography}")
        st.write(f"Publications : {profile.mediacount}")

        # Afficher les 3 dernières images
        st.subheader("🖼️ Dernières publications")

        posts = profile.get_posts()
        count = 0
        for post in posts:
            st.image(post.url, caption=f"Publié le {post.date}", use_column_width=True)
            count += 1
            if count >= 3:
                break

    except ProfileNotExistsException:
        st.error("❌ Le profil n'existe pas.")
    except ConnectionException:
        st.error("⚠️ Connexion échouée. Assure-toi que ta session est valide et que ton VPN est activé.")
    except Exception as e:
        st.error(f"🚫 Erreur : {e}")
