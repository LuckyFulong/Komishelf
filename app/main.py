import threading
import webbrowser
from flask import Flask

# 导入应用模块
import database
import scanner
import watchdog_service
from config import WEB_DIRECTORY
from routes import bp

def create_app():
    """创建并配置 Flask 应用实例。"""
    app = Flask(__name__, static_folder=WEB_DIRECTORY)
    
    # 注册蓝图
    app.register_blueprint(bp)
    
    return app

app = create_app()

if __name__ == '__main__':
    # 初始化数据库
    database.init_db()
    
    # 在后台线程中启动初次扫描
    threading.Thread(target=scanner.scan_comics, daemon=True).start()
    
    # 启动文件系统监控
    observer = watchdog_service.start_file_monitoring()

    # 准备在浏览器中打开 URL
    url = "http://127.0.0.1:5000"
    threading.Timer(1.5, lambda: webbrowser.open_new(url)).start()
    print(f"服务器已启动，请在浏览器中打开 {url}")

    try:
        # 运行 Flask 应用
        app.run(port=5000, debug=False)
    finally:
        # 确保在程序退出时停止文件监控
        if observer:
            print("[Monitor] Stopping file system monitoring...")
            observer.stop()
            observer.join()
            print("[Monitor] File system monitoring stopped.")
