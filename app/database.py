import sqlite3
import os
import json
import time

# --- 数据库和文件路径定义 ---
APP_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(APP_DIR, 'comics.db')

# --- 数据库管理 ---
def get_db_connection():
    """创建并返回一个数据库连接，并设置 row_factory 以便按列名访问。"""
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

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
