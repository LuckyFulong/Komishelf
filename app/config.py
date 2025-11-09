import os
import json

# --- 基本路径和目录配置 ---
APP_DIR = os.path.dirname(os.path.abspath(__file__))
WEB_DIRECTORY = os.path.join(APP_DIR, 'web')
COVERS_DIRECTORY = os.path.join(WEB_DIRECTORY, 'covers')

# --- 配置文件路径 ---
CONFIG_FILE = os.path.join(APP_DIR, 'config.json')

# --- 封面尺寸配置 ---
COVER_SIZES = {
    "thumbnail": 180,
    "medium": 360,
    "large": 540
}

# --- 文件类型配置 ---
IMAGE_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp']
ALLOWED_EXTENSIONS = ['.zip', '.cbz', '.rar']

# --- 配置管理函数 ---
def get_config():
    """读取并返回 JSON 配置文件内容。"""
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        # 如果文件不存在或解析失败，返回一个默认的空配置
        return {"managed_folders": []}

def save_config(config):
    """将配置字典写入 JSON 文件。"""
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=4)
