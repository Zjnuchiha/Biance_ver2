from PyQt5.QtWidgets import QMessageBox
from binance.um_futures import UMFutures
from binance.error import ClientError

class APIKeyController:
    def __init__(self, view):
        self.view = view
        
        # Kết nối signal
        self.view.test_button.clicked.connect(self.test_connection)
    
    def test_connection(self):
        """Kiểm tra kết nối đến Binance API"""
        api_key = self.view.api_key_input.text()
        api_secret = self.view.api_secret_input.text()
        
        if not api_key or not api_secret:
            QMessageBox.warning(self.view, "Lỗi", "Vui lòng nhập đầy đủ API Key và Secret")
            return
        
        try:
            # Kiểm tra kết nối sử dụng Futures Connector
            client = UMFutures(key=api_key, secret=api_secret)
            
            # Kiểm tra kết nối
            server_time = client.time()
            if 'serverTime' in server_time:
                # Kiểm tra quyền truy cập Futures
                try:
                    account_info = client.account()
                    
                    if 'assets' in account_info:
                        QMessageBox.information(
                            self.view, 
                            "Thành công", 
                            "Kết nối tới Binance Futures thành công!\n"
                            f"Số lượng tài sản: {len(account_info['assets'])}"
                        )
                    else:
                        QMessageBox.warning(
                            self.view, 
                            "Cảnh báo", 
                            "Kết nối thành công nhưng không thể lấy thông tin tài khoản Futures.\n"
                            "Vui lòng đảm bảo API key có quyền truy cập Futures."
                        )
                except ClientError as e:
                    QMessageBox.warning(
                        self.view, 
                        "Cảnh báo", 
                        f"Kết nối thành công nhưng không có quyền Futures: {e}"
                    )
            else:
                QMessageBox.warning(self.view, "Cảnh báo", "Không thể lấy thời gian máy chủ Binance")
                
        except ClientError as e:
            QMessageBox.critical(self.view, "Lỗi", f"Không thể kết nối tới Binance: {e}")
        except Exception as e:
            QMessageBox.critical(self.view, "Lỗi", f"Lỗi không xác định: {e}")