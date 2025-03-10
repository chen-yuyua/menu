import os
import fnmatch
import subprocess
import tkinter as tk
from tkinter import filedialog, Text, END, ttk
from tkinter import font
import win32com.client
import pythoncom
import threading
import re

# 全域常數
VERSION = "1.0"
APP_TITLE = f"進階檔案搜尋系統 v{VERSION}"

def resolve_shortcut(shortcut_path):
    """解析Windows捷徑(.lnk)檔案"""
    try:
        pythoncom.CoInitialize()  # 初始化COM環境
        shell = win32com.client.Dispatch("WScript.Shell")
        shortcut = shell.CreateShortCut(shortcut_path)
        target_path = shortcut.Targetpath
        pythoncom.CoUninitialize()  # 釋放COM環境
        return target_path if target_path else None
    except Exception as e:
        print(f"解析捷徑時發生錯誤: {e}")
        return None

def is_path_in_folder(path, folder):
    """檢查路徑是否在指定資料夾內或其子資料夾中"""
    # 規範化路徑以確保比較一致性
    norm_path = os.path.normpath(os.path.abspath(path))
    norm_folder = os.path.normpath(os.path.abspath(folder))

    # 檢查路徑是否為資料夾本身或其子資料夾
    return norm_path == norm_folder or norm_path.startswith(norm_folder + os.sep)

def search_files(keyword, folder_path, status_var):
    """搜尋資料夾內包含關鍵字的檔案，包括捷徑指向的資料夾
    僅搜尋指定資料夾及其子資料夾，捷徑目標也必須是由指定資料夾中的捷徑所指向
    """
    matches = {}
    processed_paths = set()  # 防止循環引用
    capture_shortcut_targets = {}  # 記錄捷徑來源與目標的對應關係
    global stop_search_flag  # 全域停止搜尋旗標
    stop_search_flag = False

    # 規範化資料夾路徑
    norm_folder_path = os.path.normpath(os.path.abspath(folder_path))

    # 要跳過的路徑
    skip_path = r"\\Apngo-olive\phcompany\部門横断プロジェクト"

    def is_in_folder_scope(path):
        """檢查路徑是否在母資料夾範圍內"""
        norm_path = os.path.normpath(os.path.abspath(path))
        # 檢查是否為母資料夾或其子資料夾
        return norm_path == norm_folder_path or norm_path.startswith(norm_folder_path + os.sep)

    def process_folder(path, is_shortcut_target=False, shortcut_source=""):
        """處理單個資料夾及其子目錄
        path: 要處理的資料夾路徑
        is_shortcut_target: 是否為捷徑目標
        shortcut_source: 如果是捷徑目標，則記錄來源捷徑路徑
        """
        nonlocal matches

        if stop_search_flag:
            return  # 檢查是否停止搜尋

        # 檢查是否包含要跳過的路徑
        if skip_path in path:
            status_var.set(f"跳過受限路徑: {path}")
            root.update_idletasks()
            return

        # 規範化路徑
        norm_path = os.path.normpath(os.path.abspath(path))

        # 檢查是否已處理過此路徑
        if norm_path in processed_paths:
            return

        # 記錄為已處理路徑
        processed_paths.add(norm_path)

        # 非捷徑目標時，檢查是否在母資料夾範圍內
        if not is_shortcut_target and not is_in_folder_scope(path):
            return

        # 捷徑目標，檢查來源是否在母資料夾範圍內
        if is_shortcut_target and shortcut_source and not is_in_folder_scope(shortcut_source):
            return

        try:
            # 更新狀態顯示
            status_var.set(f"正在搜尋: {path}")
            root.update_idletasks()

            # 僅在資料夾和檔案存在時進行搜尋
            if not os.path.exists(path):
                return

            for root_dir, dirs, files in os.walk(path):
                if stop_search_flag:
                    return  # 檢查是否停止搜尋

                # 檢查當前目錄是否包含要跳過的路徑
                if skip_path in root_dir:
                    # 跳過此目錄
                    dirs[:] = []  # 清空子目錄列表，防止進一步遍歷
                    continue

                # 處理檔案 - 搜尋檔名中包含關鍵字的檔案
                for filename in files:
                    if stop_search_flag:
                        return  # 檢查是否停止搜尋

                    if keyword.lower() in filename.lower():
                        full_path = os.path.normpath(os.path.join(root_dir, filename))

                        # 使用檔名+路徑作為唯一鍵，避免不同資料夾中同名檔案的衝突
                        result_key = filename
                        count = 1
                        while result_key in matches:
                            result_key = f"{filename} ({count})"
                            count += 1

                        # 儲存搜尋結果
                        matches[result_key] = full_path

                # 處理捷徑檔案
                for filename in files:
                    if stop_search_flag:
                        return  # 檢查是否停止搜尋

                    if filename.lower().endswith('.lnk'):
                        shortcut_path = os.path.join(root_dir, filename)

                        # 解析捷徑目標
                        target = resolve_shortcut(shortcut_path)
                        if target and os.path.isdir(target):
                            # 檢查捷徑目標是否包含要跳過的路徑
                            if skip_path in target:
                                continue

                            # 記錄捷徑來源與目標的對應關係
                            capture_shortcut_targets[target] = shortcut_path

                            # 處理捷徑目標資料夾
                            process_folder(target, True, shortcut_path)

        except PermissionError as e:
            status_var.set(f"權限錯誤: {path}")
            root.update_idletasks()
        except Exception as e:
            status_var.set(f"錯誤: {path} - {e}")
            root.update_idletasks()
            print(f"處理資料夾時發生錯誤: {e}")

    # 開始搜尋
    stop_search_flag = False  # 重置停止標記
    process_folder(folder_path)  # 從指定的母資料夾開始處理

    # 搜尋完成後更新狀態
    if stop_search_flag:
        status_var.set("搜尋已停止")
    else:
        status_var.set(f"搜尋完成，找到 {len(matches)} 個符合的檔案")

    return matches

