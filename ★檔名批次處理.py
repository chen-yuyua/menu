import tkinter as tk
import tkinter.font
from tkinter import ttk, filedialog, messagebox, scrolledtext
import os
import re
from pathlib import Path

class BatchRenameApp:
    def __init__(self, root):
        self.root = root
        self.root.title("批次檔名變更工具 - Ver.1.0")
        self.root.geometry("850x650")

        # 版本資訊
        self.version = "Ver.1.0"
        self.update_date = "2025/10/18"

        # 日系柔和風格色彩配置
        self.colors = {
            'bg_main': '#F8F4F0',      # 溫暖的米白色
            'bg_secondary': '#E8E2D5',  # 淺米色
            'accent': '#D4B5A0',       # 溫暖的卡其色
            'button': '#C8A882',       # 淺棕色
            'button_hover': '#B8986E', # 深一點的棕色
            'text': '#2C2C2C',         # 深灰黑色
            'success': '#8FBC8F',      # 淺綠色
            'warning': '#DDA0A0',      # 淺紅色
            'version_text': '#8B8B8B'  # 版本資訊灰色
        }

        # 設定主背景色
        self.root.configure(bg=self.colors['bg_main'])

        # 字型設定
        try:
            self.font_family = "BIZ UDPゴシック"
            test_font = tkinter.font.Font(family=self.font_family)
        except:
            self.font_family = "Microsoft JhengHei"

        self.fonts = {
            'title': (self.font_family, 16, 'bold'),
            'normal': (self.font_family, 10),
            'button': (self.font_family, 11),
            'small': (self.font_family, 9),
            'version': (self.font_family, 8)
        }

        self.selected_folder = ""
        self.files_list = []

        self.setup_ui()

    def setup_ui(self):
        # 頂部容器（標題和版本資訊）
        top_container = tk.Frame(self.root, bg=self.colors['bg_main'])
        top_container.pack(fill='x', pady=(20, 10))

        # 主標題（左側）
        title_frame = tk.Frame(top_container, bg=self.colors['bg_main'])
        title_frame.pack(side='left', fill='both', expand=True)

        title_label = tk.Label(
            title_frame,
            text="📁 批次檔名變更工具",
            font=self.fonts['title'],
            fg=self.colors['text'],
            bg=self.colors['bg_main']
        )
        title_label.pack(anchor='w', padx=(30, 0))

        # 版本資訊（右側）
        version_frame = tk.Frame(top_container, bg=self.colors['bg_main'])
        version_frame.pack(side='right', padx=(0, 30))

        version_label = tk.Label(
            version_frame,
            text=self.version,
            font=self.fonts['version'],
            fg=self.colors['version_text'],
            bg=self.colors['bg_main']
        )
        version_label.pack(anchor='e')

        update_label = tk.Label(
            version_frame,
            text=f"更新日期: {self.update_date}",
            font=self.fonts['version'],
            fg=self.colors['version_text'],
            bg=self.colors['bg_main']
        )
        update_label.pack(anchor='e')

        # 主容器
        main_frame = tk.Frame(self.root, bg=self.colors['bg_main'])
        main_frame.pack(fill='both', expand=True, padx=30, pady=(0, 10))

        # 資料夾選擇區域
        folder_frame = tk.LabelFrame(
            main_frame,
            text="📂 選擇資料夾",
            font=self.fonts['normal'],
            fg=self.colors['text'],
            bg=self.colors['bg_secondary'],
            relief='flat',
            bd=2
        )
        folder_frame.pack(fill='x', pady=(0, 15))

        folder_inner = tk.Frame(folder_frame, bg=self.colors['bg_secondary'])
        folder_inner.pack(fill='x', padx=15, pady=10)

        self.folder_var = tk.StringVar(value="尚未選擇資料夾...")
        folder_label = tk.Label(
            folder_inner,
            textvariable=self.folder_var,
            font=self.fonts['normal'],
            fg=self.colors['text'],
            bg=self.colors['bg_secondary'],
            anchor='w'
        )
        folder_label.pack(side='left', fill='x', expand=True)

        select_button = self.create_rounded_button(
            folder_inner,
            "選擇資料夾",
            self.select_folder,
            width=12
        )
        select_button.pack(side='right', padx=(10, 0))

        # 檔案列表區域
        files_frame = tk.LabelFrame(
            main_frame,
            text="📄 檔案列表",
            font=self.fonts['normal'],
            fg=self.colors['text'],
            bg=self.colors['bg_secondary'],
            relief='flat',
            bd=2
        )
        files_frame.pack(fill='both', expand=True, pady=(0, 15))

        # 檔案列表文字區域
        self.files_text = scrolledtext.ScrolledText(
            files_frame,
            height=8,
            font=self.fonts['small'],
            fg=self.colors['text'],
            bg='#FFFFFF',
            relief='flat',
            bd=1,
            state='disabled'
        )
        self.files_text.pack(fill='both', expand=True, padx=15, pady=10)

        # 檔名變更設定區域
        rename_frame = tk.LabelFrame(
            main_frame,
            text="✏️ 檔名變更設定",
            font=self.fonts['normal'],
            fg=self.colors['text'],
            bg=self.colors['bg_secondary'],
            relief='flat',
            bd=2
        )
        rename_frame.pack(fill='x', pady=(0, 15))

        rename_inner = tk.Frame(rename_frame, bg=self.colors['bg_secondary'])
        rename_inner.pack(fill='x', padx=15, pady=10)

        # 範例顯示
        example_frame = tk.Frame(rename_inner, bg=self.colors['bg_secondary'])
        example_frame.pack(fill='x', pady=(0, 10))

        example_label = tk.Label(
            example_frame,
            text="例: ",
            font=self.fonts['normal'],
            fg=self.colors['text'],
            bg=self.colors['bg_secondary']
        )
        example_label.pack(side='left')

        self.example_var = tk.StringVar(value="YYYY2025005_01")
        example_display = tk.Label(
            example_frame,
            textvariable=self.example_var,
            font=self.fonts['normal'],
            fg='#1E90FF',  # 藍色
            bg=self.colors['bg_secondary']
        )
        example_display.pack(side='left')

        # 檔名和帳號輸入
        input_frame = tk.Frame(rename_inner, bg=self.colors['bg_secondary'])
        input_frame.pack(fill='x', pady=(0, 10))

        # 檔名輸入
        filename_label = tk.Label(
            input_frame,
            text="檔名:",
            font=self.fonts['normal'],
            fg='#DC143C',  # 紅色
            bg=self.colors['bg_secondary']
        )
        filename_label.grid(row=0, column=0, sticky='w', pady=5, padx=(0, 10))

        self.filename_var = tk.StringVar()
        self.filename_var.trace('w', self.update_example)
        filename_entry = tk.Entry(
            input_frame,
            textvariable=self.filename_var,
            font=self.fonts['normal'],
            fg=self.colors['text'],
            relief='flat',
            bd=2,
            width=20
        )
        filename_entry.grid(row=0, column=1, sticky='w', pady=5)

        # 編號輸入
        account_label = tk.Label(
            input_frame,
            text="編號:",
            font=self.fonts['normal'],
            fg='#1E90FF',  # 藍色
            bg=self.colors['bg_secondary']
        )
        account_label.grid(row=0, column=2, sticky='w', pady=5, padx=(30, 10))

        self.account_var = tk.StringVar()
        self.account_var.trace('w', self.update_example)
        account_entry = tk.Entry(
            input_frame,
            textvariable=self.account_var,
            font=self.fonts['normal'],
            fg=self.colors['text'],
            relief='flat',
            bd=2,
            width=15
        )
        account_entry.grid(row=0, column=3, sticky='w', pady=5)

        # 序號變更選項
        options_frame = tk.Frame(rename_inner, bg=self.colors['bg_secondary'])
        options_frame.pack(fill='x', pady=(10, 0))

        self.sequence_mode = tk.StringVar(value="no_change")

        # 選項1: 最末尾數不變動
        option1 = tk.Radiobutton(
            options_frame,
            text="最末尾數不變動",
            variable=self.sequence_mode,
            value="no_change",
            font=self.fonts['normal'],
            fg=self.colors['text'],
            bg=self.colors['bg_secondary'],
            selectcolor=self.colors['accent'],
            command=self.on_sequence_mode_change
        )
        option1.pack(anchor='w', pady=2)

        # 選項2: 最末尾數變動
        option2_frame = tk.Frame(options_frame, bg=self.colors['bg_secondary'])
        option2_frame.pack(fill='x', pady=2)

        option2 = tk.Radiobutton(
            option2_frame,
            text="最末尾數變動，每隔",
            variable=self.sequence_mode,
            value="change",
            font=self.fonts['normal'],
            fg=self.colors['text'],
            bg=self.colors['bg_secondary'],
            selectcolor=self.colors['accent'],
            command=self.on_sequence_mode_change
        )
        option2.pack(side='left')

        self.interval_var = tk.StringVar(value="3")
        self.interval_var.trace('w', self.on_sequence_mode_change)
        interval_entry = tk.Entry(
            option2_frame,
            textvariable=self.interval_var,
            font=self.fonts['normal'],
            fg=self.colors['text'],
            relief='flat',
            bd=2,
            width=5
        )
        interval_entry.pack(side='left', padx=(5, 5))

        tk.Label(
            option2_frame,
            text="個跳一號",
            font=self.fonts['normal'],
            fg=self.colors['text'],
            bg=self.colors['bg_secondary']
        ).pack(side='left')

        # 範例說明
        self.example_explanation = tk.Label(
            options_frame,
            text="序號末位數保持不變，流水號連續",
            font=self.fonts['small'],
            fg='#666666',
            bg=self.colors['bg_secondary']
        )
        self.example_explanation.pack(anchor='w', pady=(5, 0))

        # 預覽按鈕
        preview_button = self.create_rounded_button(
            rename_inner,
            "🔍 預覽變更",
            self.preview_changes,
            width=15
        )
        preview_button.pack(pady=(15, 0))

        # 執行按鈕區域
        button_frame = tk.Frame(main_frame, bg=self.colors['bg_main'])
        button_frame.pack(fill='x')

        execute_button = self.create_rounded_button(
            button_frame,
            "🚀 開始批次處理",
            self.execute_rename,
            width=20,
            is_primary=True
        )
        execute_button.pack(pady=10)

    def create_rounded_button(self, parent, text, command, width=10, is_primary=False):
        """建立圓角按鈕樣式"""
        if is_primary:
            bg_color = self.colors['accent']
            hover_color = self.colors['button_hover']
        else:
            bg_color = self.colors['button']
            hover_color = self.colors['button_hover']

        button = tk.Button(
            parent,
            text=text,
            command=command,
            font=self.fonts['button'],
            fg=self.colors['text'],
            bg=bg_color,
            relief='flat',
            bd=0,
            width=width,
            cursor='hand2'
        )

        # 滑鼠懸停效果
        def on_enter(e):
            button.configure(bg=hover_color)
        def on_leave(e):
            button.configure(bg=bg_color)

        button.bind("<Enter>", on_enter)
        button.bind("<Leave>", on_leave)

        return button

    def update_example(self, *args):
        """更新範例顯示"""
        filename = self.filename_var.get()
        account = self.account_var.get()

        if filename and account:
            self.example_var.set(f"{filename}{account}_01")
        elif filename:
            self.example_var.set(f"{filename}XXXXXX_01")
        else:
            self.example_var.set("YYYYXXXXXX_01")

    def on_sequence_mode_change(self, *args):
        """當序號模式改變時更新範例說明"""
        mode = self.sequence_mode.get()
        interval = self.interval_var.get()

        if mode == "no_change":
            self.example_explanation.config(text="序號末位數保持不變，流水號連續")
        else:
            if interval.isdigit() and int(interval) > 0:
                # 生成範例 - 跳號後流水號重新從01開始
                base_name = "YYYY"
                account_base = "202500"
                examples = []
                current_last_digit = 5

                for i in range(6):  # 顯示6個範例
                    # 計算當前組內的流水號（跳號後重新開始）
                    seq_in_group = (i % int(interval)) + 1

                    # 計算末位數增量
                    if i > 0 and i % int(interval) == 0:
                        current_last_digit += 1

                    seq_num = f"{seq_in_group:02d}"
                    full_account = f"{account_base}{current_last_digit}"
                    examples.append(f"{base_name}{full_account}_{seq_num}")

                example_text = f"Ex:設定每隔{interval}個→" + ", ".join(examples)
                self.example_explanation.config(text=example_text)
            else:
                self.example_explanation.config(text="請輸入有效的間隔數字")

    def select_folder(self):
        """選擇資料夾"""
        folder = filedialog.askdirectory(title="選擇要處理的資料夾")
        if folder:
            self.selected_folder = folder
            self.folder_var.set(folder)
            self.load_files()

    def load_files(self):
        """載入資料夾中的檔案"""
        if not self.selected_folder:
            return

        try:
            files = []
            for item in os.listdir(self.selected_folder):
                item_path = os.path.join(self.selected_folder, item)
                if os.path.isfile(item_path):
                    files.append(item)

            self.files_list = sorted(files)

            # 更新檔案列表顯示
            self.files_text.config(state='normal')
            self.files_text.delete(1.0, tk.END)

            if self.files_list:
                file_text = f"找到 {len(self.files_list)} 個檔案：\n\n"
                for i, file in enumerate(self.files_list, 1):
                    file_text += f"{i:3d}. {file}\n"
            else:
                file_text = "此資料夾中沒有檔案。"

            self.files_text.insert(1.0, file_text)
            self.files_text.config(state='disabled')

        except Exception as e:
            messagebox.showerror("錯誤", f"無法載入資料夾：{str(e)}")

    def generate_new_filename(self, index, file):
        """根據設定生成新檔名"""
        filename = self.filename_var.get().strip()
        account = self.account_var.get().strip()

        if not filename or not account:
            return None

        # 取得副檔名
        _, ext = os.path.splitext(file)

        # 根據序號模式計算帳號末位數和流水號
        if self.sequence_mode.get() == "no_change":
            # 末位數不變，流水號連續
            seq_num = f"{index + 1:02d}"
            new_filename = f"{filename}{account}_{seq_num}{ext}"
        else:
            # 末位數變動，流水號在跳號後重新開始
            try:
                interval = int(self.interval_var.get())
                if interval <= 0:
                    interval = 1

                # 計算當前應該使用的末位數增量
                last_digit_increment = index // interval

                # 計算在當前帳號組內的流水號（跳號後重新從1開始）
                seq_in_group = (index % interval) + 1
                seq_num = f"{seq_in_group:02d}"

                # 從帳號中提取數字部分和末位數
                if account.isdigit():
                    # 純數字帳號
                    base_account = account[:-1] if len(account) > 1 else "0"
                    original_last_digit = int(account[-1]) if account else 1
                else:
                    # 混合字母數字，嘗試找到最後的數字部分
                    digit_match = re.search(r'(\d+)$', account)
                    if digit_match:
                        num_part = digit_match.group(1)
                        base_account = account[:-len(num_part)]
                        if len(num_part) > 1:
                            base_account += num_part[:-1]
                            original_last_digit = int(num_part[-1])
                        else:
                            original_last_digit = int(num_part)
                    else:
                        base_account = account
                        original_last_digit = 1

                new_last_digit = original_last_digit + last_digit_increment
                new_account = f"{base_account}{new_last_digit}"
                new_filename = f"{filename}{new_account}_{seq_num}{ext}"

            except ValueError:
                # 如果間隔不是有效數字，使用預設行為
                seq_num = f"{index + 1:02d}"
                new_filename = f"{filename}{account}_{seq_num}{ext}"

        return new_filename

    def preview_changes(self):
        """預覽檔名變更"""
        if not self.files_list:
            messagebox.showwarning("警告", "請先選擇包含檔案的資料夾。")
            return

        filename = self.filename_var.get().strip()
        account = self.account_var.get().strip()

        if not filename:
            messagebox.showwarning("警告", "請輸入檔名。")
            return

        if not account:
            messagebox.showwarning("警告", "請輸入編號。")
            return

        try:
            preview_text = "預覽變更結果：\n\n"

            for i, file in enumerate(self.files_list):
                new_name = self.generate_new_filename(i, file)
                if new_name:
                    preview_text += f"{file} → {new_name}\n"

            # 顯示預覽視窗
            preview_window = tk.Toplevel(self.root)
            preview_window.title("預覽變更結果")
            preview_window.geometry("700x400")
            preview_window.configure(bg=self.colors['bg_main'])

            preview_scroll = scrolledtext.ScrolledText(
                preview_window,
                font=self.fonts['small'],
                fg=self.colors['text'],
                bg='#FFFFFF'
            )
            preview_scroll.pack(fill='both', expand=True, padx=20, pady=20)
            preview_scroll.insert(1.0, preview_text)
            preview_scroll.config(state='disabled')

        except Exception as e:
            messagebox.showerror("錯誤", f"預覽失敗：{str(e)}")

    def execute_rename(self):
        """執行批次重新命名"""
        if not self.files_list:
            messagebox.showwarning("警告", "請先選擇包含檔案的資料夾。")
            return

        filename = self.filename_var.get().strip()
        account = self.account_var.get().strip()

        if not filename:
            messagebox.showwarning("警告", "請輸入檔名。")
            return

        if not account:
            messagebox.showwarning("警告", "請輸入編號。")
            return

        # 確認對話框
        if not messagebox.askyesno("確認", f"確定要重新命名 {len(self.files_list)} 個檔案嗎？\n此操作無法復原！"):
            return

        try:
            success_count = 0
            error_files = []

            for i, file in enumerate(self.files_list):
                old_path = os.path.join(self.selected_folder, file)
                new_name = self.generate_new_filename(i, file)

                if not new_name:
                    error_files.append(f"{file} (無法生成新檔名)")
                    continue

                new_path = os.path.join(self.selected_folder, new_name)

                try:
                    if old_path != new_path and not os.path.exists(new_path):
                        os.rename(old_path, new_path)
                        success_count += 1
                    elif old_path == new_path:
                        continue  # 檔名沒有改變
                    else:
                        error_files.append(f"{file} (目標檔案已存在)")
                except Exception as e:
                    error_files.append(f"{file} ({str(e)})")

            # 重新載入檔案列表
            self.load_files()

            # 顯示結果
            result_msg = f"批次處理完成！\n成功處理：{success_count} 個檔案"
            if error_files:
                result_msg += f"\n失敗：{len(error_files)} 個檔案\n\n失敗檔案：\n" + "\n".join(error_files[:10])
                if len(error_files) > 10:
                    result_msg += f"\n... 還有 {len(error_files) - 10} 個檔案"
                messagebox.showwarning("處理完成", result_msg)
            else:
                messagebox.showinfo("處理完成", result_msg)

        except Exception as e:
            messagebox.showerror("錯誤", f"批次處理失敗：{str(e)}")

def main():
    root = tk.Tk()
    app = BatchRenameApp(root)

    # 設定視窗圖示和其他屬性
    try:
        root.iconbitmap('icon.ico')
    except:
        pass

    # 設定視窗關閉事件
    def on_closing():
        if messagebox.askokcancel("結束程式", "確定要結束程式嗎？"):
            root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_closing)

    # 啟動應用程式
    root.mainloop()

if __name__ == "__main__":
    main()