import os
import logging
from telegram import Update, Bot
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext
from telegram.error import BadRequest
from pymongo import MongoClient
from PyPDF2 import PdfMerger
from PIL import Image
from flask import Flask, jsonify
import threading

# Setting up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Flask app for Koyeb health check
app = Flask(__name__)

# Constants
MONGO_URI = os.getenv("mongodb+srv://uramit0001:EZ1u5bfKYZ52XeGT@cluster0.qnbzn.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0")
LOG_CHANNEL = os.getenv("-1002356766494")
BOT_TOKEN = os.getenv("7197957512:AAEQEjTzy5uPLqS30Ed90ZurqgkV6nR_DYA")

# Initialize MongoDB client
client = MongoClient(MONGO_URI)
db = client['telegram_bot']
users_collection = db['users']

# Flask health check endpoint
@app.route('/health')
def health_check():
    return jsonify({"status": "ok", "message": "Bot is running"}), 200

# Function to start the bot and log new users
def start(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    if not users_collection.find_one({"user_id": user_id}):
        users_collection.insert_one({"user_id": user_id})
    update.message.reply_text("Welcome! Send PDF or images to merge.")

# Function to handle PDF and image files
def handle_files(update: Update, context: CallbackContext):
    if update.message.document:
        file = update.message.document
        file_id = file.file_id
        filename = f"downloads/{file_id}_{file.file_name}"
        file_info = context.bot.get_file(file_id)

        # Create 'downloads' directory if it doesn't exist
        os.makedirs("downloads", exist_ok=True)

        # Download the file
        try:
            file_info.download(filename)
            update.message.reply_text("File received.")
            logger.info(f"File downloaded: {filename}")
        except FileNotFoundError:
            update.message.reply_text("Error: Download path not found.")
            return
        except BadRequest as e:
            update.message.reply_text("File is too large to download.")
            logger.error(f"Error downloading file: {e}")

# Function to merge PDFs
def merge_pdfs(file_list):
    merger = PdfMerger()
    output_path = "downloads/merged_document.pdf"
    try:
        for pdf_file in file_list:
            merger.append(pdf_file)
        merger.write(output_path)
        merger.close()
        return output_path
    except Exception as e:
        logger.error(f"Error merging PDFs: {e}")
        return None

# Function to merge images into a single PDF
def merge_images(file_list):
    output_path = "downloads/merged_images.pdf"
    try:
        images = [Image.open(img).convert('RGB') for img in file_list]
        images[0].save(output_path, save_all=True, append_images=images[1:])
        return output_path
    except Exception as e:
        logger.error(f"Error merging images: {e}")
        return None

# Function to handle the /merge command
def merge(update: Update, context: CallbackContext):
    chat_id = update.message.chat_id
    files_to_merge = []  # Collect file paths here

    # Identify file types for merging
    for filename in os.listdir("downloads"):
        if filename.endswith(".pdf"):
            files_to_merge.append(os.path.join("downloads", filename))
        elif filename.endswith((".png", ".jpg", ".jpeg")):
            files_to_merge.append(os.path.join("downloads", filename))

    # Merge based on file type
    if all(f.endswith(".pdf") for f in files_to_merge):
        merged_file = merge_pdfs(files_to_merge)
    else:
        merged_file = merge_images(files_to_merge)

    if merged_file:
        with open(merged_file, 'rb') as file:
            context.bot.send_document(chat_id, document=file, caption="Here is your merged document.")
            context.bot.send_document(LOG_CHANNEL, document=file, caption="User requested merged document.")
    else:
        update.message.reply_text("Error merging files.")

# Function for broadcasting messages
def broadcast(update: Update, context: CallbackContext):
    message = ' '.join(context.args)
    if not message:
        update.message.reply_text("Please provide a message to broadcast.")
        return

    user_ids = [user["user_id"] for user in users_collection.find()]
    for user_id in user_ids:
        try:
            context.bot.send_message(chat_id=user_id, text=message)
        except Exception as e:
            logger.error(f"Error sending message to {user_id}: {e}")

# Function to start the Telegram bot in a separate thread
def start_bot():
    updater = Updater(BOT_TOKEN)
    dispatcher = updater.dispatcher

    # Register handlers
    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(MessageHandler(Filters.document, handle_files))
    dispatcher.add_handler(CommandHandler("merge", merge))
    dispatcher.add_handler(CommandHandler("broadcast", broadcast, pass_args=True))

    # Start the bot
    updater.start_polling()
    updater.idle()

# Run Flask app and Telegram bot in parallel
if __name__ == '__main__':
    # Start the bot in a separate thread
    bot_thread = threading.Thread(target=start_bot)
    bot_thread.start()

    # Start the Flask app for health check
    app.run(host="0.0.0.0", port=5000)