def open_file(filepath):
    """開啟檔案"""
    try:
        if os.name == 'nt':  # Windows
            os.startfile(filepath)
        elif os.name == 'posix':  # macOS 或 Linux
            subprocess.call(['open' if os.sys.platform == 'darwin' else 'xdg-open', filepath])
    except Exception as e:
        status_var.set(f"無法開啟檔案: {e}")

def stop_search():
    """停止搜尋"""
    global stop_search_flag
    stop_search_flag = True
    status_var.set("正在停止搜尋...")
    # 啟用搜尋按鈕
    search_button.config(state=tk.NORMAL)
    # 禁用停止按鈕
    stop_button.config(state=tk.DISABLED)

def perform_search():
    """執行搜尋功能"""
    keyword = keyword_entry.get()
    folder_path = folder_path_entry.get()

    if not keyword or not folder_path:
        result_text.delete("1.0", END)
        result_text.insert(END, "請輸入關鍵字與資料夾路徑！\n", "warning")
        return

    # 檢查資料夾路徑是否存在
    if not os.path.isdir(folder_path):
        result_text.delete("1.0", END)
        result_text.insert(END, f"錯誤：資料夾路徑 '{folder_path}' 不存在！\n", "warning")
        return

    # 禁用搜尋按鈕，啟用停止按鈕
    search_button.config(state=tk.DISABLED)
    stop_button.config(state=tk.NORMAL)
    result_text.delete("1.0", END)
    result_text.insert(END, "搜尋中，請稍候...\n", "info")
    result_text.insert(END, f"搜尋資料夾: {folder_path}\n", "path")
    result_text.insert(END, f"關鍵字: {keyword}\n\n", "bold")
    root.update_idletasks()

    # 使用線程執行搜尋，避免UI凍結
    def search_thread():
        global file_mapping, stop_search_flag
        stop_search_flag = False  # 重置停止標記
        file_mapping = {}  # 清空先前的結果
        try:
            file_mapping = search_files(keyword, folder_path, status_var)
        except Exception as e:
            print(f"搜尋過程中發生錯誤: {e}")
            status_var.set(f"搜尋錯誤: {e}")

        # 在主線程中更新UI
        root.after(0, update_results)

    def update_results():
        result_text.delete("1.0", END)

        if file_mapping:
            result_text.insert(END, f"搜尋完成，找到 {len(file_mapping)} 個符合的檔案\n", "count")
            result_text.insert(END, f"搜尋資料夾: {folder_path}\n", "path")
            result_text.insert(END, f"關鍵字: {keyword}\n\n", "bold")

            # 按檔名排序
            sorted_files = sorted(file_mapping.items())
            for filename, fullpath in sorted_files:
                # 使用相對路徑顯示 (可選)
                try:
                    # 檢查是否能表示為相對於母資料夾的路徑
                    if os.path.abspath(fullpath).startswith(os.path.abspath(folder_path)):
                        rel_path = os.path.relpath(fullpath, folder_path)
                        if len(rel_path) < len(fullpath):
                            display_path = f"{folder_path}\\{rel_path}"
                        else:
                            display_path = fullpath
                    else:
                        display_path = fullpath
                except:
                    display_path = fullpath

                # 突顯關鍵字
                parts = re.split(f'({re.escape(keyword)})', filename, flags=re.IGNORECASE)

                result_text.insert(END, "📄 ", "icon")
                for i, part in enumerate(parts):
                    if i % 2 == 1:  # 關鍵字部分
                        result_text.insert(END, part, "highlight")
                    else:
                        result_text.insert(END, part, "bold")

                result_text.insert(END, "\n")
                result_text.insert(END, f"  📂 {display_path}\n\n", "path")
        else:
            result_text.insert(END, "找不到相關檔案！\n\n", "warning")
            result_text.insert(END, f"搜尋資料夾: {folder_path}\n", "path")
            result_text.insert(END, f"關鍵字: {keyword}\n", "bold")

        # 重新啟用搜尋按鈕，禁用停止按鈕
        search_button.config(state=tk.NORMAL)
        stop_button.config(state=tk.DISABLED)

    # 啟動搜尋線程
    threading.Thread(target=search_thread, daemon=True).start()

