import os
import logging
import requests
from datetime import datetime
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes

# -------------------------------------------
# Load environment variables (Railway)
# -------------------------------------------
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
NETLIFY_TOKEN = os.getenv("NETLIFY_TOKEN")
NETLIFY_SITE_ID = os.getenv("NETLIFY_SITE_ID")
ALLOWED_USERS = os.getenv("ALLOWED_USERS", "")

# Convert comma-separated IDs → integers set
ALLOWED_USERS = {int(uid.strip()) for uid in ALLOWED_USERS.split(",") if uid.strip().isdigit()}

# -------------------------------------------
# Logging setup
# -------------------------------------------
logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

def log_event(message: str):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    logging.info(f"[{timestamp}] {message}")

# -------------------------------------------
# Upload file to Netlify
# -------------------------------------------
def upload_to_netlify(file_path, file_name):
    try:
        url = f"https://api.netlify.com/api/v1/sites/{NETLIFY_SITE_ID}/files/{file_name}"

        headers = {
            "Authorization": f"Bearer {NETLIFY_TOKEN}",
        }

        with open(file_path, "rb") as f:
            response = requests.put(url, headers=headers, data=f)

        if response.status_code in (200, 201):
            return True
        else:
            log_event(f"Netlify upload FAILED: {response.status_code}, {response.text}")
            return False

    except Exception as e:
        log_event(f"Upload error: {str(e)}")
        return False

# -------------------------------------------
# Handle incoming files
# -------------------------------------------
async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    # Check allowed users
    if user_id not in ALLOWED_USERS:
        await update.message.reply_text("You are not allowed to upload files.")
        log_event(f"Unauthorized attempt by {user_id}")
        return

    doc = update.message.document

    if not doc:
        await update.message.reply_text("Please send a valid Excel file.")
        return

    file_name = doc.file_name

    # Only accept xls/xlsx
    if not (file_name.endswith(".xls") or file_name.endswith(".xlsx")):
        await update.message.reply_text("Only Excel files (.xls, .xlsx) are allowed.")
        return

    # Download file to temp
    file_path = f"/tmp/{file_name}"
    new_file = await doc.get_file()
    await new_file.download_to_drive(file_path)

    log_event(f"Received file from {user_id}: {file_name}")

    # Upload to Netlify
    success = upload_to_netlify(file_path, file_name)

    if success:
        await update.message.reply_text("✅ Upload successful.")
        log_event(f"Upload success: {file_name}")
    else:
        await update.message.reply_text("❌ Upload failed.")
        log_event(f"Upload FAILED: {file_name}")

# -------------------------------------------
# Main bot starter
# -------------------------------------------
def main():
    log_event("Bot starting…")

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(MessageHandler(filters.Document.ALL, handle_file))

    app.run_polling()

# -------------------------------------------
if __name__ == "__main__":
    main()
