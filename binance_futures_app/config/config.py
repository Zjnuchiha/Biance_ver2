import os

# Thông tin ứng dụng
APP_NAME = "Binance Futures Trading"
APP_VERSION = "1.0.3"
APP_AUTHOR = "Zjn_AnhTu"

# Đường dẫn
APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(APP_DIR, "data")
ICONS_DIR = os.path.join(APP_DIR, "resources", "icons")
UI_DIR = os.path.join(APP_DIR, "views", "ui")

# File dữ liệu
USERS_FILE = os.path.join(DATA_DIR, "users.json")
TRADES_FILE = os.path.join(DATA_DIR, "trades.json")
SETTINGS_FILE = os.path.join(DATA_DIR, "settings.json")

# SQLite Database path
DATABASE_PATH = os.path.join(DATA_DIR, "binance_app.db")

# Đảm bảo các thư mục tồn tại
for directory in [DATA_DIR, ICONS_DIR, UI_DIR]:
    if not os.path.exists(directory):
        os.makedirs(directory)