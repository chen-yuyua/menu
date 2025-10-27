import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import ezdxf
import os
import math

# 輕量版本 - 移除 matplotlib 依賴以減少檔案大小
USE_PREVIEW = False  # 設定為 False 來禁用圖形預覽功能

try:
    if USE_PREVIEW:
        import matplotlib.pyplot as plt
        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
        from matplotlib.figure import Figure
        import numpy as np
        MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False

class JapaneseStyleDXFConverter:
    def __init__(self, root):
        self.root = root
        self.root.title("座標系ファイル(.txt/.csv)➜軌跡図転換(.dxfコンバーター)")
        self.root.geometry("900x700")  # 稍微增加寬度和高度
        self.root.resizable(True, True)
        self.root.minsize(850, 650)  # 調整最小尺寸

        # 日系配色テーマ（図2から）
        self.colors = {
            'bg_primary': '#FAF9F9',        # Seasalt - メイン背景
            'bg_secondary': '#FFFFFF',       # 白色 - カード背景
            'bg_card': '#FFFFFF',           # カード背景
            'accent': '#555B6E',            # Payne's gray - アクセント
            'accent_hover': '#444955',      # より濃いグレー
            'secondary': '#89B0AE',         # Cambridge blue - セカンダリ
            'secondary_hover': '#7A9B99',   # より濃い青緑
            'success': '#BEE3DB',           # Mint green - 成功色
            'success_dark': '#A8D5CC',      # より濃いミント
            'warning': '#FFD6BA',           # Apricot - 警告色
            'text_primary': '#2C2F33',      # 濃いグレー
            'text_secondary': '#555B6E',    # ミディアムグレー
            'text_light': '#89B0AE',        # ライトブルーグレー
            'border': '#E8E8E8',           # ライトボーダー
            'border_focus': '#89B0AE'       # フォーカス時のボーダー
        }

        # 進度関連変数
        self.progress_var = tk.DoubleVar()
        self.progress_text = tk.StringVar(value="変換準備完了")

        # ファイルパス変数
        self.input_file_path = tk.StringVar()
        self.output_file_path = tk.StringVar()

        # 新增：起始角度和圓心距離變數
        self.start_angle = tk.DoubleVar(value=0.00)  # 起始角度，預設0.00度
        self.center_distance = tk.DoubleVar(value=0.0000)  # 圓心距離，預設0.0000

        # 單位オプション
        self.unit_options = {
            "ミリメートル (mm)": 4,
            "センチメートル (cm)": 5,
            "メートル (m)": 6,
            "インチ (inch)": 1,
            "フィート (feet)": 2
        }
        self.selected_unit = tk.StringVar(value="ミリメートル (mm)")

        # 角度間隔オプション（動的生成）
        self.angle_options = ["ファイル選択後に表示されます"]
        self.selected_angle = tk.StringVar(value="ファイル選択後に表示されます")

        # 出力タイプオプション
        self.output_types = {
            "スプライン曲線（推奨）": "spline",
            "スムーズ多段線": "smooth_polyline",
            "多段線（直線接続）": "polyline"
        }
        self.selected_output_type = tk.StringVar(value="スプライン曲線（推奨）")

        # ファイル分析結果
        self.original_angle_step = 0.0
        self.total_points = 0
        self.is_file_analyzed = False

        # カスタムスタイルの設定
        self.setup_styles()

        # 背景色を設定
        self.root.configure(bg=self.colors['bg_primary'])

        self.setup_ui()

    def setup_styles(self):
        """日系モダンスタイルを設定"""
        style = ttk.Style()
        style.theme_use('clam')

        # フォント設定（より大きく、太字）
        header_font = ('BIZ UDPゴシック', 24, 'bold')
        title_font = ('BIZ UDPゴシック', 14, 'bold')
        label_font = ('BIZ UDPゴシック', 11, 'bold')
        text_font = ('BIZ UDPゴシック', 10)
        button_font = ('BIZ UDPゴシック', 12, 'bold')

        # カードスタイル（丸角）
        style.configure('Card.TLabelframe',
                       background=self.colors['bg_card'],
                       relief='flat',
                       borderwidth=1,
                       lightcolor=self.colors['border'],
                       darkcolor=self.colors['border'])

        style.configure('Card.TLabelframe.Label',
                       background=self.colors['bg_card'],
                       foreground=self.colors['text_primary'],
                       font=title_font)

        # プライマリボタン
        style.configure('Primary.TButton',
                       background=self.colors['accent'],
                       foreground='white',
                       borderwidth=0,
                       focuscolor='none',
                       font=button_font,
                       padding=(20, 12))

        style.map('Primary.TButton',
                 background=[('active', self.colors['accent_hover']),
                           ('pressed', self.colors['accent_hover'])])

        # セカンダリボタン
        style.configure('Secondary.TButton',
                       background=self.colors['secondary'],
                       foreground='white',
                       borderwidth=0,
                       focuscolor='none',
                       font=button_font,
                       padding=(20, 12))

        style.map('Secondary.TButton',
                 background=[('active', self.colors['secondary_hover']),
                           ('pressed', self.colors['secondary_hover'])])

        # 成功ボタン
        style.configure('Success.TButton',
                       background=self.colors['success_dark'],
                       foreground=self.colors['text_primary'],
                       borderwidth=0,
                       focuscolor='none',
                       font=('BIZ UDPゴシック', 14, 'bold'),
                       padding=(25, 15))

        style.map('Success.TButton',
                 background=[('active', self.colors['success']),
                           ('pressed', self.colors['success'])])

        # エントリーとコンボボックス
        style.configure('Modern.TEntry',
                       fieldbackground='white',
                       borderwidth=2,
                       relief='solid',
                       bordercolor=self.colors['border'],
                       padding=12,
                       font=text_font)

        style.map('Modern.TEntry',
                 bordercolor=[('focus', self.colors['border_focus'])])

        style.configure('Modern.TCombobox',
                       fieldbackground='white',
                       borderwidth=2,
                       relief='solid',
                       bordercolor=self.colors['border'],
                       padding=12,
                       font=text_font)

        style.map('Modern.TCombobox',
                 bordercolor=[('focus', self.colors['border_focus'])])

        # ラベル（ttk.Labelのみ）
        style.configure('Light.TLabel',
                       background=self.colors['bg_card'],
                       foreground=self.colors['text_light'],
                       font=text_font)

        # プログレスバー
        style.configure('Modern.Horizontal.TProgressbar',
                       background=self.colors['success_dark'],
                       troughcolor=self.colors['border'],
                       borderwidth=0,
                       lightcolor=self.colors['success_dark'],
                       darkcolor=self.colors['success_dark'],
                       thickness=15)

    def create_rounded_frame(self, parent, **kwargs):
        """丸角フレームを作成"""
        frame = tk.Frame(parent,
                        bg=self.colors['bg_card'],
                        relief='solid',
                        bd=1,
                        highlightbackground=self.colors['border'],
                        highlightthickness=1,
                        **kwargs)
        return frame

    def setup_ui(self):
        # メインコンテナ
        main_container = tk.Frame(self.root, bg=self.colors['bg_primary'])
        main_container.pack(fill=tk.BOTH, expand=True, padx=30, pady=30)

        # ヘッダーセクション
        self.create_header(main_container)

        # コンテンツエリア
        content_frame = tk.Frame(main_container, bg=self.colors['bg_primary'])
        content_frame.pack(fill=tk.BOTH, expand=True, pady=(20, 0))

        # 左側コラム
        left_column = tk.Frame(content_frame, bg=self.colors['bg_primary'])
        left_column.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 15))

        # 右側コラム
        right_column = tk.Frame(content_frame, bg=self.colors['bg_primary'])
        right_column.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(15, 0))

        # 左側：入力設定
        self.create_input_section(left_column)
        self.create_cam_parameters_section(left_column)  # 新增：凸輪參數設定
        self.create_output_section(left_column)
        self.create_button_section(left_column)

        # 右側：進度、ログ、圖形預覽（如果啟用）
        self.create_progress_section(right_column)
        self.create_status_section(right_column)

        if USE_PREVIEW and MATPLOTLIB_AVAILABLE:
            self.create_preview_section(right_column)
        else:
            self.create_info_section(right_column)



    def create_header(self, parent):
        """ヘッダーセクションを作成"""
        header_frame = self.create_rounded_frame(parent)
        header_frame.pack(fill=tk.X, pady=(0, 25))

        # ヘッダー内容コンテナ
        header_content = tk.Frame(header_frame, bg=self.colors['bg_card'])
        header_content.pack(fill=tk.X, pady=30, padx=30)

        # 版本資訊區域（右上角）
        version_frame = tk.Frame(header_content, bg=self.colors['bg_card'])
        version_frame.pack(side=tk.RIGHT, anchor=tk.NE)

        # 版本號標籤
        version_label = tk.Label(version_frame,
                                text="Ver.1.1",
                                font=('BIZ UDPゴシック', 9, 'bold'),
                                fg=self.colors['text_light'],
                                bg=self.colors['bg_card'])
        version_label.pack(anchor=tk.E)

        # 更新日期標籤
        update_date_label = tk.Label(version_frame,
                                    text="更新日:2025/10/22",
                                    font=('BIZ UDPゴシック', 8),
                                    fg=self.colors['text_light'],
                                    bg=self.colors['bg_card'])
        update_date_label.pack(anchor=tk.E, pady=(2, 0))

        # メインタイトル
        title_container = tk.Frame(header_content, bg=self.colors['bg_card'])
        title_container.pack(side=tk.LEFT, expand=True)

        # アイコンとタイトル
        icon_label = tk.Label(title_container,
                             text="📐",
                             font=('BIZ UDPゴシック', 32),
                             bg=self.colors['bg_card'],
                             fg=self.colors['accent'])
        icon_label.pack()

        title_label = tk.Label(title_container,
                              text="座標系ファイル(.txt/.csv)➜軌跡図転換(.dxfコンバーター)",
                              font=('BIZ UDPゴシック', 20, 'bold'),
                              fg=self.colors['text_primary'],
                              bg=self.colors['bg_card'])
        title_label.pack(pady=(10, 5))

        subtitle_label = tk.Label(title_container,
                                 text="高精度な座標データを美しい軌跡図に変換します",
                                 font=('BIZ UDPゴシック', 12),
                                 fg=self.colors['text_secondary'],
                                 bg=self.colors['bg_card'])
        subtitle_label.pack()

    def create_input_section(self, parent):
        """入力ファイルセクションを作成"""
        input_card = self.create_rounded_frame(parent)
        input_card.pack(fill=tk.X, pady=(0, 20))

        # セクションタイトル
        title_frame = tk.Frame(input_card, bg=self.colors['bg_card'])
        title_frame.pack(fill=tk.X, padx=25, pady=(20, 10))

        tk.Label(title_frame,
                text="📁 入力ファイル選択",
                font=('BIZ UDPゴシック', 14, 'bold'),
                fg=self.colors['text_primary'],
                bg=self.colors['bg_card']).pack(anchor=tk.W)

        # ファイル選択エリア
        file_frame = tk.Frame(input_card, bg=self.colors['bg_card'])
        file_frame.pack(fill=tk.X, padx=25, pady=(0, 15))
        file_frame.columnconfigure(0, weight=1)

        self.input_entry = ttk.Entry(file_frame,
                                    textvariable=self.input_file_path,
                                    state="readonly",
                                    style='Modern.TEntry')
        self.input_entry.grid(row=0, column=0, sticky=(tk.W, tk.E), padx=(0, 15))

        ttk.Button(file_frame,
                  text="ファイル選択",
                  command=self.select_input_file,
                  style='Secondary.TButton').grid(row=0, column=1)

        # ファイル形式説明
        info_frame = tk.Frame(input_card, bg=self.colors['bg_card'])
        info_frame.pack(fill=tk.X, padx=25, pady=(0, 15))

        tk.Label(info_frame,
                text="📝 対応形式: TXT, CSV | 📐 データ形式: x,y (カンマ区切り)",
                font=('BIZ UDPゴシック', 9),
                fg=self.colors['text_light'],
                bg=self.colors['bg_card']).pack(anchor=tk.W)

        # ファイル分析結果表示
        self.analysis_label = tk.Label(input_card,
                                      text="ファイルを選択すると自動分析が開始されます",
                                      font=('BIZ UDPゴシック', 10),
                                      fg=self.colors['text_secondary'],
                                      bg=self.colors['bg_card'])
        self.analysis_label.pack(padx=25, pady=(0, 20))

    def create_cam_parameters_section(self, parent):
        """新增：凸輪參數設定セクションを作成"""
        cam_card = self.create_rounded_frame(parent)
        cam_card.pack(fill=tk.X, pady=(0, 20))

        # セクションタイトル
        title_frame = tk.Frame(cam_card, bg=self.colors['bg_card'])
        title_frame.pack(fill=tk.X, padx=25, pady=(20, 15))

        tk.Label(title_frame,
                text="🔧 凸輪參數設定",
                font=('BIZ UDPゴシック', 14, 'bold'),
                fg=self.colors['text_primary'],
                bg=self.colors['bg_card']).pack(anchor=tk.W)

        # 參數輸入區域
        params_frame = tk.Frame(cam_card, bg=self.colors['bg_card'])
        params_frame.pack(fill=tk.X, padx=25, pady=(0, 20))
        params_frame.columnconfigure(0, weight=1)
        params_frame.columnconfigure(1, weight=1)

        # 起始角度設定
        angle_frame = tk.Frame(params_frame, bg=self.colors['bg_card'])
        angle_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), padx=(0, 10))

        tk.Label(angle_frame,
                text="起始角度 (度):",
                font=('BIZ UDPゴシック', 11, 'bold'),
                fg=self.colors['text_primary'],
                bg=self.colors['bg_card']).pack(anchor=tk.W, pady=(0, 8))

        # 起始角度輸入框，支援小數點第二位
        angle_var = tk.StringVar()
        angle_var.trace('w', lambda *args: self.validate_angle_input(angle_var))
        self.angle_entry = tk.Entry(angle_frame,
                                   textvariable=angle_var,
                                   width=12,
                                   font=('BIZ UDPゴシック', 10),
                                   bg='white',
                                   relief='solid',
                                   bd=2,
                                   highlightthickness=1,
                                   highlightcolor=self.colors['border_focus'],
                                   highlightbackground=self.colors['border'])
        self.angle_entry.pack(anchor=tk.W)
        self.angle_var = angle_var

        # 說明文字
        tk.Label(angle_frame,
                text="(例: 0.00, 15.75, 90.25)",
                font=('BIZ UDPゴシック', 8),
                fg=self.colors['text_light'],
                bg=self.colors['bg_card']).pack(anchor=tk.W, pady=(2, 0))

        # 圓心距離設定
        distance_frame = tk.Frame(params_frame, bg=self.colors['bg_card'])
        distance_frame.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(10, 0))

        tk.Label(distance_frame,
                text="中心からの距離:",
                font=('BIZ UDPゴシック', 11, 'bold'),
                fg=self.colors['text_primary'],
                bg=self.colors['bg_card']).pack(anchor=tk.W, pady=(0, 8))

        # 圓心距離輸入框，支援小數點第四位
        distance_var = tk.StringVar()
        distance_var.trace('w', lambda *args: self.validate_distance_input(distance_var))
        self.distance_entry = tk.Entry(distance_frame,
                                      textvariable=distance_var,
                                      width=15,
                                      font=('BIZ UDPゴシック', 10),
                                      bg='white',
                                      relief='solid',
                                      bd=2,
                                      highlightthickness=1,
                                      highlightcolor=self.colors['border_focus'],
                                      highlightbackground=self.colors['border'])
        self.distance_entry.pack(anchor=tk.W)
        self.distance_var = distance_var

        # 說明文字
        tk.Label(distance_frame,
                text="(例: 33.7162, 25.1234)",
                font=('BIZ UDPゴシック', 8),
                fg=self.colors['text_light'],
                bg=self.colors['bg_card']).pack(anchor=tk.W, pady=(2, 0))

        # 使用提示
        tip_frame = tk.Frame(cam_card, bg=self.colors['bg_card'])
        tip_frame.pack(fill=tk.X, padx=25, pady=(10, 20))

        tip_label = tk.Label(tip_frame,
                            text="💡 起始角度：第一個座標點的角度位置｜第一點距離：第一個座標點到圓心的直線距離（單位：mm）",
                            font=('BIZ UDPゴシック', 9),
                            fg=self.colors['text_light'],
                            bg=self.colors['bg_card'],
                            wraplength=350,
                            justify=tk.LEFT)
        tip_label.pack(anchor=tk.W)

    def validate_angle_input(self, angle_var):
        """驗證起始角度輸入（支援小數點第二位）"""
        try:
            value = angle_var.get()
            if value == "" or value == ".":
                return

            # 允許負號
            if value.startswith('-'):
                if len(value) == 1:
                    return
                value = value[1:]

            # 檢查是否為有效數字格式
            if '.' in value:
                parts = value.split('.')
                if len(parts) > 2:
                    # 多於一個小數點，截取到第一個小數點
                    corrected = parts[0] + '.' + ''.join(parts[1:])
                    angle_var.set(('-' if angle_var.get().startswith('-') else '') + corrected[:corrected.find('.') + 3])
                    return
                if len(parts[1]) > 2:
                    # 小數點後超過2位，截取到2位
                    angle_var.set(('-' if angle_var.get().startswith('-') else '') + parts[0] + '.' + parts[1][:2])
                    return

            # 轉換為浮點數驗證
            float(angle_var.get())
        except ValueError:
            # 移除無效字符
            current = angle_var.get()
            valid_chars = "0123456789.-"
            filtered = ''.join(c for c in current if c in valid_chars)
            if filtered != current:
                angle_var.set(filtered)

    def validate_distance_input(self, distance_var):
        """驗證圓心距離輸入（支援小數點第四位）"""
        try:
            value = distance_var.get()
            if value == "" or value == ".":
                return

            # 檢查是否為有效數字格式
            if '.' in value:
                parts = value.split('.')
                if len(parts) > 2:
                    # 多於一個小數點，截取到第一個小數點
                    corrected = parts[0] + '.' + ''.join(parts[1:])
                    distance_var.set(corrected[:corrected.find('.') + 5])
                    return
                if len(parts[1]) > 4:
                    # 小數點後超過4位，截取到4位
                    distance_var.set(parts[0] + '.' + parts[1][:4])
                    return

            # 轉換為浮點數驗證
            float(distance_var.get())
        except ValueError:
            # 移除無效字符
            current = distance_var.get()
            valid_chars = "0123456789."
            filtered = ''.join(c for c in current if c in valid_chars)
            if filtered != current:
                distance_var.set(filtered)

    def get_cam_parameters(self):
        """獲取凸輪參數"""
        try:
            # 從UI輸入框獲取數值
            angle_input = self.angle_var.get().strip()
            distance_input = self.distance_var.get().strip()
            
            # 處理角度值
            if angle_input:
                angle = float(angle_input)
            else:
                angle = 0.0
                
            # 處理距離值
            if distance_input:
                distance = float(distance_input)
            else:
                distance = 0.0
                
            self.log_message(f"🔧 參數讀取: 角度輸入='{angle_input}' -> {angle}°")
            self.log_message(f"🔧 參數讀取: 距離輸入='{distance_input}' -> {distance}mm")
            
            return angle, distance
        except ValueError as e:
            self.log_message(f"❌ 參數讀取錯誤: {str(e)}")
            return 0.0, 0.0

    def create_output_section(self, parent):
        """出力設定セクションを作成"""
        output_card = self.create_rounded_frame(parent)
        output_card.pack(fill=tk.X, pady=(0, 20))

        # セクションタイトル
        title_frame = tk.Frame(output_card, bg=self.colors['bg_card'])
        title_frame.pack(fill=tk.X, padx=25, pady=(20, 15))

        tk.Label(title_frame,
                text="⚙️ 出力設定",
                font=('BIZ UDPゴシック', 14, 'bold'),
                fg=self.colors['text_primary'],
                bg=self.colors['bg_card']).pack(anchor=tk.W)

        # 保存先選択
        save_frame = tk.Frame(output_card, bg=self.colors['bg_card'])
        save_frame.pack(fill=tk.X, padx=25, pady=(0, 20))
        save_frame.columnconfigure(0, weight=1)

        tk.Label(save_frame,
                text="保存先:",
                font=('BIZ UDPゴシック', 11, 'bold'),
                fg=self.colors['text_primary'],
                bg=self.colors['bg_card']).grid(row=0, column=0, sticky=tk.W, pady=(0, 8))

        save_entry_frame = tk.Frame(save_frame, bg=self.colors['bg_card'])
        save_entry_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), columnspan=2)
        save_entry_frame.columnconfigure(0, weight=1)

        self.output_entry = ttk.Entry(save_entry_frame,
                                     textvariable=self.output_file_path,
                                     state="readonly",
                                     style='Modern.TEntry')
        self.output_entry.grid(row=0, column=0, sticky=(tk.W, tk.E), padx=(0, 15))

        ttk.Button(save_entry_frame,
                  text="保存先選択",
                  command=self.select_output_file,
                  style='Secondary.TButton').grid(row=0, column=1)

        # 設定オプション
        settings_frame = tk.Frame(output_card, bg=self.colors['bg_card'])
        settings_frame.pack(fill=tk.X, padx=25, pady=(0, 20))
        settings_frame.columnconfigure(0, weight=1)
        settings_frame.columnconfigure(1, weight=1)
        settings_frame.columnconfigure(2, weight=1)

        # 単位設定
        unit_frame = tk.Frame(settings_frame, bg=self.colors['bg_card'])
        unit_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), padx=(0, 10))

        tk.Label(unit_frame,
                text="出力単位:",
                font=('BIZ UDPゴシック', 11, 'bold'),
                fg=self.colors['text_primary'],
                bg=self.colors['bg_card']).pack(anchor=tk.W, pady=(0, 8))
        self.unit_combo = ttk.Combobox(unit_frame,
                                      textvariable=self.selected_unit,
                                      values=list(self.unit_options.keys()),
                                      state="readonly",
                                      style='Modern.TCombobox',
                                      width=15)
        self.unit_combo.pack(anchor=tk.W)

        # 角度間隔設定
        angle_frame = tk.Frame(settings_frame, bg=self.colors['bg_card'])
        angle_frame.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(5, 5))

        tk.Label(angle_frame,
                text="角度間隔:",
                font=('BIZ UDPゴシック', 11, 'bold'),
                fg=self.colors['text_primary'],
                bg=self.colors['bg_card']).pack(anchor=tk.W, pady=(0, 8))
        self.angle_combo = ttk.Combobox(angle_frame,
                                       textvariable=self.selected_angle,
                                       values=self.angle_options,
                                       state="disabled",
                                       style='Modern.TCombobox',
                                       width=15)
        self.angle_combo.pack(anchor=tk.W)

        # 曲線タイプ設定
        curve_frame = tk.Frame(settings_frame, bg=self.colors['bg_card'])
        curve_frame.grid(row=0, column=2, sticky=(tk.W, tk.E), padx=(10, 0))

        tk.Label(curve_frame,
                text="曲線タイプ:",
                font=('BIZ UDPゴシック', 11, 'bold'),
                fg=self.colors['text_primary'],
                bg=self.colors['bg_card']).pack(anchor=tk.W, pady=(0, 8))
        self.curve_combo = ttk.Combobox(curve_frame,
                                       textvariable=self.selected_output_type,
                                       values=list(self.output_types.keys()),
                                       state="readonly",
                                       style='Modern.TCombobox',
                                       width=15)
        self.curve_combo.pack(anchor=tk.W)

        # 使用建議表示
        self.suggestion_frame = tk.Frame(output_card, bg=self.colors['bg_card'])
        self.suggestion_frame.pack(fill=tk.X, padx=25, pady=(10, 20))

        self.curve_combo.bind('<<ComboboxSelected>>', self.on_curve_type_changed)
        self.update_curve_suggestions()

    def create_button_section(self, parent):
        """実行ボタンセクションを作成"""
        button_frame = tk.Frame(parent, bg=self.colors['bg_primary'])
        button_frame.pack(fill=tk.X, pady=(10, 0))

        # ボタンコンテナ
        button_container = tk.Frame(button_frame, bg=self.colors['bg_primary'])
        button_container.pack()

        # メイン変換ボタン
        self.convert_btn = ttk.Button(button_container,
                                     text="🚀 軌跡図に変換",
                                     command=self.convert_to_dxf,
                                     style='Success.TButton')
        self.convert_btn.pack(side=tk.LEFT, padx=(0, 15))

        # クリアボタン
        ttk.Button(button_container,
                  text="🗑 リセット",
                  command=self.clear_all,
                  style='Primary.TButton').pack(side=tk.LEFT)

    def create_progress_section(self, parent):
        """進度セクションを作成"""
        progress_card = self.create_rounded_frame(parent)
        progress_card.pack(fill=tk.X, pady=(0, 20))

        # セクションタイトル
        title_frame = tk.Frame(progress_card, bg=self.colors['bg_card'])
        title_frame.pack(fill=tk.X, padx=25, pady=(20, 15))

        tk.Label(title_frame,
                text="📊 変換進行状況",
                font=('BIZ UDPゴシック', 14, 'bold'),
                fg=self.colors['text_primary'],
                bg=self.colors['bg_card']).pack(anchor=tk.W)

        # 進度表示
        progress_content = tk.Frame(progress_card, bg=self.colors['bg_card'])
        progress_content.pack(fill=tk.X, padx=25, pady=(0, 20))

        self.progress_text_label = tk.Label(progress_content,
                                           textvariable=self.progress_text,
                                           font=('BIZ UDPゴシック', 11),
                                           fg=self.colors['text_primary'],
                                           bg=self.colors['bg_card'])
        self.progress_text_label.pack(anchor=tk.W, pady=(0, 10))

        self.progress_bar = ttk.Progressbar(progress_content,
                                           style='Modern.Horizontal.TProgressbar',
                                           length=300,
                                           variable=self.progress_var)
        self.progress_bar.pack(fill=tk.X)

    def create_status_section(self, parent):
        """ステータスセクションを作成（縮小版）"""
        status_card = self.create_rounded_frame(parent)
        status_card.pack(fill=tk.X, pady=(0, 15))  # fill=tk.X のみに変更

        # セクションタイトル
        title_frame = tk.Frame(status_card, bg=self.colors['bg_card'])
        title_frame.pack(fill=tk.X, padx=20, pady=(15, 10))

        tk.Label(title_frame,
                text="📋 実行ログ",
                font=('BIZ UDPゴシック', 12, 'bold'),  # フォントサイズを小さく
                fg=self.colors['text_primary'],
                bg=self.colors['bg_card']).pack(anchor=tk.W)

        # ログエリア（高さを縮小）
        log_container = tk.Frame(status_card, bg=self.colors['bg_card'])
        log_container.pack(fill=tk.X, padx=20, pady=(0, 15))  # fill=tk.X のみ
        log_container.columnconfigure(0, weight=1)

        self.status_text = tk.Text(log_container,
                                  height=8,  # 高さを8に縮小
                                  wrap=tk.WORD,
                                  bg='#FAFAFA',
                                  fg=self.colors['text_primary'],
                                  font=('BIZ UDPゴシック', 8),  # フォントサイズを小さく
                                  relief='flat',
                                  borderwidth=2,
                                  highlightthickness=1,
                                  highlightcolor=self.colors['border_focus'],
                                  highlightbackground=self.colors['border'],
                                  padx=12,
                                  pady=12)

        scrollbar = ttk.Scrollbar(log_container,
                                 orient=tk.VERTICAL,
                                 command=self.status_text.yview)
        self.status_text.configure(yscrollcommand=scrollbar.set)

        self.status_text.grid(row=0, column=0, sticky=(tk.W, tk.E), padx=(0, 5))
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))

        # 初期メッセージ
        self.log_message("💡 座標ファイルを選択して軌跡図変換を開始してください")
        self.log_message("📝 手順:")
        self.log_message("   1. 座標ファイル(.txt/.csv)を選択")
        self.log_message("   2. 凸輪參數を設定（起始角度、圓心距離）")
        self.log_message("   3. 保存先を指定")
        self.log_message("   4. 出力設定を調整")
        self.log_message("   5. 変換ボタンをクリック")
        self.log_message("")

    def create_info_section(self, parent):
        """情報表示セクションを作成（軽量版）"""
        info_card = self.create_rounded_frame(parent)
        info_card.pack(fill=tk.BOTH, expand=True)

        # セクションタイトル
        title_frame = tk.Frame(info_card, bg=self.colors['bg_card'])
        title_frame.pack(fill=tk.X, padx=20, pady=(15, 10))

        tk.Label(title_frame,
                text="📊 変換情報",
                font=('BIZ UDPゴシック', 12, 'bold'),
                fg=self.colors['text_primary'],
                bg=self.colors['bg_card']).pack(anchor=tk.W)

        # 情報表示エリア
        self.info_frame = tk.Frame(info_card, bg=self.colors['bg_card'])
        self.info_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 15))

        # 初期情報
        self.info_text = tk.Text(self.info_frame,
                                height=10,
                                wrap=tk.WORD,
                                bg='#F8F9FA',
                                fg=self.colors['text_primary'],
                                font=('BIZ UDPゴシック', 9),
                                relief='flat',
                                borderwidth=2,
                                highlightthickness=1,
                                highlightcolor=self.colors['border_focus'],
                                highlightbackground=self.colors['border'],
                                padx=15,
                                pady=15,
                                state='disabled')

        info_scrollbar = ttk.Scrollbar(self.info_frame,
                                      orient=tk.VERTICAL,
                                      command=self.info_text.yview)
        self.info_text.configure(yscrollcommand=info_scrollbar.set)

        self.info_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        info_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # 初期情報メッセージ
        self.update_info_display("変換完了後に詳細情報が表示されます")

    def create_preview_section(self, parent):
        """軌跡図プレビューセクションを作成"""
        if not (USE_PREVIEW and MATPLOTLIB_AVAILABLE):
            return self.create_info_section(parent)

        preview_card = self.create_rounded_frame(parent)
        preview_card.pack(fill=tk.BOTH, expand=True)

        # セクションタイトル
        title_frame = tk.Frame(preview_card, bg=self.colors['bg_card'])
        title_frame.pack(fill=tk.X, padx=20, pady=(15, 10))

        tk.Label(title_frame,
                text="🎯 軌跡図プレビュー",
                font=('BIZ UDPゴシック', 12, 'bold'),
                fg=self.colors['text_primary'],
                bg=self.colors['bg_card']).pack(anchor=tk.W)

        # 図形表示エリア
        self.preview_frame = tk.Frame(preview_card, bg=self.colors['bg_card'])
        self.preview_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 15))

        # 初期状態のメッセージ
        self.preview_label = tk.Label(self.preview_frame,
                                     text="変換完了後に軌跡図が表示されます",
                                     font=('BIZ UDPゴシック', 10),
                                     fg=self.colors['text_secondary'],
                                     bg=self.colors['bg_card'])
        self.preview_label.pack(expand=True)

        # matplotlib図形用の変数
        self.preview_canvas = None
        self.preview_figure = None

    def update_info_display(self, message):
        """情報表示を更新（軽量版）"""
        if hasattr(self, 'info_text'):
            self.info_text.config(state='normal')
            self.info_text.delete(1.0, tk.END)
            self.info_text.insert(tk.END, message)
            self.info_text.config(state='disabled')

    def draw_trajectory_preview(self, coordinates, curve_type="spline"):
        """軌跡図のプレビューを描画"""
        if not (USE_PREVIEW and MATPLOTLIB_AVAILABLE):
            self.show_conversion_info(coordinates, curve_type)
            return

        try:
            # 既存のキャンバスがあれば削除
            if self.preview_canvas:
                self.preview_canvas.get_tk_widget().destroy()

            # プレビューラベルを非表示
            if hasattr(self, 'preview_label'):
                self.preview_label.pack_forget()

            # matplotlib を使った図形描画（元のコード）
            import numpy as np
            self.preview_figure = Figure(figsize=(6, 6), dpi=80, facecolor='white')
            ax = self.preview_figure.add_subplot(111)

            if coordinates:
                x_coords = [point[0] for point in coordinates]
                y_coords = [point[1] for point in coordinates]

                if curve_type == "spline" and len(coordinates) > 3:
                    try:
                        from scipy import interpolate
                        t = np.linspace(0, 1, len(coordinates))
                        t_new = np.linspace(0, 1, len(coordinates) * 5)

                        tck_x, _ = interpolate.splprep([x_coords, y_coords], s=0, per=True)
                        x_new, y_new = interpolate.splev(t_new, tck_x)

                        ax.plot(x_new, y_new, 'b-', linewidth=2, label='スプライン曲線')
                        ax.plot(x_coords, y_coords, 'ro', markersize=3, alpha=0.6, label='制御点')
                    except ImportError:
                        # scipy がない場合はシンプルな線で描画
                        ax.plot(x_coords + [x_coords[0]], y_coords + [y_coords[0]],
                               'b-', linewidth=2, label='軌跡')
                        ax.plot(x_coords, y_coords, 'ro', markersize=3, alpha=0.6, label='座標点')

                elif curve_type == "smooth_polyline":
                    ax.plot(x_coords + [x_coords[0]], y_coords + [y_coords[0]],
                           'g-', linewidth=2, label='スムーズ多段線')
                    ax.plot(x_coords, y_coords, 'go', markersize=3, alpha=0.6, label='制御点')
                else:
                    ax.plot(x_coords + [x_coords[0]], y_coords + [y_coords[0]],
                           'r-', linewidth=2, label='多段線')
                    ax.plot(x_coords, y_coords, 'ro', markersize=3, alpha=0.6, label='制御点')

                ax.set_aspect('equal')
                ax.grid(True, alpha=0.3)
                ax.set_title(f'軌跡図プレビュー ({len(coordinates)} 点)',
                           fontsize=12, fontweight='bold')
                ax.set_xlabel('X座標', fontsize=10)
                ax.set_ylabel('Y座標', fontsize=10)
                ax.legend(fontsize=9)

                margin = 0.1
                x_range = max(x_coords) - min(x_coords)
                y_range = max(y_coords) - min(y_coords)
                ax.set_xlim(min(x_coords) - x_range * margin, max(x_coords) + x_range * margin)
                ax.set_ylim(min(y_coords) - y_range * margin, max(y_coords) + y_range * margin)

            self.preview_figure.tight_layout()
            self.preview_canvas = FigureCanvasTkAgg(self.preview_figure, self.preview_frame)
            self.preview_canvas.draw()
            self.preview_canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

            self.log_message("📈 軌跡図プレビューを表示しました")

        except Exception as e:
            self.log_message(f"⚠️ プレビュー作成エラー: {str(e)}")
            self.show_conversion_info(coordinates, curve_type)

    def show_conversion_info(self, coordinates, curve_type):
        """軽量版：変換情報を表示"""
        if not coordinates:
            return

        # 獲取凸輪參數
        start_angle, center_distance = self.get_cam_parameters()

        info_text = f"""変換完了情報：

📊 座標点数: {len(coordinates)} 点
🎨 曲線タイプ: {curve_type}
📐 座標範囲:
   X: {min(coord[0] for coord in coordinates):.3f} ～ {max(coord[0] for coord in coordinates):.3f}
   Y: {min(coord[1] for coord in coordinates):.3f} ～ {max(coord[1] for coord in coordinates):.3f}

🔧 凸輪參數:
   起始角度: {start_angle:.2f}°
   圓心距離: {center_distance:.4f}

✅ DXFファイルが正常に作成されました。
📁 指定した保存先でファイルを確認してください。

💡 ヒント:
このDXFファイルはCADソフトウェア（AutoCAD、FreeCAD等）で
開いて詳細な軌跡図を確認できます。"""

        self.update_info_display(info_text)
        self.log_message("📊 変換情報を表示しました")

    def draw_simple_preview(self, coordinates):
        """シンプルなプレビュー（後方互換性のため保持）"""
        if USE_PREVIEW and MATPLOTLIB_AVAILABLE:
            # 元のコードと同様の処理
            pass
        else:
            self.show_conversion_info(coordinates, "simple")

    def clear_preview(self):
        """プレビューをクリア"""
        if USE_PREVIEW and MATPLOTLIB_AVAILABLE:
            if self.preview_canvas:
                self.preview_canvas.get_tk_widget().destroy()
                self.preview_canvas = None
                self.preview_figure = None

            if hasattr(self, 'preview_label'):
                self.preview_label.pack(expand=True)
        else:
            self.update_info_display("変換完了後に詳細情報が表示されます")

    def generate_angle_options(self, base_angle):
        """基準角度に基づいて角度オプションを動的生成"""
        options = []
        # 元の角度から始めて、基準角度刻みで10個のオプションを生成
        for i in range(10):
            angle = base_angle * (i + 1)
            if angle <= 45.0:  # 最大45度まで
                options.append(f"{angle:.2f}°")  # 小数点第2位まで表示
            else:
                break

        # さらに大きな角度オプションも追加
        larger_angles = [0.5, 1.0, 2.0, 3.0, 5.0, 10.0, 15.0, 30.0, 45.0]
        for angle in larger_angles:
            if angle >= base_angle:
                angle_str = f"{angle:.2f}°"  # 小数点第2位まで表示
                if angle_str not in options:
                    options.append(angle_str)

        # 自動検出オプションを先頭に追加
        options.insert(0, "自動検出（推奨）")

        return options

    def analyze_coordinate_file(self, file_path):
        """座標ファイルを分析して角度間隔を推定し、動的オプションを生成"""
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                lines = file.readlines()
                valid_lines = []
                for line in lines:
                    parts = line.strip().split(',')
                    if len(parts) == 2:
                        try:
                            x = float(parts[0].strip())
                            y = float(parts[1].strip())
                            valid_lines.append((x, y))
                        except ValueError:
                            continue

                self.total_points = len(valid_lines)

                if self.total_points > 0:
                    # 360度を総点数で割って角度間隔を推定
                    self.original_angle_step = 360.0 / self.total_points

                    # 分析結果を表示
                    analysis_text = (f"📊 分析結果: 総点数 {self.total_points} 点 | "
                                   f"推定角度間隔 {self.original_angle_step:.4f}°")
                    self.analysis_label.config(text=analysis_text, fg=self.colors['success_dark'])

                    # 角度オプションを動的生成
                    self.angle_options = self.generate_angle_options(self.original_angle_step)
                    self.angle_combo['values'] = self.angle_options
                    self.angle_combo.config(state="readonly")
                    self.selected_angle.set("自動検出（推奨）")

                    self.is_file_analyzed = True
                    return True
                else:
                    self.analysis_label.config(text="❌ 有効な座標データが見つかりませんでした",
                                             fg=self.colors['warning'])
                    return False

        except Exception as e:
            self.analysis_label.config(text=f"❌ ファイル分析エラー: {str(e)}",
                                     fg=self.colors['warning'])
            return False

    def calculate_sampling_step(self, target_angle_str):
        """目標角度間隔に基づいてサンプリングステップを計算"""
        if target_angle_str == "自動検出（推奨）":
            return 1  # すべての点を使用

        try:
            # 文字列から数値を抽出 (例: "0.5°" -> 0.5)
            target_angle = float(target_angle_str.replace('°', ''))

            if self.original_angle_step > 0:
                # サンプリングステップを計算
                sampling_step = max(1, round(target_angle / self.original_angle_step))
                return sampling_step
            else:
                return 1
        except ValueError:
            return 1

    def create_curve_geometry(self, msp, coordinates, curve_type):
        """指定された曲線タイプで座標からジオメトリを作成"""
        if not coordinates:
            return False

        try:
            if curve_type == "spline":
                # スプライン曲線を作成（最も滑らかな曲線）
                spline = msp.add_spline(coordinates, degree=3)
                spline.dxf.flags = 1  # 閉じた曲線
                self.log_message("✨ スプライン曲線を作成しました（最高品質）")
                return True

            elif curve_type == "smooth_polyline":
                # スムーズ多段線を作成
                polyline = msp.add_lwpolyline(coordinates)
                polyline.dxf.flags = 1  # 閉じたポリライン
                self.apply_curve_fitting(polyline, coordinates)
                self.log_message("✨ スムーズ多段線を作成しました（バランス型）")
                return True

            else:  # polyline
                # 従来の多段線（直線接続）
                polyline = msp.add_lwpolyline(coordinates)
                self.log_message("✨ 多段線を作成しました（シンプル型）")
                return True

        except Exception as e:
            self.log_message(f"❌ 曲線作成エラー: {str(e)}")
            # フォールバック
            msp.add_lwpolyline(coordinates)
            self.log_message("⚠️ フォールバック: 基本多段線を作成しました")
            return True

    def apply_curve_fitting(self, polyline, coordinates):
        """ポリラインに曲線フィッティングを適用"""
        try:
            if len(coordinates) > 2:
                for i in range(len(coordinates) - 1):
                    if i < len(coordinates) - 2:
                        p1 = coordinates[i]
                        p2 = coordinates[i + 1]
                        p3 = coordinates[i + 2]

                        v1 = (p2[0] - p1[0], p2[1] - p1[1])
                        v2 = (p3[0] - p2[0], p3[1] - p2[1])

                        len1 = math.sqrt(v1[0]**2 + v1[1]**2)
                        len2 = math.sqrt(v2[0]**2 + v2[1]**2)

                        if len1 > 0 and len2 > 0:
                            v1_norm = (v1[0]/len1, v1[1]/len1)
                            v2_norm = (v2[0]/len2, v2[1]/len2)

                            dot_product = v1_norm[0]*v2_norm[0] + v1_norm[1]*v2_norm[1]
                            dot_product = max(-1, min(1, dot_product))
                            angle_change = math.acos(dot_product)

                            bulge = math.tan(angle_change / 4) * 0.1
                            polyline[i].bulge = bulge

        except Exception as e:
            self.log_message(f"⚠️ 曲線フィッティング警告: {str(e)}")

    def on_curve_type_changed(self, event=None):
        """曲線タイプが変更された時の処理"""
        self.update_curve_suggestions()

    def update_curve_suggestions(self):
        """選択された曲線タイプに応じて使用建議を更新"""
        # 既存の建議を削除
        for widget in self.suggestion_frame.winfo_children():
            widget.destroy()

        curve_type = self.selected_output_type.get()

        suggestions = {
            "スプライン曲線（推奨）": {
                "icon": "🎯",
                "desc": "最高品質の滑らかな曲線。精密加工に最適です。",
                "color": self.colors['success_dark']
            },
            "スムーズ多段線": {
                "icon": "⚖️",
                "desc": "品質とファイルサイズのバランスが良い実用的な選択。",
                "color": self.colors['secondary']
            },
            "多段線（直線接続）": {
                "icon": "📦",
                "desc": "シンプルで軽量。基本的な用途に適しています。",
                "color": self.colors['text_light']
            }
        }

        if curve_type in suggestions:
            suggestion = suggestions[curve_type]

            suggestion_label = tk.Label(self.suggestion_frame,
                                       text=f"{suggestion['icon']} {suggestion['desc']}",
                                       font=('BIZ UDPゴシック', 9),
                                       fg=suggestion['color'],
                                       bg=self.colors['bg_card'])
            suggestion_label.pack(anchor=tk.W)

    def update_progress(self, value, text):
        """進度を更新"""
        self.progress_var.set(value)
        self.progress_text.set(text)
        self.root.update()

    def select_input_file(self):
        """入力座標ファイルを選択"""
        file_path = filedialog.askopenfilename(
            title="座標ファイルを選択",
            filetypes=[
                ("テキストファイル", "*.txt"),
                ("CSVファイル", "*.csv"),
                ("すべてのファイル", "*.*")
            ]
        )
        if file_path:
            self.input_file_path.set(file_path)
            self.log_message(f"✅ ファイル選択: {os.path.basename(file_path)}")

            # ファイルを分析
            self.log_message("🔍 ファイル分析を開始...")
            if self.analyze_coordinate_file(file_path):
                self.log_message("✅ ファイル分析完了 - 角度間隔オプションが更新されました")
            else:
                self.log_message("⚠️ ファイル分析に問題が発生しました")

            self.update_progress(0, "ファイル選択・分析完了")

    def select_output_file(self):
        """出力DXFファイルの保存先を選択"""
        file_path = filedialog.asksaveasfilename(
            title="DXFファイルの保存先",
            defaultextension=".dxf",
            filetypes=[
                ("DXFファイル", "*.dxf"),
                ("すべてのファイル", "*.*")
            ]
        )
        if file_path:
            self.output_file_path.set(file_path)
            self.log_message(f"✅ 保存先設定: {os.path.basename(file_path)}")
            self.update_progress(0, "保存先設定完了")

    def clear_all(self):
        """すべての設定をリセット"""
        self.input_file_path.set("")
        self.output_file_path.set("")
        self.selected_unit.set("ミリメートル (mm)")
        self.selected_angle.set("ファイル選択後に表示されます")
        self.selected_output_type.set("スプライン曲線（推奨）")

        # 重置凸輪參數
        self.angle_var.set("")
        self.distance_var.set("")

        self.status_text.delete(1.0, tk.END)
        self.update_progress(0, "変換準備完了")

        # ファイル分析結果をリセット
        self.original_angle_step = 0.0
        self.total_points = 0
        self.is_file_analyzed = False
        self.angle_options = ["ファイル選択後に表示されます"]
        self.angle_combo['values'] = self.angle_options
        self.angle_combo.config(state="disabled")
        self.analysis_label.config(text="ファイルを選択すると自動分析が開始されます",
                                  fg=self.colors['text_secondary'])

        # 曲線建議を更新
        self.update_curve_suggestions()

        # プレビューをクリア
        self.clear_preview()

        self.log_message("🗑 すべての設定がリセットされました")

    def log_message(self, message):
        """ログメッセージを表示"""
        self.status_text.insert(tk.END, message + "\n")
        self.status_text.see(tk.END)
        self.root.update()

    def transform_coordinates_with_cam_parameters(self, coordinates, start_angle, center_distance):
        """根據凸輪參數轉換座標 - 正確的凸輪理論"""
        if not coordinates:
            return coordinates
        
        # 如果沒有設定凸輪參數，直接返回原座標
        if start_angle == 0.0 and center_distance == 0.0:
            return coordinates
            
        transformed_coords = []
        start_angle_rad = math.radians(start_angle)
        
        self.log_message(f"🔧 凸輪理論轉換: 起始角度={start_angle}°, 基圓半徑={center_distance}mm")
        
        # 判斷輸入資料格式
        total_points = len(coordinates)
        angle_step = 360.0 / total_points  # 每點對應的角度間隔
        
        for i, (x, y) in enumerate(coordinates):
            # 計算當前點的角度位置
            current_angle_deg = start_angle + (i * angle_step)
            current_angle_rad = math.radians(current_angle_deg)
            
            # 凸輪理論：
            # 1. 原始座標通常是位移量或半徑值
            # 2. 基圓半徑 + 位移量 = 實際凸輪半徑
            
            if abs(y) <= 360.0 and len(str(int(y))) <= 3:  # 可能是角度值
                # 格式：(半徑值, 角度值)
                cam_radius = center_distance + x  # 基圓半徑 + 位移
                angle_rad = math.radians(y + start_angle)
                
                new_x = cam_radius * math.cos(angle_rad)
                new_y = cam_radius * math.sin(angle_rad)
                
            else:
                # 格式：(x位移, y位移) 或 (半徑, 位移)
                if abs(x) > abs(y) * 10:  # 可能是半徑格式
                    # x是半徑值，y是位移量
                    cam_radius = center_distance + y  # 基圓 + 位移
                    new_x = cam_radius * math.cos(current_angle_rad)
                    new_y = cam_radius * math.sin(current_angle_rad)
                else:
                    # 直角座標位移格式
                    # 將位移量轉換為極坐標，然後加上基圓
                    displacement_radius = math.sqrt(x*x + y*y)
                    cam_radius = center_distance + displacement_radius
                    
                    new_x = cam_radius * math.cos(current_angle_rad)
                    new_y = cam_radius * math.sin(current_angle_rad)
            
            transformed_coords.append((new_x, new_y))
            
        return transformed_coords

    def transform_coordinates_with_start_angle(self, coordinates, start_angle):
        """根據起始角度旋轉整個軌跡"""
        if not coordinates or start_angle == 0.0:
            return coordinates
        
        transformed_coords = []
        start_angle_rad = math.radians(start_angle)
        
        self.log_message(f"🔄 軌跡旋轉: 起始角度={start_angle}°")
        
        # 旋轉所有座標點
        for x, y in coordinates:
            # 應用旋轉矩陣
            cos_angle = math.cos(start_angle_rad)
            sin_angle = math.sin(start_angle_rad)
            
            new_x = x * cos_angle - y * sin_angle
            new_y = x * sin_angle + y * cos_angle
            
            transformed_coords.append((new_x, new_y))
        
        return transformed_coords

    def add_first_point_marker(self, msp, coordinates, start_angle, center_distance):
        """在軌跡的第一個座標點位置添加標記"""
        if not coordinates:
            return
        
        # 取得旋轉後軌跡的第一個座標點
        first_coord = coordinates[0]
        first_x, first_y = first_coord
        
        # 如果有指定第一點距離，在該距離位置添加標記
        if center_distance > 0:
            # 計算第一點到圓心的實際距離
            actual_distance = math.sqrt(first_x*first_x + first_y*first_y)
            
            # 如果指定距離與實際距離不同，在指定距離位置也添加標記
            if abs(actual_distance - center_distance) > 0.1:  # 容差0.1mm
                # 計算第一點的角度方向
                angle_rad = math.atan2(first_y, first_x)
                
                # 在指定距離位置添加標記
                specified_x = center_distance * math.cos(angle_rad)
                specified_y = center_distance * math.sin(angle_rad)
                
                # 指定距離位置的標記（藍色圓圈）
                specified_circle = msp.add_circle((specified_x, specified_y), 1.5)
                specified_circle.dxf.color = 5  # 藍色
                specified_circle.dxf.linetype = "CONTINUOUS"
                
                # 添加參考線到指定距離位置
                specified_line = msp.add_line((0, 0), (specified_x, specified_y))
                specified_line.dxf.color = 5  # 藍色
                specified_line.dxf.linetype = "DASHED"
                
                self.log_message(f"📍 指定距離標記: ({specified_x:.3f}, {specified_y:.3f}), 距離={center_distance}mm")
        
        # 軌跡第一點標記（紅色圓圈，直徑3mm）
        marker_circle = msp.add_circle((first_x, first_y), 1.5)
        marker_circle.dxf.color = 1  # 紅色
        marker_circle.dxf.linetype = "CONTINUOUS"
        
        # 添加從圓心到第一點的參考線
        reference_line = msp.add_line((0, 0), (first_x, first_y))
        reference_line.dxf.color = 3  # 綠色
        reference_line.dxf.linetype = "DASHED"
        
        # 計算並顯示第一點資訊
        actual_distance = math.sqrt(first_x*first_x + first_y*first_y)
        actual_angle = math.degrees(math.atan2(first_y, first_x))
        if actual_angle < 0:
            actual_angle += 360
        
        self.log_message(f"📍 軌跡第一點位置: ({first_x:.3f}, {first_y:.3f})")
        self.log_message(f"📍 第一點角度: {actual_angle:.2f}°, 距離: {actual_distance:.3f}mm")
        
        return actual_distance, actual_angle

    def add_center_circle_if_needed(self, msp, coordinates):
        """根據軌跡形狀自動添加中心基圓"""
        if not coordinates:
            return
            
        # 計算所有點到原點的距離
        distances = []
        for x, y in coordinates:
            distance = math.sqrt(x*x + y*y)
            distances.append(distance)
        
        min_distance = min(distances)
        max_distance = max(distances)
        avg_distance = sum(distances) / len(distances)
        
        # 如果軌跡是類似凸輪形狀（有內外變化），添加基圓參考
        distance_variation = max_distance - min_distance
        if distance_variation > avg_distance * 0.1:  # 變化超過平均距離的10%
            # 使用最小距離作為基圓半徑
            base_radius = min_distance * 0.9  # 稍微小一點以確保可見
            if base_radius > 0:
                base_circle = msp.add_circle((0, 0), base_radius)
                base_circle.dxf.color = 8  # 灰色
                base_circle.dxf.linetype = "DASHED"  # 虛線
                self.log_message(f"📐 自動添加基圓參考線 (半徑: {base_radius:.3f}mm)")
                return base_radius
        
        return 0

    def convert_to_dxf(self):
        """DXF変換を実行"""
        # 入力チェック
        if not self.input_file_path.get():
            messagebox.showerror("エラー", "座標ファイルを選択してください！")
            return

        if not self.output_file_path.get():
            messagebox.showerror("エラー", "保存先を選択してください！")
            return

        if not self.is_file_analyzed:
            messagebox.showerror("エラー", "ファイル分析が完了していません！")
            return

        # ボタンを無効化
        self.convert_btn.config(state='disabled')

        try:
            # 在開始處獲取凸輪參數
            start_angle, center_distance = self.get_cam_parameters()

            self.log_message("=" * 50)
            self.log_message("🚀 軌跡図変換を開始します...")
            self.log_message(f"🔧 凸輪參數設定: 起始角度={start_angle:.2f}°, 第一點距離={center_distance:.4f}mm")
            self.update_progress(10, "DXFファイル初期化中...")

            # DXFファイルを作成
            doc = ezdxf.new('R2010')
            msp = doc.modelspace()

            # 単位を設定
            unit_code = self.unit_options[self.selected_unit.get()]
            doc.header['$INSUNITS'] = unit_code
            self.log_message(f"📏 出力単位: {self.selected_unit.get()}")
            self.update_progress(20, "単位設定完了...")

            # 座標データを読み込み
            coordinates = []
            input_file = self.input_file_path.get()
            self.log_message(f"📖 データ読み込み: {os.path.basename(input_file)}")
            self.update_progress(30, "データ読み込み中...")

            # サンプリング設定
            sampling_step = self.calculate_sampling_step(self.selected_angle.get())
            self.log_message(f"🎯 角度設定: {self.selected_angle.get()}")
            if sampling_step > 1:
                self.log_message(f"📐 サンプリング: {sampling_step} 点ごとに抽出")

            with open(input_file, 'r', encoding='utf-8') as file:
                lines = file.readlines()
                total_lines = len(lines)
                line_count = 0
                valid_count = 0
                sampled_count = 0

                for i, line in enumerate(lines):
                    line_count += 1
                    progress = 30 + (i / total_lines) * 40
                    self.update_progress(progress, f"データ処理中... {i+1}/{total_lines}")

                    parts = line.strip().split(',')
                    if len(parts) == 2:
                        try:
                            x = float(parts[0].strip())
                            y = float(parts[1].strip())
                            valid_count += 1

                            if (valid_count - 1) % sampling_step == 0:
                                coordinates.append((x, y))
                                sampled_count += 1

                        except ValueError:
                            self.log_message(f"⚠️ 無効データをスキップ: 行{line_count}")
                    else:
                        if line.strip():
                            self.log_message(f"⚠️ 形式エラーをスキップ: 行{line_count}")

            self.log_message(f"📊 データ処理完了: {valid_count} 点中 {sampled_count} 点を使用")
            if sampling_step > 1:
                original_angle = 360.0 / valid_count if valid_count > 0 else 0
                actual_angle = 360.0 / sampled_count if sampled_count > 0 else 0
                self.log_message(f"📐 角度変更: {original_angle:.4f}° → {actual_angle:.4f}°")

            self.update_progress(70, "軌跡図作成中...")

            if coordinates:
                # 不進行座標轉換，保持原始軌跡
                self.log_message("📊 保持原始座標軌跡...")
                self.update_progress(75, "軌跡準備完成...")
                
                # 建立凸輪軌跡圖
                curve_type = self.output_types[self.selected_output_type.get()]
                self.log_message(f"🎨 使用曲線タイプ: {self.selected_output_type.get()}")

                success = self.create_curve_geometry(msp, coordinates, curve_type)
                if success:
                    self.log_message(f"✨ 軌跡図作成完了: {len(coordinates)} 点")
                    self.update_progress(80, "軌跡図作成完了...")

                # 自動添加基圓參考線（如果軌跡有變化）
                base_radius = self.add_center_circle_if_needed(msp, coordinates)
                
                # 添加第一座標點標記（直徑3mm圓圈）
                if start_angle != 0.0 or center_distance != 0.0:
                    self.add_first_point_marker(msp, coordinates, start_angle, center_distance)
                
                # 添加圓心標記
                # 計算適當的標記大小
                if coordinates:
                    x_coords = [coord[0] for coord in coordinates]
                    y_coords = [coord[1] for coord in coordinates]
                    max_range = max(max(x_coords) - min(x_coords), max(y_coords) - min(y_coords))
                    cross_size = max_range * 0.02  # 標記大小為圖形範圍的2%
                    circle_radius = max_range * 0.01  # 圓圈半徑為圖形範圍的1%
                else:
                    cross_size = 1.0
                    circle_radius = 0.5
                
                # 添加圓心標記（十字線）
                center_line_h = msp.add_line((-cross_size, 0), (cross_size, 0))  # 水平線
                center_line_v = msp.add_line((0, -cross_size), (0, cross_size))  # 垂直線
                center_circle = msp.add_circle((0, 0), circle_radius)
                
                # 設定圓心標記顏色
                center_line_h.dxf.color = 2  # 黃色
                center_line_v.dxf.color = 2  # 黃色  
                center_circle.dxf.color = 2  # 黃色
                
                self.log_message(f"📍 已添加圓心標記 (大小: {cross_size:.3f})")

                # 輪郭を閉じるか確認
                if len(coordinates) > 2 and curve_type != "spline":
                    first_point = coordinates[0]
                    last_point = coordinates[-1]

                    distance = ((first_point[0] - last_point[0])**2 + (first_point[1] - last_point[1])**2)**0.5
                    if distance > 1e-6:
                        response = messagebox.askyesno(
                            "軌跡を閉じる",
                            "始点と終点を結んで閉じた軌跡にしますか？"
                        )
                        if response:
                            msp.add_line(first_point, last_point)
                            self.log_message("🔗 軌跡を閉じました")
                elif curve_type == "spline":
                    self.log_message("🔄 スプライン曲線は自動的に閉じられました")

                # 軌跡図プレビューを表示
                self.log_message("📈 軌跡図プレビューを作成中...")
                self.draw_trajectory_preview(coordinates, curve_type)

                self.update_progress(90, "ファイル保存中...")

                # DXFファイルを保存
                output_file = self.output_file_path.get()
                doc.saveas(output_file)

                self.update_progress(100, "変換完了！")
                self.log_message("💾 ファイル保存完了！")
                self.log_message(f"📍 保存場所: {output_file}")
                self.log_message("🎉 軌跡図変換が正常に完了しました！")

                messagebox.showinfo("変換完了",
                                   f"軌跡図の変換が完了しました！\n\n"
                                   f"📁 保存場所:\n{output_file}\n\n"
                                   f"📊 使用点数: {len(coordinates)} 点\n"
                                   f"📐 角度設定: {self.selected_angle.get()}\n"
                                   f"🎨 曲線タイプ: {self.selected_output_type.get()}\n"
                                   f"🔧 起始角度: {start_angle:.2f}°\n"
                                   f"🔧 圓心距離: {center_distance:.4f}")

            else:
                error_msg = "有効な座標データが見つかりませんでした。"
                self.log_message(f"❌ {error_msg}")
                self.update_progress(0, "エラー発生")
                messagebox.showerror("データエラー", error_msg)

        except FileNotFoundError:
            error_msg = f"ファイルが見つかりません: {self.input_file_path.get()}"
            self.log_message(f"❌ {error_msg}")
            self.update_progress(0, "ファイルエラー")
            messagebox.showerror("ファイルエラー", error_msg)
        except Exception as e:
            error_msg = f"予期しないエラーが発生しました: {str(e)}"
            self.log_message(f"❌ {error_msg}")
            self.update_progress(0, "システムエラー")
            messagebox.showerror("システムエラー", error_msg)
        finally:
            # ボタンを有効化
            self.convert_btn.config(state='normal')

def main():
    root = tk.Tk()
    app = JapaneseStyleDXFConverter(root)

    # ウィンドウを中央に配置
    root.update_idletasks()
    width = root.winfo_width()
    height = root.winfo_height()
    x = (root.winfo_screenwidth() // 2) - (width // 2)
    y = (root.winfo_screenheight() // 2) - (height // 2)
    root.geometry(f'{width}x{height}+{x}+{y}')

    root.mainloop()

if __name__ == "__main__":
    main()
