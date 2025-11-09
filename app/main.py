import os
import zipfile
import json
import threading
import webbrowser
import io
import time
import traceback
import send2trash
from flask import Flask, jsonify, send_from_directory, request, send_file

import database
import scanner
import config
import watchdog_service

app = Flask(__name__, static_folder=config.WEB_DIRECTORY)

# --- 安全性检查 ---
def is_safe_path(path):
    app_config = config.get_config()
    abs_path = os.path.abspath(path)
    return any(abs_path.startswith(os.path.abspath(folder)) for folder in app_config.get('managed_folders', []))

# --- API 路由 ---
@app.route('/api/scan/progress')
def get_scan_progress():
    return jsonify(scanner.scan_progress)

@app.route('/')
def index():
    return send_from_directory(app.static_folder, 'index.html')

def _get_unified_comics(search_term='', filter_by='all', sort_by='date', sort_order='desc', limit=30, offset=0):
    """
    从数据库加载漫画数据，并转换为前端期望的格式，支持搜索、过滤、排序和分页。
    """
    conn = database.get_db_connection()
    cursor = conn.cursor()

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
    
    query_params = {}
    where_clauses = []
    having_clauses = []

    if filter_by == 'favorites':
        where_clauses.append("c.is_favorite = 1")
    elif filter_by == 'web':
        where_clauses.append("c.online_url IS NOT NULL")
    elif filter_by == 'downloaded':
        where_clauses.append("c.local_path IS NOT NULL")
    elif filter_by == 'undownloaded':
        where_clauses.append("c.online_url IS NOT NULL AND c.local_path IS NULL")
    elif filter_by != 'all':
        where_clauses.append("c.title IN (SELECT cf.comic_title FROM comic_folders cf JOIN folders f ON cf.folder_id = f.id WHERE f.name = :filter_by)")
        query_params['filter_by'] = filter_by

    if search_term:
        having_clauses.append("(c.displayName LIKE :search OR IFNULL(source_tags, '') LIKE :search OR IFNULL(added_tags, '') LIKE :search)")
        query_params['search'] = f"%{search_term}%"

    query_body = base_query
    if where_clauses:
        query_body += " WHERE " + " AND ".join(where_clauses)
    query_body += " GROUP BY c.title"
    if having_clauses:
        query_body += " HAVING " + " AND ".join(having_clauses)

    count_query = f"SELECT COUNT(*) FROM ({query_body})"
    cursor.execute(count_query, query_params)
    total_count = cursor.fetchone()[0]

    order_by_clause = ""
    if sort_by == 'name':
        order_by_clause = f" ORDER BY c.displayName {sort_order}"
    elif sort_by == 'date':
        order_by_clause = f" ORDER BY c.date_added {sort_order}"

    limit_clause = " LIMIT :limit OFFSET :offset"
    final_query = query_body + order_by_clause + limit_clause

    final_params = query_params.copy()
    final_params['limit'] = limit
    final_params['offset'] = offset
    
    cursor.execute(final_query, final_params)
    rows = cursor.fetchall()
    conn.close()

    frontend_comics = []
    for row in rows:
        source_tags = set(row['source_tags'].split(',')) if row['source_tags'] else set()
        added_tags = set(row['added_tags'].split(',')) if row['added_tags'] else set()
        removed_tags = set(row['removed_tags'].split(',')) if row['removed_tags'] else set()
        final_tags = sorted(list((source_tags.union(added_tags)) - removed_tags))
        folders_list = sorted(list(set(row['folders'].split(',')))) if row['folders'] else []
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
    try:
        page = request.args.get('page', 1, type=int)
        limit = request.args.get('limit', 30, type=int)
        sort_by = request.args.get('sort_by', 'date', type=str)
        sort_order = request.args.get('sort_order', 'desc', type=str)
        search_term = request.args.get('search', '', type=str).lower()
        filter_by = request.args.get('filter', 'all', type=str)
        offset = (page - 1) * limit

        paginated_comics, total_filtered_comics = _get_unified_comics(
            search_term=search_term, filter_by=filter_by, sort_by=sort_by,
            sort_order=sort_order, limit=limit, offset=offset
        )
        
        if not paginated_comics and total_filtered_comics == 0:
            conn = database.get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM comics LIMIT 1")
            is_empty = cursor.fetchone() is None
            conn.close()
            if is_empty:
                print("统一漫画数据库为空，尝试执行初次扫描...")
                scanner.scan_comics()
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
        print(f"--- ERROR in get_comics: {e} ---")
        traceback.print_exc()
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/comics/stats', methods=['GET'])
def get_comic_stats():
    try:
        conn = database.get_db_connection()
        cursor = conn.cursor()
        stats = { "folders": {} }
        stats['all'] = cursor.execute("SELECT COUNT(*) FROM comics").fetchone()[0]
        stats['favorites'] = cursor.execute("SELECT COUNT(*) FROM comics WHERE is_favorite = 1").fetchone()[0]
        stats['web'] = cursor.execute("SELECT COUNT(*) FROM comics WHERE online_url IS NOT NULL").fetchone()[0]
        stats['downloaded'] = cursor.execute("SELECT COUNT(*) FROM comics WHERE local_path IS NOT NULL").fetchone()[0]
        stats['undownloaded'] = cursor.execute("SELECT COUNT(*) FROM comics WHERE online_url IS NOT NULL AND local_path IS NULL").fetchone()[0]
        cursor.execute("SELECT f.name, COUNT(cf.comic_title) FROM folders f JOIN comic_folders cf ON f.id = cf.folder_id GROUP BY f.name")
        for row in cursor.fetchall():
            stats['folders'][row[0]] = row[1]
        conn.close()
        return jsonify(stats)
    except Exception as e:
        print(f"Error getting stats from DB: {e}")
        return jsonify({"all": 0, "favorites": 0, "web": 0, "downloaded": 0, "undownloaded": 0, "folders": {}})

