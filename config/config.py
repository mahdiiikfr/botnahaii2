import os

# Telegram Bot Token
BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN")

# Admin IDs list
ADMINS = [123456789, 987654321]  # Update with actual admin telegram IDs

# Database Configuration
DB_FILE = "database/store.db"

# Channel Configuration for Mandatory Join Check (Check Join Middleware)
REQUIRED_CHANNEL = "@my_channel"  # Telegram channel username (with @) or ID (integer)
REQUIRED_CHANNEL_LINK = "https://t.me/my_channel" # Channel link shown to users

# Admin Log Channel ID (where all logs are routed)
ADMIN_LOG_CHANNEL = -1001234567890  # Update with actual channel ID

# ZarinPal Configuration
ZARINPAL_MERCHANT_ID = "22084777-e799-400c-b57d-8a28aa22fadf"
ZARINPAL_CALLBACK_URL = "https://pay2.parslicense.ir"
ZARINPAL_SANDBOX = False  # Set to True for testing, False for production

# Card-to-Card payment info
CARD_NUMBER = "6037-9911-2233-4455"
CARD_HOLDER = "جان اسنو"

# Web server port for ZarinPal callbacks
WEB_PORT = 8080
