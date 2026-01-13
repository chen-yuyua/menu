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
        self.master.title("📅 Outlook 預定表轉換工具 v3.1")
        self.master.geometry("800x700")
        self.master.minsize(600, 500)

        # 設置背景色
        self.master.configure(bg=THEME['background'])

        # 響應式佈局配置
        self.master.grid_columnconfigure(1, weight=1)
        self.master.grid_rowconfigure(6, weight=1)

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
            text="📅 Outlook 預定表轉換工具 v3.1",
            font=('BIZ UDPゴシック', 16, 'bold'),
            bg=THEME['background'],
            fg=THEME['primary']
        )
        title_label.pack()

        subtitle_label = tk.Label(
            title_frame,
            text="新版 Outlook 長住化：智慧日期過濾，高效能資料讀取，精確約會檢測",
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
        quick_frame.grid(row=2, column=0, columnspan=2, pady=(10, 15), sticky='w')

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
            ("今天", self._set_today),
            ("明天", self._set_tomorrow),
            ("本週", self._set_this_week),
            ("下週", self._set_next_week)
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

        # === 模式選擇區域 ===
        mode_frame = tk.Frame(input_frame, bg=THEME['surface'])
        mode_frame.grid(row=3, column=0, columnspan=2, pady=(5, 0), sticky='w')

        # 調試模式勾選框（默認勾選）
        self.debug_mode_var = tk.BooleanVar(value=True)
        debug_check = tk.Checkbutton(
            mode_frame,
            text="🔧 調試模式",
            variable=self.debug_mode_var,
            font=('BIZ UDPゴシック', 9),
            bg=THEME['surface'],
            fg=THEME['text_primary'],
            selectcolor=THEME['surface'],
            activebackground=THEME['surface'],
            activeforeground=THEME['text_primary'],
            cursor='hand2'
        )
        debug_check.pack(side='left')

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

        # === 調試資訊區域 ===
        self.debug_label = tk.Label(
            self.master,
            text="",
            font=('BIZ UDPゴシック', 8),
            bg=THEME['background'],
            fg=THEME['success'],
            justify='left'
        )
        self.debug_label.grid(row=5, column=0, columnspan=3, pady=(0, 10))

        # === 結果顯示區域 ===
        result_frame = tk.Frame(self.master, bg=THEME['background'])
        result_frame.grid(row=6, column=0, columnspan=3, padx=20, pady=(0, 20), sticky='nsew')
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

    def _set_today(self):
        """設置為今天"""
        today = datetime.now().date()
        self.start_date_entry.set_date(today)
        self.end_date_entry.set_date(today)

    def _set_tomorrow(self):
        """設置為明天"""
        tomorrow = (datetime.now() + timedelta(days=1)).date()
        self.start_date_entry.set_date(tomorrow)
        self.end_date_entry.set_date(tomorrow)

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
        self.debug_label.config(text="")
        self._update_status("📝 結果已清除，請重新選擇日期範圍進行轉換")

    def _update_status(self, message: str):
        """更新狀態標籤"""
        self.status_label.config(text=message)
        self.master.update_idletasks()

    def _update_debug_info(self, message: str):
        """更新調試資訊"""
        if self.debug_mode_var.get():
            current_text = self.debug_label.cget("text")
            if current_text:
                new_text = current_text + " | " + message
            else:
                new_text = message
            self.debug_label.config(text=new_text)
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
        """獲取 Outlook 約會資料 - 完全不過濾，100% 依照 Outlook 顯示"""
        appointments_data = {}

        try:
            self._update_status("🔄 正在連接 Outlook...")
            self._update_progress(10)

            # 初始化 COM
            pythoncom.CoInitialize()

            # 連接 Outlook
            outlook = win32.Dispatch("Outlook.Application")
            namespace = outlook.GetNamespace("MAPI")
            calendar = namespace.GetDefaultFolder(9)  # 9 = olFolderCalendar

            self._update_progress(30)
            self._update_status("📅 正在讀取行事曆資料...")

            # 關鍵設定：啟用週期性會議展開
            items = calendar.Items
            items.Sort("[Start]", False)
            items.IncludeRecurrences = True  # 展開所有定期會議

            # 設置日期過濾器 - 使用更寬鬆的範圍
            # 往前後各延伸一天以確保不會遺漏任何項目
            filter_start = start_date - timedelta(days=1)
            filter_end = end_date + timedelta(days=2)

            filter_criteria = (
                f"[Start] >= '{filter_start.strftime('%m/%d/%Y 00:00')}' AND "
                f"[Start] < '{filter_end.strftime('%m/%d/%Y 23:59')}'"
            )

            self._update_progress(50)
            self._update_debug_info("開始讀取 Outlook 資料")

            restricted_items = items.Restrict(filter_criteria)
            total_items = restricted_items.Count

            self._update_debug_info(f"API 返回 {total_items} 個項目")
            self._update_status(f"📊 找到 {total_items} 個行事曆項目，正在處理...")

            # 處理每個約會項目 - 不做任何過濾
            processed_count = 0
            out_of_range_count = 0

            for i, appointment in enumerate(restricted_items):
                try:
                    # 獲取約會的開始時間
                    appointment_start = appointment.Start
                    appointment_date = appointment_start.date()

                    # 只過濾日期範圍，其他一律保留
                    if not (start_date.date() <= appointment_date <= end_date.date()):
                        out_of_range_count += 1
                        continue

                    if appointment_date not in appointments_data:
                        appointments_data[appointment_date] = []

                    # 獲取約會資訊
                    subject = appointment.Subject or "無主題"

                    # 清理 Teams 會議標識
                    subject = self._clean_meeting_subject(subject)

                    # 獲取時間資訊
                    is_all_day = getattr(appointment, 'AllDayEvent', False)

                    if is_all_day:
                        time_info = None
                    else:
                        try:
                            end_time = appointment.End
                            time_info = (appointment_start, end_time)
                        except:
                            time_info = None

                    # 建立約會物件
                    appointment_info = {
                        'subject': subject,
                        'time_info': time_info,
                        'is_all_day': is_all_day,
                        'start': appointment_start  # 保留原始開始時間用於排序和去重
                    }

                    # 簡單去重：只檢查主題和開始時間完全相同的項目
                    is_duplicate = False
                    for existing_appt in appointments_data[appointment_date]:
                        if existing_appt['subject'] == subject:
                            # 比較開始時間
                            if time_info and existing_appt['time_info']:
                                existing_start_str = existing_appt['start'].strftime('%Y-%m-%d %H:%M')
                                current_start_str = appointment_start.strftime('%Y-%m-%d %H:%M')
                                if existing_start_str == current_start_str:
                                    is_duplicate = True
                                    break
                            elif not time_info and not existing_appt['time_info']:
                                # 兩者都是全天事件且主題相同
                                is_duplicate = True
                                break

                    if not is_duplicate:
                        appointments_data[appointment_date].append(appointment_info)
                        processed_count += 1

                        # 調試輸出
                        if self.debug_mode_var.get():
                            logger.info(f"添加: {appointment_date} - {subject}")

                    # 更新進度
                    if total_items > 0:
                        progress = 50 + (i + 1) / total_items * 40
                        self._update_progress(progress)

                except Exception as item_error:
                    if self.debug_mode_var.get():
                        logger.warning(f"處理項目時出錯: {item_error}")
                    continue

            # 對每一天的約會按時間排序
            for date_key in appointments_data:
                appointments_data[date_key].sort(
                    key=lambda x: x['start'] if x.get('start') else datetime.min
                )

            self._update_progress(90)
            self._update_debug_info(f"處理: {processed_count} 項 | 範圍外: {out_of_range_count} 項")
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
                pythoncom.CoUninitialize()
            except:
                pass

        return appointments_data

    def _clean_meeting_subject(self, subject: str) -> str:
        """清理會議主題，移除 Teams 相關標識"""
        if not subject:
            return subject

        # 定義需要移除的模式
        patterns_to_remove = [
            r'\s*\(teams\)\s*',
            r'\s*\(Microsoft Teams 会議\)\s*',
            r'\s*\(Microsoft Teams 會議\)\s*',
            r'\s*\(Microsoft Teams Meeting\)\s*',
            r'\s*\(Microsoft Teams\)\s*',
            r'\s*\(Teams\)\s*',
            r'\s*\(teams 会議\)\s*',
            r'\s*\(teams 會議\)\s*',
            r'\s*\(teams meeting\)\s*',
            r'Microsoft Teams 会議:\s*',
            r'Microsoft Teams 會議:\s*',
            r'Microsoft Teams Meeting:\s*',
            r'Teams 会議:\s*',
            r'Teams 會議:\s*',
            r'Teams Meeting:\s*',
        ]

        # 移除所有匹配的模式（不區分大小寫）
        cleaned_subject = subject
        for pattern in patterns_to_remove:
            cleaned_subject = re.sub(pattern, '', cleaned_subject, flags=re.IGNORECASE)

        # 清理多餘的空格和標點符號
        cleaned_subject = re.sub(r'\s+', ' ', cleaned_subject)
        cleaned_subject = cleaned_subject.strip()
        cleaned_subject = re.sub(r'^[:\-\s]+', '', cleaned_subject)
        cleaned_subject = re.sub(r'[:\-\s]+$', '', cleaned_subject)

        return cleaned_subject if cleaned_subject else "會議"

    def _format_data(self, appointments_data: Dict, start_date: datetime, end_date: datetime) -> str:
        """格式化約會資料為顯示文字"""
        if not appointments_data:
            return "📝 指定期間內沒有找到任何行事曆項目。\n\n💡 提示：\n• 請確認選擇的日期範圍正確\n• 檢查 Outlook 中是否有相應的約會記錄"

        # 檢查是否為單日查詢
        is_single_day = start_date.date() == end_date.date()

        if is_single_day:
            return self._format_single_day_data(appointments_data, start_date)
        else:
            return self._format_multi_day_data(appointments_data, start_date, end_date)

    def _format_single_day_data(self, appointments_data: Dict, target_date: datetime) -> str:
        """格式化單日約會資料為時間表格式"""
        target_date_obj = target_date.date()
        appointments = appointments_data.get(target_date_obj, [])

        if not appointments:
            weekday_index = target_date_obj.weekday()
            weekday_str = WEEKDAY_MAP.get(weekday_index, '')
            return f"📝 {target_date_obj.strftime('%Y/%m/%d')} {weekday_str} 沒有找到任何行事曆項目。"

        # 分離全天事件和時間事件
        timed_appointments = []
        all_day_appointments = []

        for appt in appointments:
            if appt['is_all_day']:
                all_day_appointments.append(appt)
            else:
                timed_appointments.append(appt)

        # 建立輸出
        weekday_index = target_date_obj.weekday()
        weekday_str = WEEKDAY_MAP.get(weekday_index, '')

        output_lines = []
        output_lines.append(f"📅 {target_date_obj.strftime('%Y/%m/%d')} {weekday_str} 預定表")
        output_lines.append("=" * 50)

        if all_day_appointments:
            output_lines.append("🌅 全天事件:")
            for appt in all_day_appointments:
                output_lines.append(f"　　　　　　　　　{appt['subject']}")
            output_lines.append("")

        if timed_appointments:
            output_lines.append("🕐 時間事件:")
            output_lines.append("起始時間\t結束時間\t預定件名")
            output_lines.append("-" * 40)

            for appt in timed_appointments:
                if appt['time_info']:
                    start_time, end_time = appt['time_info']
                    start_str = start_time.strftime('%H:%M')
                    end_str = end_time.strftime('%H:%M') if end_time else "未知"
                    output_lines.append(f"{start_str}\t～{end_str}\t{appt['subject']}")
                else:
                    output_lines.append(f"時間未定\t\t\t{appt['subject']}")

        return "\n".join(output_lines)

    def _format_multi_day_data(self, appointments_data: Dict, start_date: datetime, end_date: datetime) -> str:
        """格式化多日約會資料為原始格式"""
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
            appointments = appointments_data.get(current_date, [])

            if appointments:
                total_appointments += len(appointments)
                subjects = [appt['subject'] for appt in appointments]
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

            # 清空結果區域和調試資訊
            self.result_text.delete(1.0, tk.END)
            self.debug_label.config(text="")

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

            # 檢查是否為單日格式
            is_single_day = start_date.date() == end_date.date()
            if is_single_day:
                self._update_status("🎉 單日時間表轉換完成！您可以複製下方結果使用")
            else:
                self._update_status("🎉 多日行程轉換完成！您可以複製下方結果使用")

            # 顯示完成訊息
            messagebox.showinfo(
                "轉換完成",
                f"✅ 預定表內容已成功轉換！\n\n📊 處理結果：\n• 日期範圍：{start_date.strftime('%Y/%m/%d')} ~ {end_date.strftime('%Y/%m/%d')}\n• 格式：{'單日時間表' if is_single_day else '多日行程表'}\n• 資料已顯示在下方文字區域\n• 您可以直接複製使用"
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