@app.route('/api/comic/<string:title>')
def get_comic_details(title):
    try:
        conn = database.get_db_connection()
        cursor = conn.cursor()
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
        comic_details = {
            "title": row['title'], "displayName": row['displayName'], "is_favorite": bool(row['is_favorite']),
            "currentPage": row['currentPage'], "totalPages": row['totalPages'], "date_added": row['date_added'],
            "local_info": {
                "path": row['local_path'], "source_folder": row['local_source_folder'],
                "cover_paths": {
                    "thumbnail": row['local_cover_path_thumbnail'], "medium": row['local_cover_path_medium'],
                    "large": row['local_cover_path_large'],
                } if row['local_cover_path_thumbnail'] else None
            } if row['local_path'] else None,
            "online_info": {"url": row['online_url'], "cover_url": row['online_cover_url']} if row['online_url'] else None,
            "source_tags": row['source_tags'].split(',') if row['source_tags'] else [],
            "added_tags": row['added_tags'].split(',') if row['added_tags'] else [],
            "removed_tags": row['removed_tags'].split(',') if row['removed_tags'] else [],
            "folders": row['folders'].split(',') if row['folders'] else []
        }
        return jsonify(comic_details)
    except Exception as e:
        print(f"--- Error in get_comic_details: {e} ---")
        traceback.print_exc()
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/comic/<string:title>/display_name', methods=['PUT'])
def update_comic_display_name(title):
    data = request.json
    new_display_name = data.get('displayName')
    if not new_display_name:
        return jsonify({"status": "error", "message": "缺少新的显示名称"}), 400
    try:
        conn = database.get_db_connection()
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

@app.route('/api/folders', methods=['GET'])
def api_get_folders():
    folders = database.get_folders()
    return jsonify(folders)

