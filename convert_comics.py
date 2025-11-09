import os
import rarfile
import zipfile

# ==============================================================================
# 请在此处修改您要转换的 RAR 文件所在的文件夹路径
# ==============================================================================
TARGET_FOLDER_PATH = r"E:\Downloads\【蓝色狂想】名侦探柯南漫画单行版1-64卷"
# ==============================================================================

def convert_rar_to_zip(folder_path):
    """
    Converts all RAR files in the specified folder to ZIP files,
    keeping the original RAR files.
    """
    if not os.path.isdir(folder_path):
        print(f"Error: Folder '{folder_path}' not found.")
        return

    print(f"Scanning folder: {folder_path}")
    converted_count = 0

    for filename in os.listdir(folder_path):
        if filename.lower().endswith(".rar"):
            rar_filepath = os.path.join(folder_path, filename)
            zip_filename = os.path.splitext(filename)[0] + ".zip"
            zip_filepath = os.path.join(folder_path, zip_filename)

            if os.path.exists(zip_filepath):
                print(f"Skipping '{filename}': '{zip_filename}' already exists.")
                continue

            try:
                print(f"Converting '{filename}' to '{zip_filename}'...")
                with rarfile.RarFile(rar_filepath, 'r') as rf:
                    with zipfile.ZipFile(zip_filepath, 'w', zipfile.ZIP_DEFLATED) as zf:
                        for item in rf.infolist():
                            # Skip directories
                            if item.isdir():
                                continue
                            # Read content from RAR and write to ZIP
                            with rf.open(item.filename) as r_file:
                                zf.writestr(item.filename, r_file.read())
                print(f"Successfully converted '{filename}'.")
                converted_count += 1
            except rarfile.BadRarFile:
                print(f"Error: '{filename}' is a bad or corrupted RAR file. Skipping.")
            except Exception as e:
                print(f"An unexpected error occurred while processing '{filename}': {e}")

    print(f"\nConversion complete. Converted {converted_count} RAR files to ZIP.")

if __name__ == "__main__":
    convert_rar_to_zip(TARGET_FOLDER_PATH)