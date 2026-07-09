import os

# Create a robust .env parser without external dependencies to avoid environment installation issues
def load_env():
    env_vars = {}
    if os.path.exists(".env"):
        try:
            with open(".env", "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, val = line.split("=", 1)
                        env_vars[key.strip()] = val.strip()
        except Exception:
            pass
    return env_vars

env = load_env()

# Telegram Bot Token
BOT_TOKEN = env.get("BOT_TOKEN", "8933190577:AAEUNcotham2d1UEGA7maE0L4J_41KJFgIo")

# Admin IDs list
ADMINS = [
    int(env.get("ADMIN_ID", "8969258358"))
]

# Database Configuration
DB_FILE = env.get("DB_FILE", "database/store.db")

# Channel Configuration for Mandatory Join Check (Check Join Middleware)
REQUIRED_CHANNEL = env.get("REQUIRED_CHANNEL", "@applevpnio")  # Telegram channel username or ID
REQUIRED_CHANNEL_LINK = env.get("REQUIRED_CHANNEL_LINK", "https://t.me/applevpnio") # Channel link

# Admin Log/Backup Channel ID (where all logs are routed)
ADMIN_LOG_CHANNEL = int(env.get("BACKUP_CHANNEL_ID", "-1004307401227"))

# ZarinPal Configuration
ZARINPAL_MERCHANT_ID = env.get("ZARINPAL_MERCHANT", "22084777-e799-400c-b57d-8a28aa22fadf")
ZARINPAL_CALLBACK_URL = env.get("WEB_URL", "http://pay2.parslicense.ir:8080")
ZARINPAL_SANDBOX = False

# Card-to-Card payment info
CARD_NUMBER = env.get("CARD_NUMBER", "6219861913428198")
CARD_HOLDER = env.get("CARD_HOLDER", "پشتیبانی")

# Web server port for ZarinPal callbacks
WEB_PORT = int(env.get("WEB_PORT", "8080"))

# Throttling click and messaging limit
THROTTLING_RATE_LIMIT = float(env.get("THROTTLING_RATE_LIMIT", "0.8"))
