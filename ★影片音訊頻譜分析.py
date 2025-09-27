import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
from moviepy.editor import VideoFileClip
from scipy.io import wavfile
from scipy.fft import fft, fftfreq
from scipy import signal
import os
import threading
from pathlib import Path
import platform
from PIL import Image
import datetime

# 優化的色彩配置 - 增強邊框和分隔效果
JAPANESE_COLORS = {
    # 主要背景色 - 溫暖的淺米色
    'bg_primary': '#F7F3E9',
    # 次要背景色 - 更淺的米白色
    'bg_secondary': '#FEFCF7',
    # 卡片背景色 - 純白色
    'bg_card': '#FFFFFF',
    # 主要文字色 - 黑色（易讀性）
    'text_primary': '#000000',
    # 次要文字色 - 深灰色
    'text_secondary': '#333333',
    # 提示文字色 - 中灰色
    'text_hint': '#666666',
    # 版本資訊文字色 - 淺灰色
    'text_version': '#999999',
    # 主要強調色 - 柔和的藍色
    'accent_primary': '#6FA8DC',
    # 次要強調色 - 溫暖的綠色
    'accent_secondary': '#81C784',
    # 警告色 - 柔和的橙色
    'warning': '#FFB74D',
    # 錯誤色 - 柔和的紅色
    'error': '#E57373',
    # 成功色 - 清新的綠色
    'success': '#A5D6A7',
    # 邊框色 - 較深的灰色（增強視覺分隔）
    'border': '#D0D0D0',
    # 分隔線色 - 中等灰色
    'divider': '#E8E8E8',
    # 陰影色 - 淡灰色
    'shadow': '#C0C0C0',
    # 強邊框色 - 用於重要區塊
    'border_strong': '#B0B0B0',
    # 輕邊框色 - 用於次要區塊
    'border_light': '#E0E0E0'
}

# 設置matplotlib日系風格
def setup_matplotlib_japanese_style():
    """設置matplotlib的日系風格"""
    plt.rcParams.update({
        'figure.facecolor': JAPANESE_COLORS['bg_card'],
        'axes.facecolor': JAPANESE_COLORS['bg_secondary'],
        'axes.edgecolor': JAPANESE_COLORS['border'],
        'axes.labelcolor': JAPANESE_COLORS['text_primary'],
        'axes.axisbelow': True,
        'axes.grid': True,
        'grid.color': JAPANESE_COLORS['divider'],
        'grid.linewidth': 0.5,
        'text.color': JAPANESE_COLORS['text_primary'],
        'xtick.color': JAPANESE_COLORS['text_secondary'],
        'ytick.color': JAPANESE_COLORS['text_secondary'],
        'xtick.labelsize': 9,
        'ytick.labelsize': 9,
        'axes.titlesize': 12,
        'axes.labelsize': 10,
        'lines.linewidth': 1.5,
        'patch.linewidth': 0.5,
        'patch.facecolor': JAPANESE_COLORS['accent_primary'],
        'patch.edgecolor': JAPANESE_COLORS['border']
    })

# 設置中文字體
def setup_chinese_font():
    """設置中文字體支援"""
    import matplotlib.font_manager as fm

    # 根據作業系統選擇合適的中文字體
    system = platform.system()
    if system == "Windows":
        chinese_fonts = ['Microsoft YaHei', 'SimHei', 'SimSun', 'KaiTi']
    elif system == "Darwin":  # macOS
        chinese_fonts = ['Hei', 'STHeiti', 'Arial Unicode MS']
    else:  # Linux
        chinese_fonts = ['WenQuanYi Micro Hei', 'Droid Sans Fallback', 'DejaVu Sans']

    # 嘗試設置中文字體
    for font_name in chinese_fonts:
        try:
            plt.rcParams['font.sans-serif'] = [font_name]
            plt.rcParams['axes.unicode_minus'] = False
            # 測試字體是否可用
            fig, ax = plt.subplots(figsize=(1, 1))
            ax.text(0.5, 0.5, '測試', fontsize=12)
            plt.close(fig)
            print(f"成功設置字體: {font_name}")
            return font_name
        except:
            continue

    # 如果都失敗，使用默認字體並警告用戶
    print("警告: 無法找到合適的中文字體，可能會出現顯示問題")
    return None

