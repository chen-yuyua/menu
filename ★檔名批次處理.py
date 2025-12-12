import tkinter as tk
import tkinter.font
from tkinter import ttk, filedialog, messagebox, scrolledtext
import os
import re
from pathlib import Path

class BatchRenameApp:
    def __init__(self, root):
        self.root = root
        self.root.title("批次檔名變更工具 - Ver.1.7")
        self.root.geometry("700x600")

        # 版本資訊
        self.version = "Ver.1.7"
        self.update_date = "2025/12/11"

        # 色彩配置 - 接近圖片風格
        self.colors = {
            'bg_main': '#FFFFFF',           # 白色背景
            'bg_frame': '#FFFFFF',          # 框架背景
            'border': '#000000',            # 黑色邊框
            'accent': '#FFE4C4',            # 淺橘色（按鈕）
            'button_execute': '#E0FFFF',    # 淺藍色（執行按鈕）
            'text': '#000000',              # 黑色文字
            'filename_color': '#0066CC',    # 檔名顏色 - 藍色
            'account_color': '#CC6600',     # 編號顏色 - 橘色
            'serial_color': '#009900',      # 正反顏色 - 綠色
            'separator_color': '#FF0066',   # 分隔符顏色 - 紫紅色
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
            'title': (self.font_family, 14, 'bold'),
            'normal': (self.font_family, 10),
            'button': (self.font_family, 11),
            'small': (self.font_family, 9),
        }

        self.selected_folder = ""
        self.files_list = []

        self.setup_ui()

    def setup_ui(self):
        # 主容器
        main_frame = tk.Frame(self.root, bg=self.colors['bg_main'],
                             highlightbackground=self.colors['border'],
                             highlightthickness=1)
        main_frame.pack(fill='both', expand=True, padx=20, pady=20)

        # 標題
        title_label = tk.Label(
            main_frame,
            text="批次檔名變更工具",
            font=self.fonts['title'],
            fg=self.colors['text'],
            bg=self.colors['bg_main']
        )
        title_label.pack(anchor='w', padx=15, pady=(15, 10))

        # ===== 選擇資料夾區域 =====
        folder_frame = tk.LabelFrame(
            main_frame,
            text="選擇資料夾:",
            font=self.fonts['normal'],
            fg=self.colors['text'],
            bg=self.colors['bg_frame'],
            relief='solid',
            bd=1
        )
        folder_frame.pack(fill='x', padx=15, pady=(0, 10))

        folder_inner = tk.Frame(folder_frame, bg=self.colors['bg_frame'])
        folder_inner.pack(fill='x', padx=10, pady=10)

        self.folder_var = tk.StringVar(value="C:/.........................")
        folder_label = tk.Label(
            folder_inner,
            textvariable=self.folder_var,
            font=self.fonts['normal'],
            fg=self.colors['text'],
            bg=self.colors['bg_frame'],
            anchor='w'
        )
        folder_label.pack(side='left', fill='x', expand=True)

        select_button = tk.Button(
            folder_inner,
            text="選擇資料夾",
            command=self.select_folder,
            font=self.fonts['button'],
            fg=self.colors['text'],
            bg=self.colors['accent'],
            relief='solid',
            bd=1,
            width=12,
            cursor='hand2'
        )
        select_button.pack(side='right', padx=(10, 0))

        # ===== 檔案列表區域 =====
        files_frame = tk.LabelFrame(
            main_frame,
            text="檔案列表",
            font=self.fonts['normal'],
            fg=self.colors['text'],
            bg=self.colors['bg_frame'],
            relief='solid',
            bd=1
        )
        files_frame.pack(fill='both', expand=True, padx=15, pady=(0, 10))

        # 檔案列表文字區域
        self.files_text = scrolledtext.ScrolledText(
            files_frame,
            height=6,
            font=self.fonts['small'],
            fg=self.colors['text'],
            bg='#FFFFFF',
            relief='solid',
            bd=1,
            state='disabled'
        )
        self.files_text.pack(fill='both', expand=True, padx=10, pady=10)

        # ===== 檔名變更設定區域 =====
        rename_frame = tk.LabelFrame(
            main_frame,
            text="檔名變更設定",
            font=self.fonts['normal'],
            fg=self.colors['text'],
            bg=self.colors['bg_frame'],
            relief='solid',
            bd=1
        )
        rename_frame.pack(fill='x', padx=15, pady=(0, 10))

        rename_inner = tk.Frame(rename_frame, bg=self.colors['bg_frame'])
        rename_inner.pack(fill='x', padx=10, pady=10)

        # 範例顯示
        example_frame = tk.Frame(rename_inner, bg=self.colors['bg_frame'])
        example_frame.pack(fill='x', pady=(0, 10))

        example_label = tk.Label(
            example_frame,
            text="例:",
            font=self.fonts['normal'],
            fg=self.colors['text'],
            bg=self.colors['bg_frame']
        )
        example_label.pack(side='left')

        # 使用Frame來容納彩色範例
        self.example_frame = tk.Frame(example_frame, bg=self.colors['bg_frame'])
        self.example_frame.pack(side='left', padx=(5, 0))

        # 初始化範例標籤
        self.example_labels = {
            'filename': None,
            'account': None,
            'serial': None
        }

        # ===== 勾選框與輸入欄位 =====
        input_frame = tk.Frame(rename_inner, bg=self.colors['bg_frame'])
        input_frame.pack(fill='x', pady=(0, 10))

        # 檔名輸入
        tk.Label(
            input_frame,
            text="檔名:",
            font=self.fonts['normal'],
            fg=self.colors['text'],
            bg=self.colors['bg_frame']
        ).grid(row=0, column=0, sticky='w', pady=5)

        self.filename_var = tk.StringVar()
        self.filename_var.trace('w', self.update_example)
        self.filename_entry = tk.Entry(
            input_frame,
            textvariable=self.filename_var,
            font=self.fonts['normal'],
            fg=self.colors['text'],
            relief='solid',
            bd=1,
            width=10
        )
        self.filename_entry.grid(row=0, column=1, sticky='w', pady=5, padx=(0, 20))

        # 編號輸入
        tk.Label(
            input_frame,
            text="編號:",
            font=self.fonts['normal'],
            fg=self.colors['text'],
            bg=self.colors['bg_frame']
        ).grid(row=0, column=2, sticky='w', pady=5)

        self.account_var = tk.StringVar()
        self.account_var.trace('w', self.update_example)
        self.account_entry = tk.Entry(
            input_frame,
            textvariable=self.account_var,
            font=self.fonts['normal'],
            fg=self.colors['text'],
            relief='solid',
            bd=1,
            width=10
        )
        self.account_entry.grid(row=0, column=3, sticky='w', pady=5, padx=(0, 20))

        # 分隔符選項
        separator_frame = tk.Frame(input_frame, bg=self.colors['bg_frame'])
        separator_frame.grid(row=0, column=4, sticky='w', pady=5, padx=(0, 10))

        tk.Label(
            separator_frame,
            text="分隔符:",
            font=self.fonts['normal'],
            fg=self.colors['text'],
            bg=self.colors['bg_frame']
        ).pack(side='top', anchor='w')

        # 分隔符選項按鈕
        self.separator_var = tk.StringVar(value="_")

        separator_options = [
            ("_", "_"),
            ("-", "-"),
            ("無", "none")
        ]

        separator_radio_frame = tk.Frame(separator_frame, bg=self.colors['bg_frame'])
        separator_radio_frame.pack(side='top', anchor='w')

        for i, (text, value) in enumerate(separator_options):
            radio = tk.Radiobutton(
                separator_radio_frame,
                text=text,
                variable=self.separator_var,
                value=value,
                font=self.fonts['small'],
                fg=self.colors['text'],
                bg=self.colors['bg_frame'],
                selectcolor='#FFFFFF',
                command=self.update_example
            )
            radio.pack(side='left', padx=(0, 5))

        # 正反輸入
        tk.Label(
            input_frame,
            text="正反:",
            font=self.fonts['normal'],
            fg=self.colors['text'],
            bg=self.colors['bg_frame']
        ).grid(row=0, column=5, sticky='w', pady=5)

        self.serial_var = tk.StringVar()
        self.serial_var.trace('w', self.update_example)
        self.serial_entry = tk.Entry(
            input_frame,
            textvariable=self.serial_var,
            font=self.fonts['normal'],
            fg=self.colors['text'],
            relief='solid',
            bd=1,
            width=6
        )
        self.serial_entry.grid(row=0, column=6, sticky='w', pady=5)

        # ===== 變更選項 =====
        options_frame = tk.Frame(rename_inner, bg=self.colors['bg_frame'])
        options_frame.pack(fill='x', pady=(5, 0))

        self.sequence_mode = tk.StringVar(value="account_change")

        # 選項1: 編號變動
        option1_frame = tk.Frame(options_frame, bg=self.colors['bg_frame'])
        option1_frame.pack(fill='x', pady=2)

        option1 = tk.Radiobutton(
            option1_frame,
            text="編號變動、每隔",
            variable=self.sequence_mode,
            value="account_change",
            font=self.fonts['normal'],
            fg=self.colors['text'],
            bg=self.colors['bg_frame'],
            selectcolor='#FFFFFF',
            command=self.on_sequence_mode_change
        )
        option1.pack(side='left')

        self.account_interval_var = tk.StringVar(value="3")
        self.account_interval_var.trace('w', self.on_sequence_mode_change)
        account_interval_entry = tk.Entry(
            option1_frame,
            textvariable=self.account_interval_var,
            font=self.fonts['normal'],
            fg=self.colors['text'],
            relief='solid',
            bd=1,
            width=5
        )
        account_interval_entry.pack(side='left', padx=(5, 5))

        tk.Label(
            option1_frame,
            text="個跳一號",
            font=self.fonts['normal'],
            fg=self.colors['text'],
            bg=self.colors['bg_frame']
        ).pack(side='left')

        # 選項2: 正反變動
        option2_frame = tk.Frame(options_frame, bg=self.colors['bg_frame'])
        option2_frame.pack(fill='x', pady=2)

        option2 = tk.Radiobutton(
            option2_frame,
            text="正反變動、每隔",
            variable=self.sequence_mode,
            value="serial_change",
            font=self.fonts['normal'],
            fg=self.colors['text'],
            bg=self.colors['bg_frame'],
            selectcolor='#FFFFFF',
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
            relief='solid',
            bd=1,
            width=5
        )
        interval_entry.pack(side='left', padx=(5, 5))

        tk.Label(
            option2_frame,
            text="個跳一號",
            font=self.fonts['normal'],
            fg=self.colors['text'],
            bg=self.colors['bg_frame']
        ).pack(side='left')

        # 範例說明
        self.example_explanation = tk.Label(
            options_frame,
            text="編號末位數保持不變、正反號連續",
            font=self.fonts['small'],
            fg='#666666',
            bg=self.colors['bg_frame']
        )
        self.example_explanation.pack(anchor='w', pady=(5, 0))

        # 預覽按鈕
        preview_button = tk.Button(
            rename_inner,
            text="預覽變更",
            command=self.preview_changes,
            font=self.fonts['button'],
            fg=self.colors['text'],
            bg=self.colors['accent'],
            relief='solid',
            bd=1,
            width=12,
            cursor='hand2'
        )
        preview_button.pack(pady=(15, 5))

        # ===== 執行按鈕 =====
        execute_button = tk.Button(
            main_frame,
            text="開始批次處理",
            command=self.execute_rename,
            font=self.fonts['button'],
            fg=self.colors['text'],
            bg=self.colors['button_execute'],
            relief='solid',
            bd=1,
            width=18,
            cursor='hand2'
        )
        execute_button.pack(pady=(5, 15))

    def update_example(self, *args):
        """更新範例顯示 - 根據輸入內容自動判斷是否使用，並用顏色區分"""
        # 清除舊的標籤
        for widget in self.example_frame.winfo_children():
            widget.destroy()

        parts = []

        # 檔名部分 - 如果有輸入就使用
        filename = self.filename_var.get().strip()
        if filename:
            label = tk.Label(
                self.example_frame,
                text=filename,
                font=self.fonts['normal'],
                fg=self.colors['filename_color'],
                bg=self.colors['bg_frame']
            )
            label.pack(side='left')
            parts.append(filename)

        # 編號部分 - 如果有輸入就使用
        account = self.account_var.get().strip()
        if account:
            label = tk.Label(
                self.example_frame,
                text=account,
                font=self.fonts['normal'],
                fg=self.colors['account_color'],
                bg=self.colors['bg_frame']
            )
            label.pack(side='left')
            parts.append(account)

        # 正反部分 - 如果有輸入就使用
        serial = self.serial_var.get().strip()
        if serial or (filename or account):  # 如果有正反輸入，或者有檔名或編號
            # 分隔符
            separator_value = self.separator_var.get()
            if parts and separator_value != "none":  # 只有當前面有內容且不是"無"時才加分隔符
                separator_text = separator_value if separator_value != "none" else ""
                if separator_text:
                    separator_label = tk.Label(
                        self.example_frame,
                        text=separator_text,
                        font=self.fonts['normal'],
                        fg=self.colors['separator_color'],
                        bg=self.colors['bg_frame']
                    )
                    separator_label.pack(side='left')

            # 正反號
            serial_text = serial if serial else "01"
            serial_label = tk.Label(
                self.example_frame,
                text=serial_text,
                font=self.fonts['normal'],
                fg=self.colors['serial_color'],
                bg=self.colors['bg_frame']
            )
            serial_label.pack(side='left')

        # 如果什麼都沒有輸入，顯示預設範例
        if not (filename or account):
            default_separator = self.separator_var.get()
            separator_text = default_separator if default_separator != "none" else ""

            default_parts = [
                ("YYYY", self.colors['filename_color']),
                ("XXXXXXXX", self.colors['account_color']),
            ]

            if separator_text:
                default_parts.append((separator_text, self.colors['separator_color']))

            default_parts.append(("01", self.colors['serial_color']))

            for text, color in default_parts:
                label = tk.Label(
                    self.example_frame,
                    text=text,
                    font=self.fonts['normal'],
                    fg=color,
                    bg=self.colors['bg_frame']
                )
                label.pack(side='left')

    def on_sequence_mode_change(self, *args):
        """當序號模式改變時更新範例說明"""
        mode = self.sequence_mode.get()

        if mode == "account_change":
            interval = self.account_interval_var.get()
            if interval.isdigit() and int(interval) > 0:
                self.example_explanation.config(
                    text=f"每{interval}個檔案後，編號末位數+1，正反號重新開始"
                )
            else:
                self.example_explanation.config(text="請輸入有效的間隔數字")
        else:  # serial_change
            interval = self.interval_var.get()
            if interval.isdigit() and int(interval) > 0:
                self.example_explanation.config(
                    text=f"每{interval}個檔案後，正反號+1，編號重新開始"
                )
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
        """根據設定生成新檔名 - 根據輸入內容自動判斷是否使用"""
        # 取得副檔名
        _, ext = os.path.splitext(file)

        parts = []

        # 檔名部分 - 如果有輸入就使用
        filename = self.filename_var.get().strip()
        if filename:
            parts.append(filename)

        # 編號部分 - 如果有輸入就使用
        account = self.account_var.get().strip()
        if account:
            if self.sequence_mode.get() == "account_change":
                # 編號變動模式 - 每隔指定個數跳一號
                try:
                    interval = int(self.account_interval_var.get())
                    if interval <= 0:
                        interval = 1

                    # 計算末位數增量
                    last_digit_increment = index // interval

                    # 處理帳號末位數
                    if account.isdigit():
                        base_account = account[:-1] if len(account) > 1 else ""
                        original_last_digit = int(account[-1]) if account else 1
                    else:
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
                    account = f"{base_account}{new_last_digit}"
                except ValueError:
                    pass

            parts.append(account)

        # 組合基本檔名
        base_name = "".join(parts)

        if not base_name:
            return None

        # 正反部分 - 如果有輸入或者前面有內容就使用
        serial_input = self.serial_var.get().strip()
        if serial_input or parts:  # 如果有正反輸入，或者前面有檔名/編號
            # 計算正反號
            if self.sequence_mode.get() == "serial_change":
                # 正反變動模式
                try:
                    interval = int(self.interval_var.get())
                    if interval <= 0:
                        interval = 1

                    # 每隔 interval 個檔案，正反號增加1
                    serial_increment = index // interval

                    # 檢查是否有自訂起始正反號
                    if serial_input and serial_input.isdigit():
                        base_serial = int(serial_input)
                    else:
                        base_serial = 1

                    current_serial = base_serial + serial_increment

                except ValueError:
                    current_serial = 1
            else:
                # 編號變動模式 - 正反號在每組內重新開始
                try:
                    interval = int(self.account_interval_var.get())
                    if interval <= 0:
                        interval = 1

                    # 在每組內的位置
                    file_in_group = index % interval

                    # 檢查是否有自訂起始正反號
                    if serial_input and serial_input.isdigit():
                        base_serial = int(serial_input)
                    else:
                        base_serial = 1

                    current_serial = base_serial + file_in_group

                except ValueError:
                    current_serial = index + 1

            # 根據分隔符設定生成檔名
            separator_value = self.separator_var.get()
            if separator_value == "none":
                new_filename = f"{base_name}{current_serial:02d}{ext}"
            else:
                new_filename = f"{base_name}{separator_value}{current_serial:02d}{ext}"
        else:
            new_filename = f"{base_name}{ext}"

        return new_filename

    def preview_changes(self):
        """預覽檔名變更"""
        if not self.files_list:
            messagebox.showwarning("警告", "請先選擇包含檔案的資料夾。")
            return

        # 檢查是否至少輸入了檔名或編號
        filename = self.filename_var.get().strip()
        account = self.account_var.get().strip()
        if not (filename or account):
            messagebox.showwarning("警告", "請至少輸入「檔名」或「編號」。")
            return

        try:
            preview_text = "預覽變更結果：\n\n"

            for i, file in enumerate(self.files_list):
                new_name = self.generate_new_filename(i, file)
                if new_name:
                    preview_text += f"{i+1:3d}. {file} → {new_name}\n"

            # 顯示預覽視窗
            preview_window = tk.Toplevel(self.root)
            preview_window.title("預覽變更結果")
            preview_window.geometry("800x500")
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

        # 檢查是否至少輸入了檔名或編號
        filename = self.filename_var.get().strip()
        account = self.account_var.get().strip()
        if not (filename or account):
            messagebox.showwarning("警告", "請至少輸入「檔名」或「編號」。")
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
                        continue
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

    # 設定視窗關閉事件
    def on_closing():
        if messagebox.askokcancel("結束程式", "確定要結束程式嗎？"):
            root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()

if __name__ == "__main__":
    main()
