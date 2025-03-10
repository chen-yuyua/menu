import os
import fnmatch
import subprocess
import tkinter as tk
from tkinter import filedialog, Text, END
from tkinter import font

def search_files(keyword, folder_path):
    """搜尋資料夾內包含關鍵字的檔案"""
    matches = {}
    for root, dirs, files in os.walk(folder_path):
        for filename in fnmatch.filter(files, f"*{keyword}*"):
            full_path = os.path.normpath(os.path.join(root, filename))
            matches[filename] = full_path
    return matches

def open_file(filepath):
    """開啟檔案"""
    try:
        if os.name == 'nt':  # Windows
            os.startfile(filepath)
        elif os.name == 'posix':  # macOS 或 Linux
            subprocess.call(['open' if os.sys.platform == 'darwin' else 'xdg-open', filepath])
    except Exception as e:
        print(f"無法開啟檔案: {e}")

def perform_search():
    """執行搜尋功能"""
    keyword = keyword_entry.get()
    folder_path = folder_path_entry.get()

    if not keyword or not folder_path:
        result_text.delete("1.0", END)
        result_text.insert(END, "請輸入關鍵字與資料夾路徑！\n")
        return

    global file_mapping
    file_mapping = search_files(keyword, folder_path)
    result_text.delete("1.0", END)

    if file_mapping:
        for filename, fullpath in file_mapping.items():
            result_text.insert(END, filename + "\n", "bold")  # 檔名用粗體
            result_text.insert(END, f"  -> {fullpath}\n", "gray")  # 路徑用淺灰色
    else:
        result_text.insert(END, "找不到相關檔案！\n")

def browse_folder():
    """瀏覽資料夾"""
    folder_path = filedialog.askdirectory()
    folder_path_entry.delete(0, END)
    folder_path_entry.insert(0, folder_path)

def on_file_select(event):
    """點擊檔案開啟"""
    cursor_position = result_text.index(tk.CURRENT)
    selected_line = result_text.get(f"{cursor_position} linestart", f"{cursor_position} lineend").strip()
    if selected_line in file_mapping:  # 確保選中的是檔名
        open_file(file_mapping[selected_line])

# 建立 GUI 主視窗
root = tk.Tk()
root.title("檔案搜尋系統")
root.configure(bg="#f0f8ff")  # 使用柔和的淺藍色背景

# 設定 grid 權重，讓結果顯示區隨視窗大小變動
root.grid_rowconfigure(3, weight=1)
root.grid_columnconfigure(0, weight=1)
root.grid_columnconfigure(1, weight=1)
root.grid_columnconfigure(2, weight=1)

# 字型設定，改用柔和且現代的 Helvetica 字型
bold_font = font.Font(root, family="Helvetica", weight="bold", size=10)
gray_font = font.Font(root, family="Helvetica", size=10)

# 關鍵字輸入區
tk.Label(root, text="關鍵字:", bg="#f0f8ff", fg="#333333").grid(row=0, column=0, padx=5, pady=5, sticky='e')
keyword_entry = tk.Entry(root, width=40, bg="#ffffff")
keyword_entry.grid(row=0, column=1, padx=5, pady=5)

# 資料夾路徑輸入區
tk.Label(root, text="資料夾路徑:", bg="#f0f8ff", fg="#333333").grid(row=1, column=0, padx=5, pady=5, sticky='e')
folder_path_entry = tk.Entry(root, width=40, bg="#ffffff")
folder_path_entry.grid(row=1, column=1, padx=5, pady=5)
folder_path_entry.insert(0, "U:\\TDD\\メカ\\教育")  # 預設資料夾路徑

browse_button = tk.Button(root, text="瀏覽", command=browse_folder, bg="#ADD8E6", relief="flat")
browse_button.grid(row=1, column=2, padx=5, pady=5)

# 搜尋按鈕
search_button = tk.Button(root, text="搜尋", command=perform_search, bg="#90EE90", relief="flat")
search_button.grid(row=2, column=1, pady=10)

# 結果顯示區 - 使用 Frame 包含 Text 與 Scrollbar，並設定隨視窗大小變動
result_frame = tk.Frame(root, bg="#f0f8ff")
result_frame.grid(row=3, column=0, columnspan=3, padx=5, pady=5, sticky="nsew")

result_text = Text(result_frame, bg="#ffffff")
result_text.pack(side="left", fill="both", expand=True)

scrollbar = tk.Scrollbar(result_frame, orient="vertical", command=result_text.yview)
scrollbar.pack(side="right", fill="y")

result_text.config(yscrollcommand=scrollbar.set)
result_text.tag_configure("bold", font=bold_font)
result_text.tag_configure("gray", font=gray_font, foreground="gray")
result_text.bind("<Double-1>", on_file_select)

# 全域檔案映射（用來記錄搜尋結果：檔名 -> 完整路徑）
file_mapping = {}

root.mainloop()
