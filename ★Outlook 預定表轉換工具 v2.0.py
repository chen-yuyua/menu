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

# 配置日誌 - 同時輸出到控制台和文件
log_filename = f"outlook_export_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_filename, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)
logger.info(f"日誌文件已創建: {log_filename}")

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
    'primary': '#2E86AB',
    'secondary': '#A23B72',
    'success': '#F18F01',
    'background': '#F5F5F5',
    'surface': '#FFFFFF',
    'text_primary': '#2D3436',
    'text_secondary': '#636E72',
    'border': '#DDD',
    'hover': '#74B9FF'
}

class ModernButton(tk.Button):
    """現代化按鈕組件"""
    def __init__(self, parent, **kwargs):
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
        self.is_processing = False

    def _setup_window(self):
        """設置主窗口屬性"""
        self.master.title("📅 Outlook 預定表轉換工具 v3.6 最終版")
        self.master.geometry("800x700")
        self.master.minsize(600, 500)
        self.master.configure(bg=THEME['background'])
        self.master.grid_columnconfigure(1, weight=1)
        self.master.grid_rowconfigure(6, weight=1)

    def _setup_styles(self):
        """設置 ttk 樣式"""
        self.style = ttk.Style()
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
            text="📅 Outlook 預定表轉換工具 v3.6",
            font=('BIZ UDPゴシック', 16, 'bold'),
            bg=THEME['background'],
            fg=THEME['primary']
        )
        title_label.pack()

        subtitle_label = tk.Label(
            title_frame,
            text="最終版：完整功能 | 詳細日誌 | 穩定可靠",
            font=('BIZ UDPゴシック', 9),
            bg=THEME['background'],
            fg=THEME['text_secondary']
        )
        subtitle_label.pack(pady=(5, 0))

        # === 輸入區域 ===
        input_frame = tk.Frame(self.master, bg=THEME['surface'], relief='solid', bd=1)
        input_frame.grid(row=1, column=0, columnspan=3, padx=20, pady=(0, 20), sticky='ew')
        input_frame.grid_columnconfigure(1, weight=1)
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
        self.start_date_entry.set_date(datetime.now().date())
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
        self.end_date_entry.set_date(datetime.now().date() + timedelta(days=6))
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
            btn.bind('<Enter>', lambda e, b=btn: b.configure(bg=THEME['text_secondary'], fg='white'))
            btn.bind('<Leave>', lambda e, b=btn: b.configure(bg=THEME['border'], fg=THEME['text_primary']))

        # === 模式選擇區域 ===
        mode_frame = tk.Frame(input_frame, bg=THEME['surface'])
        mode_frame.grid(row=3, column=0, columnspan=2, pady=(5, 0), sticky='w')

        self.debug_mode_var = tk.BooleanVar(value=False)
        debug_check = tk.Checkbutton(
            mode_frame,
            text="🔧 調試模式（顯示詳細日誌）",
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
        self.progress_bar.grid_remove()

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

        text_frame = tk.Frame(result_frame, bg=THEME['surface'], relief='solid', bd=1)
        text_frame.grid(row=1, column=0, sticky='nsew')
        text_frame.grid_columnconfigure(0, weight=1)
        text_frame.grid_rowconfigure(0, weight=1)

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

        scrollbar = Scrollbar(text_frame, command=self.result_text.yview)
        scrollbar.grid(row=0, column=1, sticky='ns')
        self.result_text.config(yscrollcommand=scrollbar.set)

    def _setup_layout(self):
        """設置佈局管理"""
        pass

    def _set_today(self):
        today = datetime.now().date()
        self.start_date_entry.set_date(today)
        self.end_date_entry.set_date(today)

    def _set_tomorrow(self):
        tomorrow = (datetime.now() + timedelta(days=1)).date()
        self.start_date_entry.set_date(tomorrow)
        self.end_date_entry.set_date(tomorrow)

    def _set_this_week(self):
        today = datetime.now()
        start_of_week = today - timedelta(days=today.weekday())
        end_of_week = start_of_week + timedelta(days=6)
        self.start_date_entry.set_date(start_of_week.date())
        self.end_date_entry.set_date(end_of_week.date())

    def _set_next_week(self):
        today = datetime.now()
        start_of_next_week = today + timedelta(days=(7 - today.weekday()))
        end_of_next_week = start_of_next_week + timedelta(days=6)
        self.start_date_entry.set_date(start_of_next_week.date())
        self.end_date_entry.set_date(end_of_next_week.date())

    def _start_export_thread(self):
        if self.is_processing:
            return
        thread = threading.Thread(target=self.export_appointments, daemon=True)
        thread.start()

    def _clear_results(self):
        self.result_text.delete(1.0, tk.END)
        self.debug_label.config(text="")
        self._update_status("📝 結果已清除，請重新選擇日期範圍進行轉換")

    def _update_status(self, message: str):
        self.status_label.config(text=message)
        self.master.update_idletasks()

    def _update_debug_info(self, message: str):
        if self.debug_mode_var.get():
            current_text = self.debug_label.cget("text")
            if current_text:
                new_text = current_text + " | " + message
            else:
                new_text = message
            self.debug_label.config(text=new_text)
            self.master.update_idletasks()

    def _show_progress(self, show: bool = True):
        if show:
            self.progress_bar.grid()
            self.progress_var.set(0)
        else:
            self.progress_bar.grid_remove()

    def _update_progress(self, value: float):
        self.progress_var.set(value)
        self.master.update_idletasks()

    def _validate_dates(self) -> tuple[datetime, datetime]:
        try:
            start_date_obj = self.start_date_entry.get_date()
            end_date_obj = self.end_date_entry.get_date()
            start_date = datetime.combine(start_date_obj, datetime.min.time())
            end_date = datetime.combine(end_date_obj, datetime.min.time())

            if start_date > end_date:
                raise ValueError("開始日期不能晚於結束日期")
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

            pythoncom.CoInitialize()
            outlook = win32.Dispatch("Outlook.Application")
            namespace = outlook.GetNamespace("MAPI")
            calendar = namespace.GetDefaultFolder(9)

            self._update_progress(30)
            self._update_status("📅 正在讀取行事曆資料...")

            items = calendar.Items
            items.Sort("[Start]", False)
            items.IncludeRecurrences = True

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

            processed_count = 0
            out_of_range_count = 0
            duplicate_count = 0

            for i, appointment in enumerate(restricted_items):
                try:
                    appointment_start = appointment.Start
                    appointment_date = appointment_start.date()

                    if not (start_date.date() <= appointment_date <= end_date.date()):
                        out_of_range_count += 1
                        continue

                    if appointment_date not in appointments_data:
                        appointments_data[appointment_date] = []

                    subject = appointment.Subject or "無主題"
                    subject = self._clean_meeting_subject(subject)

                    is_all_day = getattr(appointment, 'AllDayEvent', False)

                    if is_all_day:
                        time_info = None
                    else:
                        try:
                            end_time = appointment.End
                            time_info = (appointment_start, end_time)
                        except:
                            time_info = None

                    appointment_info = {
                        'subject': subject,
                        'time_info': time_info,
                        'is_all_day': is_all_day,
                        'start': appointment_start
                    }

                    # 去重邏輯
                    is_duplicate = False
                    for existing_appt in appointments_data[appointment_date]:
                        if existing_appt['subject'] != subject:
                            continue

                        if time_info and existing_appt['time_info']:
                            existing_start = existing_appt['start']
                            existing_end = existing_appt['time_info'][1]
                            current_end = time_info[1]

                            start_match = existing_start.strftime('%Y-%m-%d %H:%M:%S') == appointment_start.strftime('%Y-%m-%d %H:%M:%S')
                            end_match = existing_end.strftime('%Y-%m-%d %H:%M:%S') == current_end.strftime('%Y-%m-%d %H:%M:%S')

                            if start_match and end_match:
                                is_duplicate = True
                                duplicate_count += 1
                                if self.debug_mode_var.get():
                                    logger.info(f"× 去重: {appointment_date} {appointment_start.strftime('%H:%M')}-{current_end.strftime('%H:%M')} - {subject[:40]}{'...' if len(subject) > 40 else ''}")
                                break
                        elif not time_info and not existing_appt['time_info']:
                            is_duplicate = True
                            duplicate_count += 1
                            if self.debug_mode_var.get():
                                logger.info(f"× 去重（全天）: {appointment_date} - {subject[:40]}{'...' if len(subject) > 40 else ''}")
                            break

                    if not is_duplicate:
                        appointments_data[appointment_date].append(appointment_info)
                        processed_count += 1

                        if self.debug_mode_var.get():
                            time_str = ""
                            if time_info:
                                time_str = f" {appointment_start.strftime('%H:%M')}-{time_info[1].strftime('%H:%M')}"
                            else:
                                time_str = " (全天)"
                            logger.info(f"✓ 添加: {appointment_date}{time_str} - {subject[:50]}{'...' if len(subject) > 50 else ''}")

                    if total_items > 0:
                        progress = 50 + (i + 1) / total_items * 40
                        self._update_progress(progress)

                except Exception as item_error:
                    if self.debug_mode_var.get():
                        logger.warning(f"處理項目時出錯: {item_error}")
                    continue

            for date_key in appointments_data:
                appointments_data[date_key].sort(
                    key=lambda x: x['start'] if x.get('start') else datetime.min
                )

            self._update_progress(90)
            self._update_debug_info(f"✓ 處理: {processed_count} 項 | 去重: {duplicate_count} 項 | 範圍外: {out_of_range_count} 項")
            self._update_status("✅ 資料處理完成")

        except Exception as e:
            error_msg = f"無法連接或讀取 Outlook 行事曆\n\n錯誤詳情: {str(e)}"
            raise ConnectionError(error_msg)

        finally:
            try:
                pythoncom.CoUninitialize()
            except:
                pass

        return appointments_data

    def _clean_meeting_subject(self, subject: str) -> str:
        if not subject:
            return subject

        patterns_to_remove = [
            r'\s*\(teams\)\s*',
            r'\s*\(Microsoft Teams 会議\)\s*',
            r'\s*\(Microsoft Teams 會議\)\s*',
            r'\s*\(Microsoft Teams Meeting\)\s*',
            r'\s*\(Microsoft Teams\)\s*',
            r'\s*\(Teams\)\s*',
            r'Microsoft Teams 会議:\s*',
            r'Microsoft Teams 會議:\s*',
            r'Microsoft Teams Meeting:\s*',
        ]

        cleaned_subject = subject
        for pattern in patterns_to_remove:
            cleaned_subject = re.sub(pattern, '', cleaned_subject, flags=re.IGNORECASE)

        cleaned_subject = re.sub(r'\s+', ' ', cleaned_subject)
        cleaned_subject = cleaned_subject.strip()
        cleaned_subject = re.sub(r'^[:\-\s]+', '', cleaned_subject)
        cleaned_subject = re.sub(r'[:\-\s]+$', '', cleaned_subject)

        return cleaned_subject if cleaned_subject else "會議"

    def _format_data(self, appointments_data: Dict, start_date: datetime, end_date: datetime) -> str:
        if not appointments_data:
            return "📝 指定期間內沒有找到任何行事曆項目。"

        is_single_day = start_date.date() == end_date.date()

        if is_single_day:
            return self._format_single_day_data(appointments_data, start_date)
        else:
            return self._format_multi_day_data(appointments_data, start_date, end_date)

    def _format_single_day_data(self, appointments_data: Dict, target_date: datetime) -> str:
        target_date_obj = target_date.date()
        appointments = appointments_data.get(target_date_obj, [])

        if not appointments:
            weekday_index = target_date_obj.weekday()
            weekday_str = WEEKDAY_MAP.get(weekday_index, '')
            return f"📝 {target_date_obj.strftime('%Y/%m/%d')} {weekday_str} 沒有找到任何行事曆項目。"

        timed_appointments = []
        all_day_appointments = []

        for appt in appointments:
            if appt['is_all_day']:
                all_day_appointments.append(appt)
            else:
                timed_appointments.append(appt)

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
        output_lines = []
        current_date = start_date.date()
        end_date_date = end_date.date()
        total_appointments = 0

        while current_date <= end_date_date:
            weekday_index = current_date.weekday()
            weekday_str = WEEKDAY_MAP.get(weekday_index, '')
            date_str = current_date.strftime("%m/%d")
            line_prefix = f"{date_str} {weekday_str}\t"

            appointments = appointments_data.get(current_date, [])

            if appointments:
                total_appointments += len(appointments)
                subjects = [appt['subject'] for appt in appointments]
                subjects_str = '、'.join(subjects)
                output_lines.append(f"{line_prefix} {subjects_str}")
            else:
                output_lines.append(f"{line_prefix} ")

            current_date += timedelta(days=1)

        days_count = (end_date.date() - start_date.date()).days + 1
        header = f"📅 行事曆轉換結果 ({start_date.strftime('%Y/%m/%d')} ~ {end_date.strftime('%Y/%m/%d')})\n"
        header += f"📊 統計：{days_count} 天內共 {total_appointments} 個約會\n"
        header += f"{'=' * 50}\n\n"

        return header + "\n".join(output_lines)

    def export_appointments(self):
        if self.is_processing:
            return

        self.is_processing = True

        try:
            self.export_button.configure(state='disabled', text="🔄 處理中...")
            self.clear_button.configure(state='disabled')
            self._show_progress(True)
            self.result_text.delete(1.0, tk.END)
            self.debug_label.config(text="")

            logger.info("=" * 80)
            logger.info(f"開始轉換 Outlook 預定表")
            logger.info(f"日期範圍: {self.start_date_entry.get()} ~ {self.end_date_entry.get()}")
            logger.info(f"調試模式: {'開啟' if self.debug_mode_var.get() else '關閉'}")
            logger.info("=" * 80)

            self._update_status("🔍 驗證日期範圍...")
            start_date, end_date = self._validate_dates()

            appointments_data = self._get_outlook_appointments(start_date, end_date)

            self._update_status("📝 正在格式化輸出...")
            self._update_progress(95)
            formatted_output = self._format_data(appointments_data, start_date, end_date)

            self.result_text.insert(tk.END, formatted_output)
            self._update_progress(100)

            is_single_day = start_date.date() == end_date.date()
            if is_single_day:
                self._update_status("🎉 單日時間表轉換完成！您可以複製下方結果使用")
            else:
                self._update_status("🎉 多日行程轉換完成！您可以複製下方結果使用")

            import os
            log_file_path = os.path.abspath(log_filename)

            messagebox.showinfo(
                "轉換完成",
                f"✅ 預定表內容已成功轉換！\n\n"
                f"📊 處理結果：\n"
                f"• 日期範圍：{start_date.strftime('%Y/%m/%d')} ~ {end_date.strftime('%Y/%m/%d')}\n"
                f"• 格式：{'單日時間表' if is_single_day else '多日行程表'}\n"
                f"• 資料已顯示在下方文字區域\n\n"
                f"📝 詳細日誌已保存至：\n{log_file_path}"
            )

            logger.info("=" * 80)
            logger.info("轉換完成！")
            logger.info(f"日誌文件位置: {log_file_path}")
            logger.info("=" * 80)

        except ValueError as e:
            self._show_error("輸入錯誤", str(e))
        except ConnectionError as e:
            self._show_error("連接錯誤", str(e))
        except Exception as e:
            logger.error(f"匯出時發生未預期錯誤: {e}")
            self._show_error("系統錯誤", f"處理過程中發生未預期的錯誤\n\n錯誤訊息：{str(e)}")

        finally:
            self.is_processing = False
            self.export_button.configure(state='normal', text="⚡ 開始轉換預定表")
            self.clear_button.configure(state='normal')
            self._show_progress(False)

    def _show_error(self, title: str, message: str):
        messagebox.showerror(title, message)
        self._update_status(f"❌ 錯誤：{title}")


def main():
    try:
        root = tk.Tk()
        app = OutlookExportApp(root)

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
