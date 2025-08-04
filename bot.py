from dotenv import load_dotenv
load_dotenv() # This line reads the .env file

import os
import re
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import instaloader
from config import *

# --- Configuration & Environment Variables ---
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
INSTAGRAM_USERNAME = os.environ.get("INSTAGRAM_USERNAME")

# --- Setup Logging ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- Instaloader and yt-dlp Setup ---
L = instaloader.Instaloader(
    download_pictures=False,
    download_videos=False,
    download_video_thumbnails=False,
    save_metadata=False,
    compress_json=False
        )

try:
    L.load_session_from_file(INSTAGRAM_USERNAME)
except FileNotFoundError:
    logger.warning(f"Session file for {INSTAGRAM_USERNAME} not found. Please run 'instaloader --login={INSTAGRAM_USERNAME}' in your terminal.")

# --- Bot Command Handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a welcome message when the /start command is issued."""
    await update.message.reply_text(greeting_message)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles user messages containing video links."""
    url = update.message.text
    if re.search(r"(instagram\.com)", url):
        await handle_instagram(update, url)
    else:
        await update.message.reply_text("Please send a valid Instagram link.")

# --- Instagram Handler ---
async def handle_instagram(update: Update, url: str):
    """Downloads and sends an Instagram video."""
    await update.message.reply_text(wait_message)
    try:
        if "/reel/" in url:
            shortcode = url.split("/reel/")[1].split("/")[0]
            post = instaloader.Post.from_shortcode(L.context, shortcode)
            video_url = post.video_url
        elif "/stories/" in url:
            parts = url.split("/")
            username = parts[4]
            story_id = int(parts[5].split("?")[0])
            stories = L.get_stories(userids=[L.check_profile_id(username).userid])
            for story in stories:
                for item in story.get_items():
                    if item.mediaid == story_id:
                        video_url = item.video_url
                        break
                else:
                    continue
                break
        else:
            await update.message.reply_text("This doesn't look like a Reel or Story link.")
            return

        if video_url:
            await update.message.reply_video(video_url, caption=success_message)
        else:
            await update.message.reply_text("Could not find a video in this link.")

    except instaloader.exceptions.PrivateProfileNotFollowedException:
        await update.message.reply_text("This is a private account that the bot doesn't follow.")
    except instaloader.exceptions.LoginRequiredException:
        await update.message.reply_text("A login is required to access this content. Please configure the bot with an Instagram session.")
    except Exception as e:
        logger.error(f"Error handling Instagram URL: {e}")
        await update.message.reply_text("An error occurred while fetching the Instagram video.")

def main() -> None:
    """Start the bot."""
    application = Application.builder().token(TELEGRAM_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    application.run_polling()

if __name__ == '__main__':
    main()
