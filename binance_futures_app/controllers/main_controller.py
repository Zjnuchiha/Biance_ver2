import time
import datetime
import logging
from PyQt5.QtWidgets import QApplication, QMessageBox, QTableWidgetItem
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QColor

from config.logging_config import setup_logger
from models import binance_data_singleton
from views.main_view import MainView
from controllers.user_controller import UserController
from controllers.trade_controller import TradeController
from controllers.price_updater import PriceUpdater

from models.binance_client import BinanceClientModel
from models.trade_model import TradeModel
from models.settings_model import SettingsModel

# Tạo logger cho module này
logger = setup_logger(__name__)

class MainController:
    def __init__(self, username, user_data):
        self.username = username
        self.user_data = user_data

        # Khởi tạo BinanceDataModel singleton
        self.data_model = binance_data_singleton.get_instance(
            user_data["api_key"], 
            user_data["api_secret"]
        )

        # Khởi tạo models
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
        # Gán tham chiếu đến main_controller cho trade_controller
        self.trade_controller.main_controller = self

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

            # Kiểm tra nếu API key thay đổi, cập nhật BinanceDataModel
            if (self.user_data["api_key"] != self.binance_client.api_key or 
                self.user_data["api_secret"] != self.binance_client.api_secret):
                
                # Cập nhật BinanceDataModel
                self.data_model.update_api_credentials(
                    self.user_data["api_key"], 
                    self.user_data["api_secret"]
                )
                
                # Cập nhật binance_client
                self.binance_client = BinanceClientModel(
                    self.user_data["api_key"], 
                    self.user_data["api_secret"]
                )
                
                # Khởi động lại price updater
                self.start_price_updater()

    def logout(self):
        """Xử lý đăng xuất tài khoản"""
        reply = self.view.confirm_dialog('Xác nhận đăng xuất', 'Bạn có chắc chắn muốn đăng xuất không?')

        if not reply:
            return

        # Dừng các thread đang chạy
        if self.price_updater:
            self.price_updater.stop()
        
        # Dừng thread cập nhật của BinanceDataModel
        self.data_model.stop_update_thread()

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
        """Bật/tắt chế độ giao dịch tự động an toàn"""
        # Định nghĩa danh sách điều khiển cần quản lý
        controls = [
            self.view.timeframeComboBox,
            self.view.tradingMethodComboBox,  # Combobox phương pháp giao dịch
            self.view.amountSpinBox,
            self.view.leverageSpinBox,
            self.view.stopLossSpinBox,
            self.view.takeProfitSpinBox,
            self.view.symbolComboBox
        ]
        
        # Lưu trữ stylesheet gốc cho các nút nếu chưa có
        if not hasattr(self, '_original_buy_style'):
            self._original_buy_style = "background-color: #00C853; color: white; font-weight: bold; font-size: 14px; padding: 8px;"
        
        if not hasattr(self, '_original_sell_style'):
            self._original_sell_style = "background-color: #FF3D00; color: white; font-weight: bold; font-size: 14px; padding: 8px;"
        
        if state:
            # === BẬT CHẾ ĐỘ GIAO DỊCH TỰ ĐỘNG ===
            if self.binance_client.is_connected():
                # Vô hiệu hóa tất cả controls
                for control in controls:
                    control.setEnabled(False)
                    
                # Xử lý riêng cho nút mua/bán
                self.view.buyButton.setEnabled(False)
                self.view.sellButton.setEnabled(False)
                
                # Chuyển nút mua/bán sang màu xám
                self.view.buyButton.setStyleSheet("background-color: #AAAAAA; color: #FFFFFF; font-weight: bold; font-size: 14px; padding: 8px;")
                self.view.sellButton.setStyleSheet("background-color: #AAAAAA; color: #FFFFFF; font-weight: bold; font-size: 14px; padding: 8px;")
                
                # Lấy thông số giao dịch
                symbol = self.view.symbolComboBox.currentText()
                timeframe = self.view.timeframeComboBox.currentText()
                trading_method = self.view.tradingMethodComboBox.currentText()  # Lấy phương pháp giao dịch
                amount = self.view.amountSpinBox.value()
                leverage = self.view.leverageSpinBox.value()
                stop_loss = self.view.stopLossSpinBox.value()
                
                try:
                    # Bắt đầu giao dịch tự động
                    self.trade_controller.start_auto_trading(symbol, timeframe, amount, leverage, stop_loss, trading_method)
                    self.view.show_message("Giao dịch tự động", f"Đã bật chế độ giao dịch tự động với phương pháp {trading_method}")
                except Exception as e:
                    # Xử lý lỗi khi bật chế độ tự động
                    logger.error(f"Error starting auto trading: {e}")
                    self.view.show_message("Lỗi", f"Không thể bật giao dịch tự động: {e}", QMessageBox.Warning)
                    
                    # Reset lại checkbox
                    self.view.autoTradingCheckBox.setChecked(False)
                    
                    # Kích hoạt lại tất cả controls
                    for control in controls:
                        control.setEnabled(True)
                        
                    # Khôi phục nút mua/bán
                    self.view.buyButton.setEnabled(True)
                    self.view.sellButton.setEnabled(True)
                    self.view.buyButton.setStyleSheet(self._original_buy_style)
                    self.view.sellButton.setStyleSheet(self._original_sell_style)
            else:
                # Không có kết nối Binance
                self.view.show_message("Lỗi", "Không có kết nối Binance", QMessageBox.Warning)
                self.view.autoTradingCheckBox.setChecked(False)
        else:
            # === TẮT CHẾ ĐỘ GIAO DỊCH TỰ ĐỘNG ===
            try:
                # Dừng bot giao dịch tự động
                self.trade_controller.stop_auto_trading()
                
                # Kích hoạt lại tất cả controls
                for control in controls:
                    control.setEnabled(True)
                    
                # Khôi phục nút mua/bán
                self.view.buyButton.setEnabled(True)
                self.view.sellButton.setEnabled(True)
                self.view.buyButton.setStyleSheet(self._original_buy_style)
                self.view.sellButton.setStyleSheet(self._original_sell_style)
                
            except Exception as e:
                # Xử lý lỗi khi tắt chế độ tự động
                logger.error(f"Error stopping auto trading: {e}")
                self.view.show_message("Lỗi", f"Gặp lỗi khi tắt giao dịch tự động: {e}", QMessageBox.Warning)
                
                # Vẫn kích hoạt lại tất cả controls
                for control in controls:
                    control.setEnabled(True)
                    
                # Vẫn khôi phục nút mua/bán
                self.view.buyButton.setEnabled(True)
                self.view.sellButton.setEnabled(True)
                self.view.buyButton.setStyleSheet(self._original_buy_style)
                self.view.sellButton.setStyleSheet(self._original_sell_style)

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
        refresh_interval = user_settings.get("refresh_interval", 10000)
        self.timer.start(refresh_interval)

    def auto_refresh_trades(self):
            """Tự động làm mới dữ liệu giao dịch"""
            self.load_trades()