@app.route('/api/folders', methods=['POST'])
def api_add_folder():
    data = request.json
    new_folder_data = data.get('folder')
    if not new_folder_data or not new_folder_data.get('name'):
        return jsonify({"status": "error", "message": "无效的文件夹格式，需要名称"}), 400
    new_folder = {
        "name": new_folder_data['name'], "auto": new_folder_data.get('auto', False),
        "name_includes": json.dumps(new_folder_data.get('name_includes', [])),
        "tag_includes": json.dumps(new_folder_data.get('tag_includes', []))
    }
    try:
        conn = database.get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO folders (name, auto, name_includes, tag_includes) VALUES (?, ?, ?, ?)",
            (new_folder['name'], new_folder['auto'], new_folder['name_includes'], new_folder['tag_includes'])
        )
        conn.commit()
        new_folder['id'] = cursor.lastrowid
        conn.close()
        return jsonify({"status": "success", "folder": new_folder_data}), 201
    except Exception as e:
        return jsonify({"status": "error", "message": "文件夹已存在或发生其他错误: " + str(e)}), 409

@app.route('/api/folders/<string:folder_name>', methods=['PUT'])
def api_update_folder(folder_name):
    data = request.json
    try:
        conn = database.get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM folders WHERE name = ?", (folder_name,))
        folder_row = cursor.fetchone()
        if not folder_row:
            conn.close()
            return jsonify({"status": "error", "message": "文件夹未找到"}), 404
        update_fields = {}
        if 'auto' in data: update_fields['auto'] = bool(data['auto'])
        if 'name_includes' in data: update_fields['name_includes'] = json.dumps(data['name_includes'])
        if 'tag_includes' in data: update_fields['tag_includes'] = json.dumps(data['tag_includes'])
        new_name = data.get('name')
        if new_name and new_name != folder_name:
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
        updated_folder_data = next((f for f in database.get_folders() if f['name'] == (new_name or folder_name)), None)
        return jsonify({"status": "success", "folder": updated_folder_data})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/folders/<string:folder_name>', methods=['DELETE'])
def api_delete_folder(folder_name):
    try:
        conn = database.get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM folders WHERE name = ?", (folder_name,))
        folder_row = cursor.fetchone()
        if not folder_row:
            conn.close()
            return jsonify({"status": "error", "message": "文件夹未找到"}), 404
        folder_id = folder_row['id']
        cursor.execute("DELETE FROM comic_folders WHERE folder_id = ?", (folder_id,))
        cursor.execute("DELETE FROM folders WHERE id = ?", (folder_id,))
        conn.commit()
        conn.close()
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/comic/delete_single', methods=['POST'])
def delete_single_comic():
    data = request.json
    title = data.get('title')
    if not title:
        return jsonify({"status": "error", "message": "缺少标题"}), 400
    try:
        conn = database.get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT local_path, local_cover_path_thumbnail FROM comics WHERE title = ?", (title,))
        row = cursor.fetchone()
        if not row:
            conn.close()
            return jsonify({"status": "error", "message": "漫画未找到"}), 404
        if row['local_path'] and os.path.exists(row['local_path']):
            try:
                send2trash.send2trash(row['local_path'])
                print(f"已将本地漫画文件移动到回收站: {row['local_path']}")
            except OSError as e:
                print(f"移动本地漫画文件到回收站时出错 {row['local_path']}: {e}")
        if row['local_cover_path_thumbnail']:
            base_cover_path = os.path.basename(row['local_cover_path_thumbnail'])
            for size_name in config.COVER_SIZES.keys():
                cover_path = os.path.join(config.COVERS_DIRECTORY, size_name, base_cover_path)
                if os.path.exists(cover_path):
                    try:
                        os.remove(cover_path)
                    except OSError as e:
                        print(f"删除封面文件时出错 {cover_path}: {e}")
        cursor.execute("DELETE FROM comics WHERE title = ?", (title,))
        conn.commit()
        conn.close()
        return jsonify({"status": "success", "message": f"成功删除漫画 '{title}'。"})
    except Exception as e:
        print(f"--- ERROR in delete_single_comic: {e} ---")
        traceback.print_exc()
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/tampermonkey/sync', methods=['POST'])
def tampermonkey_sync():
    data = request.json
    if not data:
        return jsonify({"status": "error", "message": "No data received"}), 400
    conn = database.get_db_connection()
    cursor = conn.cursor()
    try:
        comic_srcs = data.get('comicSrcs', {})
        comic_links = data.get('comicLinks', {})
        comic_tags_from_script = data.get('comicTags', {})
        online_titles_from_script = set(comic_srcs.keys())
        cursor.execute("SELECT title FROM comics WHERE online_url IS NOT NULL AND local_path IS NULL")
        db_online_only_titles = {row['title'] for row in cursor.fetchall()}
        titles_to_remove = db_online_only_titles - online_titles_from_script
        if titles_to_remove:
            placeholders = ','.join('?' for _ in titles_to_remove)
            cursor.execute(f"DELETE FROM comics WHERE title IN ({placeholders})", tuple(titles_to_remove))
            print(f"已从数据库中移除 {cursor.rowcount} 条不再存在的在线漫画。")
        updated_count = 0
        cursor.execute("SELECT id, name FROM tags")
        tag_id_map = {row['name']: row['id'] for row in cursor.fetchall()}
        for title, cover_url in comic_srcs.items():
            url = comic_links.get(title)
            if not url: continue
            cursor.execute("""
                INSERT INTO comics (title, displayName, date_added, online_url, online_cover_url)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(title) DO UPDATE SET
                    online_url = excluded.online_url,
                    online_cover_url = excluded.online_cover_url
            """, (title, title, time.time(), url, cover_url))
            online_tags = comic_tags_from_script.get(title, [])
            if online_tags:
                cursor.execute("DELETE FROM comic_tags WHERE type = 'source' AND comic_title = ?", (title,))
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
                    cursor.executemany("INSERT OR IGNORE INTO comic_tags (comic_title, tag_id, type) VALUES (?, ?, ?)", tags_to_insert)
            updated_count += 1
        scanner.auto_classify_comics(conn)
        conn.commit()
        print(f"油猴脚本数据同步完成，更新/新增 {updated_count} 条在线漫画信息。")
        return jsonify({"status": "success", "message": "Data synced successfully."})
    except Exception as e:
        conn.rollback()
        print(f"--- ERROR in tampermonkey_sync: {e} ---")
        traceback.print_exc()
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        if conn: conn.close()

