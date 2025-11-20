import os

# === 基础配置 ===
# 获取当前脚本所在目录
BASE_DIR = os.path.abspath(os.path.dirname(__file__))

# 数据库文件路径
DB_PATH = os.path.join(BASE_DIR, "pixiv.db")

# Pixiv 图片/小说 文件的实际存储路径 (请修改这里！)
# 注意：此路径下应包含形如 "ArtistName-12345" 的文件夹
DATA_DIR = "/mnt/data"

# Flask 密钥 (生产环境请修改为随机字符串)
SECRET_KEY = 'change_this_to_secure_random_string'

# 扫描间隔 (秒)
SCAN_INTERVAL = 15
