"""
Module này cung cấp một instance singleton của BinanceDataModel
để đảm bảo toàn bộ ứng dụng chỉ sử dụng một instance duy nhất.
"""

from models.binance_data_model import BinanceDataModel

_instance = None

def get_instance(api_key=None, api_secret=None):
    """
    Lấy instance singleton của BinanceDataModel.
    
    Args:
        api_key (str, optional): API key để kết nối đến Binance. Chỉ được sử dụng khi tạo instance mới.
        api_secret (str, optional): API secret để kết nối đến Binance. Chỉ được sử dụng khi tạo instance mới.
    
    Returns:
        BinanceDataModel: Instance của BinanceDataModel
    """
    global _instance
    if _instance is None:
        _instance = BinanceDataModel(api_key, api_secret)
    elif api_key and api_secret:
        # Cập nhật thông tin API nếu khác với hiện tại
        if (api_key != _instance.api_key or api_secret != _instance.api_secret):
            _instance.update_api_credentials(api_key, api_secret)
    
    return _instance