@app.route('/api/scan', methods=['POST'])
def refresh_comics():
    return jsonify(scanner.scan_comics())

@app.route('/api/cleanup', methods=['POST'])
def cleanup_database():
    print("开始清理数据库...")
    try:
        conn = database.get_db_connection()
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
                if row['local_cover_path_thumbnail']:
                    base_cover_path = os.path.basename(row['local_cover_path_thumbnail'])
                    for size_name in config.COVER_SIZES.keys():
                        cover_path = os.path.join(config.COVERS_DIRECTORY, size_name, base_cover_path)
                        if os.path.exists(cover_path):
                            try:
                                os.remove(cover_path)
                                print(f"    - 已删除封面 ({size_name})")
                            except OSError as e:
                                print(f"    - 无法删除封面 ({size_name}): {e}")
                if row['online_url']:
                    comics_to_update.append(row['title'])
                else:
                    comics_to_remove.append(row['title'])
        if comics_to_update:
            placeholders = ','.join('?' for _ in comics_to_update)
            cursor.execute(f"UPDATE comics SET local_path = NULL, local_source_folder = NULL, local_cover_path_thumbnail = NULL, local_cover_path_medium = NULL, local_cover_path_large = NULL WHERE title IN ({placeholders})", tuple(comics_to_update))
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
        app_config = config.get_config()
        return jsonify(app_config)
    except Exception as e:
        print(f"--- ERROR in get_settings: {e} ---")
        return jsonify({"error": str(e)}), 500

