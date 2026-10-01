import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN") or ""

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

DB_PATH = str((DATA_DIR / "tempmail.db").resolve())

# Mail.tm API Base URL
MAIL_API_BASE = "https://api.mail.tm"

# Check interval in seconds for background email monitoring
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL", "4"))

# Admin / Owner Telegram IDs
raw_admins = os.getenv("ADMIN_IDS", "6566593716,7201755273,5303362533")
ADMIN_IDS = [int(x.strip()) for x in raw_admins.split(",") if x.strip().isdigit()]

# Referral & Credit settings: 1 Credit = 1 Mail
START_CREDITS = int(os.getenv("START_CREDITS", "1"))
START_MAIL_QUOTA = int(os.getenv("START_MAIL_QUOTA", "1"))
CREDITS_PER_REFERRAL = int(os.getenv("CREDITS_PER_REFERRAL", "1"))
MAILS_PER_CREDIT = int(os.getenv("MAILS_PER_CREDIT", "1"))

BOT_USERNAME = os.getenv("BOT_USERNAME", "TempMailloginBot")

