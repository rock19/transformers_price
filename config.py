"""
变形金刚比价程序配置文件
"""

import os

# ============ 路径配置 ============
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'data')
os.makedirs(DATA_DIR, exist_ok=True)

DATABASE_PATH = os.path.join(DATA_DIR, 'transformers.db')

# ============ 爬虫配置 ============
class SpiderConfig:
    # 京东 - 孩之宝官方旗舰店
    JD_STORE_URL = "https://www.hasin情玩具官方旗舰店"
    JD_KEYWORDS = ["变形金刚", "Transformers"]
    
    # 天猫 - 变形金刚玩具旗舰店
    TMALL_STORE_URL = "https://transformers.tmall.com"
    TMALL_KEYWORDS = ["变形金刚", "Transformers"]
    
    # 请求头
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }
    
    # 请求间隔（秒），防止被封
    REQUEST_DELAY = 3
    
    # 超时时间
    TIMEOUT = 30

# ============ 商品状态 ============
class ProductStatus:
    NOT_PURCHASED = "未购买"
    PURCHASED = "已购买"
    NOT_INTERESTED = "不感兴趣"

# ============ 飞书通知配置 ============
FEISHU_WEBHOOK_URL = ""  # 填入飞书机器人Webhook地址
FEISHU_ENABLED = False  # 是否启用飞书通知

# ============ 定时任务配置 ============
class SchedulerConfig:
    # 爬虫执行时间（每天几点）
    CRAWL_HOUR = 9
    CRAWL_MINUTE = 0
    
    # 是否启用定时任务
    ENABLED = True

# ============ OCR配置 ============
class OCRConfig:
    # 使用百度OCR API（需要申请）
    BAIDU_API_KEY = ""
    BAIDU_SECRET_KEY = ""
    
    # 或者使用本地OCR（需要安装tesseract）
    USE_LOCAL = False

# ============ Web服务配置 ============
class WebConfig:
    HOST = "0.0.0.0"
    PORT = 5000
    DEBUG = True
