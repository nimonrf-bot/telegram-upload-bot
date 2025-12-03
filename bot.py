import os
import zipfile
import hashlib
import requests
from datetime import datetime
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, ContextTypes, filters

# ============ CONFIG FROM RAILWAY ENV =============
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
NETLIFY_TOKEN = os.getenv("NETLIFY_TOKEN")
NETLIFY_SITE_ID = os.getenv("NETLIFY_SITE_ID")
ALLOWED_USERS = os.getenv("ALLOWED_USER_IDS", "")
ALLOWED_USERS = [int(x.strip()) for x in ALLOWED_USERS.split(",") if x.strip().isdigit()]

LOG_FILE = "bot.log"


# ============ LOGGING =============
def log_event(msg: str):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {msg}"
    print(line)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")


# ============ NETLIFY UPLOAD (CORRECT VERSION) ============
def upload_to_netlify(zip_path):
    try:
        # Read ZIP file
        with open(zip_path, "rb") as f:
            content = f.read()

        sha1 = hashlib.sha1(content).hexdigest()

        # 1️⃣ Create deploy
        create_url = f"https://api.netlify.com/api/v1/sites/{NETLIFY_SITE_ID}/deploys"
        headers = {"Authorization": f"Bearer {NETLIFY_TOKEN}"}

        deploy_config = {"files": {"upload.zip": sha1}}

        deploy_resp = requests.post(create_url, headers=headers, json=deploy_config)

        if deploy_resp.status_code not in (200, 201):
            return False, f"Deploy create failed: {deploy_resp.status_code} {deploy_resp.text}"

        deploy_id = deploy_resp.json()["id"]
        log_event(f"Created deploy: {deploy_id}")

        # 2️⃣ Upload file
        upload_url = f"https://api.netlify.com/api/v1/deploys/{deploy_id}/files/upload.zip"
        upload_headers = {
            "Authorization": f"Bearer {NETLIFY_TOKEN}",
            "Content-Type": "application/zip"
        }

        upload_resp = requests.put(upload_url, headers=upload_headers, data=content)

        if upload_resp.status_code not in (200, 201):
            return False, f"Upload failed: {upload_resp.status_code} {upload_resp.text}"

        # 3️⃣ Publish deploy
        publish_url = f"https://api.netlify.com/api/v1/deploys/{deploy_id}/publish"
        publish_resp = requests.post(publish_url, headers=headers)

        if publish_resp.status_code not in (200, 201):
            return False, f"Publish failed: {publish_resp.status_code} {publish_resp.text}"

        return True, "Upload and publish successful"

    except Exception as e:
        return False, str(e)


# ============ TELEGRAM HANDLER ============
async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if user_id not in ALLOWED_USERS:
        log_event(f"Unauthorized access attempt from {user_id}")
        await update.message.reply_text("⛔ You are not allowed.")
        return

    document = update.message.document
    file_name = document.file_name

    log_event(f"File received from {user_id}: {file_name}")

    tg_file = await document.get_file()
    dl_path = f"download_{file_name}"
    await tg_file.download_to_drive(dl_path)

    # ZIP the file
    zip_path = "upload.zip"
    with zipfile.ZipFile(zip_path, "w") as z:
        z.write(dl_path, arcname=file_name)

    log_event(f"Uploading {file_name} to Netlify...")
    ok, msg = upload_to_netlify(zip_path)

    if ok:
        log_event(f"SUCCESS: {file_name}")
        await update.message.reply_text("✅ Upload successful.")
    else:
        log_event(f"FAIL: {file_name} — {msg}")
        await update.message.reply_text("❌ Upload failed.")

    # cleanup local files
    try:
        os.remove(dl_path)
        os.remove(zip_path)
    except:
        pass


# ============ MAIN APP ============
def main():
    log_event("Bot starting…")

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(MessageHandler(filters.Document.ALL, handle_file))

    app.run_polling()


if __name__ == "__main__":
    main()
