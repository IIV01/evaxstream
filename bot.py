import os
import json
import requests
import asyncio
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from urllib.parse import urlencode
from telethon import TelegramClient, events
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# 🔑 Telegram API Credentials
API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")

# 🔑 YouTube API Credentials
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
SPONSORED_CHANNEL_ID = os.getenv("SPONSORED_CHANNEL_ID")
OAUTH_CLIENT_ID = os.getenv("OAUTH_CLIENT_ID")
OAUTH_CLIENT_SECRET = os.getenv("OAUTH_CLIENT_SECRET")
OAUTH_REDIRECT_URI = os.getenv("OAUTH_REDIRECT_URI")

# 🚀 Initialize Telegram Client
client = TelegramClient("bot", API_ID, API_HASH)
client.start(bot_token=BOT_TOKEN)

# 📂 Store Verified Users
VERIFIED_USERS_FILE = "verified_users.json"

def load_verified_users():
    if not os.path.exists(VERIFIED_USERS_FILE):
        return {}
    with open(VERIFIED_USERS_FILE, "r") as f:
        return json.load(f)

def save_verified_users(users):
    with open(VERIFIED_USERS_FILE, "w") as f:
        json.dump(users, f)

verified_users = load_verified_users()

# 🔗 Generate YouTube OAuth Link
def get_auth_link(user_id):
    params = {
        "client_id": OAUTH_CLIENT_ID,
        "redirect_uri": OAUTH_REDIRECT_URI,
        "response_type": "code",
        "scope": "https://www.googleapis.com/auth/youtube.readonly",
        "access_type": "offline",
        "prompt": "consent",
        "state": user_id
    }
    return f"https://accounts.google.com/o/oauth2/auth?{urlencode(params)}"

# 📡 Fetch Latest Movies from HDToday.cc
def fetch_latest_movies():
    url = "https://hdtoday.cc/home"
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(url, headers=headers)
    soup = BeautifulSoup(response.text, "html.parser")
    movies = {}
    
    for item in soup.select(".film_list-wrap .flw-item")[:5]:  # Get latest 5 movies
        title = item.select_one(".film-name a").text.strip()
        link = "https://hdtoday.cc" + item.select_one(".film-name a")["href"]
        movies[title] = link
    
    return movies

# 🎬 Extract Streaming Link
def get_movie_stream_link(movie_url):
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(movie_url, headers=headers)
    soup = BeautifulSoup(response.text, "html.parser")
    
    iframe = soup.find("iframe")
    if iframe:
        return iframe["src"]
    return None

# 🎭 Start Command
@client.on(events.NewMessage(pattern="/start"))
async def start(event):
    movies = fetch_latest_movies()
    if not movies:
        await event.respond("⚠️ No new movies available at the moment.")
        return
    
    movie_list = "\n".join([f"🎬 {title}" for title in movies.keys()])
    await event.respond(f"👋 Welcome! Here are the latest movies:\n\n{movie_list}\n\nReply with the movie name to watch.")

# 📺 Handle Movie Selection
@client.on(events.NewMessage())
async def handle_movie_selection(event):
    user_id = str(event.sender_id)
    movie_name = event.message.text.strip()
    
    # Check if user is verified
    if user_id not in verified_users or datetime.utcnow() > datetime.strptime(verified_users[user_id], "%Y-%m-%d %H:%M:%S"):
        auth_link = get_auth_link(user_id)
        await event.respond(f"⚠️ You must subscribe to our sponsored YouTube channel to watch movies. Click here to verify: [Verify Now]({auth_link})", link_preview=False)
        return
    
    # Fetch the movie link
    movies = fetch_latest_movies()
    if movie_name not in movies:
        await event.respond("❌ Movie not found. Please select from the latest uploads.")
        return
    
    movie_url = movies[movie_name]
    stream_link = get_movie_stream_link(movie_url)
    
    if stream_link:
        await event.respond(f"🎥 Watch **{movie_name}** here: [Click to Stream]({stream_link})", link_preview=False)
    else:
        await event.respond("⚠️ Streaming link not found. Please try again later.")

# 🔄 Exchange Authorization Code for Access Token
def exchange_code_for_token(auth_code):
    url = "https://oauth2.googleapis.com/token"
    data = {
        "client_id": OAUTH_CLIENT_ID,
        "client_secret": OAUTH_CLIENT_SECRET,
        "code": auth_code,
        "grant_type": "authorization_code",
        "redirect_uri": OAUTH_REDIRECT_URI
    }
    response = requests.post(url, data=data)
    return response.json().get("access_token")

# 🔍 Check if User Subscribed to Channel
def is_user_subscribed(access_token):
    url = f"https://www.googleapis.com/youtube/v3/subscriptions?part=snippet&mine=true&forChannelId={SPONSORED_CHANNEL_ID}"
    headers = {"Authorization": f"Bearer {access_token}"}
    response = requests.get(url, headers=headers).json()
    return "items" in response and len(response["items"]) > 0

# 🔄 Handle OAuth Callback
@client.on(events.NewMessage(pattern="/callback (.*)"))
async def handle_callback(event):
    user_id = str(event.sender_id)
    auth_code = event.pattern_match.group(1)
    access_token = exchange_code_for_token(auth_code)
    
    if access_token and is_user_subscribed(access_token):
        verified_users[user_id] = (datetime.utcnow() + timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")
        save_verified_users(verified_users)
        await event.respond("✅ Subscription verified! You now have access for 24 hours.")
    else:
        await event.respond("❌ Verification failed. Make sure you subscribed and try again.")

# 🚀 Run the Bot
if __name__ == "__main__":
    print("🤖 Bot is running...")
    client.run_until_disconnected()