def browse_folder():
    """瀏覽資料夾"""
    folder_path = filedialog.askdirectory()
    if folder_path:
        folder_path_entry.delete(0, END)
        folder_path_entry.insert(0, folder_path)

def on_file_select(event):
    """點擊檔案開啟"""
    try:
        cursor_position = result_text.index(tk.CURRENT)
        # 解析目前行號
        line_start = cursor_position.split('.')[0]

        # 獲取點擊行的文字
        line_text = result_text.get(f"{line_start}.0", f"{line_start}.end")

        if line_text.startswith("📄 "):
            # 獲取檔名
            filename = line_text[2:].strip()
            # 查找對應的路徑
            for fname, path in file_mapping.items():
                if filename.startswith(fname):
                    open_file(path)
                    break
    except Exception as e:
        status_var.set(f"點擊檔案時發生錯誤: {e}")
        print(f"點擊檔案時發生錯誤: {e}")

def create_tooltip(widget, text):
    """建立工具提示"""
    def enter(event):
        x, y, _, _ = widget.bbox("insert")
        x += widget.winfo_rootx() + 25
        y += widget.winfo_rooty() + 25

        # 建立工具提示視窗
        tooltip = tk.Toplevel(widget)
        tooltip.wm_overrideredirect(True)
        tooltip.wm_geometry(f"+{x}+{y}")

        label = tk.Label(tooltip, text=text, background="#FFFFDD", relief="solid", borderwidth=1)
        label.pack()

        widget.tooltip = tooltip

    def leave(event):
        if hasattr(widget, "tooltip"):
            widget.tooltip.destroy()

    widget.bind("<Enter>", enter)
    widget.bind("<Leave>", leave)

