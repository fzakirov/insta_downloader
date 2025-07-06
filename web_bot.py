from dotenv import load_dotenv
load_dotenv() # This line reads the .env file

from config import *
import os
import asyncio
import logging
from flask import Flask, request
from telegram import Update
from telegram.ext import Application, MessageHandler, filters


# --- Library Setup ---
import instaloader
import yt_dlp

# --- Configuration & Environment Variables ---
# These must be set in your Vercel project settings
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL") # This is your Vercel app's public URL
INSTAGRAM_USERNAME = os.environ.get("INSTAGRAM_USERNAME") # For Instagram login
INSTAGRAM_SESSION_ID = os.environ.get("INSTAGRAM_SESSION_ID")

# --- Logging Setup ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- Instaloader & yt-dlp Setup ---
L = instaloader.Instaloader()

# --- The Correct Serverless Login Method ---
if INSTAGRAM_USERNAME and INSTAGRAM_SESSION_ID:
    try:
        # Create a session dictionary
        session_data = {
            'sessionid': INSTAGRAM_SESSION_ID,
            'mid': '', 'ig_did': '', 'ig_nrcb': '', 'csrftoken': '',
            'ds_user_id': '', 'shbid': '', 'shbts': '', 'rur': ''
        }
        # Load the session directly from the dictionary
        L.context.load_session_from_dict(session_data)
        L.context.username = INSTAGRAM_USERNAME
        L.context.is_logged_in = True
        logger.info(f"Successfully loaded Instagram session for {INSTAGRAM_USERNAME}")
    except Exception as e:
        logger.error(f"Could not load Instagram session from environment variables: {e}")
else:
    logger.warning("Instagram session environment variables not set. Proceeding without login.")

YDL_OPTS = {'format': 'best', 'quiet': True, 'noplaylist': True}

# --- Core Bot Logic (Video Handlers) ---
async def handle_instagram(update, url):
    await update.message.reply_text("Fetching your Instagram link...")
    
    try:
        # Extract the shortcode from any Instagram URL (reels, posts, etc.)
        shortcode = url.split('/')[-2]
        post = instaloader.Post.from_shortcode(L.context, shortcode)

        # IMPORTANT: Check if the post actually has a video
        if post.video_url:
            await update.message.reply_video(post.video_url, caption="Here is your video!")
        else:
            logger.warning(f"Post {shortcode} is not a video.")
            await update.message.reply_text("This link doesn't seem to be a video post.")

    except instaloader.exceptions.LoginRequiredException:
        logger.error("Session ID is invalid or expired. Login is required.")
        await update.message.reply_text("Sorry, my connection to Instagram has expired. The admin needs to refresh it.")
        
    except instaloader.exceptions.RateException:
        logger.error("Instagram rate limit has been hit.")
        await update.message.reply_text("I'm being rate-limited by Instagram right now. Please try again in a little while.")

    except Exception as e:
        # This logs the TRUE error for any other unexpected issue
        logger.error(f"An unexpected error occurred fetching Instagram content: {e}")
        await update.message.reply_text("Sorry, an unknown error occurred while trying to get that post.")

async def handle_youtube(update, url):
    await update.message.reply_text(f"{wait_message}")
    try:
        with yt_dlp.YoutubeDL(YDL_OPTS) as ydl:
            info_dict = ydl.extract_info(url, download=False)
            video_url = info_dict.get('url')
        if video_url:
            await update.message.reply_video(video_url, caption=f"{success_message}")
        else:
            await update.message.reply_text(f"{fail_message_yt1}")
    except Exception as e:
        logger.error(f"Error handling YouTube URL: {e}")
        await update.message.reply_text(f"{fail_message_yt1}")

async def handle_message(update: Update, context):
    """The main message handler. Determines which function to call based on the URL."""
    if not update.message or not update.message.text:
        return

    url = update.message.text
    if "instagram.com" in url:
        await handle_instagram(update, url)
    elif "youtube.com" in url or "youtu.be" in url:
        await handle_youtube(update, url)
    else:
        await update.message.reply_text("f{greeting_message}")


# --- Vercel Serverless Setup ---
app = Flask(__name__)
ptb_app = Application.builder().token(TELEGRAM_TOKEN).build()
ptb_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

@app.route(f"/{TELEGRAM_TOKEN}", methods=["POST"])
async def webhook():
    """This endpoint receives updates from Telegram."""
    await ptb_app.initialize() 
    update_data = request.get_json(force=True)
    update = Update.de_json(update_data, ptb_app.bot)
    await ptb_app.process_update(update)
    return "ok"

@app.route("/set_webhook", methods=['GET', 'POST'])
async def set_webhook():
    """A one-time function to tell Telegram where to send updates."""
    if not WEBHOOK_URL:
        return "Error: WEBHOOK_URL environment variable not set."
    await ptb_app.initialize()
    # We include the token in the path to ensure that only Telegram can call it
    webhook_full_url = f"{WEBHOOK_URL}/{TELEGRAM_TOKEN}"
    await ptb_app.bot.set_webhook(url=webhook_full_url)
    return f"Webhook set successfully to {webhook_full_url}"

@app.route("/")
def index():
    """A simple health check page."""
    return "Bot is running. Use /set_webhook to initialize."
