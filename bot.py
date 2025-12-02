import os
import zipfile
import requests
from datetime import datetime
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, ContextTypes, filters

# -----------------------------------
# CONFIG (LOAD FROM ENVIRONMENT)
# -----------------------------------
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
NETLIFY_TOKEN = os.environ.get("NETLIFY_TOKEN")
NETLIFY_SITE_ID = os.environ.get("NETLIFY_SITE_ID")

# Only these IDs can upload; add more later
ALLOWED_USERS = [333686867]

TEMP_DIR = "temp_files"
LOG_FILE = "upload_log.txt"

os.makedirs(TEMP_DIR, exist_ok=True)


# -----------------------------------
# LOGGING
# -----------------------------------
def log_event(text: str):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] {text}\n")
    print(f"[{timestamp}] {text}")


# -----------------------------------
# ZIP + DEPLOY
# -----------------------------------
def create_and_upload_zip():
    zip_name = "deploy.zip"

    xlsx_files = [
        f for f in os.listdir(TEMP_DIR)
        if f.lower().endswith(".xlsx")
    ]

    if not xlsx_files:
        log_event("No XLSX files found for deploy.")
        return False

    with zipfile.ZipFile(zip_name, "w") as zipf:
        for fname in xlsx_files:
            full_path = os.path.join(TEMP_DIR, fname)
            zipf.write(full_path, arcname=fname)

    log_event(f"ZIP created with: {', '.join(xlsx_files)}")

    url = f"https://api.netlify.com/api/v1/sites/{NETLIFY_SITE_ID}/deploys"
    headers = {"Authorization": f"Bearer {NETLIFY_TOKEN}"}
    files = {"file": open(zip_name, "rb")}

    response = requests.post(url, headers=headers, files=files)

    if response.status_code in (200, 201):
        log_event("Netlify deploy SUCCESS.")
        return True

    log_event(f"Netlify deploy FAILED: {response.status_code} - {response.text}")
    return False


# -----------------------------------
# TELEGRAM HANDLER
# -----------------------------------
async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    user_id = user.id
    username = user.username or user.first_name or "Unknown"
    document = update.message.document

    log_event(f"Attempt by {username} (ID {user_id}) file={document.file_name}")

    if user_id not in ALLOWED_USERS:
        await update.message.reply_text("❌ You are not allowed to upload files.")
        log_event("Blocked: unauthorized user.")
        return

    if not document.file_name.lower().endswith(".xlsx"):
        await update.message.reply_text("Please send an .xlsx file.")
        log_event("Rejected: non-xlsx file.")
        return

    # Download to temp folder
    file_path = os.path.join(TEMP_DIR, document.file_name)
    tg_file = await document.get_file()
    await tg_file.download_to_drive(file_path)
    log_event(f"Downloaded: {document.file_name}")

    await update.message.reply_text("Processing file...")
    success = create_and_upload_zip()

    if success:
        await update.message.reply_text("✅ Upload completed successfully.")
    else:
        await update.message.reply_text("❌ Upload failed.")


# -----------------------------------
# MAIN
# -----------------------------------
def main():
    log_event("Bot starting…")
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(MessageHandler(filters.Document.ALL, handle_file))
    app.run_polling()


if __name__ == "__main__":
    main()
