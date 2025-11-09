import os
import zipfile
import json
import io
import time
import traceback
from PIL import Image
import rarfile

import database
from config import (
    get_config,
    COVERS_DIRECTORY,
    COVER_SIZES,
    ALLOWED_EXTENSIONS,
    IMAGE_EXTENSIONS,
    WEB_DIRECTORY
)

# --- 扫描进度跟踪 ---
scan_progress = {
    "in_progress": False,
    "total": 0,
    "current": 0,
    "message": ""
}

# --- 文件名和压缩包处理 ---
def sanitize_filename(filename):
    """
    清理文件名，移除或替换不允许的字符，并限制长度。
    """
    invalid_chars = '<>:\"/\\|?*'
    for char in invalid_chars:
        filename = filename.replace(char, '')
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

    if len(filename) > 200:
        filename = filename[:200]
    return filename

def get_image_files_from_zip(zip_path):
    """从 ZIP 文件中获取所有图片文件的列表。"""
    try:
        with zipfile.ZipFile(zip_path, 'r') as z:
            return sorted([f for f in z.namelist() if not f.startswith('__MACOSX/') and not f.endswith('/') and any(f.lower().endswith(ext) for ext in IMAGE_EXTENSIONS)])
    except FileNotFoundError:
        raise
    except Exception as e:
        print(f"无法读取压缩包 {zip_path}: {e}")
    return []

def get_first_image_from_zip(zip_path):
    """从 ZIP 文件中提取第一张图片作为封面。"""
    image_files = get_image_files_from_zip(zip_path)
    if not image_files: return None
    try:
        with zipfile.ZipFile(zip_path, 'r') as z:
            return z.read(image_files[0])
    except Exception as e:
        print(f"无法提取封面 {zip_path}: {e}")
    return None

def get_image_files_from_rar(rar_path):
    """从 RAR 文件中获取所有图片文件的列表。"""
    try:
        with rarfile.RarFile(rar_path, 'r') as r:
            return sorted([f.filename for f in r.infolist() if not f.isdir and any(f.filename.lower().endswith(ext) for ext in IMAGE_EXTENSIONS)])
    except FileNotFoundError:
        raise
    except rarfile.BadRarFile:
        print(f"无法读取 RAR 文件 (可能已损坏或密码保护) {rar_path}")
    except Exception as e:
        print(f"无法读取 RAR 文件 {rar_path}: {e}")
    return []

def get_first_image_from_rar(rar_path):
    """从 RAR 文件中提取第一张图片作为封面。"""
    image_files = get_image_files_from_rar(rar_path)
    if not image_files: return None
    try:
        with rarfile.RarFile(rar_path, 'r') as r:
            return r.read(image_files[0])
    except rarfile.BadRarFile:
        print(f"无法提取 RAR 封面 (可能已损坏或密码保护) {rar_path}")
    except Exception as e:
        print(f"无法提取 RAR 封面 {rar_path}: {e}")
    return None

# --- 核心扫描和分类逻辑 ---
def scan_comics(folder_to_scan=None):
    """
    扫描指定的漫画文件夹，更新数据库，并生成封面。
    """
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

        conn = database.get_db_connection()
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
            
            cursor.execute("SELECT local_path FROM comics WHERE title = ?", (comic_name,))
            result = cursor.fetchone()

            if result is None:
                comics_to_add.append((comic_name, comic_name, time.time(), comic_path, source_folder))
            elif result['local_path'] is None:
                comics_to_update.append((comic_path, source_folder, comic_name))

        if comics_to_add:
            cursor.executemany("INSERT INTO comics (title, displayName, date_added, local_path, local_source_folder) VALUES (?, ?, ?, ?, ?)", comics_to_add)
            print(f"快速添加了 {len(comics_to_add)} 本新漫画。")

        if comics_to_update:
            cursor.executemany("UPDATE comics SET local_path = ?, local_source_folder = ? WHERE title = ?", comics_to_update)
            print(f"为 {len(comics_to_update)} 本在线漫画关联了本地文件。")
        
        conn.commit()

        cursor.execute("SELECT title, local_path, local_cover_path_thumbnail FROM comics WHERE local_path IS NOT NULL")
        all_local_comics = cursor.fetchall()

        for i, comic_row in enumerate(all_local_comics):
            comic_path = comic_row['local_path']
            if not os.path.exists(comic_path): continue

            comic_name = comic_row['title']
            scan_progress['current'] = i + 1
            scan_progress['message'] = f"正在处理封面: {comic_name}"
            
            cover_path_thumb = comic_row['local_cover_path_thumbnail']
            if cover_path_thumb and os.path.exists(os.path.join(WEB_DIRECTORY, cover_path_thumb.replace('/', os.sep))):
                continue

            file_extension = os.path.splitext(comic_path)[1].lower()
            image_data = None
            if file_extension == '.zip' or file_extension == '.cbz':
                image_data = get_first_image_from_zip(comic_path)
            elif file_extension == '.rar':
                image_data = get_first_image_from_rar(comic_path)
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
        print(f"--- 扫描时出错: {e} ---")
        traceback.print_exc()
    finally:
        scan_progress['in_progress'] = False
        scan_progress['message'] = "扫描完成"
        
    return list(database.load_unified_comics().values())


def auto_classify_comics(conn):
    """
    对尚未分类的漫画应用自动分类规则。
    """
    print("开始自动分类...")
    cursor = conn.cursor()

    cursor.execute("SELECT id, name, name_includes, tag_includes FROM folders WHERE auto = 1")
    auto_folder_rules = cursor.fetchall()
    
    if not auto_folder_rules:
        print("没有配置自动分类文件夹，跳过。")
        return

    auto_folder_id_map = {f['id'] for f in auto_folder_rules}

    cursor.execute("SELECT title FROM comics")
    all_comics_titles = [row['title'] for row in cursor.fetchall()]
    
    cursor.execute("SELECT ct.comic_title, t.name, ct.type FROM comic_tags ct JOIN tags t ON ct.tag_id = t.id")
    tags_rows = cursor.fetchall()
    tags_map = {}
    for row in tags_rows:
        title = row['comic_title']
        if title not in tags_map:
            tags_map[title] = {'source': set(), 'added': set(), 'removed': set()}
        tags_map[title][row['type']].add(row['name'])

    cursor.execute("SELECT comic_title, folder_id FROM comic_folders")
    comic_folders_rows = cursor.fetchall()
    comic_folders_map = {}
    for row in comic_folders_rows:
        title = row['comic_title']
        if title not in comic_folders_map:
            comic_folders_map[title] = set()
        comic_folders_map[title].add(row['folder_id'])

    classified_count = 0
    updates_to_perform = []

    for title in all_comics_titles:
        current_folders = comic_folders_map.get(title, set())
        manual_folders = {f_id for f_id in current_folders if f_id not in auto_folder_id_map}
        
        comic_tags = tags_map.get(title, {})
        source_tags = comic_tags.get('source', set())
        added_tags = comic_tags.get('added', set())
        removed_tags = comic_tags.get('removed', set())
        final_tags = (source_tags.union(added_tags)) - removed_tags
        processed_tags = {tag.lower().replace('无', '無') for tag in final_tags}
        
        processed_title = title.lower().replace('无', '無')

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
            folders_to_remove = {f_id for f_id in current_folders if f_id in auto_folder_id_map}
            for f_id in folders_to_remove:
                updates_to_perform.append((title, f_id, 'delete'))
            for f_id in newly_matched_auto_folders:
                updates_to_perform.append((title, f_id, 'insert'))

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
