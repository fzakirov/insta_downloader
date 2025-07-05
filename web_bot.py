from dotenv import load_dotenv
load_dotenv() # This line reads the .env file


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

# --- Logging Setup ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- Instaloader & yt-dlp Setup ---
L = instaloader.Instaloader()
YDL_OPTS = {'format': 'best', 'quiet': True, 'noplaylist': True}

# --- Core Bot Logic (Video Handlers) ---
async def handle_instagram(update, url):
    await update.message.reply_text("Fetching public Instagram Reel...")
    try:
        shortcode = url.split("/reel/")[1].split("/")[0]
        post = instaloader.Post.from_shortcode(L.context, shortcode)
        await update.message.reply_video(post.video_url, caption="Here is your video!")
    except Exception as e:
        logger.error(f"Failed to fetch Instagram Reel without login: {e}")
        await update.message.reply_text("Sorry, I can only fetch public Reels, and this one failed. Private content and Stories require a login, which is not supported in this simple setup.")

async def handle_youtube(update, url):
    await update.message.reply_text("Fetching YouTube Short...")
    try:
        with yt_dlp.YoutubeDL(YDL_OPTS) as ydl:
            info_dict = ydl.extract_info(url, download=False)
            video_url = info_dict.get('url')
        if video_url:
            await update.message.reply_video(video_url, caption="Here is your video!")
        else:
            await update.message.reply_text("Could not extract video from this YouTube link.")
    except Exception as e:
        logger.error(f"Error handling YouTube URL: {e}")
        await update.message.reply_text("An error occurred while fetching the YouTube video.")

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
        await update.message.reply_text("Please send a valid public Instagram Reel or YouTube link.")


# --- Vercel Serverless Setup ---
app = Flask(__name__)
ptb_app = Application.builder().token(TELEGRAM_TOKEN).build()
ptb_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

@app.route(f"/{TELEGRAM_TOKEN}", methods=["POST"])
async def webhook():
    """This endpoint receives updates from Telegram."""
    update_data = request.get_json(force=True)
    update = Update.de_json(update_data, ptb_app.bot)
    await ptb_app.process_update(update)
    return "ok"

@app.route("/set_webhook", methods=['GET', 'POST'])
async def set_webhook():
    """A one-time function to tell Telegram where to send updates."""
    if not WEBHOOK_URL:
        return "Error: WEBHOOK_URL environment variable not set."
    
    # We include the token in the path to ensure that only Telegram can call it
    webhook_full_url = f"{WEBHOOK_URL}/{TELEGRAM_TOKEN}"
    await ptb_app.bot.set_webhook(url=webhook_full_url)
    return f"Webhook set successfully to {webhook_full_url}"

@app.route("/")
def index():
    """A simple health check page."""
    return "Bot is running. Use /set_webhook to initialize."
