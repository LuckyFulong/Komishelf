import os
import sys

# 1. ！！！！！！！！！！！！！！！！！！！！！！！！！！！！
# ！！！   请将此路径修改为你的漫画库根目录   ！！！
# ！！！！！！！！！！！！！！！！！！！！！！！！！！！！
#    注意：路径前的 r 很重要，它能防止 \ 被转义
root_dir = r"E:\mod\新建文件夹\紳士漫畫 (ZH)"

# 2. 定义合法的漫画文件扩展名（小写）
comic_extensions = ('.cbz', '.cbr', '.cb7', '.zip', '.rar')

def rename_comics():
    print(f"--- 开始扫描目录: {root_dir} ---")
    
    # 检查路径是否存在
    if not os.path.isdir(root_dir):
        print(f"错误: 路径 '{root_dir}' 不存在或不是一个目录。请检查脚本中的 root_dir 变量。")
        return

    # 3. 遍历根目录
    for folder_name in os.listdir(root_dir):
        folder_path = os.path.join(root_dir, folder_name)

        # 4. 确保它是一个文件夹
        if os.path.isdir(folder_path):
            new_name_base = folder_name  # 新的文件名（不含扩展名）
            
            found_comic = False
            try:
                # 5. 遍历文件夹内部的文件
                for file_name in os.listdir(folder_path):
                    old_file_path = os.path.join(folder_path, file_name)
                    
                    # 6. 检查是否是文件，并且扩展名是我们想要的
                    if os.path.isfile(old_file_path) and file_name.lower().endswith(comic_extensions):
                        
                        # 7. 获取扩展名
                        file_ext = os.path.splitext(file_name)[1]
                        
                        # 8. 构造新文件名和路径
                        new_file_name = new_name_base + file_ext
                        new_file_path = os.path.join(folder_path, new_file_name)
                        
                        # 9. 检查新旧文件名是否相同
                        if old_file_path == new_file_path:
                            print(f"  [跳过] {folder_name} -> {new_file_name} (文件名已正确)")
                        else:
                            # 10. 执行重命名
                            os.rename(old_file_path, new_file_path)
                            print(f"  [成功] {folder_name}: {file_name} -> {new_file_name}")
                        
                        found_comic = True
                        # 假设每个文件夹下只有一个漫画文件，重命名后跳出内部循环
                        break
                        
                if not found_comic:
                    print(f"  [警告] 在 {folder_name} 中未找到漫画文件。")
                    
            except Exception as e:
                print(f"  [失败] 处理 {folder_name} 时出错: {e}")

    print("--- 批量重命名完成！ ---")

if __name__ == "__main__":
    # 设置编码为 UTF-8，防止Windows命令行输出乱码
    if sys.stdout.encoding != 'utf-8':
        sys.stdout.reconfigure(encoding='utf-8')
        
    rename_comics()