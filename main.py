from instaloader import Instaloader, Hashtag
import time
import os
from dotenv import load_dotenv

load_dotenv()

loader = Instaloader()
loader.load_session_from_file(os.getenv("INSTAGRAM_USER"), os.getenv("INSTAGRAM_SESSION"))

hashtag = Hashtag.from_name(loader.context, "hairstylistantwerp")

for post in hashtag.get_posts():
    print(f"Downloading post by @{post.owner_username}")
    loader.download_post(post, target="hairstylistantwerp")
    time.sleep(15)
