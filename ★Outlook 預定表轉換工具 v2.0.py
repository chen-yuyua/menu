import tkinter as tk
from tkinter import messagebox, Text, ttk, Scrollbar
from datetime import datetime, timedelta
import win32com.client as win32
import pythoncom
import sys
import re
from tkcalendar import DateEntry
import threading
from typing import Optional, Dict, List
import logging

# 配置日誌
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 預先定義日期到星期幾的轉換，日文格式
WEEKDAY_MAP = {
    0: '(月)',  # 星期一
    1: '(火)',  # 星期二
    2: '(水)',  # 星期三
    3: '(木)',  # 星期四
    4: '(金)',  # 星期五
    5: '(土)',  # 星期六
    6: '(日)'   # 星期日
}

# 現代化的顏色主題
THEME = {
    'primary': '#2E86AB',      # 藍色主色
    'secondary': '#A23B72',    # 紫紅色輔助色
    'success': '#F18F01',      # 橙色成功色
    'background': '#F5F5F5',   # 淺灰背景
    'surface': '#FFFFFF',      # 白色表面
    'text_primary': '#2D3436', # 深灰文字
    'text_secondary': '#636E72', # 中灰文字
    'border': '#DDD',          # 邊框色
    'hover': '#74B9FF'         # 懸停色
}

class ModernButton(tk.Button):
    """現代化按鈕組件"""
    def __init__(self, parent, **kwargs):
        # 設置默認樣式
        default_style = {
            'bg': THEME['primary'],
            'fg': 'white',
            'font': ('BIZ UDPゴシック', 10, 'bold'),
            'relief': 'flat',
            'bd': 0,
            'padx': 20,
            'pady': 8,
            'cursor': 'hand2'
        }
        default_style.update(kwargs)
        super().__init__(parent, **default_style)

        # 綁定懸停效果
        self.bind('<Enter>', self._on_enter)
        self.bind('<Leave>', self._on_leave)
        self.original_bg = self['bg']

    def _on_enter(self, event):
        self.configure(bg=THEME['hover'])

    def _on_leave(self, event):
        self.configure(bg=self.original_bg)

