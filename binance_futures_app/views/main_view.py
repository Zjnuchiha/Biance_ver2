from PyQt5.QtWidgets import QMainWindow, QHeaderView, QLabel, QMessageBox, QTableWidgetItem, QPushButton, QDoubleSpinBox
from PyQt5.QtCore import Qt, QUrl
from PyQt5.QtGui import QIcon, QColor
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5 import uic
from PyQt5.QtCore import pyqtSignal
import os
import logging
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.config import UI_DIR, ICONS_DIR

class MainView(QMainWindow):
    close_position_signal = pyqtSignal(str, str, str)  # trade_id, symbol, side
    def __init__(self, username):
        super().__init__()
        # Nạp file UI trực tiếp
        uic.loadUi(os.path.join(UI_DIR, 'main_window.ui'), self)

        # Thiết lập kích thước tối thiểu lớn hơn
        self.setMinimumSize(1800, 1000)

        # Thiết lập tiêu đề và icon
        self.setWindowTitle(f"Binance Futures Trading - {username}")
        try:
            self.setWindowIcon(QIcon(os.path.join(ICONS_DIR, "app_icon.png")))
        except:
            pass

        # Cấu hình tiêu đề và nút người dùng
        self.userButton.setText(username)
        # Đảm bảo nút đăng xuất hiển thị
        self.logoutButton.setVisible(True)

        self.setup_ui()

    def setup_ui(self):
        """Thiết lập các thành phần UI"""
        # Tạo label hiển thị trạng thái giao dịch tự động
        self.auto_trading_status = QLabel("Giao dịch tự động: Đã tắt")
        self.verticalLayout_2.addWidget(self.auto_trading_status)
        # Thiết lập header cho bảng giao dịch
        self.tradeTable.setColumnCount(12)
        self.tradeTable.setHorizontalHeaderLabels([
        "ID", "Cặp giao dịch", "Loại", "Giá", "Số lượng", "Thời gian", 
        "Lời/Lỗ", "Nguồn", "Loại lệnh", "Stop Loss", "Take Profit", "Trạng thái"
        ])
        # Điều chỉnh hình dạng của header
        header = self.tradeTable.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)  # ID
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)  # Cặp giao dịch
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)  # Loại
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)  # Giá
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)  # Số lượng
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)  # Thời gian
        header.setSectionResizeMode(6, QHeaderView.ResizeToContents)  # Lời/Lỗ
        header.setSectionResizeMode(7, QHeaderView.ResizeToContents)  # Nguồn
        header.setSectionResizeMode(8, QHeaderView.ResizeToContents)  # Loại lệnh
        header.setSectionResizeMode(9, QHeaderView.ResizeToContents)  # Stop Loss
        header.setSectionResizeMode(10, QHeaderView.ResizeToContents)  # Take Profit
        header.setSectionResizeMode(11, QHeaderView.ResizeToContents)  # Trạng thái

        # Tạo QWebEngineView cho biểu đồ
        self.chart_view = QWebEngineView()

        # Cấu hình WebEngineView với kích thước lớn hơn
        self.chart_view.setMinimumSize(1100, 750)  # Tăng kích thước để hiển thị đầy đủ

        # Bỏ qua lỗi CSP từ Binance
        profile = self.chart_view.page().profile()
        settings = self.chart_view.settings()
        settings.setAttribute(settings.WebAttribute.JavascriptCanAccessClipboard, True)
        settings.setAttribute(settings.WebAttribute.LocalContentCanAccessRemoteUrls, True)

        # Thêm vào container
        self.chartContainer.addWidget(self.chart_view)

        # Thêm các cặp giao dịch phổ biến
        popular_symbols = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "ADAUSDT", "DOGEUSDT", "XRPUSDT", 
                      "SOLUSDT", "AVAXUSDT", "DOTUSDT", "MATICUSDT", "LINKUSDT"]
        self.symbolComboBox.addItems(popular_symbols)

        # Thêm các khung thời gian
        self.timeframeComboBox.addItems(["1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "1d"])

        # URL cho biểu đồ Binance Futures
        self.binance_futures_chart_url = "https://www.binance.com/en/futures/{symbol}"

    def update_price_display(self, price, symbol):
        """Cập nhật hiển thị giá"""
        # Cập nhật tiêu đề cửa sổ
        self.setWindowTitle(f"Binance Futures Trading - {symbol}: {price}")

        # Cập nhật thanh trạng thái
        self.statusbar.showMessage(f"Giá hiện tại: {price}", 3000)

    def update_balance_display(self, balances, symbol):
        """Cập nhật hiển thị số dư"""
        try:
            # Lấy base asset từ symbol
            base_asset = symbol.replace('USDT', '')

            # Chuẩn bị thông tin hiển thị
            balance_html = "<div style='margin: 2px;'>"

            # Hiển thị số dư USDT (quan trọng nhất trong Futures)
            if 'USDT' in balances:
                usdt_data = balances['USDT']
                usdt_balance = usdt_data['wallet_balance']
                usdt_pnl = usdt_data['unrealized_pnl']
                usdt_available = usdt_data['available_balance']

                # Định dạng số dư với bố cục tốt hơn
                balance_html += f"<b>USDT:</b> {usdt_balance:.2f}<br>"
                balance_html += f"<small>Khả dụng: {usdt_available:.2f}</small>"

                # Hiển thị lãi/lỗ nếu có
                if usdt_pnl != 0:
                    pnl_color = "green" if usdt_pnl > 0 else "red"
                    balance_html += f"<br><span style='color:{pnl_color};'><b>PnL:</b> {usdt_pnl:.2f}</span>"
            else:
                # Hiển thị tổng số dư USDT nếu có
                if 'total_usdt' in balances:
                    balance_html += f"<b>USDT:</b> {balances['total_usdt']:.2f}"

            # Hiển thị số dư của base asset nếu có
            if base_asset in balances:
                asset_data = balances[base_asset]
                asset_balance = asset_data['wallet_balance']

                # Thêm thông tin base asset
                balance_html += f"<br><b>{base_asset}:</b> {asset_balance}"

            balance_html += "</div>"

            # Nếu không có thông tin số dư
            if balance_html == "<div style='margin: 2px;'></div>":
                balance_html = "<div>Không có số dư</div>"

            # Cập nhật UI
            self.balanceValueLabel.setText(balance_html)
            self.balanceValueLabel.setTextFormat(Qt.RichText)

        except Exception as e:
            self.balanceValueLabel.setText("<div style='color:red'>Lỗi khi cập nhật số dư</div>")

        except Exception as e:
            print(f"Lỗi khi cập nhật số dư: {e}")

    def update_trades_table(self, trades_data):
        """Cập nhật bảng giao dịch"""
        # Xóa dữ liệu hiện tại
        self.tradeTable.setRowCount(0)

        # Duyệt qua danh sách giao dịch và thêm vào bảng
        for i, trade in enumerate(trades_data):
            self.tradeTable.insertRow(i)

            # Thêm dữ liệu vào bảng
            self.tradeTable.setItem(i, 0, QTableWidgetItem(str(trade["id"])))
            self.tradeTable.setItem(i, 1, QTableWidgetItem(trade["symbol"]))

            side_item = QTableWidgetItem(trade["side"])
            if trade["side"] == "BUY":
                side_item.setForeground(QColor(0, 200, 83))  # Xanh lá
            else:
                side_item.setForeground(QColor(255, 61, 0))  # Đỏ
            self.tradeTable.setItem(i, 2, side_item)

            self.tradeTable.setItem(i, 3, QTableWidgetItem(str(trade["price"])))
            self.tradeTable.setItem(i, 4, QTableWidgetItem(str(trade["quantity"])))
            # Hiển thị entry_time thay vì timestamp
            entry_time = trade.get("entry_time", trade.get("timestamp", ""))
            self.tradeTable.setItem(i, 5, QTableWidgetItem(entry_time))

            pnl_item = QTableWidgetItem(f"{trade.get('pnl', 0):.2f}")
            if trade.get("pnl", 0) > 0:
                pnl_item.setForeground(QColor(0, 200, 83))  # Xanh lá
            elif trade.get("pnl", 0) < 0:
                pnl_item.setForeground(QColor(255, 61, 0))  # Đỏ
            self.tradeTable.setItem(i, 6, pnl_item)

            # Nguồn lệnh
            source = trade.get("source", "Ứng dụng")
            source_item = QTableWidgetItem(source)
            source_color = QColor(0, 120, 215) if source == "Ứng dụng" else QColor(245, 158, 11)
            source_item.setForeground(source_color)
            self.tradeTable.setItem(i, 7, source_item)

            # Loại lệnh
            order_type = trade.get("order_type", "Đã đóng" if trade["status"] == "FILLED" else "Đang mở")
            type_item = QTableWidgetItem(order_type)
            if order_type == "Đang mở":
                type_item.setForeground(QColor(255, 153, 0))  # Cam
            else:
                type_item.setForeground(QColor(128, 128, 128))  # Xám
            self.tradeTable.setItem(i, 8, type_item)

            # Stop Loss và Take Profit
            sl_value = trade.get("stop_loss", "")
            tp_value = trade.get("take_profit", "")
            logging.debug(f"Show order trade with ID {trade.get('id', 'N/A')}, SL: {sl_value}, TP: {tp_value}")

            # Hiển thị giá trị thực, không thêm dấu phần trăm
            sl_item = QTableWidgetItem(f"{sl_value}" if sl_value else "")
            tp_item = QTableWidgetItem(f"{tp_value}" if tp_value else "")

            # Thêm màu sắc để dễ nhận biết
            if sl_value:
                sl_item.setForeground(QColor(255, 0, 0))  # Đỏ
            if tp_value:
                tp_item.setForeground(QColor(0, 255, 0))  # Xanh lá

            self.tradeTable.setItem(i, 9, sl_item)
            self.tradeTable.setItem(i, 10, tp_item)
            status = trade.get("status", "")

            # Nếu là "Đang mở", hiển thị nút đóng vị thế
            if order_type == "Đang mở":
                close_button = QPushButton("Đóng vị thế")
                close_button.setStyleSheet("background-color: #E74C3C; color: white;")
                # Lưu thông tin trade vào button để sử dụng khi click
                close_button.setProperty("trade_id", trade["id"])
                close_button.setProperty("symbol", trade["symbol"])
                close_button.setProperty("side", trade["side"])
                close_button.clicked.connect(self.on_close_position_clicked)
                self.tradeTable.setCellWidget(i, 11, close_button)
            else:
                status_item = QTableWidgetItem(status)
                self.tradeTable.setItem(i, 11, status_item)

    def update_summary(self, total_profit, win_rate, update_time):
        """Cập nhật thông tin tổng kết"""
        self.totalProfitLabel.setText(f"Tổng lợi nhuận: {total_profit:.2f} USDT")

        # Thiết lập màu sắc
        if total_profit > 0:
            self.totalProfitLabel.setStyleSheet("color: #00C853; font-weight: bold;")
        elif total_profit < 0:
            self.totalProfitLabel.setStyleSheet("color: #FF3D00; font-weight: bold;")

        self.winRateLabel.setText(f"Tỷ lệ thắng: {win_rate:.2f}%")
        self.lastUpdateLabel.setText(f"Cập nhật lần cuối: {update_time}")

    def filter_trades(self, filter_text):
        """Lọc bảng giao dịch"""
        for row in range(self.tradeTable.rowCount()):
            show_row = True

            if filter_text == "Đang mở":
                # Kiểm tra cột "Loại lệnh" (cột 8)
                type_item = self.tradeTable.item(row, 8)
                if type_item and type_item.text() != "Đang mở":
                    show_row = False

            elif filter_text == "Đã đóng":
                # Kiểm tra cột "Loại lệnh" (cột 8)
                type_item = self.tradeTable.item(row, 8)
                if type_item and type_item.text() != "Đã đóng":
                    show_row = False

            elif filter_text == "Ứng dụng":
                # Kiểm tra cột "Nguồn" (cột 7)
                source_item = self.tradeTable.item(row, 7)
                if source_item and source_item.text() != "Ứng dụng":
                    show_row = False

            elif filter_text == "Binance":
                # Kiểm tra cột "Nguồn" (cột 7)
                source_item = self.tradeTable.item(row, 7)
                if source_item and source_item.text() != "Binance":
                    show_row = False

            self.tradeTable.setRowHidden(row, not show_row)

    def load_chart(self, symbol):
        """Tải biểu đồ cho cặp giao dịch"""
        chart_url = self.binance_futures_chart_url.format(symbol=symbol)
        self.statusbar.showMessage(f"Đang tải biểu đồ Binance Futures: {chart_url}", 3000)
        self.chart_view.load(QUrl(chart_url))

    def show_message(self, title, message, icon=QMessageBox.Information):
        """Hiển thị thông báo"""
        # Sử dụng phương thức phù hợp theo loại icon
        if icon == QMessageBox.Warning:
            QMessageBox.warning(self, title, message)
        elif icon == QMessageBox.Critical:
            QMessageBox.critical(self, title, message)
        elif icon == QMessageBox.Question:
            QMessageBox.question(self, title, message)
        else:  # Mặc định là Information
            QMessageBox.information(self, title, message)

    def confirm_dialog(self, title, message):
        """Hiển thị hộp thoại xác nhận"""
        reply = QMessageBox.question(
            self, 
            title,
            message,
            QMessageBox.Yes | QMessageBox.No, 
            QMessageBox.No
        )

        return reply == QMessageBox.Yes
    def on_close_position_clicked(self):
        """Xử lý khi nút đóng vị thế được nhấn"""
        button = self.sender()
        if button:
            trade_id = button.property("trade_id")
            symbol = button.property("symbol")
            side = button.property("side")

            logging.info(f"Close position button clicked for: ID={trade_id}, Symbol={symbol}, Side={side}")

            # Hiển thị dialog xác nhận
            confirm = self.confirm_dialog(
                'Xác nhận đóng vị thế', 
                f'Bạn có chắc chắn muốn đóng vị thế {symbol} ({side}) không?'
            )

            if confirm:
                # Gửi tín hiệu đóng vị thế với các tham số cụ thể
                self.close_position_signal.emit(str(trade_id), symbol, side)
                logging.info(f"Emitted close_position_signal for: ID={trade_id}, Symbol={symbol}, Side={side}")

        # Spin box cho Stop Loss (giá trị thực, không phải %)
        self.stopLossSpinBox = QDoubleSpinBox(self)
        self.stopLossSpinBox.setMaximum(1000000.0)
        self.stopLossSpinBox.setDecimals(2)
        self.stopLossSpinBox.setValue(0.0)  # Mặc định là 0
        self.stopLossSpinBox.setSpecialValueText("")  # Khi giá trị = 0, hiển thị trống
        self.stopLossSpinBox.setSuffix("")  # Xóa ký hiệu phần trăm

        # Spin box cho Take Profit (giá trị thực, không phải %)
        self.takeProfitSpinBox = QDoubleSpinBox(self)
        self.takeProfitSpinBox.setMaximum(1000000.0)
        self.takeProfitSpinBox.setDecimals(2)
        self.takeProfitSpinBox.setValue(0.0)  # Mặc định là 0
        self.takeProfitSpinBox.setSpecialValueText("")  # Khi giá trị = 0, hiển thị trống
        self.takeProfitSpinBox.setSuffix("")  # Xóa ký hiệu phần trăm