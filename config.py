import os
from dotenv import load_dotenv, find_dotenv

# Ensure .env is loaded reliably regardless of current working directory
_dotenv_path = os.getenv('DOTENV_PATH') or find_dotenv(usecwd=True) or os.path.join(os.path.dirname(__file__), '.env')
if _dotenv_path:
    load_dotenv(dotenv_path=_dotenv_path)
else:
    load_dotenv()

# Telegram
BOT_TOKEN = os.getenv('BOT_TOKEN')
# Handle multiple admin IDs
admin_ids_str = os.getenv('ADMIN_ID', '')
if admin_ids_str:
    ADMIN_IDS = [int(id.strip()) for id in admin_ids_str.split(',')]
    ADMIN_ID = ADMIN_IDS[0]  # Keep first one for backward compatibility
else:
    ADMIN_IDS = []
    ADMIN_ID = None

# Payme
PAYME_MERCHANT_ID = os.getenv('PAYME_MERCHANT_ID')
PAYME_SECRET_KEY = os.getenv('PAYME_SECRET_KEY')
PAYME_CALLBACK_PATH = os.getenv('PAYME_CALLBACK_PATH', '/payme-callback')

# Рабочее время
WORK_START_HOUR = int(os.getenv('WORK_START_HOUR', '1'))
WORK_END_HOUR   = int(os.getenv('WORK_END_HOUR',   '23'))

# Data files
BASE_DIR = os.path.dirname(__file__)
DATA_DIR = os.path.join(BASE_DIR, 'data')
REVIEWS_FILE     = os.path.join(DATA_DIR, 'reviews.json')
AVAILABILITY_FILE = os.path.join(DATA_DIR, 'availability.json')
ORDERS_DB        = os.path.join(DATA_DIR, 'orders.json')

# MongoDB (support both MONGO_URI and MONGODB_URI)
MONGO_URI = os.getenv('MONGO_URI') or os.getenv('MONGODB_URI')
MONGO_DB_NAME = os.getenv('MONGO_DB_NAME', 'samsariya')
MONGO_COLLECTION_ORDERS = os.getenv('MONGO_COLLECTION_ORDERS', 'orders')
MONGO_COLLECTION_REVIEWS = os.getenv('MONGO_COLLECTION_REVIEWS', 'reviews')
MONGO_COLLECTION_AVAILABILITY = os.getenv('MONGO_COLLECTION_AVAILABILITY', 'availability')
MONGO_COLLECTION_PRODUCTS = os.getenv('MONGO_COLLECTION_PRODUCTS', 'inventory')
MONGO_COLLECTION_NOTIFICATIONS = os.getenv('MONGO_COLLECTION_NOTIFICATIONS', 'notifications')
MONGO_COLLECTION_TEMP_CARTS = os.getenv('MONGO_COLLECTION_TEMP_CARTS', 'temp_carts')

# Business information
BUSINESS_NAME = "Самсария"
BUSINESS_ADDRESS = "г. Ташкент, Мирзо-Улугбекский район, улица Аккурган, дом 23А"
BUSINESS_LANDMARK = "ориентир - стадион \"Старт\" Новомосковская"
BUSINESS_LATITUDE = 41.3267486726436  # Replace with your exact coordinates for Аккурган, 23А
BUSINESS_LONGITUDE = 69.3030988958  # Replace with your exact coordinates for Аккурган, 23А
BUSINESS_PHONE_MAIN = "+998880009099"
BUSINESS_PHONE_EXTRA = "+998935191337"
BUSINESS_TELEGRAM = "@samsariya_tas_bot"
BUSINESS_HOURS = "09:00 - 17:00"
DELIVERY_AREA = "по всему Ташкенту"