@app.route('/api/settings/folders', methods=['POST', 'DELETE'])
def manage_folders():
    data = request.json
    folder_path = data.get('path')
    if not folder_path:
        return jsonify({"status": "error", "message": "缺少文件夹路径"}), 400
    app_config = config.get_config()
    if request.method == 'POST':
        if not os.path.isdir(folder_path):
            return jsonify({"status": "error", "message": "无效的或不存在的文件夹路径"}), 400
        if folder_path not in app_config['managed_folders']:
            app_config['managed_folders'].append(folder_path)
            config.save_config(app_config)
            threading.Thread(target=scanner.scan_comics, args=(folder_path,), daemon=True).start()
            return jsonify({"status": "success", "message": "文件夹已添加，正在后台扫描..."})
        else:
            return jsonify({"status": "info", "message": "文件夹已存在"}), 200
    elif request.method == 'DELETE':
        if folder_path in app_config['managed_folders']:
            app_config['managed_folders'].remove(folder_path)
            config.save_config(app_config)
            try:
                conn = database.get_db_connection()
                cursor = conn.cursor()
                path_pattern = folder_path + '%'
                cursor.execute("SELECT title, online_url FROM comics WHERE local_source_folder LIKE ?", (path_pattern,))
                rows = cursor.fetchall()
                comics_to_remove = []
                comics_to_update = []
                for row in rows:
                    if row['online_url']: comics_to_update.append(row['title'])
                    else: comics_to_remove.append(row['title'])
                if comics_to_update:
                    placeholders = ','.join('?' for _ in comics_to_update)
                    cursor.execute(f"UPDATE comics SET local_path = NULL, local_source_folder = NULL WHERE title IN ({placeholders})", tuple(comics_to_update))
                if comics_to_remove:
                    placeholders = ','.join('?' for _ in comics_to_remove)
                    cursor.execute(f"DELETE FROM comics WHERE title IN ({placeholders})", tuple(comics_to_remove))
                conn.commit()
                conn.close()
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
    app_config = config.get_config()
    if old_path not in app_config.get('managed_folders', []):
        return jsonify({"status": "error", "message": "未在配置中找到旧的路径"}), 404
    app_config['managed_folders'] = [new_path if p == old_path else p for p in app_config['managed_folders']]
    config.save_config(app_config)
    try:
        conn = database.get_db_connection()
        cursor = conn.cursor()
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
    set_to = data.get('favorite')
    if not isinstance(titles_to_update, list):
        return jsonify({"status": "error", "message": "无效的请求格式，需要 titles 列表"}), 400
    if not titles_to_update:
        return jsonify({"status": "success"})
    try:
        conn = database.get_db_connection()
        cursor = conn.cursor()
        placeholders = ','.join('?' for _ in titles_to_update)
        if set_to is None:
            cursor.execute(f"UPDATE comics SET is_favorite = NOT is_favorite WHERE title IN ({placeholders})", tuple(titles_to_update))
        else:
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
        conn = database.get_db_connection()
        cursor = conn.cursor()
        placeholders = ','.join('?' for _ in titles_to_delete)
        cursor.execute(f"SELECT title, local_path, local_cover_path_thumbnail FROM comics WHERE title IN ({placeholders})", tuple(titles_to_delete))
        rows = cursor.fetchall()
        for row in rows:
            if row['local_path'] and os.path.exists(row['local_path']):
                try:
                    send2trash.send2trash(row['local_path'])
                    print(f"已将本地漫画文件移动到回收站: {row['local_path']}")
                except OSError as e:
                    print(f"移动本地漫画文件到回收站时出错 {row['local_path']}: {e}")
            if row['local_cover_path_thumbnail']:
                base_cover_path = os.path.basename(row['local_cover_path_thumbnail'])
                for size_name in config.COVER_SIZES.keys():
                    cover_path = os.path.join(config.COVERS_DIRECTORY, size_name, base_cover_path)
                    if os.path.exists(cover_path):
                        try: os.remove(cover_path)
                        except OSError as e: print(f"Error deleting cover file {cover_path}: {e}")
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
        conn = database.get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM tags WHERE name = ?", (tag_name,))
        tag_row = cursor.fetchone()
        if not tag_row:
            cursor.execute("INSERT INTO tags (name) VALUES (?)", (tag_name,))
            tag_id = cursor.lastrowid
        else:
            tag_id = tag_row['id']
        if action == 'add':
            cursor.execute("DELETE FROM comic_tags WHERE comic_title = ? AND tag_id = ? AND type = 'removed'", (title, tag_id))
            cursor.execute("INSERT OR IGNORE INTO comic_tags (comic_title, tag_id, type) VALUES (?, ?, 'added')", (title, tag_id))
        elif action == 'remove':
            cursor.execute("DELETE FROM comic_tags WHERE comic_title = ? AND tag_id = ? AND type = 'added'", (title, tag_id))
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
        conn = database.get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM folders WHERE name = ?", (folder_name,))
        folder_row = cursor.fetchone()
        if not folder_row:
            conn.close()
            return jsonify({"status": "error", "message": "文件夹未找到"}), 404
        folder_id = folder_row['id']
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
        conn = database.get_db_connection()
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
        conn = database.get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT local_path, local_source_folder, local_cover_path_thumbnail, local_cover_path_medium, local_cover_path_large FROM comics WHERE title = ?", (local_comic_title,))
        local_row = cursor.fetchone()
        if not local_row or not local_row['local_path']:
            conn.close()
            return jsonify({"status": "error", "message": f"'{local_comic_title}' 不是一个有效的本地漫画"}), 400
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
        pages = scanner.get_image_files_from_zip(comic_path)
        conn = database.get_db_connection()
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
        conn = database.get_db_connection()
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
    print("开始清理无效的封面缓存...")
    try:
        conn = database.get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT local_cover_path_thumbnail FROM comics WHERE local_cover_path_thumbnail IS NOT NULL")
        referenced_covers = {os.path.basename(row['local_cover_path_thumbnail']) for row in cursor.fetchall()}
        conn.close()
        if not os.path.exists(config.COVERS_DIRECTORY):
            return jsonify({"status": "success", "message": "封面文件夹不存在。", "deleted_files": 0})
        actual_files = set()
        for size_dir in os.listdir(config.COVERS_DIRECTORY):
            full_size_dir = os.path.join(config.COVERS_DIRECTORY, size_dir)
            if os.path.isdir(full_size_dir):
                for file in os.listdir(full_size_dir):
                    actual_files.add(file)
        orphaned_files = actual_files - referenced_covers
        deleted_count = 0
        for file in orphaned_files:
            for size_name in config.COVER_SIZES.keys():
                file_path = os.path.join(config.COVERS_DIRECTORY, size_name, file)
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
        conn = database.get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM comics")
        cursor.execute("DELETE FROM tags")
        cursor.execute("DELETE FROM folders")
        cursor.execute("DELETE FROM comic_tags")
        cursor.execute("DELETE FROM comic_folders")
        conn.commit()
        conn.close()
        print("Cleared all tables in the database.")
        default_config = {"managed_folders": []}
        config.save_config(default_config)
        print(f"Reset {config.CONFIG_FILE}")
        if os.path.exists(config.COVERS_DIRECTORY):
            for root, _, files in os.walk(config.COVERS_DIRECTORY):
                for file in files:
                    try:
                        os.remove(os.path.join(root, file))
                    except OSError as e:
                        print(f"Error deleting cover file {os.path.join(root, file)}: {e}")
            print(f"Cleared all files from {config.COVERS_DIRECTORY}")
        print("所有数据清除完成。")
        return jsonify({"status": "success", "message": "所有数据已清除。"})
    except Exception as e:
        print(f"--- ERROR in clear_all_data: {e} ---")
        traceback.print_exc()
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/<path:path>')
def serve_static(path):
    return send_from_directory(app.static_folder, path)

if __name__ == '__main__':
    database.init_db()
    threading.Thread(target=scanner.scan_comics, daemon=True).start()
    observer = watchdog_service.start_file_monitoring()
    url = "http://127.0.0.1:5000"
    threading.Timer(1.5, lambda: webbrowser.open_new(url)).start()
    print(f"服务器已启动，请在浏览器中打开 {url}")
    try:
        app.run(port=5000, debug=False)
    finally:
        if observer:
            print("[Monitor] Stopping file system monitoring...")
            observer.stop()
            observer.join()
            print("[Monitor] File system monitoring stopped.")