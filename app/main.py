import os
import zipfile
import json
import threading
import webbrowser
import io
import time
import sqlite3
from PIL import Image
from flask import Flask, jsonify, send_from_directory, request, send_file
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# --- 配置 ---
APP_DIR = os.path.dirname(os.path.abspath(__file__))
WEB_DIRECTORY = os.path.join(APP_DIR, 'web')
COVERS_DIRECTORY = os.path.join(WEB_DIRECTORY, 'covers')
COVER_SIZES = {
    "thumbnail": 180,
    "medium": 360,
    "large": 540
}

app = Flask(__name__, static_folder=WEB_DIRECTORY)

# --- 数据库和文件路径定义 ---
CONFIG_FILE = os.path.join(APP_DIR, 'config.json')
DB_FILE = os.path.join(APP_DIR, 'comics.db') # <--- 使用 SQLite 数据库

# --- 数据库初始化 ---
def init_db():
    """初始化数据库，创建表和索引（如果不存在）。"""
    conn = get_db_connection()
    cursor = conn.cursor()

    # 创建表
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS comics (
        title TEXT PRIMARY KEY,
        displayName TEXT,
        is_favorite INTEGER DEFAULT 0,
        currentPage INTEGER DEFAULT 0,
        totalPages INTEGER DEFAULT 0,
        date_added REAL,
        local_path TEXT,
        local_source_folder TEXT,
        local_cover_path_thumbnail TEXT,
        local_cover_path_medium TEXT,
        local_cover_path_large TEXT,
        online_url TEXT,
        online_cover_url TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS folders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL,
        auto INTEGER DEFAULT 0,
        name_includes TEXT,
        tag_includes TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS tags (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS comic_folders (
        comic_title TEXT,
        folder_id INTEGER,
        PRIMARY KEY (comic_title, folder_id),
        FOREIGN KEY (comic_title) REFERENCES comics (title) ON DELETE CASCADE,
        FOREIGN KEY (folder_id) REFERENCES folders (id) ON DELETE CASCADE
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS comic_tags (
        comic_title TEXT,
        tag_id INTEGER,
        type TEXT,
        PRIMARY KEY (comic_title, tag_id, type),
        FOREIGN KEY (comic_title) REFERENCES comics (title) ON DELETE CASCADE,
        FOREIGN KEY (tag_id) REFERENCES tags (id) ON DELETE CASCADE
    )
    """)

    # 创建索引以提高查询性能
    print("正在检查并创建数据库索引...")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_comics_date_added ON comics (date_added)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_comics_displayName ON comics (displayName)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_comics_is_favorite ON comics (is_favorite)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_comics_local_path ON comics (local_path)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_comic_tags_comic_title ON comic_tags (comic_title)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_comic_tags_tag_id ON comic_tags (tag_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_comic_folders_comic_title ON comic_folders (comic_title)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_comic_folders_folder_id ON comic_folders (folder_id)")
    
    conn.commit()
    conn.close()
    print("数据库初始化完成，表和索引已确认。")

# --- 数据库管理 ---
def get_db_connection():
    """创建并返回一个数据库连接，并设置 row_factory 以便按列名访问。"""
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

# --- 配置管理 ---
def get_config():
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"managed_folders": []} # 提供默认配置

def save_config(config):
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=4)

# --- 全局常量 ---
IMAGE_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp']
ALLOWED_EXTENSIONS = ['.zip', '.cbz'] # 支持的漫画文件扩展名

def sanitize_filename(filename):
    """
    清理文件名，移除或替换不允许的字符，并限制长度。
    """
    # 替换不允许的字符
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        filename = filename.replace(char, '')
    # 替换可能导致路径问题的字符
    filename = filename.replace(' ', '_')
    filename = filename.replace('-', '_')
    filename = filename.replace('[', '(').replace(']', ')')
    filename = filename.replace('<', '(').replace('>', ')')
    filename = filename.replace(':', '_')
    filename = filename.replace('\\', '_')
    filename = filename.replace('/', '_')
    filename = filename.replace('|', '_')
    filename = filename.replace('?', '')
    filename = filename.replace('*', '')

    # 限制文件名长度，例如200个字符，保留扩展名空间
    if len(filename) > 200:
        filename = filename[:200]
    return filename

# --- 文件夹管理 (数据库版) ---
def get_folders():
    """从数据库获取所有文件夹定义。"""
    folders = []
    try:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("SELECT name, auto, name_includes, tag_includes FROM folders ORDER BY name")
        rows = c.fetchall()
        conn.close()
        for row in rows:
            folders.append({
                "name": row['name'],
                "auto": bool(row['auto']),
                "name_includes": json.loads(row['name_includes']),
                "tag_includes": json.loads(row['tag_includes'])
            })
        return folders
    except Exception as e:
        print(f"Error getting folders from DB: {e}")
        return []

# --- 统一漫画数据管理 (数据库版) ---
def load_unified_comics():
    """
    从数据库加载所有漫画数据，并以原始 JSON 文件的字典格式返回。
    这主要用于需要全量数据的旧函数，新逻辑应直接查询数据库。
    """
    comics_map = {}
    try:
        conn = get_db_connection()
        c = conn.cursor()
        # 主要的 comics 表查询
        c.execute("SELECT * FROM comics")
        comics_rows = c.fetchall()

        # 预加载所有标签和文件夹关系以提高效率
        c.execute("""
            SELECT ct.comic_title, t.name, ct.type 
            FROM comic_tags ct JOIN tags t ON ct.tag_id = t.id
        """)
        tags_rows = c.fetchall()
        tags_map = {}
        for row in tags_rows:
            if row['comic_title'] not in tags_map:
                tags_map[row['comic_title']] = {'source': [], 'added': [], 'removed': []}
            tags_map[row['comic_title']][row['type']].append(row['name'])

        c.execute("""
            SELECT cf.comic_title, f.name 
            FROM comic_folders cf JOIN folders f ON cf.folder_id = f.id
        """)
        folders_rows = c.fetchall()
        comic_folders_map = {}
        for row in folders_rows:
            if row['comic_title'] not in comic_folders_map:
                comic_folders_map[row['comic_title']] = []
            comic_folders_map[row['comic_title']].append(row['name'])

        conn.close()

        for row in comics_rows:
            title = row['title']
            comics_map[title] = {
                "title": title,
                "displayName": row['displayName'],
                "is_favorite": bool(row['is_favorite']),
                "currentPage": row['currentPage'],
                "totalPages": row['totalPages'],
                "date_added": row['date_added'],
                "local_info": {
                    "path": row['local_path'],
                    "source_folder": row['local_source_folder'],
                    "cover_paths": {
                        "thumbnail": row['local_cover_path_thumbnail'],
                        "medium": row['local_cover_path_medium'],
                        "large": row['local_cover_path_large'],
                    } if row['local_cover_path_thumbnail'] else None
                } if row['local_path'] else None,
                "online_info": {
                    "url": row['online_url'],
                    "cover_url": row['online_cover_url']
                } if row['online_url'] else None,
                "source_tags": tags_map.get(title, {}).get('source', []),
                "added_tags": tags_map.get(title, {}).get('added', []),
                "removed_tags": tags_map.get(title, {}).get('removed', []),
                "folders": comic_folders_map.get(title, [])
            }
        return comics_map
    except Exception as e:
        print(f"Error loading unified comics from DB: {e}")
        return {}

# save_unified_comics 和 save_folders 函数不再需要，因为我们将直接执行 SQL 命令。
# 为了安全起见，暂时将它们注释掉，而不是完全删除。
# def save_folders(folders):
#     with open(FOLDERS_FILE, 'w', encoding='utf-8') as f:
#         json.dump(folders, f, ensure_ascii=False, indent=4)
#
# def save_unified_comics(unified_comics_data):
#     with open(UNIFIED_DB_FILE, 'w', encoding='utf-8') as f:
#         json.dump(unified_comics_data, f, ensure_ascii=False, indent=4)



# --- 文件处理 ---
def get_image_files_from_zip(zip_path):
    try:
        with zipfile.ZipFile(zip_path, 'r') as z:
            return sorted([f for f in z.namelist() if not f.startswith('__MACOSX/') and not f.endswith('/') and any(f.lower().endswith(ext) for ext in IMAGE_EXTENSIONS)])
    except FileNotFoundError:
        raise # 重新抛出异常，由调用方处理
    except Exception as e:
        print(f"无法读取压缩包 {zip_path}: {e}")
    return []

def get_first_image_from_zip(zip_path):
    image_files = get_image_files_from_zip(zip_path)
    if not image_files: return None
    try:
        with zipfile.ZipFile(zip_path, 'r') as z:
            return z.read(image_files[0])
    except Exception as e:
        print(f"无法提取封面 {zip_path}: {e}")
    return None

# --- 核心扫描逻辑 (数据库版) ---
def scan_comics(folder_to_scan=None):
    global scan_progress
    if scan_progress['in_progress']:
        print("扫描已在进行中，请稍后再试。")
        return

    scan_progress['in_progress'] = True
    scan_progress['current'] = 0
    scan_progress['total'] = 0
    scan_progress['message'] = "正在开始扫描..."

    try:
        print("开始扫描漫画...")
        config = get_config()
        os.makedirs(COVERS_DIRECTORY, exist_ok=True)
        for size_name in COVER_SIZES.keys():
            os.makedirs(os.path.join(COVERS_DIRECTORY, size_name), exist_ok=True)

        conn = get_db_connection()
        cursor = conn.cursor()

        scan_folders = [folder_to_scan] if folder_to_scan else config.get('managed_folders', [])
        if not scan_folders:
            print("没有配置漫画库路径，扫描中止。")
            scan_progress['in_progress'] = False
            return

        scan_progress['message'] = "正在搜集文件..."
        disk_comic_paths = set()
        for folder in scan_folders:
            if not os.path.isdir(folder):
                continue
            for root, _, files in os.walk(folder):
                for file in files:
                    if any(file.lower().endswith(ext) for ext in ALLOWED_EXTENSIONS):
                        disk_comic_paths.add(os.path.join(root, file))
        
        paths_to_process = list(disk_comic_paths)
        scan_progress['total'] = len(paths_to_process)

        # 快速将所有新漫画添加到数据库
        cursor.execute("SELECT title, local_path FROM comics WHERE local_path IS NOT NULL")
        existing_comics = {row['title']: row['local_path'] for row in cursor.fetchall()}
        existing_local_paths = set(existing_comics.values())

        comics_to_add = []
        comics_to_update = []

        for i, comic_path in enumerate(paths_to_process):
            scan_progress['current'] = i + 1
            comic_name = os.path.splitext(os.path.basename(comic_path))[0]
            scan_progress['message'] = f"正在快速添加: {comic_name}"
            
            if comic_path in existing_local_paths:
                continue

            source_folder = next((f for f in config.get('managed_folders', []) if comic_path.startswith(f)), None)
            
            # 检查漫画名是否已存在（例如，一个在线漫画）
            cursor.execute("SELECT local_path FROM comics WHERE title = ?", (comic_name,))
            result = cursor.fetchone()

            if result is None: # 漫画名不存在，是全新的
                comics_to_add.append((
                    comic_name, comic_name, time.time(), comic_path, source_folder
                ))
            elif result['local_path'] is None: # 漫画存在但没有本地信息
                comics_to_update.append((comic_path, source_folder, comic_name))

        if comics_to_add:
            cursor.executemany("""
                INSERT INTO comics (title, displayName, date_added, local_path, local_source_folder)
                VALUES (?, ?, ?, ?, ?)
            """, comics_to_add)
            print(f"快速添加了 {len(comics_to_add)} 本新漫画。")

        if comics_to_update:
            cursor.executemany("""
                UPDATE comics SET local_path = ?, local_source_folder = ? WHERE title = ?
            """, comics_to_update)
            print(f"为 {len(comics_to_update)} 本在线漫画关联了本地文件。")
        
        conn.commit()

        # 现在，进行完整的封面生成和处理
        cursor.execute("SELECT title, local_path, local_cover_path_thumbnail FROM comics WHERE local_path IS NOT NULL")
        all_local_comics = cursor.fetchall()

        for i, comic_row in enumerate(all_local_comics):
            comic_path = comic_row['local_path']
            if not os.path.exists(comic_path): continue

            comic_name = comic_row['title']
            scan_progress['current'] = i + 1
            scan_progress['message'] = f"正在处理封面: {comic_name}"
            
            # 检查封面是否存在且有效
            cover_path_thumb = comic_row['local_cover_path_thumbnail']
            if cover_path_thumb and os.path.exists(os.path.join(WEB_DIRECTORY, cover_path_thumb.replace('/', os.sep))):
                continue

            image_data = get_first_image_from_zip(comic_path)
            if image_data:
                try:
                    img = Image.open(io.BytesIO(image_data)).convert("RGB")
                except Exception as e:
                    print(f"  - 无法打开封面图片 {comic_name}: {e}")
                    continue

                cover_filename = f"{sanitize_filename(comic_name)}.jpg"
                cover_paths = {}

                for size_name, width in COVER_SIZES.items():
                    try:
                        w, h = img.size
                        aspect_ratio = h / w
                        new_height = int(width * aspect_ratio)
                        resized_img = img.resize((width, new_height), Image.Resampling.LANCZOS)
                        
                        size_dir = os.path.join(COVERS_DIRECTORY, size_name)
                        output_path = os.path.join(size_dir, cover_filename)
                        
                        resized_img.save(output_path, "JPEG", quality=95)
                        cover_paths[size_name] = f"covers/{size_name}/{cover_filename}"
                    except Exception as e:
                        print(f"  - 无法调整大小或保存封面 {comic_name} ({size_name}): {e}")
                
                if len(cover_paths) == len(COVER_SIZES):
                    cursor.execute("""
                        UPDATE comics SET 
                        local_cover_path_thumbnail = ?, 
                        local_cover_path_medium = ?, 
                        local_cover_path_large = ?
                        WHERE title = ?
                    """, (
                        cover_paths.get('thumbnail'),
                        cover_paths.get('medium'),
                        cover_paths.get('large'),
                        comic_name
                    ))
        
        conn.commit()

        scan_progress['message'] = "正在自动分类..."
        auto_classify_comics(conn)
        
        conn.commit()
        conn.close()
        print("扫描完成.")
        
    except Exception as e:
        import traceback
        print(f"--- 扫描时出错: {e} ---")
        traceback.print_exc()
    finally:
        scan_progress['in_progress'] = False
        scan_progress['message'] = "扫描完成"
        
    return list(load_unified_comics().values())


def auto_classify_comics(conn):
    """
    对尚未分类的漫画应用自动分类规则 (数据库版)。
    """
    print("开始自动分类...")
    cursor = conn.cursor()

    # 1. 获取自动分类文件夹的规则
    cursor.execute("SELECT id, name, name_includes, tag_includes FROM folders WHERE auto = 1")
    auto_folder_rules = cursor.fetchall()
    
    if not auto_folder_rules:
        print("没有配置自动分类文件夹，跳过。")
        return

    auto_folder_id_map = {f['id'] for f in auto_folder_rules}

    # 2. 获取所有漫画的标题、标签和当前文件夹
    cursor.execute("SELECT title FROM comics")
    all_comics_titles = [row['title'] for row in cursor.fetchall()]
    
    # 3. 准备数据
    # 获取所有标签
    cursor.execute("""
        SELECT ct.comic_title, t.name, ct.type
        FROM comic_tags ct JOIN tags t ON ct.tag_id = t.id
    """)
    tags_rows = cursor.fetchall()
    tags_map = {}
    for row in tags_rows:
        title = row['comic_title']
        if title not in tags_map:
            tags_map[title] = {'source': set(), 'added': set(), 'removed': set()}
        tags_map[title][row['type']].add(row['name'])

    # 获取所有文件夹关系
    cursor.execute("SELECT comic_title, folder_id FROM comic_folders")
    comic_folders_rows = cursor.fetchall()
    comic_folders_map = {}
    for row in comic_folders_rows:
        title = row['comic_title']
        if title not in comic_folders_map:
            comic_folders_map[title] = set()
        comic_folders_map[title].add(row['folder_id'])

    # 4. 遍历每本漫画进行分类
    classified_count = 0
    updates_to_perform = [] # (comic_title, folder_id)

    for title in all_comics_titles:
        current_folders = comic_folders_map.get(title, set())
        manual_folders = {f_id for f_id in current_folders if f_id not in auto_folder_id_map}
        
        # 计算最终标签
        comic_tags = tags_map.get(title, {})
        source_tags = comic_tags.get('source', set())
        added_tags = comic_tags.get('added', set())
        removed_tags = comic_tags.get('removed', set())
        final_tags = (source_tags.union(added_tags)) - removed_tags
        processed_tags = {tag.lower().replace('无', '無') for tag in final_tags}
        
        processed_title = title.lower().replace('无', '無')

        # 匹配新的自动文件夹
        newly_matched_auto_folders = set()
        for rule in auto_folder_rules:
            name_includes = [k.strip().lower().replace('无', '無') for k in json.loads(rule['name_includes']) if k.strip()]
            tag_includes = {t.strip().lower().replace('无', '無') for t in json.loads(rule['tag_includes']) if t.strip()}

            if not name_includes and not tag_includes:
                continue

            name_match = not name_includes or any(k in processed_title for k in name_includes)
            tag_match = not tag_includes or not processed_tags.isdisjoint(tag_includes)
            
            if name_match and tag_match:
                newly_matched_auto_folders.add(rule['id'])
        
        final_folder_ids = manual_folders.union(newly_matched_auto_folders)
        
        if final_folder_ids != current_folders:
            classified_count += 1
            # 记录需要进行的数据库更新
            # 首先移除所有旧的自动文件夹关联
            folders_to_remove = {f_id for f_id in current_folders if f_id in auto_folder_id_map}
            for f_id in folders_to_remove:
                updates_to_perform.append((title, f_id, 'delete'))
            # 然后添加所有新的自动文件夹关联
            for f_id in newly_matched_auto_folders:
                updates_to_perform.append((title, f_id, 'insert'))

    # 5. 执行数据库更新
    if updates_to_perform:
        for title, folder_id, action in updates_to_perform:
            if action == 'delete':
                cursor.execute("DELETE FROM comic_folders WHERE comic_title = ? AND folder_id = ?", (title, folder_id))
            elif action == 'insert':
                cursor.execute("INSERT OR IGNORE INTO comic_folders (comic_title, folder_id) VALUES (?, ?)", (title, folder_id))
        
        conn.commit()
        print(f"更新了 {classified_count} 本漫画的文件夹。")
    else:
        print("没有漫画的文件夹被更新。")



# --- 安全性检查 ---
def is_safe_path(path):
    config = get_config()
    abs_path = os.path.abspath(path)
    return any(abs_path.startswith(os.path.abspath(folder)) for folder in config.get('managed_folders', []))

# --- 扫描进度跟踪 ---
scan_progress = {
    "in_progress": False,
    "total": 0,
    "current": 0,
    "message": ""
}

# --- Watchdog 实时文件处理 ---
def handle_comic_created(comic_path):
    """处理新创建的漫画文件。"""
    try:
        print(f"[DB Update] 开始处理新漫画: {os.path.basename(comic_path)}")
        conn = get_db_connection()
        cursor = conn.cursor()

        comic_name = os.path.splitext(os.path.basename(comic_path))[0]
        config = get_config()
        source_folder = next((f for f in config.get('managed_folders', []) if comic_path.startswith(f)), None)

        # 使用 UPSERT 逻辑
        cursor.execute("""
            INSERT INTO comics (title, displayName, date_added, local_path, local_source_folder)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(title) DO UPDATE SET
                local_path = excluded.local_path,
                local_source_folder = excluded.local_source_folder,
                date_added = excluded.date_added
        """, (comic_name, comic_name, time.time(), comic_path, source_folder))

        # 生成封面
        image_data = get_first_image_from_zip(comic_path)
        if image_data:
            img = Image.open(io.BytesIO(image_data)).convert("RGB")
            cover_filename = f"{sanitize_filename(comic_name)}.jpg"
            cover_paths = {}
            for size_name, width in COVER_SIZES.items():
                w, h = img.size
                aspect_ratio = h / w
                new_height = int(width * aspect_ratio)
                resized_img = img.resize((width, new_height), Image.Resampling.LANCZOS)
                size_dir = os.path.join(COVERS_DIRECTORY, size_name)
                output_path = os.path.join(size_dir, cover_filename)
                resized_img.save(output_path, "JPEG", quality=95)
                cover_paths[size_name] = f"covers/{size_name}/{cover_filename}"
            
            if len(cover_paths) == len(COVER_SIZES):
                cursor.execute("""
                    UPDATE comics SET 
                    local_cover_path_thumbnail = ?, 
                    local_cover_path_medium = ?, 
                    local_cover_path_large = ?
                    WHERE title = ?
                """, (
                    cover_paths.get('thumbnail'),
                    cover_paths.get('medium'),
                    cover_paths.get('large'),
                    comic_name
                ))
        
        # 自动分类
        auto_classify_comics(conn)
        
        conn.commit()
        conn.close()
        print(f"[DB Update] 成功添加/更新漫画: {comic_name}")

    except Exception as e:
        import traceback
        print(f"--- 处理新漫画时出错 {comic_path}: {e} ---")
        traceback.print_exc()

def handle_comic_deleted(comic_path):
    """处理被删除的漫画文件。"""
    try:
        print(f"[DB Update] 开始处理删除: {os.path.basename(comic_path)}")
        conn = get_db_connection()
        cursor = conn.cursor()

        # 查找漫画以获取封面信息
        cursor.execute("SELECT title, local_cover_path_thumbnail, online_url FROM comics WHERE local_path = ?", (comic_path,))
        comic_row = cursor.fetchone()

        if comic_row:
            comic_title = comic_row['title']
            
            # 删除封面文件
            if comic_row['local_cover_path_thumbnail']:
                base_cover_name = os.path.basename(comic_row['local_cover_path_thumbnail'])
                for size_name in COVER_SIZES.keys():
                    cover_to_delete = os.path.join(COVERS_DIRECTORY, size_name, base_cover_name)
                    if os.path.exists(cover_to_delete):
                        os.remove(cover_to_delete)
                        print(f"  - 已删除封面: {cover_to_delete}")

            # 如果有在线版本，则只清除本地信息；否则，完全删除。
            if comic_row['online_url']:
                cursor.execute("""
                    UPDATE comics SET
                    local_path = NULL, local_source_folder = NULL,
                    local_cover_path_thumbnail = NULL, local_cover_path_medium = NULL, local_cover_path_large = NULL
                    WHERE title = ?
                """, (comic_title,))
                print(f"[DB Update] 已从漫画 '{comic_title}' 中移除本地路径信息。")
            else:
                cursor.execute("DELETE FROM comics WHERE title = ?", (comic_title,))
                print(f"[DB Update] 已从数据库中完全删除漫画 '{comic_title}'。")
            
            conn.commit()
        else:
            print(f"[DB Update] 在数据库中未找到路径为 {comic_path} 的漫画，无需操作。")

        conn.close()

    except Exception as e:
        import traceback
        print(f"--- 处理删除漫画时出错 {comic_path}: {e} ---")
        traceback.print_exc()

def handle_comic_moved(src_path, dest_path):
    """处理移动或重命名的漫画文件。"""
    try:
        print(f"[DB Update] 开始处理移动/重命名: {os.path.basename(src_path)} -> {os.path.basename(dest_path)}")
        conn = get_db_connection()
        cursor = conn.cursor()

        # 查找旧漫画以获取信息
        cursor.execute("SELECT title, local_cover_path_thumbnail FROM comics WHERE local_path = ?", (src_path,))
        comic_row = cursor.fetchone()

        if comic_row:
            old_title = comic_row['title']
            new_title = os.path.splitext(os.path.basename(dest_path))[0]
            
            # 重命名封面文件
            if comic_row['local_cover_path_thumbnail']:
                old_cover_base = sanitize_filename(old_title) + ".jpg"
                new_cover_base = sanitize_filename(new_title) + ".jpg"
                if old_cover_base != new_cover_base:
                    for size_name in COVER_SIZES.keys():
                        old_cover_path = os.path.join(COVERS_DIRECTORY, size_name, old_cover_base)
                        new_cover_path = os.path.join(COVERS_DIRECTORY, size_name, new_cover_base)
                        if os.path.exists(old_cover_path):
                            os.rename(old_cover_path, new_cover_path)
                            print(f"  - 已重命名封面: {old_cover_path} -> {new_cover_path}")
            
            # 更新数据库记录
            # 注意：这假设 title 是可以改变的。如果 title 是主键且不能变，需要更复杂的逻辑。
            # 在这个应用中，title 就是文件名，所以它必须改变。
            new_cover_thumb = f"covers/thumbnail/{sanitize_filename(new_title)}.jpg"
            new_cover_medium = f"covers/medium/{sanitize_filename(new_title)}.jpg"
            new_cover_large = f"covers/large/{sanitize_filename(new_title)}.jpg"

            # 因为 title 是主键，我们不能直接更新它。我们需要用新的 title 创建一个副本，然后删除旧的。
            cursor.execute("SELECT * FROM comics WHERE title = ?", (old_title,))
            old_data = cursor.fetchone()
            
            # 复制数据到新条目
            cursor.execute("""
                INSERT OR REPLACE INTO comics 
                (title, displayName, is_favorite, currentPage, totalPages, date_added, local_path, local_source_folder, 
                local_cover_path_thumbnail, local_cover_path_medium, local_cover_path_large, online_url, online_cover_url)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                new_title, new_title, old_data['is_favorite'], old_data['currentPage'], old_data['totalPages'], old_data['date_added'],
                dest_path, old_data['local_source_folder'], new_cover_thumb, new_cover_medium, new_cover_large,
                old_data['online_url'], old_data['online_cover_url']
            ))

            # 迁移标签和文件夹
            cursor.execute("UPDATE comic_tags SET comic_title = ? WHERE comic_title = ?", (new_title, old_title))
            cursor.execute("UPDATE comic_folders SET comic_title = ? WHERE comic_title = ?", (new_title, old_title))

            # 删除旧条目
            cursor.execute("DELETE FROM comics WHERE title = ?", (old_title,))

            conn.commit()
            print(f"[DB Update] 成功将 '{old_title}' 重命名/移动为 '{new_title}'。")
        else:
            # 如果在数据库中找不到旧路径，这可能是一个新文件，当作创建处理
            print(f"[DB Update] 未找到旧路径 {src_path}，将其作为新文件处理。")
            handle_comic_created(dest_path)

        conn.close()

    except Exception as e:
        import traceback
        print(f"--- 处理移动/重命名漫画时出错 {src_path} -> {dest_path}: {e} ---")
        traceback.print_exc()


# --- Watchdog File System Monitoring ---

class ComicBookEventHandler(FileSystemEventHandler):
    """Handles file system events for comic book files."""

    def on_created(self, event):
        if not event.is_directory and any(event.src_path.lower().endswith(ext) for ext in ALLOWED_EXTENSIONS):
            # 增加延时以确保文件写入完成
            time.sleep(1)
            handle_comic_created(event.src_path)

    def on_deleted(self, event):
        if not event.is_directory and any(event.src_path.lower().endswith(ext) for ext in ALLOWED_EXTENSIONS):
            handle_comic_deleted(event.src_path)

    def on_moved(self, event):
        if not event.is_directory and any(event.dest_path.lower().endswith(ext) for ext in ALLOWED_EXTENSIONS):
            # 增加延时以确保文件移动完成
            time.sleep(1)
            handle_comic_moved(event.src_path, event.dest_path)

def start_file_monitoring():
    """Initializes and starts the file system observer."""
    config = get_config()
    managed_folders = config.get('managed_folders', [])
    if not managed_folders:
        print("[Monitor] No managed folders configured. File monitoring will not start.")
        return None

    event_handler = ComicBookEventHandler()
    observer = Observer()
    for folder in managed_folders:
        if os.path.isdir(folder):
            observer.schedule(event_handler, folder, recursive=True)
            print(f"[Monitor] Watching folder: {folder}")
        else:
            print(f"[Monitor] Warning: Configured folder does not exist, cannot watch: {folder}")
    
    if not observer.emitters:
        print("[Monitor] No valid folders to watch. File monitoring will not start.")
        return None

    observer.start()
    print("[Monitor] File system monitoring started in background.")
    return observer

# --- API 路由 ---
@app.route('/api/scan/progress')
def get_scan_progress():
    return jsonify(scan_progress)

@app.route('/')
def index():
    return send_from_directory(app.static_folder, 'index.html')

def _get_unified_comics(search_term='', filter_by='all', sort_by='date', sort_order='desc', limit=30, offset=0):
    """
    从数据库加载漫画数据，并转换为前端期望的格式，支持搜索、过滤、排序和分页。
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    # --- 构建基础查询 ---
    base_query = """
        SELECT
            c.title, c.displayName, c.is_favorite, c.currentPage, c.totalPages, c.date_added,
            c.local_path, c.local_cover_path_thumbnail, c.local_cover_path_medium, c.local_cover_path_large,
            c.online_url, c.online_cover_url,
            GROUP_CONCAT(DISTINCT CASE WHEN ct.type = 'source' THEN t.name ELSE NULL END) as source_tags,
            GROUP_CONCAT(DISTINCT CASE WHEN ct.type = 'added' THEN t.name ELSE NULL END) as added_tags,
            GROUP_CONCAT(DISTINCT CASE WHEN ct.type = 'removed' THEN t.name ELSE NULL END) as removed_tags,
            GROUP_CONCAT(DISTINCT f.name) as folders
        FROM comics c
        LEFT JOIN comic_tags ct ON c.title = ct.comic_title
        LEFT JOIN tags t ON ct.tag_id = t.id
        LEFT JOIN comic_folders cf ON c.title = cf.comic_title
        LEFT JOIN folders f ON cf.folder_id = f.id
    """
    
    # --- 构建 WHERE 和 HAVING 子句的参数 ---
    query_params = {}
    where_clauses = []
    having_clauses = []

    # 过滤
    if filter_by == 'favorites':
        where_clauses.append("c.is_favorite = 1")
    elif filter_by == 'web':
        where_clauses.append("c.online_url IS NOT NULL")
    elif filter_by == 'downloaded':
        where_clauses.append("c.local_path IS NOT NULL")
    elif filter_by == 'undownloaded':
        where_clauses.append("c.online_url IS NOT NULL AND c.local_path IS NULL")
    elif filter_by != 'all':
        # 文件夹过滤
        where_clauses.append("c.title IN (SELECT cf.comic_title FROM comic_folders cf JOIN folders f ON cf.folder_id = f.id WHERE f.name = :filter_by)")
        query_params['filter_by'] = filter_by

    # 搜索
    if search_term:
        having_clauses.append("(c.displayName LIKE :search OR IFNULL(source_tags, '') LIKE :search OR IFNULL(added_tags, '') LIKE :search)")
        query_params['search'] = f"%{search_term}%"

    # --- 构建查询主体 ---
    query_body = base_query
    if where_clauses:
        query_body += " WHERE " + " AND ".join(where_clauses)
    query_body += " GROUP BY c.title"
    if having_clauses:
        query_body += " HAVING " + " AND ".join(having_clauses)

    # --- 获取总数 ---
    count_query = f"SELECT COUNT(*) FROM ({query_body})"
    cursor.execute(count_query, query_params)
    total_count = cursor.fetchone()[0]

    # --- 构建最终查询以获取数据 ---
    order_by_clause = ""
    if sort_by == 'name':
        order_by_clause = f" ORDER BY c.displayName {sort_order}"
    elif sort_by == 'date':
        order_by_clause = f" ORDER BY c.date_added {sort_order}"

    limit_clause = " LIMIT :limit OFFSET :offset"
    final_query = query_body + order_by_clause + limit_clause

    # 添加分页参数
    final_params = query_params.copy()
    final_params['limit'] = limit
    final_params['offset'] = offset
    
    cursor.execute(final_query, final_params)
    rows = cursor.fetchall()
    conn.close()

    # --- 格式化为前端期望的结构 ---
    frontend_comics = []
    for row in rows:
        # 处理标签
        source_tags = set(row['source_tags'].split(',')) if row['source_tags'] else set()
        added_tags = set(row['added_tags'].split(',')) if row['added_tags'] else set()
        removed_tags = set(row['removed_tags'].split(',')) if row['removed_tags'] else set()
        final_tags = sorted(list((source_tags.union(added_tags)) - removed_tags))

        # 处理文件夹
        folders_list = sorted(list(set(row['folders'].split(',')))) if row['folders'] else []

        # 构建 sources
        sources = []
        if row['local_path']:
            sources.append({"type": "local", "path": row['local_path']})
        if row['online_url']:
            sources.append({"type": "online", "url": row['online_url']})

        frontend_comics.append({
            "title": row['title'],
            "displayName": row['displayName'],
            "is_favorite": bool(row['is_favorite']),
            "tags": final_tags,
            "folders": folders_list,
            "currentPage": row['currentPage'],
            "totalPages": row['totalPages'],
            "date_added": row['date_added'],
            "cover_paths_local": {
                "thumbnail": row['local_cover_path_thumbnail'],
                "medium": row['local_cover_path_medium'],
                "large": row['local_cover_path_large'],
            } if row['local_cover_path_thumbnail'] else None,
            "cover_url_online": row['online_cover_url'],
            "sources": sources
        })

    return frontend_comics, total_count

@app.route('/api/comics', methods=['GET'])
def get_comics():
    """
    提供统一后的漫画数据，支持分页、排序、过滤和搜索 (数据库版)。
    """
    try:
        # --- 获取查询参数 ---
        page = request.args.get('page', 1, type=int)
        limit = request.args.get('limit', 30, type=int)
        sort_by = request.args.get('sort_by', 'date', type=str)
        sort_order = request.args.get('sort_order', 'desc', type=str)
        search_term = request.args.get('search', '', type=str).lower()
        filter_by = request.args.get('filter', 'all', type=str)
        offset = (page - 1) * limit

        # --- 从数据库获取数据 ---
        paginated_comics, total_filtered_comics = _get_unified_comics(
            search_term=search_term,
            filter_by=filter_by,
            sort_by=sort_by,
            sort_order=sort_order,
            limit=limit,
            offset=offset
        )
        
        # 检查数据库是否为空
        if not paginated_comics and total_filtered_comics == 0:
             # 检查数据库中是否有任何漫画
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM comics LIMIT 1")
            is_empty = cursor.fetchone() is None
            conn.close()
            if is_empty:
                print("统一漫画数据库为空，尝试执行初次扫描...")
                scan_comics()
                # 再次获取数据
                paginated_comics, total_filtered_comics = _get_unified_comics(
                    search_term=search_term, filter_by=filter_by, sort_by=sort_by,
                    sort_order=sort_order, limit=limit, offset=offset
                )

        response = jsonify({
            "comics": paginated_comics,
            "total_comics": total_filtered_comics,
            "page": page,
            "limit": limit
        })
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        return response
    except Exception as e:
        import traceback
        print(f"--- ERROR in get_comics: {e} ---")
        traceback.print_exc()
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/comics/stats', methods=['GET'])
def get_comic_stats():
    """
    计算并返回各类漫画的数量 (数据库版)。
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        stats = { "folders": {} }

        # 使用 SQL COUNT 高效计算
        stats['all'] = cursor.execute("SELECT COUNT(*) FROM comics").fetchone()[0]
        stats['favorites'] = cursor.execute("SELECT COUNT(*) FROM comics WHERE is_favorite = 1").fetchone()[0]
        stats['web'] = cursor.execute("SELECT COUNT(*) FROM comics WHERE online_url IS NOT NULL").fetchone()[0]
        stats['downloaded'] = cursor.execute("SELECT COUNT(*) FROM comics WHERE local_path IS NOT NULL").fetchone()[0]
        stats['undownloaded'] = cursor.execute("SELECT COUNT(*) FROM comics WHERE online_url IS NOT NULL AND local_path IS NULL").fetchone()[0]

        # 计算每个文件夹中的漫画数量
        cursor.execute("""
            SELECT f.name, COUNT(cf.comic_title)
            FROM folders f
            JOIN comic_folders cf ON f.id = cf.folder_id
            GROUP BY f.name
        """)
        for row in cursor.fetchall():
            stats['folders'][row[0]] = row[1]
        
        conn.close()
        return jsonify(stats)
    except Exception as e:
        print(f"Error getting stats from DB: {e}")
        # Fallback or error response
        return jsonify({
            "all": 0, "favorites": 0, "web": 0, 
            "downloaded": 0, "undownloaded": 0, "folders": {}
        })


@app.route('/api/comic/<string:title>')
def get_comic_details(title):
    """
    获取单本漫画的详细信息 (数据库版)。
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # 使用与 _get_unified_comics 类似的查询，但针对单个漫画
        cursor.execute("""
            SELECT
                c.title, c.displayName, c.is_favorite, c.currentPage, c.totalPages, c.date_added,
                c.local_path, c.local_source_folder, 
                c.local_cover_path_thumbnail, c.local_cover_path_medium, c.local_cover_path_large,
                c.online_url, c.online_cover_url,
                GROUP_CONCAT(DISTINCT CASE WHEN ct.type = 'source' THEN t.name ELSE NULL END) as source_tags,
                GROUP_CONCAT(DISTINCT CASE WHEN ct.type = 'added' THEN t.name ELSE NULL END) as added_tags,
                GROUP_CONCAT(DISTINCT CASE WHEN ct.type = 'removed' THEN t.name ELSE NULL END) as removed_tags,
                GROUP_CONCAT(DISTINCT f.name) as folders
            FROM comics c
            LEFT JOIN comic_tags ct ON c.title = ct.comic_title
            LEFT JOIN tags t ON ct.tag_id = t.id
            LEFT JOIN comic_folders cf ON c.title = cf.comic_title
            LEFT JOIN folders f ON cf.folder_id = f.id
            WHERE c.title = ?
            GROUP BY c.title
        """, (title,))
        
        row = cursor.fetchone()
        conn.close()

        if not row:
            return jsonify({"status": "error", "message": "漫画未找到"}), 404

        # 将 row 格式化为前端期望的 JSON 结构
        # 这个结构与 load_unified_comics 返回的内部结构一致
        comic_details = {
            "title": row['title'],
            "displayName": row['displayName'],
            "is_favorite": bool(row['is_favorite']),
            "currentPage": row['currentPage'],
            "totalPages": row['totalPages'],
            "date_added": row['date_added'],
            "local_info": {
                "path": row['local_path'],
                "source_folder": row['local_source_folder'],
                "cover_paths": {
                    "thumbnail": row['local_cover_path_thumbnail'],
                    "medium": row['local_cover_path_medium'],
                    "large": row['local_cover_path_large'],
                } if row['local_cover_path_thumbnail'] else None
            } if row['local_path'] else None,
            "online_info": {
                "url": row['online_url'],
                "cover_url": row['online_cover_url']
            } if row['online_url'] else None,
            "source_tags": row['source_tags'].split(',') if row['source_tags'] else [],
            "added_tags": row['added_tags'].split(',') if row['added_tags'] else [],
            "removed_tags": row['removed_tags'].split(',') if row['removed_tags'] else [],
            "folders": row['folders'].split(',') if row['folders'] else []
        }
        
        return jsonify(comic_details)

    except Exception as e:
        import traceback
        print(f"--- Error in get_comic_details: {e} ---")
        traceback.print_exc()
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/comic/<string:title>/display_name', methods=['PUT'])
def update_comic_display_name(title):
    """
    更新漫画的显示名称 (数据库版)。
    """
    data = request.json
    new_display_name = data.get('displayName')

    if not new_display_name:
        return jsonify({"status": "error", "message": "缺少新的显示名称"}), 400

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE comics SET displayName = ? WHERE title = ?", (new_display_name, title))
        conn.commit()
        
        if cursor.rowcount == 0:
            conn.close()
            return jsonify({"status": "error", "message": "漫画未找到"}), 404
        
        conn.close()
        return jsonify({"status": "success", "message": "显示名称已更新"})
    except Exception as e:
        print(f"Error updating display name in DB: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


# --- 文件夹 API ---
@app.route('/api/folders', methods=['GET'])
def api_get_folders():
    folders = get_folders()
    return jsonify(folders)

@app.route('/api/folders', methods=['POST'])
def api_add_folder():
    data = request.json
    new_folder_data = data.get('folder')
    if not new_folder_data or not new_folder_data.get('name'):
        return jsonify({"status": "error", "message": "无效的文件夹格式，需要名称"}), 400

    new_folder = {
        "name": new_folder_data['name'],
        "auto": new_folder_data.get('auto', False),
        "name_includes": json.dumps(new_folder_data.get('name_includes', [])),
        "tag_includes": json.dumps(new_folder_data.get('tag_includes', []))
    }

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO folders (name, auto, name_includes, tag_includes) VALUES (?, ?, ?, ?)",
            (new_folder['name'], new_folder['auto'], new_folder['name_includes'], new_folder['tag_includes'])
        )
        conn.commit()
        new_folder['id'] = cursor.lastrowid
        conn.close()
        return jsonify({"status": "success", "folder": new_folder_data}), 201
    except sqlite3.IntegrityError:
        return jsonify({"status": "error", "message": "文件夹已存在"}), 409
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/folders/<string:folder_name>', methods=['PUT'])
def api_update_folder(folder_name):
    data = request.json
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Find the folder first
        cursor.execute("SELECT id FROM folders WHERE name = ?", (folder_name,))
        folder_row = cursor.fetchone()
        if not folder_row:
            conn.close()
            return jsonify({"status": "error", "message": "文件夹未找到"}), 404
        
        folder_id = folder_row['id']

        # Prepare fields to update
        update_fields = {}
        if 'auto' in data:
            update_fields['auto'] = bool(data['auto'])
        if 'name_includes' in data:
            update_fields['name_includes'] = json.dumps(data['name_includes'])
        if 'tag_includes' in data:
            update_fields['tag_includes'] = json.dumps(data['tag_includes'])
        
        new_name = data.get('name')
        if new_name and new_name != folder_name:
            # Check for name conflict before updating
            cursor.execute("SELECT id FROM folders WHERE name = ?", (new_name,))
            if cursor.fetchone():
                conn.close()
                return jsonify({"status": "error", "message": "该文件夹名称已存在"}), 409
            update_fields['name'] = new_name

        if update_fields:
            set_clause = ", ".join([f"{key} = ?" for key in update_fields.keys()])
            params = list(update_fields.values()) + [folder_name]
            cursor.execute(f"UPDATE folders SET {set_clause} WHERE name = ?", tuple(params))
            conn.commit()

        conn.close()
        
        # Re-fetch the updated folder data to return it
        updated_folder_data = next((f for f in get_folders() if f['name'] == (new_name or folder_name)), None)
        
        return jsonify({"status": "success", "folder": updated_folder_data})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/folders/<string:folder_name>', methods=['DELETE'])
def api_delete_folder(folder_name):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Find folder id
        cursor.execute("SELECT id FROM folders WHERE name = ?", (folder_name,))
        folder_row = cursor.fetchone()
        if not folder_row:
            conn.close()
            return jsonify({"status": "error", "message": "文件夹未找到"}), 404
        
        folder_id = folder_row['id']
        
        # Delete from comic_folders junction table first
        cursor.execute("DELETE FROM comic_folders WHERE folder_id = ?", (folder_id,))
        
        # Delete from folders table
        cursor.execute("DELETE FROM folders WHERE id = ?", (folder_id,))
        
        conn.commit()
        conn.close()
        
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/comic/<string:title>', methods=['DELETE'])
def delete_single_comic(title):
    """
    完全删除单本漫画，包括其本地文件和封面。
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT local_path, local_cover_path_thumbnail FROM comics WHERE title = ?", (title,))
        row = cursor.fetchone()

        if not row:
            conn.close()
            return jsonify({"status": "error", "message": "漫画未找到"}), 404

        # 删除本地文件
        if row['local_path'] and os.path.exists(row['local_path']):
            try:
                os.remove(row['local_path'])
                print(f"已删除本地漫画文件: {row['local_path']}")
            except OSError as e:
                print(f"删除本地漫画文件时出错 {row['local_path']}: {e}")
        
        # 删除封面
        if row['local_cover_path_thumbnail']:
            base_cover_path = os.path.basename(row['local_cover_path_thumbnail'])
            for size_name in COVER_SIZES.keys():
                cover_path = os.path.join(COVERS_DIRECTORY, size_name, base_cover_path)
                if os.path.exists(cover_path):
                    try:
                        os.remove(cover_path)
                    except OSError as e:
                        print(f"删除封面文件时出错 {cover_path}: {e}")
        
        # 从数据库中删除条目
        cursor.execute("DELETE FROM comics WHERE title = ?", (title,))
        deleted_count = cursor.rowcount
        
        conn.commit()
        conn.close()
        
        if deleted_count > 0:
            return jsonify({"status": "success", "message": f"成功删除漫画 '{title}'。"})
        else:
            # This case should ideally not be reached if the initial find was successful
            return jsonify({"status": "error", "message": "在数据库中删除漫画时失败。"}), 500

    except Exception as e:
        import traceback
        print(f"--- ERROR in delete_single_comic: {e} ---")
        traceback.print_exc()
        return jsonify({"status": "error", "message": str(e)}), 500


# --- 新增：油猴脚本数据接口 (数据库版) ---
@app.route('/api/tampermonkey/sync', methods=['POST'])
def tampermonkey_sync():
    data = request.json
    if not data:
        return jsonify({"status": "error", "message": "No data received"}), 400
    
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        comic_srcs = data.get('comicSrcs', {})
        comic_links = data.get('comicLinks', {})
        comic_tags_from_script = data.get('comicTags', {})

        # --- 1. 移除不再存在的在线漫画 ---
        online_titles_from_script = set(comic_srcs.keys())
        
        cursor.execute("SELECT title FROM comics WHERE online_url IS NOT NULL AND local_path IS NULL")
        db_online_only_titles = {row['title'] for row in cursor.fetchall()}
        
        titles_to_remove = db_online_only_titles - online_titles_from_script
        
        if titles_to_remove:
            placeholders = ','.join('?' for _ in titles_to_remove)
            cursor.execute(f"DELETE FROM comics WHERE title IN ({placeholders})", tuple(titles_to_remove))
            print(f"已从数据库中移除 {cursor.rowcount} 条不再存在的在线漫画。")

        # --- 2. 更新/新增逻辑 ---
        updated_count = 0
        
        # 预加载所有标签以提高效率
        cursor.execute("SELECT id, name FROM tags")
        tag_id_map = {row['name']: row['id'] for row in cursor.fetchall()}

        for title, cover_url in comic_srcs.items():
            url = comic_links.get(title)
            if not url:
                continue

            # 使用 INSERT ... ON CONFLICT DO UPDATE (UPSERT)
            cursor.execute("""
                INSERT INTO comics (title, displayName, date_added, online_url, online_cover_url)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(title) DO UPDATE SET
                    online_url = excluded.online_url,
                    online_cover_url = excluded.online_cover_url
            """, (title, title, time.time(), url, cover_url))
            
            # 更新 source_tags
            online_tags = comic_tags_from_script.get(title, [])
            if online_tags:
                # 首先移除该漫画所有旧的 'source' 标签
                cursor.execute("""
                    DELETE FROM comic_tags 
                    WHERE type = 'source' AND comic_title = ?
                """, (title,))

                # 添加新的 'source' 标签
                tags_to_insert = []
                for tag_name in set(online_tags):
                    if tag_name not in tag_id_map:
                        cursor.execute("INSERT INTO tags (name) VALUES (?)", (tag_name,))
                        tag_id = cursor.lastrowid
                        tag_id_map[tag_name] = tag_id
                    else:
                        tag_id = tag_id_map[tag_name]
                    tags_to_insert.append((title, tag_id, 'source'))
                
                if tags_to_insert:
                    cursor.executemany(
                        "INSERT OR IGNORE INTO comic_tags (comic_title, tag_id, type) VALUES (?, ?, ?)",
                        tags_to_insert
                    )
            updated_count += 1

        # --- 3. 自动分类 ---
        auto_classify_comics(conn)

        conn.commit()
        print(f"油猴脚本数据同步完成，更新/新增 {updated_count} 条在线漫画信息。")
        return jsonify({"status": "success", "message": "Data synced successfully."})

    except Exception as e:
        conn.rollback()
        import traceback
        print(f"--- ERROR in tampermonkey_sync: {e} ---")
        traceback.print_exc()
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        if conn:
            conn.close()



@app.route('/api/scan', methods=['POST'])
def refresh_comics():
    return jsonify(scan_comics())


@app.route('/api/cleanup', methods=['POST'])
def cleanup_database():
    """
    清理数据库，移除指向无效本地路径的条目 (数据库版)。
    """
    print("开始清理数据库...")
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT title, local_path, local_cover_path_thumbnail, online_url FROM comics WHERE local_path IS NOT NULL")
        rows = cursor.fetchall()
        
        cleaned_count = 0
        comics_to_remove = []
        comics_to_update = []
        
        for row in rows:
            if not os.path.exists(row['local_path']):
                print(f"  - 正在处理丢失的本地漫画: {row['title']}")
                cleaned_count += 1
                
                # 删除封面
                if row['local_cover_path_thumbnail']:
                    base_cover_path = os.path.basename(row['local_cover_path_thumbnail'])
                    for size_name in COVER_SIZES.keys():
                        cover_path = os.path.join(COVERS_DIRECTORY, size_name, base_cover_path)
                        if os.path.exists(cover_path):
                            try:
                                os.remove(cover_path)
                                print(f"    - 已删除封面 ({size_name})")
                            except OSError as e:
                                print(f"    - 无法删除封面 ({size_name}): {e}")

                if row['online_url']:
                    # 如果有在线信息，则只移除本地信息
                    comics_to_update.append(row['title'])
                else:
                    # 否则，完全移除
                    comics_to_remove.append(row['title'])

        if comics_to_update:
            placeholders = ','.join('?' for _ in comics_to_update)
            cursor.execute(f"""
                UPDATE comics SET 
                local_path = NULL, local_source_folder = NULL, 
                local_cover_path_thumbnail = NULL, local_cover_path_medium = NULL, local_cover_path_large = NULL
                WHERE title IN ({placeholders})
            """, tuple(comics_to_update))

        if comics_to_remove:
            placeholders = ','.join('?' for _ in comics_to_remove)
            cursor.execute(f"DELETE FROM comics WHERE title IN ({placeholders})", tuple(comics_to_remove))

        conn.commit()
        conn.close()

        message = f"清理完成。共处理 {cleaned_count} 个无效条目。"
        print(message)
        return jsonify({"status": "success", "message": message, "cleaned_count": cleaned_count})

    except Exception as e:
        print(f"--- ERROR in cleanup_database: {e} ---")
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/ping', methods=['GET'])
def ping():
    return jsonify({"status": "ok"})

@app.route('/api/settings', methods=['GET'])
def get_settings():
    try:
        config = get_config()
        return jsonify(config)
    except Exception as e:
        print(f"--- ERROR in get_settings: {e} ---")
        return jsonify({"error": str(e)}), 500

@app.route('/api/settings/folders', methods=['POST', 'DELETE'])
def manage_folders():
    data = request.json
    folder_path = data.get('path')

    if not folder_path:
        return jsonify({"status": "error", "message": "缺少文件夹路径"}), 400

    config = get_config()
    
    if request.method == 'POST':
        if not os.path.isdir(folder_path):
            return jsonify({"status": "error", "message": "无效的或不存在的文件夹路径"}), 400

        if folder_path not in config['managed_folders']:
            config['managed_folders'].append(folder_path)
            save_config(config)
            threading.Thread(target=scan_comics, args=(folder_path,), daemon=True).start()
            return jsonify({"status": "success", "message": "文件夹已添加，正在后台扫描..."})
        else:
            return jsonify({"status": "info", "message": "文件夹已存在"}), 200

    elif request.method == 'DELETE':
        if folder_path in config['managed_folders']:
            config['managed_folders'].remove(folder_path)
            save_config(config)

            try:
                conn = get_db_connection()
                cursor = conn.cursor()
                
                # 找到所有受影响的漫画
                path_pattern = folder_path + '%'
                cursor.execute("SELECT title, online_url FROM comics WHERE local_source_folder LIKE ?", (path_pattern,))
                rows = cursor.fetchall()

                comics_to_remove = []
                comics_to_update = []
                for row in rows:
                    if row['online_url']:
                        comics_to_update.append(row['title'])
                    else:
                        comics_to_remove.append(row['title'])
                
                if comics_to_update:
                    placeholders = ','.join('?' for _ in comics_to_update)
                    cursor.execute(f"UPDATE comics SET local_path = NULL, local_source_folder = NULL WHERE title IN ({placeholders})", tuple(comics_to_update))

                if comics_to_remove:
                    placeholders = ','.join('?' for _ in comics_to_remove)
                    cursor.execute(f"DELETE FROM comics WHERE title IN ({placeholders})", tuple(comics_to_remove))

                conn.commit()
                conn.close()
                
                # 触发一次封面清理
                cleanup_database()

                return jsonify({"status": "success", "message": "文件夹已移除"})
            except Exception as e:
                 return jsonify({"status": "error", "message": str(e)}), 500
        else:
            return jsonify({"status": "error", "message": "文件夹未找到"}), 404
    
    return jsonify({"status": "error", "message": "不支持的请求方法"}), 405

@app.route('/api/settings/folders/relocate', methods=['POST'])
def relocate_folder():
    data = request.json
    old_path = data.get('old_path')
    new_path = data.get('new_path')

    if not old_path or not new_path:
        return jsonify({"status": "error", "message": "缺少新或旧的文件夹路径"}), 400

    if not os.path.isdir(new_path):
        return jsonify({"status": "error", "message": "新的路径无效或不存在"}), 400

    config = get_config()
    if old_path not in config.get('managed_folders', []):
        return jsonify({"status": "error", "message": "未在配置中找到旧的路径"}), 404

    # 1. 更新 config.json
    config['managed_folders'] = [new_path if p == old_path else p for p in config['managed_folders']]
    save_config(config)

    # 2. 更新数据库
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 规范化路径以处理 OS 差异
        old_path_norm = os.path.normpath(old_path)
        new_path_norm = os.path.normpath(new_path)

        cursor.execute("SELECT title, local_path, local_source_folder FROM comics WHERE local_path LIKE ?", (old_path_norm + '%',))
        rows = cursor.fetchall()
        
        updates = []
        for row in rows:
            new_comic_path = os.path.join(new_path_norm, os.path.relpath(os.path.normpath(row['local_path']), old_path_norm))
            new_source_folder = new_path if os.path.normpath(row['local_source_folder']) == old_path_norm else row['local_source_folder']
            updates.append((new_comic_path, new_source_folder, row['title']))

        if updates:
            cursor.executemany("UPDATE comics SET local_path = ?, local_source_folder = ? WHERE title = ?", updates)
            conn.commit()

        conn.close()
        message = f"路径已成功迁移。在 {len(updates)} 本漫画中更新了路径。"
        print(message)
        return jsonify({"status": "success", "message": message, "updated_count": len(updates)})

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500



@app.route('/api/comics/favorite', methods=['POST'])
def handle_favorite():
    data = request.json
    titles_to_update = data.get('titles', [])
    set_to = data.get('favorite') # True, False, or None for toggle

    if not isinstance(titles_to_update, list):
        return jsonify({"status": "error", "message": "无效的请求格式，需要 titles 列表"}), 400
    if not titles_to_update:
        return jsonify({"status": "success"})

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        placeholders = ','.join('?' for _ in titles_to_update)
        
        if set_to is None: # 切换模式
            cursor.execute(f"UPDATE comics SET is_favorite = NOT is_favorite WHERE title IN ({placeholders})", tuple(titles_to_update))
        else: # 设置模式
            cursor.execute(f"UPDATE comics SET is_favorite = ? WHERE title IN ({placeholders})", (bool(set_to),) + tuple(titles_to_update))
        
        conn.commit()
        conn.close()
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/comics/delete_full', methods=['POST'])
def delete_full_comics():
    data = request.json
    titles_to_delete = data.get('titles', [])

    if not isinstance(titles_to_delete, list):
        return jsonify({"status": "error", "message": "Invalid request format, 'titles' list required"}), 400
    if not titles_to_delete:
        return jsonify({"status": "success", "deleted_count": 0})

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        placeholders = ','.join('?' for _ in titles_to_delete)
        cursor.execute(f"SELECT title, local_path, local_cover_path_thumbnail FROM comics WHERE title IN ({placeholders})", tuple(titles_to_delete))
        rows = cursor.fetchall()

        for row in rows:
            # 删除本地文件
            if row['local_path'] and os.path.exists(row['local_path']):
                try:
                    os.remove(row['local_path'])
                    print(f"Deleted local comic file: {row['local_path']}")
                except OSError as e:
                    print(f"Error deleting local comic file {row['local_path']}: {e}")
            
            # 删除封面
            if row['local_cover_path_thumbnail']:
                base_cover_path = os.path.basename(row['local_cover_path_thumbnail'])
                for size_name in COVER_SIZES.keys():
                    cover_path = os.path.join(COVERS_DIRECTORY, size_name, base_cover_path)
                    if os.path.exists(cover_path):
                        try:
                            os.remove(cover_path)
                        except OSError as e:
                            print(f"Error deleting cover file {cover_path}: {e}")
        
        # 从数据库中删除条目
        cursor.execute(f"DELETE FROM comics WHERE title IN ({placeholders})", tuple(titles_to_delete))
        deleted_count = cursor.rowcount
        
        conn.commit()
        conn.close()
        
        return jsonify({"status": "success", "message": f"Successfully deleted {deleted_count} comics.", "deleted_count": deleted_count})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/comic/<string:title>/tags', methods=['POST'])
def handle_single_tag(title):
    data = request.json
    action = data.get('action')
    tag_name = data.get('tag')

    if not all([action, tag_name]):
        return jsonify({"status": "error", "message": "需要提供 'action' 和 'tag'"}), 400

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # 获取 tag_id，如果不存在则创建
        cursor.execute("SELECT id FROM tags WHERE name = ?", (tag_name,))
        tag_row = cursor.fetchone()
        if not tag_row:
            cursor.execute("INSERT INTO tags (name) VALUES (?)", (tag_name,))
            tag_id = cursor.lastrowid
        else:
            tag_id = tag_row['id']

        if action == 'add':
            # 如果存在 'removed' 类型的，则删除它
            cursor.execute("DELETE FROM comic_tags WHERE comic_title = ? AND tag_id = ? AND type = 'removed'", (title, tag_id))
            # 添加 'added' 类型的 (如果不存在)
            cursor.execute("INSERT OR IGNORE INTO comic_tags (comic_title, tag_id, type) VALUES (?, ?, 'added')", (title, tag_id))
        elif action == 'remove':
            # 如果存在 'added' 类型的，则删除它
            cursor.execute("DELETE FROM comic_tags WHERE comic_title = ? AND tag_id = ? AND type = 'added'", (title, tag_id))
            # 添加 'removed' 类型的 (如果不存在)
            cursor.execute("INSERT OR IGNORE INTO comic_tags (comic_title, tag_id, type) VALUES (?, ?, 'removed')", (title, tag_id))
        else:
            conn.close()
            return jsonify({"status": "error", "message": "无效的 'action'"}), 400

        conn.commit()
        conn.close()
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/comics/folder', methods=['POST'])
def handle_folder_assignment():
    data = request.json
    titles_to_update = data.get('titles', [])
    folder_name = data.get('folder')

    if not isinstance(titles_to_update, list) or not folder_name:
        return jsonify({"status": "error", "message": "无效的请求格式"}), 400

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # 获取 folder_id
        cursor.execute("SELECT id FROM folders WHERE name = ?", (folder_name,))
        folder_row = cursor.fetchone()
        if not folder_row:
            conn.close()
            return jsonify({"status": "error", "message": "文件夹未找到"}), 404
        folder_id = folder_row['id']

        # 为所有漫画批量添加关联
        inserts = [(title, folder_id) for title in titles_to_update]
        cursor.executemany("INSERT OR IGNORE INTO comic_folders (comic_title, folder_id) VALUES (?, ?)", inserts)

        conn.commit()
        conn.close()
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/comics/folder/remove_all', methods=['POST'])
def remove_from_all_folders():
    data = request.json
    titles_to_update = data.get('titles', [])
    if not isinstance(titles_to_update, list):
        return jsonify({"status": "error", "message": "无效的请求格式"}), 400
    if not titles_to_update:
        return jsonify({"status": "success"})
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        placeholders = ','.join('?' for _ in titles_to_update)
        cursor.execute(f"DELETE FROM comic_folders WHERE comic_title IN ({placeholders})", tuple(titles_to_update))
        conn.commit()
        conn.close()
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/comics/merge', methods=['POST'])
def merge_comics():
    data = request.json
    online_comic_title = data.get('online_comic_title')
    local_comic_title = data.get('local_comic_title')

    if not online_comic_title or not local_comic_title:
        return jsonify({"status": "error", "message": "缺少在线漫画或本地漫画的标题"}), 400

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # 获取本地漫画的信息
        cursor.execute("SELECT local_path, local_source_folder, local_cover_path_thumbnail, local_cover_path_medium, local_cover_path_large FROM comics WHERE title = ?", (local_comic_title,))
        local_row = cursor.fetchone()
        if not local_row or not local_row['local_path']:
            conn.close()
            return jsonify({"status": "error", "message": f"'{local_comic_title}' 不是一个有效的本地漫画"}), 400

        # 更新在线漫画条目
        cursor.execute("""
            UPDATE comics SET
                local_path = ?, local_source_folder = ?,
                local_cover_path_thumbnail = ?, local_cover_path_medium = ?, local_cover_path_large = ?
            WHERE title = ? AND online_url IS NOT NULL
        """, (
            local_row['local_path'], local_row['local_source_folder'],
            local_row['local_cover_path_thumbnail'], local_row['local_cover_path_medium'], local_row['local_cover_path_large'],
            online_comic_title
        ))

        if cursor.rowcount == 0:
            conn.close()
            return jsonify({"status": "error", "message": f"'{online_comic_title}' 不是一个有效的在线漫画或更新失败"}), 400

        # 删除旧的本地漫画条目
        cursor.execute("DELETE FROM comics WHERE title = ?", (local_comic_title,))

        conn.commit()
        conn.close()
        return jsonify({"status": "success", "message": f"漫画 '{local_comic_title}' 已成功合并到 '{online_comic_title}'。"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/comic/pages')
def get_comic_pages():
    comic_path = request.args.get('path')
    if not comic_path or not is_safe_path(comic_path): return "无效的漫画路径", 400
    
    try:
        pages = get_image_files_from_zip(comic_path)
        
        # 更新数据库中的 totalPages
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE comics SET totalPages = ? WHERE local_path = ?", (len(pages), comic_path))
        conn.commit()
        conn.close()

        return jsonify(pages)
    except FileNotFoundError:
        return jsonify({"error": "漫画文件未找到，可能已被移动或删除。"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/comic/page')
def get_comic_page():
    comic_path = request.args.get('path')
    page_file = request.args.get('page')
    if not comic_path or not page_file or not is_safe_path(comic_path): return "无效请求", 400
    try:
        with zipfile.ZipFile(comic_path, 'r') as z:
            if page_file in z.namelist():
                image_data = z.read(page_file)
                return send_file(io.BytesIO(image_data), mimetype=f'image/{os.path.splitext(page_file)[1][1:]}')
            else:
                return "页面在压缩包中未找到", 404
    except FileNotFoundError:
        return "漫画文件未找到，可能已被移动或删除。", 404
    except Exception as e:
        print(f"获取漫画页面时发生未知错误: {e}")
        return str(e), 500

@app.route('/api/comic/progress', methods=['POST'])
def update_progress():
    data = request.json
    comic_path, page = data.get('path'), data.get('page')
    if not comic_path or not is_safe_path(comic_path) or page is None: return "无效请求", 400
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE comics SET currentPage = ? WHERE local_path = ?", (page, comic_path))
        conn.commit()
        
        if cursor.rowcount == 0:
            conn.close()
            return jsonify({"status": "error", "message": "未找到漫画"}), 404
        
        conn.close()
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/clean_cover_cache', methods=['POST'])
def clean_cover_cache():
    """
    清理无效的封面缓存 (数据库版)。
    """
    print("开始清理无效的封面缓存...")
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT local_cover_path_thumbnail FROM comics WHERE local_cover_path_thumbnail IS NOT NULL")
        
        referenced_covers = {os.path.basename(row['local_cover_path_thumbnail']) for row in cursor.fetchall()}
        conn.close()

        if not os.path.exists(COVERS_DIRECTORY):
            return jsonify({"status": "success", "message": "封面文件夹不存在。", "deleted_files": 0})

        actual_files = set()
        for size_dir in os.listdir(COVERS_DIRECTORY):
            full_size_dir = os.path.join(COVERS_DIRECTORY, size_dir)
            if os.path.isdir(full_size_dir):
                for file in os.listdir(full_size_dir):
                    actual_files.add(file)
        
        orphaned_files = actual_files - referenced_covers
        deleted_count = 0
        
        for file in orphaned_files:
            for size_name in COVER_SIZES.keys():
                file_path = os.path.join(COVERS_DIRECTORY, size_name, file)
                if os.path.exists(file_path):
                    try:
                        os.remove(file_path)
                        deleted_count += 1
                    except OSError as e:
                        print(f"  - 无法删除 {file_path}: {e}")
        
        print(f"清理完成。共删除 {deleted_count} 个文件。")
        return jsonify({"status": "success", "message": "缓存清理完成。", "deleted_files": deleted_count})

    except Exception as e:
        print(f"--- 清理缓存时发生错误: {e} ---")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/clear_all_data', methods=['POST'])
def clear_all_data():
    print("开始清除所有数据...")
    try:
        # 1. Close any active connections and delete DB file
        # (This is tricky in a web server context, better to just clear tables)
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM comics")
        cursor.execute("DELETE FROM tags")
        cursor.execute("DELETE FROM folders")
        # Junction tables are cleared by foreign key cascades if set up, otherwise clear manually
        cursor.execute("DELETE FROM comic_tags")
        cursor.execute("DELETE FROM comic_folders")
        conn.commit()
        conn.close()
        print("Cleared all tables in the database.")

        # 2. Reset config.json
        default_config = {"managed_folders": []}
        save_config(default_config)
        print(f"Reset {CONFIG_FILE}")

        # 3. Clear all cover files
        if os.path.exists(COVERS_DIRECTORY):
            for root, _, files in os.walk(COVERS_DIRECTORY):
                for file in files:
                    try:
                        os.remove(os.path.join(root, file))
                    except OSError as e:
                        print(f"Error deleting cover file {os.path.join(root, file)}: {e}")
            print(f"Cleared all files from {COVERS_DIRECTORY}")

        print("所有数据清除完成。")
        return jsonify({"status": "success", "message": "所有数据已清除。"})
    except Exception as e:
        import traceback
        print(f"--- ERROR in clear_all_data: {e} ---")
        traceback.print_exc()
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/<path:path>')
def serve_static(path):
    return send_from_directory(app.static_folder, path)

if __name__ == '__main__':
    init_db()
    
    # Start the initial scan in a background thread
    threading.Thread(target=scan_comics, daemon=True).start()
    
    # Start file system monitoring
    observer = start_file_monitoring()

    # Open the web browser
    url = "http://127.0.0.1:5000"
    threading.Timer(1.5, lambda: webbrowser.open_new(url)).start()
    print(f"服务器已启动，请在浏览器中打开 {url}")

    try:
        # Run the Flask app
        app.run(port=5000, debug=False)
    finally:
        if observer:
            print("[Monitor] Stopping file system monitoring...")
            observer.stop()
            observer.join()
            print("[Monitor] File system monitoring stopped.")