class OutlookExportApp:
    def __init__(self, master):
        self.master = master
        self._setup_window()
        self._setup_styles()
        self._create_widgets()
        self._setup_layout()

        # 狀態變數
        self.is_processing = False

    def _setup_window(self):
        """設置主窗口屬性"""
        self.master.title("📅 Outlook 預定表轉換工具 v2.0")
        self.master.geometry("800x650")
        self.master.minsize(600, 500)

        # 設置圖標（如果有的話）
        try:
            # self.master.iconbitmap('icon.ico')  # 如果有圖標文件
            pass
        except:
            pass

        # 設置背景色
        self.master.configure(bg=THEME['background'])

        # 響應式佈局配置
        self.master.grid_columnconfigure(1, weight=1)
        self.master.grid_rowconfigure(5, weight=1)

    def _setup_styles(self):
        """設置 ttk 樣式"""
        self.style = ttk.Style()

        # 配置進度條樣式
        self.style.configure(
            "Custom.Horizontal.TProgressbar",
            background=THEME['primary'],
            troughcolor=THEME['border'],
            borderwidth=0,
            lightcolor=THEME['primary'],
            darkcolor=THEME['primary']
        )

    def _create_widgets(self):
        """創建所有 UI 組件"""

        # === 標題區域 ===
        title_frame = tk.Frame(self.master, bg=THEME['background'])
        title_frame.grid(row=0, column=0, columnspan=3, pady=(20, 30), sticky='ew')

        title_label = tk.Label(
            title_frame,
            text="📅 Outlook 預定表轉換工具",
            font=('BIZ UDPゴシック', 16, 'bold'),
            bg=THEME['background'],
            fg=THEME['primary']
        )
        title_label.pack()

        subtitle_label = tk.Label(
            title_frame,
            text="輕鬆將您的 Outlook 行事曆轉換為文字格式",
            font=('BIZ UDPゴシック', 9),
            bg=THEME['background'],
            fg=THEME['text_secondary']
        )
        subtitle_label.pack(pady=(5, 0))

        # === 輸入區域 ===
        input_frame = tk.Frame(self.master, bg=THEME['surface'], relief='solid', bd=1)
        input_frame.grid(row=1, column=0, columnspan=3, padx=20, pady=(0, 20), sticky='ew')
        input_frame.grid_columnconfigure(1, weight=1)

        # 添加內邊距
        input_frame.configure(padx=20, pady=20)

        # 開始日期
        start_label = tk.Label(
            input_frame,
            text="🗓️ 開始日期:",
            font=('BIZ UDPゴシック', 10, 'bold'),
            bg=THEME['surface'],
            fg=THEME['text_primary']
        )
        start_label.grid(row=0, column=0, padx=(0, 15), pady=(0, 15), sticky='w')

        self.start_date_entry = DateEntry(
            input_frame,
            width=15,
            background=THEME['primary'],
            foreground='white',
            borderwidth=2,
            font=('BIZ UDPゴシック', 10),
            date_pattern='yyyy-mm-dd',
            relief='flat'
        )
        self.start_date_entry.set_date(datetime.now() + timedelta(days=1))
        self.start_date_entry.grid(row=0, column=1, padx=(0, 20), pady=(0, 15), sticky='w')

        # 結束日期
        end_label = tk.Label(
            input_frame,
            text="🏁 結束日期:",
            font=('BIZ UDPゴシック', 10, 'bold'),
            bg=THEME['surface'],
            fg=THEME['text_primary']
        )
        end_label.grid(row=1, column=0, padx=(0, 15), pady=(0, 15), sticky='w')

        self.end_date_entry = DateEntry(
            input_frame,
            width=15,
            background=THEME['primary'],
            foreground='white',
            borderwidth=2,
            font=('BIZ UDPゴシック', 10),
            date_pattern='yyyy-mm-dd',
            relief='flat'
        )
        self.end_date_entry.set_date(datetime.now() + timedelta(days=7))
        self.end_date_entry.grid(row=1, column=1, padx=(0, 20), pady=(0, 15), sticky='w')

        # 快速選擇按鈕
        quick_frame = tk.Frame(input_frame, bg=THEME['surface'])
        quick_frame.grid(row=2, column=0, columnspan=2, pady=(10, 0), sticky='w')

        quick_label = tk.Label(
            quick_frame,
            text="⚡ 快速選擇:",
            font=('BIZ UDPゴシック', 9),
            bg=THEME['surface'],
            fg=THEME['text_secondary']
        )
        quick_label.pack(side='left', padx=(0, 10))

        # 快速選擇按鈕
        quick_buttons = [
            ("本週", self._set_this_week),
            ("下週", self._set_next_week),
            ("下個月", self._set_next_month)
        ]

        for text, command in quick_buttons:
            btn = tk.Button(
                quick_frame,
                text=text,
                command=command,
                font=('BIZ UDPゴシック', 8),
                bg=THEME['border'],
                fg=THEME['text_primary'],
                relief='flat',
                bd=0,
                padx=12,
                pady=4,
                cursor='hand2'
            )
            btn.pack(side='left', padx=(0, 5))

            # 添加懸停效果
            btn.bind('<Enter>', lambda e, b=btn: b.configure(bg=THEME['text_secondary'], fg='white'))
            btn.bind('<Leave>', lambda e, b=btn: b.configure(bg=THEME['border'], fg=THEME['text_primary']))

        # === 操作按鈕區域 ===
        button_frame = tk.Frame(self.master, bg=THEME['background'])
        button_frame.grid(row=2, column=0, columnspan=3, pady=20)

        self.export_button = ModernButton(
            button_frame,
            text="⚡ 開始轉換預定表",
            command=self._start_export_thread,
            font=('BIZ UDPゴシック', 12, 'bold'),
            padx=30,
            pady=12
        )
        self.export_button.pack(side='left', padx=(0, 10))

        self.clear_button = ModernButton(
            button_frame,
            text="🗑️ 清除結果",
            command=self._clear_results,
            bg=THEME['text_secondary'],
            font=('BIZ UDPゴシック', 10),
            padx=20,
            pady=10
        )
        self.clear_button.pack(side='left')

        # === 進度條 ===
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(
            self.master,
            variable=self.progress_var,
            style="Custom.Horizontal.TProgressbar",
            mode='determinate',
            length=300
        )
        self.progress_bar.grid(row=3, column=0, columnspan=3, pady=(0, 10))
        self.progress_bar.grid_remove()  # 初始隱藏

        # === 狀態標籤 ===
        self.status_label = tk.Label(
            self.master,
            text="📝 請選擇日期範圍，然後點擊轉換按鈕開始操作",
            font=('BIZ UDPゴシック', 9),
            bg=THEME['background'],
            fg=THEME['text_secondary']
        )
        self.status_label.grid(row=4, column=0, columnspan=3, pady=(0, 10))

        # === 結果顯示區域 ===
        result_frame = tk.Frame(self.master, bg=THEME['background'])
        result_frame.grid(row=5, column=0, columnspan=3, padx=20, pady=(0, 20), sticky='nsew')
        result_frame.grid_columnconfigure(0, weight=1)
        result_frame.grid_rowconfigure(1, weight=1)

        result_title = tk.Label(
            result_frame,
            text="📋 轉換結果 (可直接複製使用)",
            font=('BIZ UDPゴシック', 11, 'bold'),
            bg=THEME['background'],
            fg=THEME['text_primary']
        )
        result_title.grid(row=0, column=0, sticky='w', pady=(0, 10))

        # 文字顯示區域框架
        text_frame = tk.Frame(result_frame, bg=THEME['surface'], relief='solid', bd=1)
        text_frame.grid(row=1, column=0, sticky='nsew')
        text_frame.grid_columnconfigure(0, weight=1)
        text_frame.grid_rowconfigure(0, weight=1)

        # 結果文字區域
        self.result_text = Text(
            text_frame,
            font=('Consolas', 10),
            bg=THEME['surface'],
            fg=THEME['text_primary'],
            relief='flat',
            bd=10,
            wrap='word',
            selectbackground=THEME['primary'],
            selectforeground='white'
        )
        self.result_text.grid(row=0, column=0, sticky='nsew')

        # 滾動條
        scrollbar = Scrollbar(text_frame, command=self.result_text.yview)
        scrollbar.grid(row=0, column=1, sticky='ns')
        self.result_text.config(yscrollcommand=scrollbar.set)

    def _setup_layout(self):
        """設置佈局管理"""
        pass  # 佈局已在 _create_widgets 中設置

    def _set_this_week(self):
        """設置為本週"""
        today = datetime.now()
        start_of_week = today - timedelta(days=today.weekday())
        end_of_week = start_of_week + timedelta(days=6)

        self.start_date_entry.set_date(start_of_week.date())
        self.end_date_entry.set_date(end_of_week.date())

    def _set_next_week(self):
        """設置為下週"""
        today = datetime.now()
        start_of_next_week = today + timedelta(days=(7 - today.weekday()))
        end_of_next_week = start_of_next_week + timedelta(days=6)

        self.start_date_entry.set_date(start_of_next_week.date())
        self.end_date_entry.set_date(end_of_next_week.date())

    def _set_next_month(self):
        """設置為下個月"""
        today = datetime.now()
        if today.month == 12:
            next_month = today.replace(year=today.year + 1, month=1, day=1)
        else:
            next_month = today.replace(month=today.month + 1, day=1)

        # 下個月的最後一天
        if next_month.month == 12:
            last_day = next_month.replace(year=next_month.year + 1, month=1, day=1) - timedelta(days=1)
        else:
            last_day = next_month.replace(month=next_month.month + 1, day=1) - timedelta(days=1)

        self.start_date_entry.set_date(next_month.date())
        self.end_date_entry.set_date(last_day.date())

    def _start_export_thread(self):
        """在新線程中開始匯出程序"""
        if self.is_processing:
            return

        # 在新線程中執行匯出
        thread = threading.Thread(target=self.export_appointments, daemon=True)
        thread.start()

    def _clear_results(self):
        """清除結果區域"""
        self.result_text.delete(1.0, tk.END)
        self._update_status("📝 結果已清除，請重新選擇日期範圍進行轉換")

    def _update_status(self, message: str):
        """更新狀態標籤"""
        self.status_label.config(text=message)
        self.master.update_idletasks()

    def _show_progress(self, show: bool = True):
        """顯示或隱藏進度條"""
        if show:
            self.progress_bar.grid()
            self.progress_var.set(0)
        else:
            self.progress_bar.grid_remove()

    def _update_progress(self, value: float):
        """更新進度條"""
        self.progress_var.set(value)
        self.master.update_idletasks()

    def _validate_dates(self) -> tuple[datetime, datetime]:
        """驗證並獲取日期"""
        try:
            start_date_obj = self.start_date_entry.get_date()
            end_date_obj = self.end_date_entry.get_date()

            start_date = datetime.combine(start_date_obj, datetime.min.time())
            end_date = datetime.combine(end_date_obj, datetime.min.time())

            if start_date > end_date:
                raise ValueError("開始日期不能晚於結束日期")

            # 檢查日期範圍是否合理（不超過6個月）
            if (end_date - start_date).days > 180:
                raise ValueError("日期範圍不能超過 6 個月")

            return start_date, end_date

        except Exception as e:
            raise ValueError(f"日期驗證失敗: {str(e)}")

    def _get_outlook_appointments(self, start_date: datetime, end_date: datetime) -> Optional[Dict]:
        """獲取 Outlook 約會資料"""
        appointments_data = {}

        try:
            self._update_status("🔄 正在連接 Outlook...")
            self._update_progress(10)

            # 初始化 COM
            import pythoncom
            pythoncom.CoInitialize()

            # 連接 Outlook
            outlook = win32.Dispatch("Outlook.Application")
            namespace = outlook.GetNamespace("MAPI")
            calendar = namespace.GetDefaultFolder(9)  # 9 = olFolderCalendar

            self._update_progress(30)
            self._update_status("📅 正在讀取行事曆資料...")

            # 設置日期過濾器
            end_date_inclusive = end_date + timedelta(days=1)
            filter_criteria = (
                f"[Start] >= '{start_date.strftime('%m/%d/%Y')}' AND "
                f"[Start] < '{end_date_inclusive.strftime('%m/%d/%Y')}'"
            )

            items = calendar.Items
            items.Sort("[Start]", False)
            items.IncludeRecurrences = True
            items.SetColumns("Start,Subject,Location,AllDayEvent")

            self._update_progress(50)

            restricted_items = items.Restrict(filter_criteria)
            total_items = restricted_items.Count

            self._update_status(f"📊 找到 {total_items} 個行事曆項目，正在處理...")

            # 處理每個約會項目
            for i, appointment in enumerate(restricted_items):
                try:
                    appointment_date = appointment.Start.date()
                    if start_date.date() <= appointment_date <= end_date.date():
                        if appointment_date not in appointments_data:
                            appointments_data[appointment_date] = []

                        # 建立約會詳細資訊
                        subject = appointment.Subject or "無主題"
                        location = getattr(appointment, 'Location', '') or ""

                        # 清理 Teams 會議相關字樣
                        subject = self._clean_meeting_subject(subject)

                        # 只使用主題，不顯示任何位置資訊
                        display_text = subject

                        if display_text not in appointments_data[appointment_date]:
                            appointments_data[appointment_date].append(display_text)

                    # 更新進度
                    if total_items > 0:
                        progress = 50 + (i + 1) / total_items * 40
                        self._update_progress(progress)

                except Exception as item_error:
                    logger.warning(f"處理約會項目時發生錯誤: {item_error}")
                    continue

            self._update_progress(90)
            self._update_status("✅ 資料處理完成")

        except Exception as e:
            error_code = getattr(e, 'args', [None])[0] if hasattr(e, 'args') else None
            error_msg = ""

            if error_code == -2147221008:
                error_msg = ("COM 初始化錯誤\n\n"
                           "可能的解決方案:\n"
                           "• 重新啟動程式\n"
                           "• 確認 Outlook 已完全啟動\n"
                           "• 重新啟動 Outlook\n"
                           "• 以系統管理員身分執行程式")
            elif error_code == -2147221005:
                error_msg = ("Outlook 應用程式無法啟動\n\n"
                           "請檢查:\n"
                           "• Outlook 是否正確安裝\n"
                           "• Outlook 是否已設定電子郵件帳戶\n"
                           "• 重新啟動 Outlook")
            else:
                error_msg = f"無法連接或讀取 Outlook 行事曆\n\n錯誤詳情: {str(e)}\n\n請確認:\n• Outlook 已正確安裝並啟動\n• 您有權限訪問行事曆\n• 網路連線正常"

            raise ConnectionError(error_msg)

        finally:
            # 清理 COM
            try:
                import pythoncom
                pythoncom.CoUninitialize()
            except:
                pass

        return appointments_data

    def _clean_meeting_subject(self, subject: str) -> str:
        """清理會議主題，移除 Teams 相關標識"""
        if not subject:
            return subject

        import re

        # 定義需要移除的模式
        patterns_to_remove = [
            r'\(teams\)',                           # (teams)
            r'\(Microsoft Teams 会議\)',            # (Microsoft Teams 会議)
            r'\(Microsoft Teams 會議\)',            # (Microsoft Teams 會議)
            r'\(Microsoft Teams Meeting\)',         # (Microsoft Teams Meeting)
            r'\(Microsoft Teams\)',                 # (Microsoft Teams)
            r'\(Teams\)',                          # (Teams)
            r'\(teams 会議\)',                     # (teams 会議)
            r'\(teams 會議\)',                     # (teams 會議)
            r'\(teams meeting\)',                  # (teams meeting)
            r'Microsoft Teams 会議:',              # Microsoft Teams 会議:
            r'Microsoft Teams 會議:',              # Microsoft Teams 會議:
            r'Microsoft Teams Meeting:',           # Microsoft Teams Meeting:
            r'Teams 会議:',                        # Teams 会議:
            r'Teams 會議:',                        # Teams 會議:
            r'Teams Meeting:',                     # Teams Meeting:
        ]

        # 移除所有匹配的模式（不區分大小寫）
        cleaned_subject = subject
        for pattern in patterns_to_remove:
            cleaned_subject = re.sub(pattern, '', cleaned_subject, flags=re.IGNORECASE)

        # 清理多餘的空格和標點符號
        cleaned_subject = re.sub(r'\s+', ' ', cleaned_subject)  # 合併多個空格
        cleaned_subject = cleaned_subject.strip()               # 移除前後空格
        cleaned_subject = re.sub(r'^[:\-\s]+', '', cleaned_subject)  # 移除開頭的冒號、破折號、空格
        cleaned_subject = re.sub(r'[:\-\s]+$', '', cleaned_subject)  # 移除結尾的冒號、破折號、空格

        return cleaned_subject if cleaned_subject else "會議"

    def _format_data(self, appointments_data: Dict, start_date: datetime, end_date: datetime) -> str:
        """格式化約會資料為顯示文字"""
        if not appointments_data:
            return "📝 指定期間內沒有找到任何行事曆項目。\n\n💡 提示：\n• 請確認選擇的日期範圍正確\n• 檢查 Outlook 中是否有相應的約會記錄"

        output_lines = []
        current_date = start_date.date()
        end_date_date = end_date.date()

        total_appointments = 0

        # 生成每日資料
        while current_date <= end_date_date:
            weekday_index = current_date.weekday()
            weekday_str = WEEKDAY_MAP.get(weekday_index, '')
            date_str = current_date.strftime("%m/%d")

            line_prefix = f"{date_str} {weekday_str}\t"

            # 獲取當天的約會列表
            subjects = appointments_data.get(current_date, [])

            if subjects:
                total_appointments += len(subjects)
                subjects_str = '、'.join(subjects)
                output_lines.append(f"{line_prefix} {subjects_str}")
            else:
                output_lines.append(f"{line_prefix} ")

            current_date += timedelta(days=1)

        # 添加統計資訊
        days_count = (end_date.date() - start_date.date()).days + 1
        header = f"📅 行事曆轉換結果 ({start_date.strftime('%Y/%m/%d')} ~ {end_date.strftime('%Y/%m/%d')})\n"
        header += f"📊 統計：{days_count} 天內共 {total_appointments} 個約會\n"
        header += f"{'=' * 50}\n\n"

        return header + "\n".join(output_lines)

    def export_appointments(self):
        """主要的匯出函數"""
        if self.is_processing:
            return

        self.is_processing = True

        try:
            # 禁用按鈕
            self.export_button.configure(state='disabled', text="🔄 處理中...")
            self.clear_button.configure(state='disabled')

            # 顯示進度條
            self._show_progress(True)

            # 清空結果區域
            self.result_text.delete(1.0, tk.END)

            # 驗證日期
            self._update_status("🔍 驗證日期範圍...")
            start_date, end_date = self._validate_dates()

            # 獲取 Outlook 資料
            appointments_data = self._get_outlook_appointments(start_date, end_date)

            # 格式化輸出
            self._update_status("📝 正在格式化輸出...")
            self._update_progress(95)
            formatted_output = self._format_data(appointments_data, start_date, end_date)

            # 顯示結果
            self.result_text.insert(tk.END, formatted_output)
            self._update_progress(100)
            self._update_status("🎉 轉換完成！您可以複製下方結果使用")

            # 顯示完成訊息
            messagebox.showinfo(
                "轉換完成",
                f"✅ 預定表內容已成功轉換！\n\n📊 處理結果：\n• 日期範圍：{start_date.strftime('%Y/%m/%d')} ~ {end_date.strftime('%Y/%m/%d')}\n• 資料已顯示在下方文字區域\n• 您可以直接複製使用"
            )

        except ValueError as e:
            self._show_error("輸入錯誤", str(e))

        except ConnectionError as e:
            self._show_error("連接錯誤", str(e))

        except Exception as e:
            logger.error(f"匯出時發生未預期錯誤: {e}")
            self._show_error(
                "系統錯誤",
                f"處理過程中發生未預期的錯誤\n\n錯誤訊息：{str(e)}\n\n請嘗試重新啟動程式或聯繫技術支援"
            )

        finally:
            # 恢復 UI 狀態
            self.is_processing = False
            self.export_button.configure(state='normal', text="⚡ 開始轉換預定表")
            self.clear_button.configure(state='normal')
            self._show_progress(False)

    def _show_error(self, title: str, message: str):
        """顯示錯誤訊息"""
        messagebox.showerror(title, message)
        self._update_status(f"❌ 錯誤：{title}")


