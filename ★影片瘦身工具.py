import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import subprocess
import threading
import os
import shutil

class BatchVideoCompressorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("通用影片批量瘦身工具 Ver.1.2 (支援 MOV, AVI, MKV...)")
        self.root.geometry("700x580")

        # 設定樣式
        self.style = ttk.Style()
        self.style.theme_use('clam')
        self.style.configure('TButton', font=('微軟正黑體', 10))
        self.style.configure('TLabel', font=('微軟正黑體', 10))
        self.style.configure('Treeview', font=('微軟正黑體', 10), rowheight=25)
        self.style.configure('Treeview.Heading', font=('微軟正黑體', 10, 'bold'))

        # 初始化變數
        self.ffmpeg_path = None
        self.file_list = [] # 儲存 (file_path, item_id)
        self.is_running = False

        # 檢查 FFmpeg
        if not self.check_ffmpeg():
            messagebox.showerror("錯誤", "找不到 FFmpeg！\n\n請將 ffmpeg.exe 放在此程式同一資料夾內，\n或者確認已安裝並設定環境變數。")
            self.root.destroy()
            return

        self.create_widgets()

    def check_ffmpeg(self):
        """檢查系統中是否有 FFmpeg，並設定正確路徑"""
        try:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            local_ffmpeg = os.path.join(current_dir, "ffmpeg.exe")
            if os.path.exists(local_ffmpeg):
                self.ffmpeg_path = local_ffmpeg
                return True
        except Exception:
            pass

        if shutil.which("ffmpeg"):
            self.ffmpeg_path = "ffmpeg"
            return True
        return False

    def create_widgets(self):
        # --- 頂部操作區 ---
        frame_top = tk.Frame(self.root, pady=10)
        frame_top.pack(fill="x", padx=15)

        btn_add = ttk.Button(frame_top, text="+ 加入影片 (支援多種格式)", command=self.add_files)
        btn_add.pack(side="left", padx=5)

        btn_clear = ttk.Button(frame_top, text="清空列表", command=self.clear_list)
        btn_clear.pack(side="left", padx=5)

        # --- 中間列表區 (Treeview) ---
        frame_list = tk.Frame(self.root)
        frame_list.pack(fill="both", expand=True, padx=15, pady=5)

        # 定義欄位
        columns = ("filename", "size", "status")
        self.tree = ttk.Treeview(frame_list, columns=columns, show="headings", selectmode="browse")

        # 設定標題
        self.tree.heading("filename", text="檔案名稱")
        self.tree.heading("size", text="原始大小")
        self.tree.heading("status", text="狀態")

        # 設定欄寬
        self.tree.column("filename", width=400)
        self.tree.column("size", width=100, anchor="center")
        self.tree.column("status", width=100, anchor="center")

        # 捲動軸
        scrollbar = ttk.Scrollbar(frame_list, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # --- 底部設定與執行區 ---
        frame_bottom = tk.LabelFrame(self.root, text="壓縮設定與執行", font=('微軟正黑體', 11), padx=10, pady=10)
        frame_bottom.pack(fill="x", padx=15, pady=15)

        # 壓縮品質滑桿
        frame_slider = tk.Frame(frame_bottom)
        frame_slider.pack(fill="x", pady=5)

        tk.Label(frame_slider, text="畫質設定 (CRF):", font=('微軟正黑體', 10, 'bold')).pack(side="left")

        self.crf_var = tk.IntVar(value=28)
        self.slider = ttk.Scale(frame_slider, from_=18, to=40, variable=self.crf_var, command=self.update_crf_label)
        self.slider.pack(side="left", fill="x", expand=True, padx=15)

        self.lbl_crf_val = tk.Label(frame_slider, text=f"28 (建議)", font=('微軟正黑體', 10, 'bold'), width=10)
        self.lbl_crf_val.pack(side="left")

        tk.Label(frame_bottom, text="數值越大 = 檔案越小但畫質越差 (建議範圍 24-30)", fg="gray", font=('微軟正黑體', 9)).pack(anchor="w", pady=(0, 10))

        # 進度條與按鈕
        self.progress = ttk.Progressbar(frame_bottom, mode='determinate')
        self.progress.pack(fill="x", pady=5)

        self.btn_run = ttk.Button(frame_bottom, text="開始批量轉換與壓縮", command=self.start_batch_processing)
        self.btn_run.pack(pady=5, ipadx=30, ipady=5)

        self.lbl_msg = tk.Label(frame_bottom, text="準備就緒", fg="blue")
        self.lbl_msg.pack()

        # --- 作者資訊 ---
        lbl_author = tk.Label(self.root, text="Ver.1.2 | 作成者: chenyw", fg="gray", font=('微軟正黑體', 8))
        lbl_author.pack(side="bottom", pady=5)

    def update_crf_label(self, val):
        v = int(float(val))
        self.lbl_crf_val.config(text=f"{v}")

    def format_size(self, size_bytes):
        return f"{size_bytes / (1024*1024):.1f} MB"

    def add_files(self):
        if self.is_running:
            return

        filetypes = [
            ("Video files", "*.mp4 *.mov *.avi *.mkv *.wmv *.flv *.webm"),
            ("All files", "*.*")
        ]

        files = filedialog.askopenfilenames(filetypes=filetypes)
        for f in files:
            if any(existing_file[0] == f for existing_file in self.file_list):
                continue

            try:
                size = os.path.getsize(f)
                size_str = self.format_size(size)
            except:
                size_str = "未知"

            item_id = self.tree.insert("", "end", values=(os.path.basename(f), size_str, "等待中"))
            self.file_list.append((f, item_id))

        self.lbl_msg.config(text=f"目前共有 {len(self.file_list)} 個檔案等待處理")

    def clear_list(self):
        if self.is_running:
            messagebox.showwarning("警告", "正在執行壓縮中，無法清空列表。")
            return

        self.tree.delete(*self.tree.get_children())
        self.file_list = []
        self.lbl_msg.config(text="列表已清空")
        self.progress['value'] = 0

    def start_batch_processing(self):
        if not self.file_list:
            messagebox.showinfo("提示", "請先加入影片檔案！")
            return

        if self.is_running:
            return

        self.is_running = True
        self.btn_run.config(state="disabled")
        self.slider.config(state="disabled")

        threading.Thread(target=self.run_process_loop, daemon=True).start()

    def run_process_loop(self):
        total_files = len(self.file_list)
        crf_value = int(self.crf_var.get())

        # 初始化覆蓋偏好 (None: 尚未選擇, True: 全部覆蓋, False: 全部自動更名)
        overwrite_mode = None

        for index, (file_path, item_id) in enumerate(self.file_list):
            self.root.after(0, lambda i=item_id: self.tree.set(i, "status", "處理中..."))
            self.root.after(0, lambda idx=index: self.lbl_msg.config(text=f"正在處理第 {idx+1}/{total_files} 個檔案..."))

            dir_name = os.path.dirname(file_path)
            file_name = os.path.basename(file_path)
            name, _ = os.path.splitext(file_name)

            # 預設輸出檔名
            default_output_file = os.path.join(dir_name, f"{name}_compressed.mp4")
            final_output_file = default_output_file

            # --- 檢查檔案是否存在 (套用模式) ---
            if os.path.exists(final_output_file):
                should_overwrite = False

                # 如果已經有偏好，直接套用
                if overwrite_mode is not None:
                    should_overwrite = overwrite_mode
                else:
                    # 第一次遇到衝突，詢問使用者
                    should_overwrite = messagebox.askyesno(
                        "檔案重複確認",
                        f"檔案已存在：\n{os.path.basename(final_output_file)}\n\n是否覆蓋該檔案？\n\n(注意：此選擇將自動套用於本次所有重複檔名)\n\n選擇「是」：全部覆蓋舊檔\n選擇「否」：全部自動更名",
                        parent=self.root
                    )
                    # 記錄選擇
                    overwrite_mode = should_overwrite

                if not should_overwrite:
                    # 自動更名邏輯: _compressed_1, _compressed_2...
                    counter = 1
                    base_path = os.path.join(dir_name, f"{name}_compressed")
                    while os.path.exists(final_output_file):
                        final_output_file = f"{base_path}_{counter}.mp4"
                        counter += 1

            # 執行壓縮
            cmd = [
                self.ffmpeg_path,
                "-i", file_path,
                "-vcodec", "libx264",
                "-crf", str(crf_value),
                "-y",
                final_output_file
            ]

            success = False
            try:
                startupinfo = None
                if os.name == 'nt':
                    startupinfo = subprocess.STARTUPINFO()
                    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

                process = subprocess.run(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    startupinfo=startupinfo
                )
                if process.returncode == 0:
                    success = True
            except Exception:
                success = False

            status_text = "完成" if success else "失敗"
            self.root.after(0, lambda i=item_id, s=status_text: self.tree.set(i, "status", s))

            progress_val = ((index + 1) / total_files) * 100
            self.root.after(0, lambda v=progress_val: self.progress.configure(value=v))

        self.root.after(0, self.finish_batch)

    def finish_batch(self):
        self.is_running = False
        self.btn_run.config(state="normal")
        self.slider.config(state="normal")
        self.lbl_msg.config(text="所有作業已完成！", fg="green")
        messagebox.showinfo("完成", "所有影片已處理完畢！\n輸出檔案統一為 MP4 格式。")

if __name__ == "__main__":
    root = tk.Tk()
    app = BatchVideoCompressorApp(root)
    root.mainloop()