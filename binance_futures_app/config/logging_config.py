
"""
Module cấu hình logging cho ứng dụng
"""
import os
import logging
import logging.handlers
from logging.handlers import RotatingFileHandlerandlers

def setup_logger(name=None, level=logging.INFO):
    """
    Thiết lập và trả về logger có thể sử dụng ở các module khác
    
    Args:
        name (str, optional): Tên của logger. Nếu None sẽ trả về root logger.
        level (int, optional): Mức log. Mặc định là INFO.
    
    Returns:
        logging.Logger: Logger đã được cấu hình
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # Chỉ thêm handler nếu logger chưa có handler nào
    if not logger.handlers and not logger.parent.handlers:
        # Đảm bảo thư mục logs tồn tại
        log_dir = 'logs'
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
        
        log_file = os.path.join(log_dir, f"{name or 'app'}.log")
        
        # Tạo handlers
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=2*1024*1024,  # 2MB
            backupCount=3,
            encoding='utf-8'
        )
        
        # Tạo console handler với level cao hơn
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.WARNING)
        
        # Tạo formatter
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)
        
        # Thêm handlers vào logger
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
    
    return logger