class VideoAudioAnalyzer:
    def __init__(self, root):
        self.root = root
        self.root.title("Audio Spectrum Analyzer - 影片音訊頻譜分析器")
        self.root.geometry("1440x980")

        # 設置日系風格
        self.setup_japanese_ui_style()

        # 設置matplotlib樣式
        setup_matplotlib_japanese_style()

        # 設置中文字體
        self.chinese_font = setup_chinese_font()

        # 設置tkinter字體
        self.setup_fonts()

        # 變數
        self.video_file = None
        self.temp_audio_file = "temp_audio.wav"
        self.is_processing = False
        self.audio_duration = 0
        self.sample_rate = 0
        self.save_directory = None
        self.captured_screenshots = []

        # 分析類型設定
        self.analysis_type = tk.StringVar(value="high_freq")  # 預設為高頻分析

        # 時頻分析結果
        self.time_freq_data = None
        self.time_peaks = []

        # 創建GUI元素
        self.create_widgets()

    def setup_japanese_ui_style(self):
        """設置日系UI風格 - 增強邊框效果"""
        # 設置主窗口背景
        self.root.configure(bg=JAPANESE_COLORS['bg_primary'])

        # 創建自定義樣式
        self.style = ttk.Style()

        # 設置主題
        self.style.theme_use('clam')

        # 配置各種元件的樣式
        self.style.configure('Title.TLabel',
                           font=('Yu Gothic UI', 16, 'bold'),
                           foreground=JAPANESE_COLORS['text_primary'],
                           background=JAPANESE_COLORS['bg_card'])

        self.style.configure('Version.TLabel',
                           font=('Yu Gothic UI', 8),
                           foreground=JAPANESE_COLORS['text_version'],
                           background=JAPANESE_COLORS['bg_card'])

        self.style.configure('Heading.TLabel',
                           font=('Yu Gothic UI', 12, 'bold'),
                           foreground=JAPANESE_COLORS['text_primary'],
                           background=JAPANESE_COLORS['bg_card'])

        self.style.configure('Body.TLabel',
                           font=('Yu Gothic UI', 9),
                           foreground=JAPANESE_COLORS['text_primary'],
                           background=JAPANESE_COLORS['bg_card'])

        self.style.configure('Secondary.TLabel',
                           font=('Yu Gothic UI', 9),
                           foreground=JAPANESE_COLORS['text_secondary'],
                           background=JAPANESE_COLORS['bg_card'])

        self.style.configure('Hint.TLabel',
                           font=('Yu Gothic UI', 8),
                           foreground=JAPANESE_COLORS['text_hint'],
                           background=JAPANESE_COLORS['bg_card'])

        # 按鈕樣式 - 增強邊框
        self.style.configure('Primary.TButton',
                           font=('Yu Gothic UI', 9, 'bold'),
                           foreground='white',
                           background=JAPANESE_COLORS['accent_primary'],
                           borderwidth=2,
                           focuscolor='none',
                           relief='solid')

        self.style.map('Primary.TButton',
                      background=[('active', '#5A9BD4'),
                                ('pressed', '#4A8BC2')],
                      bordercolor=[('active', JAPANESE_COLORS['border_strong'])])

        self.style.configure('Secondary.TButton',
                           font=('Yu Gothic UI', 9),
                           foreground=JAPANESE_COLORS['text_primary'],
                           background=JAPANESE_COLORS['bg_secondary'],
                           borderwidth=2,
                           focuscolor='none',
                           relief='solid')

        self.style.map('Secondary.TButton',
                      background=[('active', JAPANESE_COLORS['divider']),
                                ('pressed', JAPANESE_COLORS['border'])],
                      bordercolor=[('active', JAPANESE_COLORS['border_strong'])])

        # 框架樣式 - 增強邊框
        self.style.configure('Card.TLabelframe',
                           background=JAPANESE_COLORS['bg_card'],
                           borderwidth=2,
                           relief='solid',
                           bordercolor=JAPANESE_COLORS['border'])

        self.style.configure('Card.TLabelframe.Label',
                           font=('Yu Gothic UI', 10, 'bold'),
                           foreground=JAPANESE_COLORS['text_primary'],
                           background=JAPANESE_COLORS['bg_card'])

        # 強調框架樣式 - 更明顯的邊框
        self.style.configure('StrongCard.TLabelframe',
                           background=JAPANESE_COLORS['bg_card'],
                           borderwidth=3,
                           relief='solid',
                           bordercolor=JAPANESE_COLORS['border_strong'])

        self.style.configure('StrongCard.TLabelframe.Label',
                           font=('Yu Gothic UI', 10, 'bold'),
                           foreground=JAPANESE_COLORS['text_primary'],
                           background=JAPANESE_COLORS['bg_card'])

        # 進度條樣式
        self.style.configure('Japanese.Horizontal.TProgressbar',
                           background=JAPANESE_COLORS['accent_primary'],
                           troughcolor=JAPANESE_COLORS['divider'],
                           borderwidth=1,
                           lightcolor=JAPANESE_COLORS['accent_primary'],
                           darkcolor=JAPANESE_COLORS['accent_primary'])

        # Notebook樣式 - 增強邊框
        self.style.configure('Japanese.TNotebook',
                           background=JAPANESE_COLORS['bg_card'],
                           borderwidth=2,
                           relief='solid')

        self.style.configure('Japanese.TNotebook.Tab',
                           background=JAPANESE_COLORS['bg_secondary'],
                           foreground=JAPANESE_COLORS['text_primary'],
                           padding=[20, 8],
                           font=('Yu Gothic UI', 9),
                           borderwidth=1)

        self.style.map('Japanese.TNotebook.Tab',
                      background=[('selected', JAPANESE_COLORS['bg_card']),
                                ('active', JAPANESE_COLORS['divider'])],
                      foreground=[('selected', JAPANESE_COLORS['text_primary'])])

    def setup_fonts(self):
        """設置字體"""
        system = platform.system()
        if system == "Windows":
            self.font_family = 'Yu Gothic UI'
        elif system == "Darwin":  # macOS
            self.font_family = 'Hiragino Sans'
        else:  # Linux
            self.font_family = 'Noto Sans CJK JP'

        # 嘗試使用日系字體，失敗則使用系統默認
        try:
            test_font = (self.font_family, 9)
            test_label = tk.Label(self.root, text="テスト", font=test_font)
            test_label.destroy()
        except:
            self.font_family = 'TkDefaultFont'

        self.fonts = {
            'title': (self.font_family, 16, 'bold'),
            'heading': (self.font_family, 12, 'bold'),
            'body': (self.font_family, 9),
            'small': (self.font_family, 8),
            'code': ('Consolas', 9)
        }

    def create_widgets(self):
        # 創建主容器框架 - 添加明顯邊框
        main_container = tk.Frame(self.root, bg=JAPANESE_COLORS['bg_primary'],
                                 relief='solid', borderwidth=2,
                                 highlightbackground=JAPANESE_COLORS['border_strong'])
        main_container.pack(fill="both", expand=True, padx=10, pady=10)

        # 主框架 - 使用Canvas來實現更好的滾動效果
        main_canvas = tk.Canvas(main_container, bg=JAPANESE_COLORS['bg_primary'],
                               highlightthickness=0,
                               relief='solid', borderwidth=1,
                               highlightbackground=JAPANESE_COLORS['border'])
        main_scrollbar = ttk.Scrollbar(main_container, orient="vertical", command=main_canvas.yview)

        # 創建可滾動的內容框架 - 添加邊框
        self.main_frame = tk.Frame(main_canvas, bg=JAPANESE_COLORS['bg_primary'],
                                  relief='flat', borderwidth=0)

        self.main_frame.bind(
            "<Configure>",
            lambda e: main_canvas.configure(scrollregion=main_canvas.bbox("all"))
        )

        main_canvas.create_window((0, 0), window=self.main_frame, anchor="nw")
        main_canvas.configure(yscrollcommand=main_scrollbar.set)

        main_canvas.pack(side="left", fill="both", expand=True, padx=5, pady=5)
        main_scrollbar.pack(side="right", fill="y", padx=(5, 5), pady=5)

        # 配置網格權重
        self.main_frame.columnconfigure(0, weight=1)

        # 標題區域
        self.create_title_section()

        # 檔案選擇區域
        self.create_file_selection_section()

        # 分析設定區域
        self.create_analysis_settings_section()

        # 處理控制區域
        self.create_control_section()

        # 截圖預覽區域
        self.create_preview_section()

        # 結果顯示區域
        self.create_results_section()

        # 綁定滾輪事件
        self.bind_mousewheel(main_canvas)

    def bind_mousewheel(self, canvas):
        """綁定滾輪事件"""
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)

    def create_title_section(self):
        """創建標題區域 - 增強邊框"""
        title_frame = ttk.Frame(self.main_frame, style='StrongCard.TLabelframe', padding="25")
        title_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(10, 20), padx=10)
        title_frame.columnconfigure(0, weight=1)

        # 添加陰影效果的內部框架
        shadow_frame = tk.Frame(title_frame, bg=JAPANESE_COLORS['shadow'], height=2)
        shadow_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=(15, 0))

        # 標題容器 - 包含主標題和版本資訊
        title_container = ttk.Frame(title_frame)
        title_container.grid(row=0, column=0, sticky=(tk.W, tk.E))
        title_container.columnconfigure(0, weight=1)

        # 主標題
        title_label = ttk.Label(title_container,
                              text="🎵 Audio Spectrum Analyzer",
                              style='Title.TLabel')
        title_label.grid(row=0, column=0)

        # 版本資訊 - 右上角，增加邊框
        version_frame = tk.Frame(title_container, bg=JAPANESE_COLORS['bg_secondary'],
                               relief='solid', borderwidth=1,
                               highlightbackground=JAPANESE_COLORS['border'])
        version_frame.grid(row=0, column=1, sticky=tk.E, padx=(20, 0))

        version_label = tk.Label(version_frame,
                               text="作成：設計分室　Ver.1.0",
                               font=self.fonts['small'],
                               fg=JAPANESE_COLORS['text_version'],
                               bg=JAPANESE_COLORS['bg_secondary'])
        version_label.pack(padx=8, pady=4)

        # 副標題
        subtitle_label = ttk.Label(title_frame,
                                 text="影片音訊頻譜分析器 - 含時間分析及智能截圖功能",
                                 style='Body.TLabel')
        subtitle_label.grid(row=1, column=0, pady=(10, 0))

    def create_file_selection_section(self):
        """創建檔案選擇區域 - 增強視覺分隔"""
        file_frame = ttk.LabelFrame(self.main_frame, text="📁 步驟 1: 選擇檔案與設定",
                                   style='StrongCard.TLabelframe', padding="25")
        file_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(0, 20), padx=10)
        file_frame.columnconfigure(1, weight=1)

        # 影片檔案選擇區域 - 添加內部邊框
        video_section = tk.Frame(file_frame, bg=JAPANESE_COLORS['bg_card'],
                               relief='solid', borderwidth=1,
                               highlightbackground=JAPANESE_COLORS['border_light'])
        video_section.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 15), padx=5)
        video_section.columnconfigure(1, weight=1)

        video_label = tk.Label(video_section, text="影片檔案:",
                             font=self.fonts['heading'],
                             fg=JAPANESE_COLORS['text_primary'],
                             bg=JAPANESE_COLORS['bg_card'])
        video_label.grid(row=0, column=0, sticky=tk.W, pady=15, padx=15)

        file_select_frame = tk.Frame(video_section, bg=JAPANESE_COLORS['bg_card'])
        file_select_frame.grid(row=0, column=1, sticky=(tk.W, tk.E), pady=15, padx=15)
        file_select_frame.columnconfigure(1, weight=1)

        self.select_button = ttk.Button(file_select_frame, text="選擇影片檔案",
                                       command=self.select_file, style='Primary.TButton')
        self.select_button.grid(row=0, column=0, padx=(0, 10))

        self.file_label = tk.Label(file_select_frame, text="尚未選擇檔案",
                                 font=self.fonts['body'],
                                 fg=JAPANESE_COLORS['text_hint'],
                                 bg=JAPANESE_COLORS['bg_card'])
        self.file_label.grid(row=0, column=1, sticky=(tk.W, tk.E))

        # 支援格式說明區域 - 添加邊框
        format_section = tk.Frame(file_frame, bg=JAPANESE_COLORS['bg_secondary'],
                                relief='solid', borderwidth=1,
                                highlightbackground=JAPANESE_COLORS['border_light'])
        format_section.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 15), padx=5)

        format_title = tk.Label(format_section, text="📋 支援的影片格式:",
                              font=self.fonts['body'],
                              fg=JAPANESE_COLORS['text_secondary'],
                              bg=JAPANESE_COLORS['bg_secondary'])
        format_title.grid(row=0, column=0, sticky=tk.W, padx=15, pady=(10, 5))

        format_list = tk.Label(format_section,
                             text="MP4, AVI, MOV, MKV, WMV, FLV, WebM, M4V, 3GP, MPG/MPEG",
                             font=self.fonts['body'],
                             fg=JAPANESE_COLORS['text_primary'],
                             bg=JAPANESE_COLORS['bg_secondary'])
        format_list.grid(row=1, column=0, sticky=tk.W, padx=30, pady=(0, 10))

        # 檔案限制說明區域 - 添加邊框
        limitation_section = tk.Frame(file_frame, bg=JAPANESE_COLORS['bg_secondary'],
                                    relief='solid', borderwidth=1,
                                    highlightbackground=JAPANESE_COLORS['border_light'])
        limitation_section.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 15), padx=5)

        limitation_title = tk.Label(limitation_section, text="⚠️ 檔案來源限制:",
                                   font=self.fonts['body'],
                                   fg=JAPANESE_COLORS['text_secondary'],
                                   bg=JAPANESE_COLORS['bg_secondary'])
        limitation_title.grid(row=0, column=0, sticky=tk.W, padx=15, pady=(10, 5))

        limitations = [
            "• 建議檔案大小小於 2GB，以獲得最佳處理效能",
            "• 不支援加密或受保護的影片檔案",
            "• 音訊取樣率建議 44.1kHz 或更高，以確保分析精度",
            "• 影片長度超過 30 分鐘時，處理時間會較長"
        ]

        for i, limitation in enumerate(limitations):
            limit_label = tk.Label(limitation_section, text=limitation,
                                 font=self.fonts['body'],
                                 fg=JAPANESE_COLORS['text_primary'],
                                 bg=JAPANESE_COLORS['bg_secondary'])
            limit_label.grid(row=i+1, column=0, sticky=tk.W, padx=30, pady=2)

        # 在最後添加底部間距
        bottom_spacer = tk.Frame(limitation_section, bg=JAPANESE_COLORS['bg_secondary'], height=10)
        bottom_spacer.grid(row=len(limitations)+1, column=0, sticky=(tk.W, tk.E))

        # 儲存位置和截圖設定區域 - 並排顯示並添加邊框
        settings_container = tk.Frame(file_frame, bg=JAPANESE_COLORS['bg_card'])
        settings_container.grid(row=3, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10), padx=5)
        settings_container.columnconfigure(0, weight=1)
        settings_container.columnconfigure(1, weight=1)

        # 儲存位置區域
        save_section = tk.Frame(settings_container, bg=JAPANESE_COLORS['bg_secondary'],
                              relief='solid', borderwidth=1,
                              highlightbackground=JAPANESE_COLORS['border_light'])
        save_section.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(0, 5), pady=5)
        save_section.columnconfigure(0, weight=1)

        save_title = tk.Label(save_section, text="💾 儲存位置",
                            font=self.fonts['heading'],
                            fg=JAPANESE_COLORS['text_primary'],
                            bg=JAPANESE_COLORS['bg_secondary'])
        save_title.grid(row=0, column=0, pady=(10, 5), padx=15)

        save_button_frame = tk.Frame(save_section, bg=JAPANESE_COLORS['bg_secondary'])
        save_button_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), padx=15, pady=(0, 5))
        save_button_frame.columnconfigure(0, weight=1)

        self.save_dir_button = ttk.Button(save_button_frame, text="選擇儲存位置",
                                         command=self.select_save_directory, style='Secondary.TButton')
        self.save_dir_button.grid(row=0, column=0, pady=5)

        self.save_dir_label = tk.Label(save_section, text="將儲存到程式所在目錄",
                                     font=self.fonts['small'],
                                     fg=JAPANESE_COLORS['text_hint'],
                                     bg=JAPANESE_COLORS['bg_secondary'],
                                     wraplength=200)
        self.save_dir_label.grid(row=2, column=0, padx=15, pady=(0, 10))

        # 截圖設定區域
        screenshot_section = tk.Frame(settings_container, bg=JAPANESE_COLORS['bg_secondary'],
                                    relief='solid', borderwidth=1,
                                    highlightbackground=JAPANESE_COLORS['border_light'])
        screenshot_section.grid(row=0, column=1, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(5, 0), pady=5)

        screenshot_title = tk.Label(screenshot_section, text="📸 截圖設定",
                                   font=self.fonts['heading'],
                                   fg=JAPANESE_COLORS['text_primary'],
                                   bg=JAPANESE_COLORS['bg_secondary'])
        screenshot_title.grid(row=0, column=0, columnspan=3, pady=(10, 5), padx=15)

        screenshot_config_frame = tk.Frame(screenshot_section, bg=JAPANESE_COLORS['bg_secondary'])
        screenshot_config_frame.grid(row=1, column=0, columnspan=3, padx=15, pady=(0, 5))

        tk.Label(screenshot_config_frame, text="截圖數量:",
               font=self.fonts['body'],
               fg=JAPANESE_COLORS['text_primary'],
               bg=JAPANESE_COLORS['bg_secondary']).grid(row=0, column=0, sticky=tk.W)

        self.screenshot_count = tk.IntVar(value=5)
        screenshot_spinbox = ttk.Spinbox(screenshot_config_frame, from_=1, to=20, width=8,
                                       textvariable=self.screenshot_count, font=self.fonts['body'])
        screenshot_spinbox.grid(row=0, column=1, padx=(10, 5))

        tk.Label(screenshot_section, text="(最高振幅的前N個時間點)",
               font=self.fonts['small'],
               fg=JAPANESE_COLORS['text_hint'],
               bg=JAPANESE_COLORS['bg_secondary']).grid(row=2, column=0, columnspan=3, padx=15, pady=(0, 10))

    def create_analysis_settings_section(self):
        """創建分析設定區域 - 增強邊框效果"""
        analysis_frame = ttk.LabelFrame(self.main_frame, text="🔧 分析設定",
                                       style='StrongCard.TLabelframe', padding="25")
        analysis_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=(0, 20), padx=10)
        analysis_frame.columnconfigure(0, weight=1)

        # 分析類型選擇區域 - 添加明顯邊框
        analysis_type_section = tk.Frame(analysis_frame, bg=JAPANESE_COLORS['bg_secondary'],
                                       relief='solid', borderwidth=2,
                                       highlightbackground=JAPANESE_COLORS['border_strong'])
        analysis_type_section.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 15), padx=5)

        analysis_label = tk.Label(analysis_type_section, text="🎯 分析類型:",
                                font=self.fonts['heading'],
                                fg=JAPANESE_COLORS['text_primary'],
                                bg=JAPANESE_COLORS['bg_secondary'])
        analysis_label.grid(row=0, column=0, sticky=tk.W, pady=(15, 10), padx=20)

        analysis_type_frame = tk.Frame(analysis_type_section, bg=JAPANESE_COLORS['bg_secondary'])
        analysis_type_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(0, 15), padx=20)

        # 高頻分析選項 - 添加邊框
        high_freq_frame = tk.Frame(analysis_type_frame, bg=JAPANESE_COLORS['bg_card'],
                                 relief='solid', borderwidth=1,
                                 highlightbackground=JAPANESE_COLORS['border'])
        high_freq_frame.grid(row=0, column=0, padx=(0, 10), pady=5)

        high_freq_radio = ttk.Radiobutton(high_freq_frame,
                                         text="高頻分析 (>1000 Hz)",
                                         variable=self.analysis_type,
                                         value="high_freq")
        high_freq_radio.pack(padx=15, pady=10)

        # 低頻分析選項 - 添加邊框
        low_freq_frame = tk.Frame(analysis_type_frame, bg=JAPANESE_COLORS['bg_card'],
                                relief='solid', borderwidth=1,
                                highlightbackground=JAPANESE_COLORS['border'])
        low_freq_frame.grid(row=0, column=1, padx=(0, 10), pady=5)

        low_freq_radio = ttk.Radiobutton(low_freq_frame,
                                        text="低頻分析 (<200 Hz)",
                                        variable=self.analysis_type,
                                        value="low_freq")
        low_freq_radio.pack(padx=15, pady=10)

        # 全頻分析選項 - 添加邊框
        full_freq_frame = tk.Frame(analysis_type_frame, bg=JAPANESE_COLORS['bg_card'],
                                 relief='solid', borderwidth=1,
                                 highlightbackground=JAPANESE_COLORS['border'])
        full_freq_frame.grid(row=0, column=2, pady=5)

        full_freq_radio = ttk.Radiobutton(full_freq_frame,
                                         text="全頻分析 (20-20000 Hz)",
                                         variable=self.analysis_type,
                                         value="full_freq")
        full_freq_radio.pack(padx=15, pady=10)

        # 分析說明區域 - 添加邊框
        analysis_desc_section = tk.Frame(analysis_frame, bg=JAPANESE_COLORS['bg_secondary'],
                                        relief='solid', borderwidth=1,
                                        highlightbackground=JAPANESE_COLORS['border_light'])
        analysis_desc_section.grid(row=1, column=0, sticky=(tk.W, tk.E), padx=5)

        descriptions = {
            "high_freq": "💡 適用於機械摩擦、軸承異音、電機高頻噪音等分析",
            "low_freq": "💡 適用於振動、共振、結構異音、低頻噪音等分析",
            "full_freq": "💡 完整頻譜分析，適用於綜合性音訊檢測"
        }

        self.analysis_desc_label = tk.Label(analysis_desc_section,
                                           text=descriptions["high_freq"],
                                           font=self.fonts['body'],
                                           fg=JAPANESE_COLORS['text_secondary'],
                                           bg=JAPANESE_COLORS['bg_secondary'])
        self.analysis_desc_label.grid(row=0, column=0, sticky=tk.W, padx=20, pady=15)

        # 綁定分析類型變更事件
        self.analysis_type.trace('w', lambda *args: self.update_analysis_description())

    def update_analysis_description(self):
        """更新分析類型說明"""
        descriptions = {
            "high_freq": "💡 適用於機械摩擦、軸承異音、電機高頻噪音等分析",
            "low_freq": "💡 適用於振動、共振、結構異音、低頻噪音等分析",
            "full_freq": "💡 完整頻譜分析，適用於綜合性音訊檢測"
        }

        current_type = self.analysis_type.get()
        self.analysis_desc_label.config(text=descriptions.get(current_type, ""))

    def create_control_section(self):
        """創建控制區域 - 增強視覺效果"""
        control_frame = ttk.LabelFrame(self.main_frame, text="⚡ 步驟 2: 開始分析",
                                      style='StrongCard.TLabelframe', padding="25")
        control_frame.grid(row=3, column=0, sticky=(tk.W, tk.E), pady=(0, 20), padx=10)
        control_frame.columnconfigure(1, weight=1)

        # 按鈕區域 - 添加強調邊框
        button_section = tk.Frame(control_frame, bg=JAPANESE_COLORS['accent_primary'],
                                relief='solid', borderwidth=3,
                                highlightbackground=JAPANESE_COLORS['border_strong'])
        button_section.grid(row=0, column=0, padx=(0, 20), pady=10)

        self.process_button = ttk.Button(button_section, text="🎬 開始頻譜分析與截圖",
                                        command=self.start_analysis, state="disabled",
                                        style='Primary.TButton')
        self.process_button.pack(padx=20, pady=15)

        # 進度區域 - 添加邊框
        progress_section = tk.Frame(control_frame, bg=JAPANESE_COLORS['bg_secondary'],
                                  relief='solid', borderwidth=1,
                                  highlightbackground=JAPANESE_COLORS['border'])
        progress_section.grid(row=0, column=1, sticky=(tk.W, tk.E), pady=10)
        progress_section.columnconfigure(0, weight=1)

        progress_title = tk.Label(progress_section, text="📊 處理進度",
                                font=self.fonts['heading'],
                                fg=JAPANESE_COLORS['text_primary'],
                                bg=JAPANESE_COLORS['bg_secondary'])
        progress_title.grid(row=0, column=0, pady=(10, 5))

        self.progress = ttk.Progressbar(progress_section, mode='determinate',
                                       style='Japanese.Horizontal.TProgressbar')
        self.progress.grid(row=1, column=0, sticky=(tk.W, tk.E), padx=20, pady=(0, 5))

        self.status_label = tk.Label(progress_section, text="等待開始分析...",
                                    font=self.fonts['body'],
                                    fg=JAPANESE_COLORS['text_primary'],
                                    bg=JAPANESE_COLORS['bg_secondary'])
        self.status_label.grid(row=2, column=0, padx=20, pady=(0, 10))

    def create_preview_section(self):
        """創建預覽區域 - 增強邊框"""
        preview_frame = ttk.LabelFrame(self.main_frame, text="🖼️ 步驟 3: 截圖預覽",
                                      style='StrongCard.TLabelframe', padding="20")
        preview_frame.grid(row=4, column=0, sticky=(tk.W, tk.E), pady=(0, 20), padx=10)
        preview_frame.columnconfigure(0, weight=1)

        # 創建預覽容器 - 添加明顯邊框
        preview_container = tk.Frame(preview_frame, bg=JAPANESE_COLORS['bg_secondary'],
                                   relief='solid', borderwidth=2,
                                   highlightbackground=JAPANESE_COLORS['border_strong'])
        preview_container.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=10)
        preview_container.columnconfigure(0, weight=1)

        # 創建滾動框架用於顯示截圖
        preview_canvas = tk.Canvas(preview_container, height=160, bg=JAPANESE_COLORS['bg_secondary'],
                                  highlightthickness=0,
                                  relief='sunken', borderwidth=1)
        preview_scrollbar = ttk.Scrollbar(preview_container, orient="horizontal",
                                         command=preview_canvas.xview)

        self.preview_scrollable_frame = tk.Frame(preview_canvas, bg=JAPANESE_COLORS['bg_secondary'])

        self.preview_scrollable_frame.bind(
            "<Configure>",
            lambda e: preview_canvas.configure(scrollregion=preview_canvas.bbox("all"))
        )

        preview_canvas.create_window((0, 0), window=self.preview_scrollable_frame, anchor="nw")
        preview_canvas.configure(xscrollcommand=preview_scrollbar.set)

        preview_canvas.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=10, pady=(10, 5))
        preview_scrollbar.grid(row=1, column=0, sticky=(tk.W, tk.E), padx=10, pady=(0, 10))

    def create_results_section(self):
        """創建結果區域 - 增強邊框效果"""
        result_frame = ttk.LabelFrame(self.main_frame, text="📊 步驟 4: 分析結果",
                                     style='StrongCard.TLabelframe', padding="20")
        result_frame.grid(row=5, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=10, pady=(0, 10))
        result_frame.columnconfigure(0, weight=1)
        result_frame.rowconfigure(0, weight=1)

        # 創建結果容器 - 添加邊框
        results_container = tk.Frame(result_frame, bg=JAPANESE_COLORS['bg_card'],
                                   relief='solid', borderwidth=2,
                                   highlightbackground=JAPANESE_COLORS['border_strong'])
        results_container.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=10)
        results_container.columnconfigure(0, weight=1)
        results_container.rowconfigure(0, weight=1)

        # 創建筆記本（標籤頁）- 增強邊框
        self.notebook = ttk.Notebook(results_container, style='Japanese.TNotebook')
        self.notebook.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=10, pady=10)

        # 頻譜圖標籤頁
        self.spectrum_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.spectrum_frame, text="📈 整體頻譜圖")

        # 時頻分析標籤頁
        self.timefreq_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.timefreq_frame, text="🌊 時頻分析圖")

        # 分析結果標籤頁
        self.analysis_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.analysis_frame, text="📋 分析報告")

        # 創建matplotlib圖表
        self.create_plots()

        # 創建分析結果顯示區域
        self.create_analysis_display()

    def create_plots(self):
        # 創建整體頻譜圖容器 - 添加邊框
        spectrum_container = tk.Frame(self.spectrum_frame, bg=JAPANESE_COLORS['bg_card'],
                                    relief='solid', borderwidth=1,
                                    highlightbackground=JAPANESE_COLORS['border'])
        spectrum_container.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # 創建整體頻譜圖
        self.fig1 = Figure(figsize=(12, 6), dpi=100, facecolor=JAPANESE_COLORS['bg_card'])
        self.ax1 = self.fig1.add_subplot(111)
        self.ax1.set_title("音訊頻譜分析 (dB)", fontsize=14, color=JAPANESE_COLORS['text_primary'], pad=20)
        self.ax1.set_xlabel("頻率 (Hz)", fontsize=12, color=JAPANESE_COLORS['text_primary'])
        self.ax1.set_ylabel("振幅 (dB)", fontsize=12, color=JAPANESE_COLORS['text_primary'])
        self.ax1.grid(True, which="both", linestyle='--', linewidth=0.5, color=JAPANESE_COLORS['divider'])
        self.ax1.set_xlim(0, 20000)
        self.ax1.set_facecolor(JAPANESE_COLORS['bg_secondary'])

        # 創建畫布1
        self.canvas1 = FigureCanvasTkAgg(self.fig1, spectrum_container)
        self.canvas1.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # 創建時頻分析圖容器 - 添加邊框
        timefreq_container = tk.Frame(self.timefreq_frame, bg=JAPANESE_COLORS['bg_card'],
                                    relief='solid', borderwidth=1,
                                    highlightbackground=JAPANESE_COLORS['border'])
        timefreq_container.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # 創建時頻分析圖
        self.fig2 = Figure(figsize=(12, 8), dpi=100, facecolor=JAPANESE_COLORS['bg_card'])

        # 時頻圖（頻譜圖）
        self.ax2 = self.fig2.add_subplot(211)
        self.ax2.set_title("時頻分析圖 (頻譜圖)", fontsize=14, color=JAPANESE_COLORS['text_primary'], pad=15)
        self.ax2.set_xlabel("時間 (秒)", fontsize=12, color=JAPANESE_COLORS['text_primary'])
        self.ax2.set_ylabel("頻率 (Hz)", fontsize=12, color=JAPANESE_COLORS['text_primary'])
        self.ax2.set_facecolor(JAPANESE_COLORS['bg_secondary'])

        # 時間-峰值振幅圖
        self.ax3 = self.fig2.add_subplot(212)
        self.ax3.set_title("各時間點最大振幅變化", fontsize=14, color=JAPANESE_COLORS['text_primary'], pad=15)
        self.ax3.set_xlabel("時間 (秒)", fontsize=12, color=JAPANESE_COLORS['text_primary'])
        self.ax3.set_ylabel("最大振幅 (dB)", fontsize=12, color=JAPANESE_COLORS['text_primary'])
        self.ax3.grid(True, linestyle='--', linewidth=0.5, color=JAPANESE_COLORS['divider'])
        self.ax3.set_facecolor(JAPANESE_COLORS['bg_secondary'])

        self.fig2.tight_layout(pad=3.0)

        # 創建畫布2
        self.canvas2 = FigureCanvasTkAgg(self.fig2, timefreq_container)
        self.canvas2.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    def create_analysis_display(self):
        """創建分析結果顯示區域 - 增強邊框"""
        # 分析結果容器 - 添加邊框
        analysis_container = tk.Frame(self.analysis_frame, bg=JAPANESE_COLORS['bg_card'],
                                    relief='solid', borderwidth=1,
                                    highlightbackground=JAPANESE_COLORS['border'])
        analysis_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        text_frame = tk.Frame(analysis_container, bg=JAPANESE_COLORS['bg_card'])
        text_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # 滾動條
        scrollbar = ttk.Scrollbar(text_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # 文本框 - 增強邊框
        self.result_text = tk.Text(text_frame, wrap=tk.WORD,
                                  yscrollcommand=scrollbar.set,
                                  font=self.fonts['body'],
                                  bg=JAPANESE_COLORS['bg_secondary'],
                                  fg=JAPANESE_COLORS['text_primary'],
                                  selectbackground=JAPANESE_COLORS['accent_primary'],
                                  selectforeground='white',
                                  borderwidth=2,
                                  relief='solid',
                                  highlightbackground=JAPANESE_COLORS['border'],
                                  padx=15, pady=15)
        self.result_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.result_text.yview)

    # 保留原有的其他方法（分析邏輯部分不需要修改邊框相關代碼）
    def select_file(self):
        """選擇影片檔案"""
        file_types = [
            ("影片檔案", "*.mp4 *.avi *.mov *.mkv *.wmv *.flv *.webm *.m4v *.3gp *.mpg *.mpeg"),
            ("常用格式", "*.mp4 *.avi *.mov *.mkv"),
            ("所有檔案", "*.*")
        ]

        filename = filedialog.askopenfilename(
            title="選擇影片檔案",
            filetypes=file_types
        )

        if filename:
            self.video_file = filename
            self.file_label.config(text=f"✅ 已選擇: {Path(filename).name}")
            self.file_label.configure(fg=JAPANESE_COLORS['success'])
            self.process_button.config(state="normal")

    def select_save_directory(self):
        """選擇截圖儲存位置"""
        directory = filedialog.askdirectory(title="選擇截圖儲存位置")

        if directory:
            self.save_directory = directory
            self.save_dir_label.config(text=f"📁 儲存到: {directory}")
            self.save_dir_label.configure(fg=JAPANESE_COLORS['text_secondary'])
        else:
            self.save_directory = None
            self.save_dir_label.config(text="📁 將儲存到程式所在目錄")
            self.save_dir_label.configure(fg=JAPANESE_COLORS['text_hint'])

    def get_frequency_range(self):
        """根據分析類型獲取頻率範圍"""
        analysis_type = self.analysis_type.get()
        if analysis_type == "high_freq":
            return {"start": 1000, "name": "高頻", "description": "機械摩擦、軸承異音等"}
        elif analysis_type == "low_freq":
            return {"start": 0, "end": 200, "name": "低頻", "description": "振動、共振、結構異音等"}
        else:  # full_freq
            return {"start": 20, "end": 20000, "name": "全頻", "description": "完整音訊頻譜"}

    def start_analysis(self):
        """開始分析（在新線程中執行）"""
        if self.is_processing:
            return

        self.is_processing = True
        self.process_button.config(state="disabled")
        self.progress.config(mode='determinate', value=0)

        # 清空之前的截圖預覽
        for widget in self.preview_scrollable_frame.winfo_children():
            widget.destroy()
        self.captured_screenshots = []

        # 在新線程中執行分析，避免GUI凍結
        thread = threading.Thread(target=self.perform_analysis)
        thread.daemon = True
        thread.start()

    def update_progress(self, value, maximum=100):
        """更新進度條"""
        self.root.after(0, lambda: self.progress.config(value=value, maximum=maximum))

    def perform_analysis(self):
        """執行完整的音訊分析"""
        try:
            total_steps = 6
            current_step = 0

            # 步驟1: 提取音訊
            current_step += 1
            self.update_progress(current_step * 100 / total_steps)
            self.update_status("🎵 正在從影片提取音訊...")
            self.extract_audio()

            # 步驟2: 頻譜分析
            current_step += 1
            self.update_progress(current_step * 100 / total_steps)
            self.update_status("📊 正在進行頻譜分析...")
            self.analyze_spectrum()

            # 步驟3: 時頻分析
            current_step += 1
            self.update_progress(current_step * 100 / total_steps)
            self.update_status("🌊 正在進行時頻分析...")
            self.analyze_time_frequency()

            # 步驟4: 截取關鍵時間點的畫面
            current_step += 1
            self.update_progress(current_step * 100 / total_steps)
            self.update_status("📸 正在截取關鍵時間點畫面...")
            self.capture_key_moments()

            # 步驟5: 繪製圖表
            current_step += 1
            self.update_progress(current_step * 100 / total_steps)
            self.update_status("🎨 正在生成精美圖表...")
            self.plot_spectrum()
            self.plot_time_frequency()

            # 步驟6: 顯示分析結果
            current_step += 1
            self.update_progress(current_step * 100 / total_steps)
            self.update_status("📋 正在整理分析結果...")
            self.display_analysis_results()
            self.display_screenshot_preview()

            self.update_status("✨ 分析完成！")

        except Exception as e:
            messagebox.showerror("錯誤", f"分析過程中發生錯誤：\n{str(e)}")
            self.update_status("❌ 分析失敗")
        finally:
            self.cleanup()

    def update_status(self, message):
        """更新狀態標籤（線程安全）"""
        self.root.after(0, lambda: self.status_label.config(text=message))

    def extract_audio(self):
        """從影片中提取音訊"""
        clip = VideoFileClip(self.video_file)
        self.audio_duration = clip.duration
        clip.audio.write_audiofile(self.temp_audio_file, codec='pcm_s16le', verbose=False, logger=None)
        clip.close()

    def analyze_spectrum(self):
        """進行頻譜分析"""
        # 讀取WAV檔案
        self.sample_rate, data = wavfile.read(self.temp_audio_file)

        # 如果是立體聲，取左聲道
        if data.ndim > 1:
            self.audio_data = data[:, 0]
        else:
            self.audio_data = data

        # 執行FFT
        N = len(self.audio_data)
        yf = fft(self.audio_data)
        xf = fftfreq(N, 1 / self.sample_rate)

        # 只取正頻率部分
        self.xf_positive = xf[:N//2]
        yf_positive = 2.0/N * np.abs(yf[:N//2])

        # 轉換為分貝
        self.yf_db = 20 * np.log10(yf_positive, out=np.zeros_like(yf_positive),
                                   where=(yf_positive!=0))

        # 分析特定頻率範圍的噪音
        self.analyze_frequency_noise()

    def analyze_time_frequency(self):
        """進行時頻分析"""
        # 設定時頻分析參數
        window_length = int(self.sample_rate * 0.1)  # 0.1秒窗口
        overlap = window_length // 2  # 50%重疊

        # 執行短時傅立葉變換 (STFT)
        frequencies, times, Zxx = signal.stft(
            self.audio_data,
            fs=self.sample_rate,
            window='hann',
            nperseg=window_length,
            noverlap=overlap
        )

        # 轉換為分貝
        magnitude_db = 20 * np.log10(np.abs(Zxx) + 1e-10)

        # 只保留人耳可聽範圍 (0-20kHz)
        freq_mask = frequencies <= 20000
        self.stft_frequencies = frequencies[freq_mask]
        self.stft_times = times
        self.stft_magnitude = magnitude_db[freq_mask, :]

        # 分析每個時間點的峰值
        self.analyze_time_peaks()

    def analyze_time_peaks(self):
        """分析每個時間點的峰值"""
        self.time_peaks = []
        freq_range = self.get_frequency_range()

        # 根據分析類型設定頻率範圍
        if "end" in freq_range:  # 低頻或全頻
            freq_mask = (self.stft_frequencies >= freq_range["start"]) & (self.stft_frequencies <= freq_range["end"])
        else:  # 高頻
            freq_mask = self.stft_frequencies >= freq_range["start"]

        for i, time_point in enumerate(self.stft_times):
            # 取得該時間點的目標頻率範圍頻譜
            target_spectrum = self.stft_magnitude[freq_mask, i]
            target_freqs = self.stft_frequencies[freq_mask]

            # 找出該時間點的最大值
            if len(target_spectrum) > 0:
                max_idx = np.argmax(target_spectrum)
                max_magnitude = target_spectrum[max_idx]
                max_frequency = target_freqs[max_idx]

                # 找出該時間點所有超過閾值的峰值
                threshold = -50  # dB閾值
                peak_indices = []
                for j in range(1, len(target_spectrum) - 1):
                    if (target_spectrum[j] > target_spectrum[j-1] and
                        target_spectrum[j] > target_spectrum[j+1] and
                        target_spectrum[j] > threshold):
                        peak_indices.append(j)

                peak_info = {
                    'time': time_point,
                    'max_frequency': max_frequency,
                    'max_magnitude': max_magnitude,
                    'peak_count': len(peak_indices),
                    'peaks': [(target_freqs[idx], target_spectrum[idx]) for idx in peak_indices]
                }
                self.time_peaks.append(peak_info)

        # 找出全域最大峰值
        if self.time_peaks:
            self.global_max_peak = max(self.time_peaks, key=lambda x: x['max_magnitude'])
        else:
            self.global_max_peak = None

    def capture_key_moments(self):
        """截取關鍵時間點的畫面"""
        if not self.time_peaks:
            return

        # 獲取要截圖的數量
        screenshot_count = min(self.screenshot_count.get(), len(self.time_peaks))

        # 按振幅排序，選取前N個峰值
        sorted_peaks = sorted(self.time_peaks, key=lambda x: x['max_magnitude'], reverse=True)[:screenshot_count]

        # 設定儲存目錄
        if self.save_directory:
            save_dir = Path(self.save_directory)
        else:
            save_dir = Path.cwd()

        # 創建以當前時間命名的子目錄
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        video_name = Path(self.video_file).stem
        analysis_type_name = self.get_frequency_range()["name"]
        screenshot_dir = save_dir / f"{video_name}_{analysis_type_name}分析_screenshots_{timestamp}"
        screenshot_dir.mkdir(exist_ok=True)

        # 開啟影片進行截圖
        clip = VideoFileClip(self.video_file)

        self.captured_screenshots = []

        for i, peak in enumerate(sorted_peaks):
            try:
                # 截取該時間點的畫面
                time_point = peak['time']

                # 確保時間點在影片範圍內
                time_point = max(0, min(time_point, clip.duration - 0.1))

                # 獲取畫面
                frame = clip.get_frame(time_point)

                # 轉換為PIL圖像
                image = Image.fromarray(frame)

                # 生成檔案名稱
                filename = f"{analysis_type_name}_peak_{i+1:02d}_time_{time_point:.2f}s_freq_{peak['max_frequency']:.0f}Hz_mag_{peak['max_magnitude']:.1f}dB.jpg"
                filepath = screenshot_dir / filename

                # 儲存圖像
                image.save(filepath, "JPEG", quality=90)

                # 記錄截圖資訊
                screenshot_info = {
                    'rank': i + 1,
                    'time': time_point,
                    'frequency': peak['max_frequency'],
                    'magnitude': peak['max_magnitude'],
                    'filepath': filepath,
                    'image': image.copy()  # 保存圖像副本用於預覽
                }
                self.captured_screenshots.append(screenshot_info)

                # 更新進度
                progress = 50 + (i + 1) / screenshot_count * 30  # 50-80%的進度用於截圖
                self.update_progress(progress)

            except Exception as e:
                print(f"截圖失敗 {time_point:.2f}s: {e}")
                continue

        clip.close()

        # 儲存截圖資訊檔案
        info_file = screenshot_dir / "screenshot_info.txt"
        with open(info_file, 'w', encoding='utf-8') as f:
            f.write(f"影片檔案: {Path(self.video_file).name}\n")
            f.write(f"分析類型: {analysis_type_name}分析\n")
            f.write(f"分析時間: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"總共截圖: {len(self.captured_screenshots)} 張\n\n")
            f.write("截圖詳細資訊:\n")
            f.write("="*60 + "\n")

            for screenshot in self.captured_screenshots:
                f.write(f"排名: {screenshot['rank']}\n")
                f.write(f"時間: {screenshot['time']:.2f} 秒\n")
                f.write(f"頻率: {screenshot['frequency']:.1f} Hz\n")
                f.write(f"振幅: {screenshot['magnitude']:.1f} dB\n")
                f.write(f"檔案: {screenshot['filepath'].name}\n")
                f.write("-" * 40 + "\n")

    def display_screenshot_preview(self):
        """顯示截圖預覽 - 增強邊框效果"""
        def update_preview():
            # 清空現有預覽
            for widget in self.preview_scrollable_frame.winfo_children():
                widget.destroy()

            if not self.captured_screenshots:
                no_screenshot_frame = tk.Frame(self.preview_scrollable_frame,
                                             bg=JAPANESE_COLORS['bg_card'],
                                             relief='solid', borderwidth=2,
                                             highlightbackground=JAPANESE_COLORS['border'])
                no_screenshot_frame.pack(side=tk.LEFT, padx=20, pady=20)

                no_screenshot_label = tk.Label(no_screenshot_frame,
                                              text="📷 沒有截圖\n請確保影片檔案有效",
                                              font=self.fonts['body'],
                                              fg=JAPANESE_COLORS['text_hint'],
                                              bg=JAPANESE_COLORS['bg_card'],
                                              justify=tk.CENTER)
                no_screenshot_label.pack(padx=30, pady=30)
                return

            # 顯示截圖預覽
            for i, screenshot in enumerate(self.captured_screenshots):
                # 創建預覽框架 - 增強邊框效果
                preview_frame = tk.Frame(self.preview_scrollable_frame,
                                       bg=JAPANESE_COLORS['bg_card'],
                                       relief="solid", borderwidth=2,
                                       highlightbackground=JAPANESE_COLORS['border_strong'])
                preview_frame.pack(side=tk.LEFT, padx=8, pady=8)

                # 縮小圖像用於預覽
                image = screenshot['image']
                # 計算縮放比例，使高度為90像素
                height = 90
                width = int(image.width * height / image.height)
                thumbnail = image.resize((width, height), Image.Resampling.LANCZOS)

                # 轉換為tkinter可用的圖像
                from PIL import ImageTk
                photo = ImageTk.PhotoImage(thumbnail)

                # 圖像容器 - 添加內部邊框
                img_container = tk.Frame(preview_frame, bg=JAPANESE_COLORS['border'],
                                       relief='solid', borderwidth=1)
                img_container.pack(padx=8, pady=(8, 5))

                # 顯示縮圖
                img_label = tk.Label(img_container, image=photo,
                                   bg=JAPANESE_COLORS['bg_card'], borderwidth=0)
                img_label.image = photo  # 保持引用
                img_label.pack(padx=2, pady=2)

                # 資訊容器 - 添加背景邊框
                info_container = tk.Frame(preview_frame, bg=JAPANESE_COLORS['bg_secondary'],
                                        relief='solid', borderwidth=1)
                info_container.pack(padx=8, pady=(0, 8), fill=tk.X)

                # 顯示資訊
                info_text = f"#{screenshot['rank']} - {screenshot['time']:.1f}s\n{screenshot['frequency']:.0f}Hz ({screenshot['magnitude']:.1f}dB)"
                info_label = tk.Label(info_container, text=info_text,
                                    font=self.fonts['small'], justify=tk.CENTER,
                                    bg=JAPANESE_COLORS['bg_secondary'],
                                    fg=JAPANESE_COLORS['text_primary'])
                info_label.pack(padx=8, pady=8)

                # 添加點擊事件打開完整圖像
                def open_full_image(filepath=screenshot['filepath']):
                    try:
                        if platform.system() == "Windows":
                            os.startfile(filepath)
                        elif platform.system() == "Darwin":  # macOS
                            os.system(f"open '{filepath}'")
                        else:  # Linux
                            os.system(f"xdg-open '{filepath}'")
                    except Exception as e:
                        messagebox.showerror("錯誤", f"無法開啟圖像: {e}")

                img_label.bind("<Button-1>", lambda e, fp=screenshot['filepath']: open_full_image(fp))
                img_label.config(cursor="hand2")

                # 添加懸停效果
                def on_enter(e, frame=preview_frame):
                    frame.configure(highlightbackground=JAPANESE_COLORS['accent_primary'])
                def on_leave(e, frame=preview_frame):
                    frame.configure(highlightbackground=JAPANESE_COLORS['border_strong'])

                preview_frame.bind("<Enter>", on_enter)
                preview_frame.bind("<Leave>", on_leave)
                img_label.bind("<Enter>", on_enter)
                img_label.bind("<Leave>", on_leave)
                info_label.bind("<Enter>", on_enter)
                info_label.bind("<Leave>", on_leave)

        self.root.after(0, update_preview)

    def analyze_frequency_noise(self):
        """分析特定頻率範圍的噪音"""
        freq_range = self.get_frequency_range()

        # 根據分析類型設定頻率範圍
        if "end" in freq_range:  # 低頻或全頻
            freq_mask = (self.xf_positive >= freq_range["start"]) & (self.xf_positive <= freq_range["end"])
        else:  # 高頻
            freq_mask = self.xf_positive >= freq_range["start"]

        target_freqs = self.xf_positive[freq_mask]
        target_magnitudes = self.yf_db[freq_mask]

        # 找出峰值（簡單的峰值檢測）
        peaks = []
        threshold = -60  # dB閾值

        for i in range(1, len(target_magnitudes) - 1):
            if (target_magnitudes[i] > target_magnitudes[i-1] and
                target_magnitudes[i] > target_magnitudes[i+1] and
                target_magnitudes[i] > threshold):
                peaks.append({
                    'frequency': target_freqs[i],
                    'magnitude': target_magnitudes[i]
                })

        # 按振幅排序，取前10個最強的峰值
        self.freq_peaks = sorted(peaks, key=lambda x: x['magnitude'], reverse=True)[:10]

        # 統計資訊
        self.analysis_stats = {
            'total_peaks': len(peaks),
            'max_magnitude': max(target_magnitudes) if len(target_magnitudes) > 0 else 0,
            'avg_magnitude': np.mean(target_magnitudes) if len(target_magnitudes) > 0 else 0,
            'freq_range': freq_range
        }

    def plot_spectrum(self):
        """繪製頻譜圖"""
        def update_plot():
            self.ax1.clear()
            self.ax1.plot(self.xf_positive, self.yf_db, color=JAPANESE_COLORS['accent_primary'],
                         linewidth=1.5, alpha=0.8)

            freq_range = self.get_frequency_range()

            # 根據分析類型添加標記線
            if freq_range["name"] == "高頻":
                self.ax1.axvline(x=freq_range["start"], color=JAPANESE_COLORS['warning'],
                               linestyle='--', linewidth=2,
                               label=f'高頻區域 (>{freq_range["start"]} Hz)', alpha=0.8)
            elif freq_range["name"] == "低頻":
                self.ax1.axvline(x=freq_range["end"], color=JAPANESE_COLORS['warning'],
                               linestyle='--', linewidth=2,
                               label=f'低頻區域 (<{freq_range["end"]} Hz)', alpha=0.8)
            else:  # 全頻
                self.ax1.axvspan(freq_range["start"], freq_range["end"],
                               color=JAPANESE_COLORS['accent_secondary'], alpha=0.1,
                               label=f'分析範圍 ({freq_range["start"]}-{freq_range["end"]} Hz)')

            self.ax1.set_title(f"音訊{freq_range['name']}頻譜分析 (dB)",
                             fontsize=14, color=JAPANESE_COLORS['text_primary'], pad=20)
            self.ax1.set_xlabel("頻率 (Hz)", fontsize=12, color=JAPANESE_COLORS['text_primary'])
            self.ax1.set_ylabel("振幅 (dB)", fontsize=12, color=JAPANESE_COLORS['text_primary'])
            self.ax1.grid(True, which="both", linestyle='--', linewidth=0.5, color=JAPANESE_COLORS['divider'])
            self.ax1.legend(prop={'size': 10})
            self.ax1.set_xlim(0, 20000)
            self.ax1.set_facecolor(JAPANESE_COLORS['bg_secondary'])

            # 標記峰值
            for peak in self.freq_peaks[:5]:  # 只標記前5個最強峰值
                self.ax1.plot(peak['frequency'], peak['magnitude'], 'o',
                             color=JAPANESE_COLORS['error'], markersize=8, alpha=0.8,
                             markeredgecolor='white', markeredgewidth=1)
                self.ax1.annotate(f"{peak['frequency']:.0f}Hz",
                               xy=(peak['frequency'], peak['magnitude']),
                               xytext=(5, 5), textcoords='offset points',
                               fontsize=8, ha='left', color=JAPANESE_COLORS['text_primary'])

            self.canvas1.draw()

        self.root.after(0, update_plot)

    def plot_time_frequency(self):
        """繪製時頻分析圖"""
        def update_plot():
            # 清空圖表
            self.ax2.clear()
            self.ax3.clear()

            freq_range = self.get_frequency_range()

            # 繪製時頻圖（頻譜圖）
            im = self.ax2.imshow(
                self.stft_magnitude,
                aspect='auto',
                origin='lower',
                extent=[self.stft_times[0], self.stft_times[-1],
                       self.stft_frequencies[0], self.stft_frequencies[-1]],
                cmap='viridis',
                vmin=-80, vmax=0
            )

            self.ax2.set_title(f"時頻分析圖 - {freq_range['name']}頻譜分析",
                             fontsize=14, color=JAPANESE_COLORS['text_primary'], pad=15)
            self.ax2.set_xlabel("時間 (秒)", fontsize=12, color=JAPANESE_COLORS['text_primary'])
            self.ax2.set_ylabel("頻率 (Hz)", fontsize=12, color=JAPANESE_COLORS['text_primary'])

            # 根據分析類型添加頻率範圍標記
            if freq_range["name"] == "高頻":
                self.ax2.axhline(y=freq_range["start"], color=JAPANESE_COLORS['warning'],
                               linestyle='--', linewidth=2, alpha=0.8)
            elif freq_range["name"] == "低頻":
                self.ax2.axhline(y=freq_range["end"], color=JAPANESE_COLORS['warning'],
                               linestyle='--', linewidth=2, alpha=0.8)

            self.ax2.set_facecolor(JAPANESE_COLORS['bg_secondary'])

            # 添加顏色條
            cbar = self.fig2.colorbar(im, ax=self.ax2)
            cbar.set_label('振幅 (dB)', fontsize=10, color=JAPANESE_COLORS['text_primary'])

            # 標記截圖時間點
            for i, screenshot in enumerate(self.captured_screenshots[:10]):  # 最多顯示10個
                self.ax2.axvline(x=screenshot['time'], color=JAPANESE_COLORS['accent_secondary'],
                               linestyle='-', linewidth=3, alpha=0.8)
                if i < 5:  # 只標註前5個以避免重疊
                    self.ax2.annotate(f"#{screenshot['rank']}",
                                    xy=(screenshot['time'], screenshot['frequency']),
                                    xytext=(5, 5), textcoords='offset points',
                                    fontsize=8, color=JAPANESE_COLORS['accent_secondary'], weight='bold')

            # 標記全域最大峰值位置
            if self.global_max_peak:
                self.ax2.plot(self.global_max_peak['time'],
                             self.global_max_peak['max_frequency'],
                             '*', color=JAPANESE_COLORS['error'], markersize=20,
                             markeredgecolor='white', markeredgewidth=2)

            # 繪製時間-峰值振幅圖
            times = [peak['time'] for peak in self.time_peaks]
            max_magnitudes = [peak['max_magnitude'] for peak in self.time_peaks]

            # 主要振幅線
            self.ax3.plot(times, max_magnitudes, color=JAPANESE_COLORS['accent_primary'],
                         linewidth=2, label=f'{freq_range["name"]}頻最大振幅', alpha=0.8)
            self.ax3.fill_between(times, max_magnitudes, color=JAPANESE_COLORS['accent_primary'], alpha=0.2)

            # 標記截圖時間點
            for screenshot in self.captured_screenshots:
                self.ax3.axvline(x=screenshot['time'], color=JAPANESE_COLORS['error'],
                               linestyle='-', linewidth=2, alpha=0.8)
                self.ax3.plot(screenshot['time'], screenshot['magnitude'],
                             'o', color=JAPANESE_COLORS['error'], markersize=10,
                             markeredgecolor='white', markeredgewidth=2)

            # 標記全域最大峰值
            if self.global_max_peak:
                self.ax3.plot(self.global_max_peak['time'],
                             self.global_max_peak['max_magnitude'],
                             '*', color=JAPANESE_COLORS['error'], markersize=20,
                             markeredgecolor='white', markeredgewidth=2)

            self.ax3.set_title(f"各時間點{freq_range['name']}頻最大振幅變化 (紅線=截圖時間點)",
                             fontsize=14, color=JAPANESE_COLORS['text_primary'], pad=15)
            self.ax3.set_xlabel("時間 (秒)", fontsize=12, color=JAPANESE_COLORS['text_primary'])
            self.ax3.set_ylabel("最大振幅 (dB)", fontsize=12, color=JAPANESE_COLORS['text_primary'])
            self.ax3.grid(True, linestyle='--', linewidth=0.5, color=JAPANESE_COLORS['divider'])
            self.ax3.legend()
            self.ax3.set_facecolor(JAPANESE_COLORS['bg_secondary'])

            self.fig2.tight_layout(pad=3.0)
            self.canvas2.draw()

        self.root.after(0, update_plot)

    def display_analysis_results(self):
        """顯示分析結果"""
        def update_results():
            self.result_text.delete(1.0, tk.END)

            freq_range = self.get_frequency_range()

            # 基本資訊
            result_text = f"🎵 === 音訊{freq_range['name']}頻譜分析結果 (含時間維度及截圖) === 🎵\n\n"
            result_text += f"📁 影片檔案: {Path(self.video_file).name}\n"
            result_text += f"🔧 分析類型: {freq_range['name']}頻分析 ({freq_range['description']})\n"
            result_text += f"⏱️ 影片總長度: {self.audio_duration:.2f} 秒\n"
            result_text += f"🎚️ 音訊取樣率: {self.sample_rate} Hz\n"

            if freq_range["name"] == "高頻":
                result_text += f"🔊 分析範圍: >{freq_range['start']} Hz (高頻區域)\n\n"
            elif freq_range["name"] == "低頻":
                result_text += f"🔊 分析範圍: {freq_range['start']}-{freq_range['end']} Hz (低頻區域)\n\n"
            else:
                result_text += f"🔊 分析範圍: {freq_range['start']}-{freq_range['end']} Hz (全頻區域)\n\n"

            # 截圖資訊
            result_text += "📸 === 截圖資訊 === 📸\n"
            if self.captured_screenshots:
                result_text += f"✨ 共截取 {len(self.captured_screenshots)} 張關鍵時間點畫面\n"
                screenshot_dir = self.captured_screenshots[0]['filepath'].parent
                result_text += f"📁 儲存位置: {screenshot_dir}\n"
                result_text += "🖱️ 點擊下方預覽圖像可開啟完整圖片\n\n"

                result_text += "📋 截圖詳細列表:\n"
                for screenshot in self.captured_screenshots:
                    result_text += f"#{screenshot['rank']:2d}. ⏰{screenshot['time']:6.2f}秒 - "
                    result_text += f"🎵{screenshot['frequency']:7.1f}Hz - 📊{screenshot['magnitude']:6.2f}dB\n"
                    result_text += f"     📄 檔案: {screenshot['filepath'].name}\n"
                result_text += "\n"
            else:
                result_text += "❌ 未能成功截取畫面\n\n"

            # 整體統計資訊
            result_text += f"📈 === {freq_range['name']}頻統計資訊 === 📈\n"
            result_text += f"🔍 檢測到的{freq_range['name']}頻峰值數量: {self.analysis_stats['total_peaks']}\n"
            result_text += f"📊 {freq_range['name']}頻區域最大振幅: {self.analysis_stats['max_magnitude']:.2f} dB\n"
            result_text += f"📊 {freq_range['name']}頻區域平均振幅: {self.analysis_stats['avg_magnitude']:.2f} dB\n\n"

            # 時間分析結果
            result_text += "⏰ === 時間維度分析結果 === ⏰\n"
            if self.global_max_peak:
                result_text += f"🎯 全域最大峰值出現時間: {self.global_max_peak['time']:.2f} 秒\n"
                result_text += f"   🎵 對應頻率: {self.global_max_peak['max_frequency']:.1f} Hz\n"
                result_text += f"   📊 振幅大小: {self.global_max_peak['max_magnitude']:.2f} dB\n"
                result_text += f"   🔢 該時間點峰值數量: {self.global_max_peak['peak_count']}\n\n"

            # 主要峰值頻率
            if self.freq_peaks:
                result_text += f"🎵 === 主要{freq_range['name']}頻峰值 (整體平均) === 🎵\n"
                for i, peak in enumerate(self.freq_peaks, 1):
                    result_text += f"{i:2d}. 🎵 {peak['frequency']:8.1f} Hz - 📊 {peak['magnitude']:6.2f} dB\n"
            else:
                result_text += f"🎵 === {freq_range['name']}頻峰值 === 🎵\n"
                result_text += f"✅ 未檢測到明顯的{freq_range['name']}頻峰值\n"

            result_text += "\n"

            # 分析建議
            result_text += "💡 === 分析重點提示 === 💡\n"
            result_text += "1. 🖼️ 查看截圖預覽區域，了解異常音訊產生時的機械動作\n"
            result_text += "2. 📊 時頻分析圖中的綠色垂直線標示了截圖時間點\n"
            result_text += "3. ⭐ 紅色星號標記了全域最大峰值的時間和頻率位置\n"
            result_text += "4. 📈 振幅變化圖中的紅點顯示了所有截圖時間點\n"
            result_text += "5. 🔍 通過對比截圖與頻譜，可以找出產生異常音訊的具體機械動作\n"
            result_text += "6. 📋 詳細的截圖資訊已儲存為文字檔案，便於後續分析\n\n"

            # 根據分析類型提供特定建議
            if freq_range["name"] == "高頻":
                result_text += "🔧 === 高頻分析特殊建議 === 🔧\n"
                result_text += "• 關注軸承、齒輪等旋轉部件的異音\n"
                result_text += "• 檢查電機或馬達的高頻電磁噪音\n"
                result_text += "• 注意金屬摩擦或碰撞產生的尖銳聲音\n\n"
            elif freq_range["name"] == "低頻":
                result_text += "🔧 === 低頻分析特殊建議 === 🔧\n"
                result_text += "• 關注結構振動或共振問題\n"
                result_text += "• 檢查大型部件的不平衡或鬆動\n"
                result_text += "• 注意低速旋轉部件的週期性異音\n\n"

            # 健康狀態評估
            result_text += "🏥 === 設備狀態評估 === 🏥\n"
            if self.global_max_peak:
                if self.global_max_peak['max_magnitude'] > -30:
                    result_text += "🔴 警告: 檢測到非常高的峰值，建議立即檢查設備\n"
                    result_text += "   🔧 結合截圖分析該時間點的機械動作\n"
                elif self.global_max_peak['max_magnitude'] > -40:
                    result_text += "🟡 注意: 檢測到較高的峰值，建議密切監控\n"
                    result_text += "   🔧 建議檢查截圖中對應的機械部件\n"
                else:
                    result_text += "🟢 良好: 峰值在正常範圍內\n"

                # 分析峰值分佈的時間特性
                if len(self.time_peaks) > 0:
                    high_magnitude_count = sum(1 for p in self.time_peaks if p['max_magnitude'] > -40)
                    high_ratio = high_magnitude_count / len(self.time_peaks)

                    if high_ratio > 0.3:
                        result_text += "⚠️ 高振幅時間點比例較高，設備可能存在持續性問題\n"
                        result_text += "   🔧 建議檢查截圖中重複出現的機械動作\n"
                    elif high_ratio > 0.1:
                        result_text += "ℹ️ 偶有高振幅時間點，建議定期監控\n"
                    else:
                        result_text += "✅ 高振幅時間點比例較低，設備狀況良好\n"
            else:
                result_text += "✅ 未檢測到明顯異常，設備狀況良好\n"

            self.result_text.insert(tk.END, result_text)

        self.root.after(0, update_results)

    def cleanup(self):
        """清理資源"""
        def finish_cleanup():
            self.progress.config(mode='indeterminate')
            self.progress.stop()
            self.process_button.config(state="normal")
            self.is_processing = False

        # 刪除暫存音訊檔
        try:
            if os.path.exists(self.temp_audio_file):
                os.remove(self.temp_audio_file)
        except:
            pass

        self.root.after(0, finish_cleanup)

def main():
    """主函數"""
    root = tk.Tk()
    app = VideoAudioAnalyzer(root)

    # 設置視窗圖示（如果有的話）
    try:
        root.iconbitmap('icon.ico')  # 可選：添加應用程式圖示
    except:
        pass

    # 設置關閉事件
    def on_closing():
        if app.is_processing:
            if messagebox.askokcancel("退出", "分析正在進行中，確定要退出嗎？"):
                root.destroy()
        else:
            root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_closing)

    # 啟動GUI
    root.mainloop()

if __name__ == "__main__":
    main()