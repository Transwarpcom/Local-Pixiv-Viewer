import os
import secrets

# === 基础配置 ===
# 获取当前脚本所在目录
BASE_DIR = os.path.abspath(os.path.dirname(__file__))

# 数据库文件路径
DB_PATH = os.path.join(BASE_DIR, "pixiv.db")

# Pixiv 图片/小说 文件的实际存储路径 (请修改这里！)
# 注意：此路径下应包含形如 "ArtistName-12345" 的文件夹
DATA_DIR = os.environ.get('DATA_DIR', "/mnt/data")

# 缩略图路径 (可选)
THUMBS_DIR = os.environ.get('THUMBS_DIR')
THUMBS_URL_PREFIX = "/thumbs/" if THUMBS_DIR else "/files/"

# Flask 密钥
# 优先从环境变量获取，如果没有则生成一个随机密钥（每次重启会变更，导致 session 失效）
SECRET_KEY = os.environ.get('SECRET_KEY')
if not SECRET_KEY:
    SECRET_KEY = secrets.token_hex(32)
    # 打印警告，告知用户正在使用临时密钥
    print("WARNING: SECRET_KEY not set in environment. Using ephemeral random key. Sessions will not persist across restarts.")

# 扫描间隔 (秒)
SCAN_INTERVAL = 15
