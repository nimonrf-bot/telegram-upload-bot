import os
import logging
import requests
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, ContextTypes, filters

# --------------------------------------------------------
# Logging setup
# --------------------------------------------------------
logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

print("[BOT] Starting...")

# --------------------------------------------------------
# Load environment variables (Railway)
# --------------------------------------------------------
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
NETLIFY_TOKEN = os.getenv("NETLIFY_TOKEN")
NETLIFY_SITE_ID = os.getenv("NETLIFY_SITE_ID")
ALLOWED_USERS = os.getenv("ALLOWED_USERS", "")

# Allowed users: "12345,67890"
ALLOWED_USERS = {int(uid.strip()) for uid in ALLOWED_USERS.split(",") if uid.strip().isdigit()}

# --------------------------------------------------------
# Upload to Netlify (FINAL WORKING VERSION)
# --------------------------------------------------------
def upload_to_netlify(file_path, filename):
    try:
        # STEP 1 — Create deploy request
        create_url = f"https://api.netlify.com/api/v1/sites/{NETLIFY_SITE_ID}/deploys?trigger_branch=main"
        headers = {"Authorization": f"Bearer {NETLIFY_TOKEN}"}

        logging.info("[UPLOAD] Creating deploy...")
        create_resp = requests.post(create_url, headers=headers)

        if create_resp.status_code != 200:
            logging.error("Deploy create failed: %s %s", create_resp.status_code, create_resp.text)
            return None, f"Deploy create failed: {create_resp.status_code}"

        deploy_id = create_resp.json()["id"]
        logging.info("[UPLOAD] Deploy created: %s", deploy_id)

        # STEP 2 — Upload the file
        upload_url = f"https://api.netlify.com/api/v1/deploys/{deploy_id}/files/{filename}"

        with open(file_path, "rb") as f:
            upload_resp = requests.put(upload_url, headers=headers, data=f)

        if upload_resp.status_code not in (200, 201):
            logging.error("File upload failed: %s %s", upload_resp.status_code, upload_resp.text)
            return None, f"File upload failed: {upload_resp.status_code} {upload_resp.text}"

        logging.info("[UPLOAD] File uploaded OK")

        # STEP 3 — Publish deploy
        publish_url = f"https://api.netlify.com/api/v1/deploys/{deploy_id}/restore"
        publish_resp = requests.post(publish_url, headers=headers)

        if publish_resp.status_code != 200:
            logging.error("Publish failed: %s %s", publish_resp.status_code, publish_resp.text)
            return None, f"Publish failed: {publish_resp.status_code} {publish_resp.text}"

        logging.info("[UPLOAD] Publish OK")

        # STEP 4 — Construct final URL
        safe_filename = filename.replace(" ", "%20")
        final_url = f"https://main--glistening-heliotrope-8f80fd.netlify.app/{safe_filename}"

        return final_url, None

    except Exception as e:
        logging.exception("Unexpected error")
        return None, str(e)


# --------------------------------------------------------
# Telegram: handle incoming documents
# --------------------------------------------------------
async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    filename = update.message.document.file_name

    # Security check
    if user_id not in ALLOWED_USERS:
        msg = f"Unauthorized user: {user_id}"
        logging.warning("[SECURITY] " + msg)
        await update.message.reply_text("❌ You are not allowed to upload.")
        return

    logging.info("[BOT] File received from %s: %s", user_id, filename)

    # Download the file
    file = await update.message.document.get_file()
    await file.download_to_drive(filename)

    logging.info("[BOT] Uploading %s to Netlify...", filename)

    final_url, error = upload_to_netlify(filename, filename)

    if error:
        logging.error("[BOT] Upload failed: %s", error)
        await update.message.reply_text(f"❌ Upload failed:\n{error}")
    else:
        logging.info("[BOT] Upload successful!")
        await update.message.reply_text(f"✅ Uploaded successfully:\n{final_url}")


# --------------------------------------------------------
# Main Bot Runner
# --------------------------------------------------------
def main():
    application = (
        ApplicationBuilder()
        .token(TELEGRAM_TOKEN)
        .concurrent_updates(True)
        .build()
    )

    application.add_handler(MessageHandler(filters.Document.ALL, handle_document))

    print("[BOT] Running polling...")
    application.run_polling()


if __name__ == "__main__":
    main()