def show_about_dialog():
    """顯示關於對話框"""
    about_window = tk.Toplevel(root)
    about_window.title(f"關於 {APP_TITLE}")
    about_window.geometry("400x300")
    about_window.resizable(False, False)
    about_window.configure(bg="#FFFFFF")
    about_window.transient(root)  # 設為主視窗的子視窗

    # 設置視窗置中
    about_window.geometry("+%d+%d" % (
        root.winfo_rootx() + (root.winfo_width() // 2) - (400 // 2),
        root.winfo_rooty() + (root.winfo_height() // 2) - (300 // 2)
    ))

    # 頂部標題
    tk.Label(
        about_window,
        text=f"進階檔案搜尋系統",
        font=("微軟正黑體", 16, "bold"),
        bg="#FFFFFF",
        fg=primary_color,
        pady=10
    ).pack()

    # 版本資訊
    tk.Label(
        about_window,
        text=f"版本：{VERSION}",
        font=("微軟正黑體", 12),
        bg="#FFFFFF",
        fg=text_color,
        pady=5
    ).pack()

    # 分隔線
    separator = ttk.Separator(about_window, orient="horizontal")
    separator.pack(fill="x", padx=20, pady=10)

    # 功能說明
    feature_frame = tk.Frame(about_window, bg="#FFFFFF", padx=20)
    feature_frame.pack(fill="both", expand=True)

    features = [
        "✓ 檔案關鍵字搜尋",
        "✓ 支援捷徑資料夾的遞迴搜尋",
        "✓ 自動跳過受限路徑",
        "✓ 可隨時停止搜尋",
        "✓ 簡潔美觀的使用者介面"
    ]

    for feature in features:
        tk.Label(
            feature_frame,
            text=feature,
            font=("微軟正黑體", 10),
            bg="#FFFFFF",
            fg=text_color,
            anchor="w",
            pady=2
        ).pack(fill="x")

    # 分隔線
    separator2 = ttk.Separator(about_window, orient="horizontal")
    separator2.pack(fill="x", padx=20, pady=10)

    # 版本歷史
    tk.Label(
        about_window,
        text="版本歷史：",
        font=("微軟正黑體", 10, "bold"),
        bg="#FFFFFF",
        fg=text_color,
        anchor="w",
        padx=20
    ).pack(fill="x")

    tk.Label(
        about_window,
        text="v1.0 - 初始版本",
        font=("微軟正黑體", 9),
        bg="#FFFFFF",
        fg="#666666",
        anchor="w",
        padx=30
    ).pack(fill="x")

    # 底部按鈕
    btn_frame = tk.Frame(about_window, bg="#FFFFFF", pady=10)
    btn_frame.pack(fill="x")

    ttk.Button(
        btn_frame,
        text="確定",
        command=about_window.destroy,
        style="TButton",
        width=10
    ).pack()

def clear_results():
    """清除搜尋結果"""
    result_text.delete("1.0", END)
    result_text.insert(END, f"歡迎使用進階檔案搜尋系統 v{VERSION}\n\n", "info")
    result_text.insert(END, "1. 輸入檔案關鍵字\n")
    result_text.insert(END, "2. 選擇要搜尋的資料夾\n")
    result_text.insert(END, "3. 點擊「開始搜尋」按鈕\n\n")
    result_text.insert(END, "✨ 本系統支援捷徑資料夾的遞迴搜尋，可深入探索資料夾最底層 ✨\n", "highlight")

# 建立 GUI 主視窗
root = tk.Tk()
root.title(APP_TITLE)
root.geometry("800x600")
root.configure(bg="#F4F7FC")

# 設定主題色彩
primary_color = "#4A6FE3"  # 藍色
secondary_color = "#E3EAF6"  # 淺藍灰色
accent_color = "#6BCB77"  # 綠色
text_color = "#2D3748"  # 深灰色

# 設定 grid 權重，讓結果顯示區隨視窗大小變動
root.grid_rowconfigure(4, weight=1)
root.grid_columnconfigure(0, weight=0)
root.grid_columnconfigure(1, weight=5)
root.grid_columnconfigure(2, weight=0)

# 建立自定義的字型
title_font = font.Font(family="微軟正黑體", size=14, weight="bold")
label_font = font.Font(family="微軟正黑體", size=10)
button_font = font.Font(family="微軟正黑體", size=10, weight="bold")
result_font = font.Font(family="微軟正黑體", size=10)
bold_font = font.Font(family="微軟正黑體", size=10, weight="bold")
path_font = font.Font(family="微軟正黑體", size=9)

# 建立選單欄
menu_bar = tk.Menu(root)
root.config(menu=menu_bar)

# 檔案選單
file_menu = tk.Menu(menu_bar, tearoff=0)
menu_bar.add_cascade(label="檔案", menu=file_menu)
file_menu.add_command(label="開啟資料夾", command=browse_folder)
file_menu.add_separator()
file_menu.add_command(label="離開", command=root.quit)

# 工具選單
tools_menu = tk.Menu(menu_bar, tearoff=0)
menu_bar.add_cascade(label="工具", menu=tools_menu)
tools_menu.add_command(label="清除搜尋結果", command=clear_results)

# 幫助選單
help_menu = tk.Menu(menu_bar, tearoff=0)
menu_bar.add_cascade(label="幫助", menu=help_menu)
help_menu.add_command(label="關於", command=show_about_dialog)

# 創建樣式
style = ttk.Style()
style.theme_use('clam')  # 使用clam主題作為基礎

# 配置樣式
style.configure("TEntry", padding=8, relief="flat", background=secondary_color)
style.configure("TButton",
                font=button_font,
                padding=8,
                relief="flat",
                background=primary_color,
                foreground="white")
style.map("TButton",
          background=[("active", primary_color), ("pressed", "#3A5FC3")],
          foreground=[("active", "white"), ("pressed", "white")])

style.configure("Search.TButton",
                font=button_font,
                padding=8,
                relief="flat",
                background=accent_color,
                foreground="white")
style.map("Search.TButton",
          background=[("active", accent_color), ("pressed", "#5ABB67")],
          foreground=[("active", "white"), ("pressed", "white")])

style.configure("Stop.TButton",
                font=button_font,
                padding=8,
                relief="flat",
                background="#E74C3C",
                foreground="white")
style.map("Stop.TButton",
          background=[("active", "#E74C3C"), ("pressed", "#C0392B")],
          foreground=[("active", "white"), ("pressed", "white")])

# 標題區域
header_frame = tk.Frame(root, bg="#F4F7FC", pady=10)
header_frame.grid(row=0, column=0, columnspan=3, sticky="ew")

header_label = tk.Label(
    header_frame,
    text=f"📁 {APP_TITLE}",
    font=title_font,
    bg="#F4F7FC",
    fg=primary_color
)
header_label.pack()

# 創建主體框架
main_frame = tk.Frame(root, bg="#F4F7FC", padx=20, pady=10)
main_frame.grid(row=1, column=0, columnspan=3, sticky="ew")

# 關鍵字輸入區
keyword_label = tk.Label(
    main_frame,
    text="關鍵字:",
    font=label_font,
    bg="#F4F7FC",
    fg=text_color,
    pady=5
)
keyword_label.grid(row=0, column=0, padx=5, pady=5, sticky='e')

keyword_entry = ttk.Entry(main_frame, width=50, font=label_font)
keyword_entry.grid(row=0, column=1, padx=5, pady=5, sticky='ew')
create_tooltip(keyword_entry, "輸入要搜尋的檔案關鍵字")

# 資料夾路徑輸入區
folder_label = tk.Label(
    main_frame,
    text="資料夾路徑:",
    font=label_font,
    bg="#F4F7FC",
    fg=text_color,
    pady=5
)
folder_label.grid(row=1, column=0, padx=5, pady=5, sticky='e')

folder_path_entry = ttk.Entry(main_frame, width=50, font=label_font)
folder_path_entry.grid(row=1, column=1, padx=5, pady=5, sticky='ew')
folder_path_entry.insert(0, "U:\\TDD\\メカ\\教育")  # 預設資料夾路徑
create_tooltip(folder_path_entry, "選擇要搜尋的資料夾路徑")

browse_button = ttk.Button(
    main_frame,
    text="瀏覽",
    command=browse_folder,
    style="TButton"
)
browse_button.grid(row=1, column=2, padx=5, pady=5)

# 設定列權重以允許輸入框擴展
main_frame.grid_columnconfigure(1, weight=1)

# 按鈕區域
button_frame = tk.Frame(root, bg="#F4F7FC", pady=10)
button_frame.grid(row=2, column=0, columnspan=3, sticky="ew")

# 建立按鈕容器，並排
button_container = tk.Frame(button_frame, bg="#F4F7FC")
button_container.pack()

# 搜尋按鈕
search_button = ttk.Button(
    button_container,
    text="開始搜尋",
    command=perform_search,
    style="Search.TButton"
)
search_button.pack(side=tk.LEFT, padx=5)

# 停止按鈕
stop_button = ttk.Button(
    button_container,
    text="停止搜尋",
    command=stop_search,
    style="Stop.TButton",
    state=tk.DISABLED  # 初始時禁用
)
stop_button.pack(side=tk.LEFT, padx=5)

# 狀態顯示
status_frame = tk.Frame(root, bg="#F4F7FC")
status_frame.grid(row=3, column=0, columnspan=3, sticky="ew", padx=20)

status_var = tk.StringVar()
status_var.set("就緒")
status_label = tk.Label(
    status_frame,
    textvariable=status_var,
    bg="#F4F7FC",
    fg="#666666",
    font=path_font,
    anchor='w'
)
status_label.pack(fill="x")

# 結果顯示區 - 使用 Frame 包含 Text 與 Scrollbar，並設定隨視窗大小變動
result_frame = tk.Frame(root, bg="#F4F7FC", padx=20, pady=10)
result_frame.grid(row=4, column=0, columnspan=3, sticky="nsew")

# 創建帶有邊框的容器
text_container = tk.Frame(
    result_frame,
    bg="white",
    highlightbackground="#DDDDDD",
    highlightthickness=1
)
text_container.pack(fill="both", expand=True)

result_text = Text(
    text_container,
    bg="white",
    fg=text_color,
    font=result_font,
    wrap="word",
    padx=10,
    pady=10,
    borderwidth=0,
    highlightthickness=0
)
result_text.pack(side="left", fill="both", expand=True)

scrollbar = ttk.Scrollbar(text_container, orient="vertical", command=result_text.yview)
scrollbar.pack(side="right", fill="y")

result_text.config(yscrollcommand=scrollbar.set)

# 配置文字標籤
result_text.tag_configure("bold", font=bold_font)
result_text.tag_configure("path", font=path_font, foreground="#666666")
result_text.tag_configure("info", foreground="#3498db")
result_text.tag_configure("warning", foreground="#e74c3c")
result_text.tag_configure("count", font=bold_font, foreground=primary_color)
result_text.tag_configure("highlight", background="#FFF2CC", font=bold_font)
result_text.tag_configure("icon", foreground=primary_color)

# 綁定文字點擊事件
result_text.bind("<Button-1>", on_file_select)

# 底部版本和版權信息
footer_frame = tk.Frame(root, bg="#F4F7FC", pady=5)
footer_frame.grid(row=5, column=0, columnspan=3, sticky="ew")

version_label = tk.Label(
    footer_frame,
    text=f"版本 {VERSION} | 開發者：Claude",
    font=("微軟正黑體", 8),
    bg="#F4F7FC",
    fg="#999999",
    cursor="hand2"  # 滑鼠變成手指形狀
)
version_label.pack(side=tk.RIGHT, padx=10)
version_label.bind("<Button-1>", lambda e: show_about_dialog())

# 全域變數
file_mapping = {}  # 檔名 -> 完整路徑
stop_search_flag = False  # 停止搜尋標記

# 初始顯示訊息
result_text.insert(END, f"歡迎使用進階檔案搜尋系統 v{VERSION}\n\n", "info")
result_text.insert(END, "1. 輸入檔案關鍵字\n")
result_text.insert(END, "2. 選擇要搜尋的資料夾\n")
result_text.insert(END, "3. 點擊「開始搜尋」按鈕\n\n")
result_text.insert(END, "✨ 本系統支援捷徑資料夾的遞迴搜尋，可深入探索資料夾最底層 ✨\n", "highlight")
result_text.insert(END, "📋 版本說明：\n", "bold")
result_text.insert(END, "v1.0 - 初始版本：檔案關鍵字搜尋、支援捷徑資料夾\n", "path")

# 啟動主視窗
root.mainloop()