def check_environment() -> bool:
    """檢查執行環境"""
    if sys.platform != "win32":
        return False

    try:
        # 嘗試導入必要的模組
        import win32com.client
        import pythoncom

        # 嘗試初始化 COM 並連接 Outlook 測試
        pythoncom.CoInitialize()
        try:
            outlook = win32com.client.Dispatch("Outlook.Application")
            # 測試是否能訪問命名空間
            namespace = outlook.GetNamespace("MAPI")
            pythoncom.CoUninitialize()
            return True
        except:
            pythoncom.CoUninitialize()
            return False

    except ImportError:
        return False


def main():
    """主程式入口"""
    # 環境檢查
    if not check_environment():
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(
            "環境錯誤",
            "❌ 此工具需要 Windows 作業系統和已安裝的 Outlook 才能運行。\n\n"
            "📋 系統需求：\n"
            "• Windows 作業系統\n"
            "• Microsoft Outlook (已安裝並設定)\n"
            "• Python win32com 套件\n\n"
            "🔧 如果 Outlook 已安裝但仍顯示此錯誤：\n"
            "• 請先啟動 Outlook 並確認可正常使用\n"
            "• 設定至少一個電子郵件帳戶\n"
            "• 嘗試以系統管理員身分執行此程式"
        )
        return

    # 啟動應用程式
    try:
        root = tk.Tk()
        app = OutlookExportApp(root)

        # 設置窗口關閉事件
        def on_closing():
            if not app.is_processing:
                root.destroy()
            else:
                if messagebox.askokcancel("確認退出", "目前正在處理中，確定要退出嗎？"):
                    root.destroy()

        root.protocol("WM_DELETE_WINDOW", on_closing)
        root.mainloop()

    except Exception as e:
        logger.error(f"啟動應用程式時發生錯誤: {e}")
        messagebox.showerror("啟動錯誤", f"無法啟動應用程式：{str(e)}")


if __name__ == "__main__":
    main()