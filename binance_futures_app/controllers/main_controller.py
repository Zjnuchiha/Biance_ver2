from PyQt5.QtWidgets import QApplication, QMessageBox, QTableWidgetItem
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QColor

import time
import datetime
import logging
from config.logging_config import setup_logger

# Tạo logger cho module này
logger = setup_logger(__name__)

from views.main_view import MainView
from controllers.user_controller import UserController
from controllers.trade_controller import TradeController
from controllers.price_updater import PriceUpdater

from models.binance_client import BinanceClientModel
from models.trade_model import TradeModel
from models.settings_model import SettingsModel

class MainController:
    def __init__(self, username, user_data):
        self.username = username
        self.user_data = user_data

        # Khởi tạo models
        logger.info(f"Initialization BinanceClientModel with API key: {'*****' if user_data['api_key'] else 'does not exist'}")
        self.binance_client = BinanceClientModel(user_data["api_key"], user_data["api_secret"])
        self.trade_model = TradeModel()
        self.settings_model = SettingsModel()

        # Kiểm tra kết nối
        if self.binance_client.is_connected():
            logger.info("Successfully connected to Binance API")
        else:
            logger.warning("Connection failed to Binance API")

        # Khởi tạo view
        self.view = MainView(username)

        # Khởi tạo biến theo dõi
        self.current_price = 0.0
        self.refresh_timer = time.time()

        # Thiết lập controller
        self.setup_controllers()
        self.connect_signals()
        self.setup_auto_refresh()

        # Tải dữ liệu ban đầu
        symbol = self.view.symbolComboBox.currentText()
        self.view.load_chart(symbol)
        self.load_trades()

        # Bắt đầu cập nhật giá và số dư
        self.start_price_updater()

    def setup_controllers(self):
        """Thiết lập các controllers phụ"""
        self.trade_controller = TradeController(self.view, self.binance_client, self.trade_model, self.username)
        self.price_updater = None

    def connect_signals(self):
        """Kết nối các signals"""
        self.view.userButton.clicked.connect(self.open_user_management)
        self.view.logoutButton.clicked.connect(self.logout)
        self.view.symbolComboBox.currentTextChanged.connect(self.change_symbol)
        self.view.autoTradingCheckBox.stateChanged.connect(self.toggle_auto_trading)
        self.view.buyButton.clicked.connect(lambda: self.trade_controller.place_order("BUY"))
        self.view.sellButton.clicked.connect(lambda: self.trade_controller.place_order("SELL"))
        self.view.filterComboBox.currentTextChanged.connect(self.filter_trades)

    def show(self):
        """Hiển thị giao diện chính"""
        self.view.show()

    def open_user_management(self):
        """Mở dialog quản lý tài khoản"""
        user_controller = UserController(self.username, self.user_data)
        result = user_controller.show_dialog()

        if result:
            # Cập nhật thông tin người dùng nếu có thay đổi
            self.user_data = user_controller.get_updated_user_data()

            # Kiểm tra nếu API key thay đổi, khởi tạo lại binance client
            if (self.user_data["api_key"] != self.binance_client.api_key or 
                self.user_data["api_secret"] != self.binance_client.api_secret):
                self.binance_client = BinanceClientModel(
                    self.user_data["api_key"], 
                    self.user_data["api_secret"]
                )
                self.start_price_updater()

    def logout(self):
        """Xử lý đăng xuất tài khoản"""
        reply = self.view.confirm_dialog('Xác nhận đăng xuất', 'Bạn có chắc chắn muốn đăng xuất không?')

        if not reply:
            return

        # Dừng các thread đang chạy
        if self.price_updater:
            self.price_updater.stop()

        # Mở cửa sổ đăng nhập mới
        from controllers.login_controller import LoginController
        self.login_controller = LoginController()
        self.login_controller.show()
        self.view.close()

    def change_symbol(self, symbol):
        """Xử lý khi thay đổi cặp giao dịch"""
        # Cập nhật biểu đồ
        self.view.load_chart(symbol)

        # Cập nhật updater giá
        self.start_price_updater()

        # Cập nhật thông báo trạng thái
        self.view.statusbar.showMessage(f"Đã chuyển sang cặp giao dịch {symbol}", 3000)

    def start_price_updater(self):
        """Bắt đầu cập nhật giá và số dư"""
        if self.binance_client.is_connected():
            symbol = self.view.symbolComboBox.currentText()

            # Dừng updater hiện tại nếu có
            if self.price_updater:
                self.price_updater.stop()

            # Khởi tạo và bắt đầu updater mới
            self.price_updater = PriceUpdater(self.binance_client, symbol)
            self.price_updater.price_update.connect(self.update_price)
            self.price_updater.balance_update.connect(self.update_balance)
            self.price_updater.error_signal.connect(self.display_error)
            self.price_updater.start()

    def display_error(self, error_msg):
        """Hiển thị thông báo lỗi"""
        self.view.statusbar.showMessage(error_msg, 5000)

    def update_price(self, price):
        """Cập nhật giá hiện tại"""
        # Lưu giá hiện tại vào biến của lớp
        self.current_price = float(price)

        # Cập nhật hiển thị giá
        symbol = self.view.symbolComboBox.currentText()
        self.view.update_price_display(price, symbol)

        # Cập nhật dữ liệu giao dịch định kỳ
        current_time = time.time()
        if current_time - self.refresh_timer > 60:
            self.load_trades()
            self.refresh_timer = current_time

    def update_balance(self, balances):
        """Cập nhật thông tin số dư"""
        symbol = self.view.symbolComboBox.currentText()
        self.view.update_balance_display(balances, symbol)

    def toggle_auto_trading(self, state):
        """Bật/tắt chế độ giao dịch tự động"""
        # Bật/tắt các điều khiển
        controls = [
            self.view.timeframeComboBox,
            self.view.amountSpinBox,
            self.view.leverageSpinBox,
            self.view.stopLossSpinBox,
            self.view.buyButton,
            self.view.sellButton,
            self.view.symbolComboBox
        ]

        for control in controls:
            control.setEnabled(not state)

        if state:
            # Bật giao dịch tự động
            if self.binance_client.is_connected():
                symbol = self.view.symbolComboBox.currentText()
                timeframe = self.view.timeframeComboBox.currentText()
                amount = self.view.amountSpinBox.value()
                leverage = self.view.leverageSpinBox.value()
                stop_loss = self.view.stopLossSpinBox.value()

                self.trade_controller.start_auto_trading(symbol, timeframe, amount, leverage, stop_loss)

                self.view.show_message("Giao dịch tự động", "Đã bật chế độ giao dịch tự động")
            else:
                self.view.show_message("Lỗi", "Không có kết nối Binance", QMessageBox.Warning)
                self.view.autoTradingCheckBox.setChecked(False)
        else:
            # Tắt giao dịch tự động
            self.trade_controller.stop_auto_trading()
            self.view.show_message("Giao dịch tự động", "Đã tắt chế độ giao dịch tự động")

    def load_trades(self):
        """Tải lịch sử giao dịch - Chỉ lấy ID từ local DB và tải thông tin chi tiết từ Binance"""
        try:
            # Lấy thông tin IDs giao dịch từ cơ sở dữ liệu
            local_trades = self.trade_model.get_user_trades(self.username)

            # Nạp dữ liệu chi tiết từ Binance
            all_trades = []
            if self.binance_client.is_connected():
                try:
                    # Lấy tất cả vị thế và giao dịch hiện tại từ Binance 
                    binance_trades = self.trade_controller.get_binance_trades()

                    # Tạo từ điển tra cứu nhanh cho các giao dịch Binance dựa trên ID
                    binance_trades_dict = {str(trade.get('id')): trade for trade in binance_trades}

                    # Cập nhật thông tin chi tiết cho từng ID giao dịch local
                    for local_trade in local_trades:
                        trade_id = str(local_trade.get('id', ''))

                        # Nếu có thông tin chi tiết từ Binance, sử dụng nó
                        if trade_id in binance_trades_dict:
                            # Bổ sung thông tin từ local vào thông tin Binance
                            binance_trade = binance_trades_dict[trade_id].copy()
                            # Giữ lại timestamp và source từ local nếu có
                            if 'timestamp' in local_trade and local_trade['timestamp']:
                                binance_trade['timestamp'] = local_trade['timestamp']
                            if 'source' in local_trade and local_trade['source']:
                                binance_trade['source'] = local_trade['source']

                            all_trades.append(binance_trade)
                            # Đánh dấu đã sử dụng
                            del binance_trades_dict[trade_id]
                        else:
                            # Nếu không có thông tin chi tiết, dùng thông tin cơ bản từ local
                            all_trades.append(local_trade)

                    # Thêm các giao dịch từ Binance không có trong local
                    all_trades.extend(binance_trades_dict.values())

                except Exception as e:
                    logging.error(f"Lỗi khi tải dữ liệu giao dịch từ Binance: {e}")
                    # Nếu lỗi, hiển thị dữ liệu local
                    all_trades = local_trades
            else:
                # Không có kết nối Binance, chỉ hiển thị dữ liệu local
                all_trades = local_trades

            # Hiển thị lên bảng
            self.view.update_trades_table(all_trades)

            # Cập nhật lại thời gian làm mới
            self.refresh_timer = time.time()

        except Exception as e:
            logging.error(f"Lỗi khi tải dữ liệu giao dịch: {e}")

    def filter_trades(self, filter_text):
        """Lọc bảng giao dịch"""
        self.view.filter_trades(filter_text)

    def setup_auto_refresh(self):
        """Thiết lập tự động làm mới dữ liệu"""
        self.timer = QTimer()
        self.timer.timeout.connect(self.auto_refresh_trades)

        # Lấy cài đặt thời gian làm mới từ settings_model
        # Thời gian làm mới cửa sổ lệnh là 15s
        user_settings = self.settings_model.get_user_settings(self.username)
        refresh_interval = user_settings.get("refresh_interval", 15000)
        self.timer.start(refresh_interval)

    def auto_refresh_trades(self):
        """Tự động làm mới dữ liệu giao dịch"""
        self.load_trades()

    def setup_controllers(self):
        """Thiết lập các controllers phụ"""
        self.trade_controller = TradeController(self.view, self.binance_client, self.trade_model, self.username)
        # Gán tham chiếu đến main_controller cho trade_controller
        self.trade_controller.main_controller = self
        self.price_updater = None