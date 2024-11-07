from flask import Flask
from telegram import Update
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext
from pymongo import MongoClient
import io
import threading
from PIL import Image
import fitz  # PyMuPDF

# Bot token and MongoDB URI
TOKEN = '7197957512:AAEQEjTzy5uPLqS30Ed90ZurqgkV6nR_DYA'
CHANNEL_ID = -1002356766494  # Replace with your actual channel ID
MONGO_URI = 'mongodb+srv://uramit0001:EZ1u5bfKYZ52XeGT@cluster0.qnbzn.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0'  # MongoDB URI

# Flask app for health check
app = Flask(__name__)

# MongoDB setup
client = MongoClient(MONGO_URI)
db = client['telegram_bot']
users_collection = db['users']

# Initialize updater for bot
updater = Updater(TOKEN, use_context=True)
dispatcher = updater.dispatcher

# Health check route
@app.route("/health", methods=["GET"])
def health_check():
    return "OK", 200

# Command to start the bot
def start(update: Update, context: CallbackContext):
    user = update.message.from_user
    update.message.reply_text("Hi! Send me images or PDFs to merge.")
    
    # Check if user is new, then store in MongoDB
    if not users_collection.find_one({"user_id": user.id}):
        users_collection.insert_one({"user_id": user.id, "username": user.username or user.first_name})

# Function to handle files (images and PDFs)
def handle_files(update: Update, context: CallbackContext):
    file = update.message.document or update.message.photo[-1]
    
    file_id = file.file_id
    file_info = context.bot.get_file(file_id)
    file_info.download(f"downloads/{file_id}")
    
    # Log the file upload to MongoDB and the log channel
    log_file_upload(update.message.from_user, file.file_name if file.file_name else "image/photo")
    
# Log uploaded files to the channel and MongoDB
def log_file_upload(user, file_name):
    log_message = f"User {user.username} uploaded {file_name}."
    
    # Send to the log channel
    context.bot.send_message(chat_id=CHANNEL_ID, text=log_message)
    
    # Log the action in MongoDB
    db['file_logs'].insert_one({"user_id": user.id, "username": user.username, "file_name": file_name})

# Command to merge files (images/PDFs)
def merge(update: Update, context: CallbackContext):
    # Your logic to merge the files (images/PDFs) here.
    # For simplicity, we are assuming merging logic is handled properly.
    
    merged_file = "path_to_merged_file"  # Placeholder for merged file path
    context.bot.send_document(chat_id=update.message.chat_id, document=open(merged_file, 'rb'))
    context.bot.send_message(chat_id=CHANNEL_ID, text="Merged file sent to user.")

# Command to broadcast messages to all users
def broadcast(update: Update, context: CallbackContext):
    message = ' '.join(context.args)
    users = users_collection.find()
    
    for user in users:
        context.bot.send_message(chat_id=user['user_id'], text=message)
    
    update.message.reply_text("Broadcast message sent to all users.")

# Set up handlers
dispatcher.add_handler(CommandHandler("start", start))
dispatcher.add_handler(MessageHandler(Filters.document | Filters.photo, handle_files))
dispatcher.add_handler(CommandHandler("merge", merge))
dispatcher.add_handler(CommandHandler("broadcast", broadcast))

# Bot running in a separate thread
def start_bot():
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    threading.Thread(target=start_bot).start()
    app.run(host="0.0.0.0", port=5000)
