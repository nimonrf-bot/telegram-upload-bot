import os
import logging
import hashlib
import requests
from datetime import datetime

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    MessageHandler,
    CallbackContext,
    filters,
)

# ----------------------------------------------------
# Logging
# ----------------------------------------------------
logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
log = logging.getLogger(__name__)

def log_event(msg):
    timestamp = datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")
    logging.info(f"{timestamp} {msg}")

# ----------------------------------------------------
# Load environment variables (Railway)
# ----------------------------------------------------
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
NETLIFY_TOKEN = os.getenv("NETLIFY_TOKEN")
NETLIFY_SITE_ID = os.getenv("NETLIFY_SITE_ID")
ALLOWED_USERS = os.getenv("ALLOWED_USER_IDS", "")

# Convert ALLOWED_USERS env string → set of ints
ALLOWED_USERS = {int(uid.strip()) for uid in ALLOWED_USERS.split(",") if uid.strip().isdigit()}

# ----------------------------------------------------
# Netlify Upload Function (FINAL)
# ----------------------------------------------------
def upload_to_netlify(file_path, filename):
    try:
        if not NETLIFY_TOKEN or not NETLIFY_SITE_ID:
            return False, "Missing Netlify token or site ID"

        headers = {"Authorization": f"Bearer {NETLIFY_TOKEN}"}

        # STEP 1 → CREATE DEPLOY
        create_url = f"https://api.netlify.com/api/v1/sites/{NETLIFY_SITE_ID}/deploys"
        res = requests.post(create_url, headers=headers)

        if res.status_code != 200:
            return False, f"Deploy create failed: {res.status_code} {res.text}"

        deploy_id = res.json()["id"]
        log_event(f"Created deploy: {deploy_id}")

        # STEP 2 → READ FILE
        with open(file_path, "rb") as f:
            file_bytes = f.read()

        # STEP 3 → UPLOAD FILE to deploy
        upload_url = f"https://api.netlify.com/api/v1/deploys/{deploy_id}/files/{filename}"

        upload_headers = {
            "Authorization": f"Bearer {NETLIFY_TOKEN}",
            "Content-Type": "application/octet-stream",
            "Content-Length": str(len(file_bytes)),
        }

        res2 = requests.put(upload_url, headers=upload_headers, data=file_bytes)

        if res2.status_code not in (200, 201):
            return False, f"File upload failed: {res2.status_code} {res2.text}"

        # STEP 4 → PUBLISH DEPLOY
        publish_url = f"https://api.netlify.com/api/v1/deploys/{deploy_id}/publish"
        res3 = requests.post(publish_url, headers=headers)

        if res3.status_code != 200:
            return False, f"Publish failed: {res3.status_code} {res3.text}"

        final_url = res3.json()["deploy_ssl_url"] + "/" + filename

        return True, final_url

    except Exception as e:
        return False, f"Exception: {str(e)}"

# ----------------------------------------------------
# Handle document upload
# ----------------------------------------------------
async def handle_file(update: Update, context: CallbackContext):
    user = update.effective_user
    user_id = user.id

    if user_id not in ALLOWED_USERS:
        log_event(f"Unauthorized access attempt from {user_id}")
        await update.message.reply_text("❌ You are not allowed.")
        return

    doc = update.message.document
    filename = doc.file_name
    log_event(f"File received from {user_id}: {filename}")

    # Download file
    file = await context.bot.get_file(doc.file_id)
    file_path = f"/tmp/{filename}"
    await file.download_to_drive(file_path)

    log_event(f"Uploading {filename} to Netlify...")

    # Upload
    ok, result = upload_to_netlify(file_path, filename)

    if ok:
        log_event(f"SUCCESS: {filename} → {result}")
        await update.message.reply_text(f"✅ Upload complete:\n{result}")
    else:
        log_event(f"FAIL: {filename} — {result}")
        await update.message.reply_text(f"❌ Upload failed:\n{result}")

# ----------------------------------------------------
# MAIN
# ----------------------------------------------------
def main():
    log_event("Bot starting…")

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(MessageHandler(filters.Document.ALL, handle_file))

    app.run_polling()

# ----------------------------------------------------
if __name__ == "__main__":
    main()
