import os
import time
import traceback
from PIL import Image
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

import database
import scanner
import config

# --- Watchdog 实时文件处理 ---

def handle_comic_created(comic_path):
    """处理新创建的漫画文件。"""
    try:
        print(f"[DB Update] 开始处理新漫画: {os.path.basename(comic_path)}")
        conn = database.get_db_connection()
        cursor = conn.cursor()

        comic_name = os.path.splitext(os.path.basename(comic_path))[0]
        app_config = config.get_config()
        source_folder = next((f for f in app_config.get('managed_folders', []) if comic_path.startswith(f)), None)

        cursor.execute("""
            INSERT INTO comics (title, displayName, date_added, local_path, local_source_folder)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(title) DO UPDATE SET
                local_path = excluded.local_path,
                local_source_folder = excluded.local_source_folder,
                date_added = excluded.date_added
        """, (comic_name, comic_name, time.time(), comic_path, source_folder))

        image_data = scanner.get_first_image_from_zip(comic_path)
        if image_data:
            img = Image.open(io.BytesIO(image_data)).convert("RGB")
            cover_filename = f"{scanner.sanitize_filename(comic_name)}.jpg"
            cover_paths = {}
            for size_name, width in config.COVER_SIZES.items():
                w, h = img.size
                aspect_ratio = h / w
                new_height = int(width * aspect_ratio)
                resized_img = img.resize((width, new_height), Image.Resampling.LANCZOS)
                size_dir = os.path.join(config.COVERS_DIRECTORY, size_name)
                output_path = os.path.join(size_dir, cover_filename)
                resized_img.save(output_path, "JPEG", quality=95)
                cover_paths[size_name] = f"covers/{size_name}/{cover_filename}"
            
            if len(cover_paths) == len(config.COVER_SIZES):
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
        
        scanner.auto_classify_comics(conn)
        
        conn.commit()
        conn.close()
        print(f"[DB Update] 成功添加/更新漫画: {comic_name}")

    except Exception as e:
        print(f"--- 处理新漫画时出错 {comic_path}: {e} ---")
        traceback.print_exc()

def handle_comic_deleted(comic_path):
    """处理被删除的漫画文件。"""
    try:
        print(f"[DB Update] 开始处理删除: {os.path.basename(comic_path)}")
        conn = database.get_db_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT title, local_cover_path_thumbnail, online_url FROM comics WHERE local_path = ?", (comic_path,))
        comic_row = cursor.fetchone()

        if comic_row:
            comic_title = comic_row['title']
            
            if comic_row['local_cover_path_thumbnail']:
                base_cover_name = os.path.basename(comic_row['local_cover_path_thumbnail'])
                for size_name in config.COVER_SIZES.keys():
                    cover_to_delete = os.path.join(config.COVERS_DIRECTORY, size_name, base_cover_name)
                    if os.path.exists(cover_to_delete):
                        os.remove(cover_to_delete)
                        print(f"  - 已删除封面: {cover_to_delete}")

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
        print(f"--- 处理删除漫画时出错 {comic_path}: {e} ---")
        traceback.print_exc()

def handle_comic_moved(src_path, dest_path):
    """处理移动或重命名的漫画文件。"""
    try:
        print(f"[DB Update] 开始处理移动/重命名: {os.path.basename(src_path)} -> {os.path.basename(dest_path)}")
        conn = database.get_db_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT title, local_cover_path_thumbnail FROM comics WHERE local_path = ?", (src_path,))
        comic_row = cursor.fetchone()

        if comic_row:
            old_title = comic_row['title']
            new_title = os.path.splitext(os.path.basename(dest_path))[0]
            
            if comic_row['local_cover_path_thumbnail']:
                old_cover_base = scanner.sanitize_filename(old_title) + ".jpg"
                new_cover_base = scanner.sanitize_filename(new_title) + ".jpg"
                if old_cover_base != new_cover_base:
                    for size_name in config.COVER_SIZES.keys():
                        old_cover_path = os.path.join(config.COVERS_DIRECTORY, size_name, old_cover_base)
                        new_cover_path = os.path.join(config.COVERS_DIRECTORY, size_name, new_cover_base)
                        if os.path.exists(old_cover_path):
                            os.rename(old_cover_path, new_cover_path)
                            print(f"  - 已重命名封面: {old_cover_path} -> {new_cover_path}")
            
            new_cover_thumb = f"covers/thumbnail/{scanner.sanitize_filename(new_title)}.jpg"
            new_cover_medium = f"covers/medium/{scanner.sanitize_filename(new_title)}.jpg"
            new_cover_large = f"covers/large/{scanner.sanitize_filename(new_title)}.jpg"

            cursor.execute("SELECT * FROM comics WHERE title = ?", (old_title,))
            old_data = cursor.fetchone()
            
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

            cursor.execute("UPDATE comic_tags SET comic_title = ? WHERE comic_title = ?", (new_title, old_title))
            cursor.execute("UPDATE comic_folders SET comic_title = ? WHERE comic_title = ?", (new_title, old_title))

            cursor.execute("DELETE FROM comics WHERE title = ?", (old_title,))

            conn.commit()
            print(f"[DB Update] 成功将 '{old_title}' 重命名/移动为 '{new_title}'。")
        else:
            print(f"[DB Update] 未找到旧路径 {src_path}，将其作为新文件处理。")
            handle_comic_created(dest_path)

        conn.close()

    except Exception as e:
        print(f"--- 处理移动/重命名漫画时出错 {src_path} -> {dest_path}: {e} ---")
        traceback.print_exc()


class ComicBookEventHandler(FileSystemEventHandler):
    """Handles file system events for comic book files."""
    def on_created(self, event):
        if not event.is_directory and any(event.src_path.lower().endswith(ext) for ext in config.ALLOWED_EXTENSIONS):
            time.sleep(1)
            handle_comic_created(event.src_path)

    def on_deleted(self, event):
        if not event.is_directory and any(event.src_path.lower().endswith(ext) for ext in config.ALLOWED_EXTENSIONS):
            handle_comic_deleted(event.src_path)

    def on_moved(self, event):
        if not event.is_directory and any(event.dest_path.lower().endswith(ext) for ext in config.ALLOWED_EXTENSIONS):
            time.sleep(1)
            handle_comic_moved(event.src_path, event.dest_path)

def start_file_monitoring():
    """Initializes and starts the file system observer."""
    app_config = config.get_config()
    managed_folders = app_config.get('managed_folders', [])
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
