import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import ezdxf
import os
import math
import statistics
from datetime import datetime

# 設定是否使用圖形預覽
USE_PREVIEW = True

try:
    if USE_PREVIEW:
        import matplotlib.pyplot as plt
        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
        from matplotlib.figure import Figure
        import numpy as np
        MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False
    USE_PREVIEW = False

class CoordinateValidator:
    def __init__(self, root):
        self.root = root
        self.root.title("座標驗證ツール - DXF軌跡図精度確認システム")
        self.root.geometry("1000x700")
        self.root.resizable(True, True)
        self.root.minsize(950, 650)

        # 日系配色テーマ
        self.colors = {
            'bg_primary': '#FAF9F9',
            'bg_secondary': '#FFFFFF',
            'bg_card': '#FFFFFF',
            'accent': '#555B6E',
            'accent_hover': '#444955',
            'secondary': '#89B0AE',
            'secondary_hover': '#7A9B99',
            'success': '#BEE3DB',
            'success_dark': '#A8D5CC',
            'warning': '#FFD6BA',
            'error': '#FFB3B3',
            'text_primary': '#2C2F33',
            'text_secondary': '#555B6E',
            'text_light': '#89B0AE',
            'border': '#E8E8E8',
            'border_focus': '#89B0AE'
        }

        # データ保存用変数
        self.original_coords = []
        self.dxf_coords = []
        self.comparison_results = {}
        self.validation_report = ""

        # ファイルパス変数
        self.txt_file_path = tk.StringVar()
        self.dxf_file_path = tk.StringVar()

        # 許容誤差設定
        self.tolerance_var = tk.DoubleVar(value=0.001)

        # 進度變數
        self.progress_var = tk.DoubleVar()
        self.progress_text = tk.StringVar(value="驗證準備完了")

        self.setup_styles()
        self.root.configure(bg=self.colors['bg_primary'])
        self.setup_ui()

    def setup_styles(self):
        """日系モダンスタイルを設定"""
        style = ttk.Style()
        style.theme_use('clam')

        # フォント設定
        header_font = ('BIZ UDPゴシック', 20, 'bold')
        title_font = ('BIZ UDPゴシック', 12, 'bold')
        label_font = ('BIZ UDPゴシック', 10, 'bold')
        text_font = ('BIZ UDPゴシック', 9)
        button_font = ('BIZ UDPゴシック', 10, 'bold')

        # カードスタイル
        style.configure('Card.TLabelframe',
                       background=self.colors['bg_card'],
                       relief='flat',
                       borderwidth=1)

        # プライマリボタン
        style.configure('Primary.TButton',
                       background=self.colors['accent'],
                       foreground='white',
                       borderwidth=0,
                       font=button_font,
                       padding=(15, 8))

        # セカンダリボタン
        style.configure('Secondary.TButton',
                       background=self.colors['secondary'],
                       foreground='white',
                       borderwidth=0,
                       font=button_font,
                       padding=(15, 8))

        # 成功ボタン
        style.configure('Success.TButton',
                       background=self.colors['success_dark'],
                       foreground=self.colors['text_primary'],
                       borderwidth=0,
                       font=('BIZ UDPゴシック', 12, 'bold'),
                       padding=(20, 10))

        # エントリー
        style.configure('Modern.TEntry',
                       fieldbackground='white',
                       borderwidth=2,
                       relief='solid',
                       bordercolor=self.colors['border'],
                       padding=8,
                       font=text_font)

        # プログレスバー
        style.configure('Modern.Horizontal.TProgressbar',
                       background=self.colors['success_dark'],
                       troughcolor=self.colors['border'],
                       borderwidth=0,
                       thickness=12)

    def configure_matplotlib_fonts(self):
        """matplotlib の日本語フォント設定"""
        if not MATPLOTLIB_AVAILABLE:
            return

        try:
            import matplotlib.pyplot as plt
            import matplotlib as mpl
            from matplotlib import font_manager

            # 日本語フォントの候補リスト
            japanese_fonts = [
                'BIZ UDPゴシック',
                'Yu Gothic',
                'Meiryo',
                'MS Gothic',
                'Hiragino Sans',
                'Noto Sans CJK JP',
                'IPAexGothic',
                'TakaoGothic',
                'DejaVu Sans'
            ]

            # 利用可能なフォントを検索
            available_fonts = [f.name for f in font_manager.fontManager.ttflist]
            selected_font = None

            for font in japanese_fonts:
                if font in available_fonts:
                    selected_font = font
                    break

            # フォント設定を適用
            if selected_font:
                plt.rcParams['font.family'] = selected_font
                mpl.rcParams['font.family'] = selected_font
            else:
                # フォールバック設定
                plt.rcParams['font.family'] = 'DejaVu Sans'
                mpl.rcParams['font.family'] = 'DejaVu Sans'

            # 日本語文字の負号表示問題を解決
            plt.rcParams['axes.unicode_minus'] = False
            mpl.rcParams['axes.unicode_minus'] = False

            return selected_font

        except Exception as e:
            print(f"フォント設定エラー: {e}")
            return None

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
        main_container.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        # ヘッダー
        self.create_header(main_container)

        # メインコンテンツエリア
        content_frame = tk.Frame(main_container, bg=self.colors['bg_primary'])
        content_frame.pack(fill=tk.BOTH, expand=True, pady=(15, 0))

        # 左側コラム（設定とコントロール）
        left_column = tk.Frame(content_frame, bg=self.colors['bg_primary'])
        left_column.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
        left_column.config(width=400)

        # 右側コラム（結果表示）
        right_column = tk.Frame(content_frame, bg=self.colors['bg_primary'])
        right_column.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(10, 0))

        # 左側コンテンツ
        self.create_file_selection_section(left_column)
        self.create_settings_section(left_column)
        self.create_control_section(left_column)
        self.create_progress_section(left_column)

        # 右側コンテンツ
        self.create_results_section(right_column)
        if USE_PREVIEW and MATPLOTLIB_AVAILABLE:
            self.create_visualization_section(right_column)

    def configure_matplotlib_fonts(self):
        """matplotlib の日本語フォント設定"""
        if not MATPLOTLIB_AVAILABLE:
            return

        try:
            import matplotlib.pyplot as plt
            import matplotlib as mpl
            from matplotlib import font_manager

            # 日本語フォントの候補リスト
            japanese_fonts = [
                'BIZ UDPゴシック',
                'Yu Gothic',
                'Meiryo',
                'MS Gothic',
                'Hiragino Sans',
                'Noto Sans CJK JP',
                'IPAexGothic',
                'TakaoGothic',
                'DejaVu Sans'
            ]

            # 利用可能なフォントを検索
            available_fonts = [f.name for f in font_manager.fontManager.ttflist]
            selected_font = None

            for font in japanese_fonts:
                if font in available_fonts:
                    selected_font = font
                    break

            # フォント設定を適用
            if selected_font:
                plt.rcParams['font.family'] = selected_font
                mpl.rcParams['font.family'] = selected_font
            else:
                # フォールバック設定
                plt.rcParams['font.family'] = 'DejaVu Sans'
                mpl.rcParams['font.family'] = 'DejaVu Sans'

            # 日本語文字の負号表示問題を解決
            plt.rcParams['axes.unicode_minus'] = False
            mpl.rcParams['axes.unicode_minus'] = False

            return selected_font

        except Exception as e:
            print(f"フォント設定エラー: {e}")
            return None

    def create_header(self, parent):
        """ヘッダーセクション"""
        header_frame = self.create_rounded_frame(parent)
        header_frame.pack(fill=tk.X, pady=(0, 15))

        title_container = tk.Frame(header_frame, bg=self.colors['bg_card'])
        title_container.pack(pady=20)

        # アイコンとタイトル
        icon_label = tk.Label(title_container,
                             text="🔍",
                             font=('BIZ UDPゴシック', 28),
                             bg=self.colors['bg_card'],
                             fg=self.colors['accent'])
        icon_label.pack()

        title_label = tk.Label(title_container,
                              text="座標驗證ツール",
                              font=('BIZ UDPゴシック', 18, 'bold'),
                              fg=self.colors['text_primary'],
                              bg=self.colors['bg_card'])
        title_label.pack(pady=(8, 3))

        subtitle_label = tk.Label(title_container,
                                 text="DXF軌跡図と元座標の精度を詳細比較・分析",
                                 font=('BIZ UDPゴシック', 10),
                                 fg=self.colors['text_secondary'],
                                 bg=self.colors['bg_card'])
        subtitle_label.pack()

    def create_file_selection_section(self, parent):
        """ファイル選択セクション"""
        file_card = self.create_rounded_frame(parent)
        file_card.pack(fill=tk.X, pady=(0, 15))

        # セクションタイトル
        title_frame = tk.Frame(file_card, bg=self.colors['bg_card'])
        title_frame.pack(fill=tk.X, padx=20, pady=(15, 10))

        tk.Label(title_frame,
                text="📁 比較ファイル選択",
                font=('BIZ UDPゴシック', 12, 'bold'),
                fg=self.colors['text_primary'],
                bg=self.colors['bg_card']).pack(anchor=tk.W)

        # 元座標ファイル選択
        txt_frame = tk.Frame(file_card, bg=self.colors['bg_card'])
        txt_frame.pack(fill=tk.X, padx=20, pady=(0, 10))
        txt_frame.columnconfigure(0, weight=1)

        tk.Label(txt_frame,
                text="元座標ファイル (.txt/.csv):",
                font=('BIZ UDPゴシック', 9, 'bold'),
                fg=self.colors['text_primary'],
                bg=self.colors['bg_card']).grid(row=0, column=0, sticky=tk.W, pady=(0, 5))

        entry_frame1 = tk.Frame(txt_frame, bg=self.colors['bg_card'])
        entry_frame1.grid(row=1, column=0, sticky=(tk.W, tk.E), columnspan=2)
        entry_frame1.columnconfigure(0, weight=1)

        self.txt_entry = ttk.Entry(entry_frame1,
                                  textvariable=self.txt_file_path,
                                  state="readonly",
                                  style='Modern.TEntry')
        self.txt_entry.grid(row=0, column=0, sticky=(tk.W, tk.E), padx=(0, 10))

        ttk.Button(entry_frame1,
                  text="選択",
                  command=self.select_txt_file,
                  style='Secondary.TButton').grid(row=0, column=1)

        # DXFファイル選択
        dxf_frame = tk.Frame(file_card, bg=self.colors['bg_card'])
        dxf_frame.pack(fill=tk.X, padx=20, pady=(0, 15))
        dxf_frame.columnconfigure(0, weight=1)

        tk.Label(dxf_frame,
                text="DXFファイル:",
                font=('BIZ UDPゴシック', 9, 'bold'),
                fg=self.colors['text_primary'],
                bg=self.colors['bg_card']).grid(row=0, column=0, sticky=tk.W, pady=(0, 5))

        entry_frame2 = tk.Frame(dxf_frame, bg=self.colors['bg_card'])
        entry_frame2.grid(row=1, column=0, sticky=(tk.W, tk.E), columnspan=2)
        entry_frame2.columnconfigure(0, weight=1)

        self.dxf_entry = ttk.Entry(entry_frame2,
                                  textvariable=self.dxf_file_path,
                                  state="readonly",
                                  style='Modern.TEntry')
        self.dxf_entry.grid(row=0, column=0, sticky=(tk.W, tk.E), padx=(0, 10))

        ttk.Button(entry_frame2,
                  text="選択",
                  command=self.select_dxf_file,
                  style='Secondary.TButton').grid(row=0, column=1)

    def create_settings_section(self, parent):
        """設定セクション"""
        settings_card = self.create_rounded_frame(parent)
        settings_card.pack(fill=tk.X, pady=(0, 15))

        # セクションタイトル
        title_frame = tk.Frame(settings_card, bg=self.colors['bg_card'])
        title_frame.pack(fill=tk.X, padx=20, pady=(15, 10))

        tk.Label(title_frame,
                text="⚙️ 驗證設定",
                font=('BIZ UDPゴシック', 12, 'bold'),
                fg=self.colors['text_primary'],
                bg=self.colors['bg_card']).pack(anchor=tk.W)

        # 許容誤差設定
        tolerance_frame = tk.Frame(settings_card, bg=self.colors['bg_card'])
        tolerance_frame.pack(fill=tk.X, padx=20, pady=(0, 15))

        tk.Label(tolerance_frame,
                text="許容誤差:",
                font=('BIZ UDPゴシック', 9, 'bold'),
                fg=self.colors['text_primary'],
                bg=self.colors['bg_card']).pack(anchor=tk.W, pady=(0, 5))

        tolerance_input_frame = tk.Frame(tolerance_frame, bg=self.colors['bg_card'])
        tolerance_input_frame.pack(fill=tk.X)

        self.tolerance_entry = ttk.Entry(tolerance_input_frame,
                                        textvariable=self.tolerance_var,
                                        style='Modern.TEntry',
                                        width=15)
        self.tolerance_entry.pack(side=tk.LEFT)

        tk.Label(tolerance_input_frame,
                text="(単位: mm)",
                font=('BIZ UDPゴシック', 8),
                fg=self.colors['text_light'],
                bg=self.colors['bg_card']).pack(side=tk.LEFT, padx=(10, 0))

    def create_control_section(self, parent):
        """コントロールセクション"""
        control_frame = tk.Frame(parent, bg=self.colors['bg_primary'])
        control_frame.pack(fill=tk.X, pady=(10, 0))

        button_container = tk.Frame(control_frame, bg=self.colors['bg_primary'])
        button_container.pack()

        # 検証実行ボタン
        self.validate_btn = ttk.Button(button_container,
                                      text="🔍 座標驗證實行",
                                      command=self.run_validation,
                                      style='Success.TButton')
        self.validate_btn.pack(side=tk.LEFT, padx=(0, 10))

        # クリアボタン
        ttk.Button(button_container,
                  text="🗑 クリア",
                  command=self.clear_all,
                  style='Primary.TButton').pack(side=tk.LEFT)

    def create_progress_section(self, parent):
        """進度セクション"""
        progress_card = self.create_rounded_frame(parent)
        progress_card.pack(fill=tk.X, pady=(15, 0))

        # セクションタイトル
        title_frame = tk.Frame(progress_card, bg=self.colors['bg_card'])
        title_frame.pack(fill=tk.X, padx=20, pady=(15, 10))

        tk.Label(title_frame,
                text="📊 進行状況",
                font=('BIZ UDPゴシック', 12, 'bold'),
                fg=self.colors['text_primary'],
                bg=self.colors['bg_card']).pack(anchor=tk.W)

        # 進度内容
        progress_content = tk.Frame(progress_card, bg=self.colors['bg_card'])
        progress_content.pack(fill=tk.X, padx=20, pady=(0, 15))

        self.progress_text_label = tk.Label(progress_content,
                                           textvariable=self.progress_text,
                                           font=('BIZ UDPゴシック', 9),
                                           fg=self.colors['text_primary'],
                                           bg=self.colors['bg_card'])
        self.progress_text_label.pack(anchor=tk.W, pady=(0, 8))

        self.progress_bar = ttk.Progressbar(progress_content,
                                           style='Modern.Horizontal.TProgressbar',
                                           length=200,
                                           variable=self.progress_var)
        self.progress_bar.pack(fill=tk.X)

    def create_results_section(self, parent):
        """結果表示セクション"""
        results_card = self.create_rounded_frame(parent)
        results_card.pack(fill=tk.BOTH, expand=True, pady=(0, 15))

        # セクションタイトル
        title_frame = tk.Frame(results_card, bg=self.colors['bg_card'])
        title_frame.pack(fill=tk.X, padx=20, pady=(15, 10))

        title_label = tk.Label(title_frame,
                              text="📋 驗證結果詳細",
                              font=('BIZ UDPゴシック', 12, 'bold'),
                              fg=self.colors['text_primary'],
                              bg=self.colors['bg_card'])
        title_label.pack(side=tk.LEFT)

        # エクスポートボタン
        ttk.Button(title_frame,
                  text="📄 レポート出力",
                  command=self.export_report,
                  style='Secondary.TButton').pack(side=tk.RIGHT)

        # 結果表示エリア
        results_container = tk.Frame(results_card, bg=self.colors['bg_card'])
        results_container.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 15))
        results_container.columnconfigure(0, weight=1)

        self.results_text = tk.Text(results_container,
                                   wrap=tk.WORD,
                                   bg='#FAFAFA',
                                   fg=self.colors['text_primary'],
                                   font=('BIZ UDPゴシック', 9),
                                   relief='flat',
                                   borderwidth=2,
                                   highlightthickness=1,
                                   highlightcolor=self.colors['border_focus'],
                                   highlightbackground=self.colors['border'],
                                   padx=15,
                                   pady=15)

        results_scrollbar = ttk.Scrollbar(results_container,
                                         orient=tk.VERTICAL,
                                         command=self.results_text.yview)
        self.results_text.configure(yscrollcommand=results_scrollbar.set)

        self.results_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(0, 5))
        results_scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        results_container.rowconfigure(0, weight=1)

        # 初期メッセージ
        self.display_initial_message()

    def create_visualization_section(self, parent):
        """視覚化セクション"""
        viz_card = self.create_rounded_frame(parent)
        viz_card.pack(fill=tk.BOTH, expand=True)

        # セクションタイトル
        title_frame = tk.Frame(viz_card, bg=self.colors['bg_card'])
        title_frame.pack(fill=tk.X, padx=20, pady=(15, 10))

        tk.Label(title_frame,
                text="📊 座標比較視覚化",
                font=('BIZ UDPゴシック', 12, 'bold'),
                fg=self.colors['text_primary'],
                bg=self.colors['bg_card']).pack(anchor=tk.W)

        # 視覚化エリア
        self.viz_frame = tk.Frame(viz_card, bg=self.colors['bg_card'])
        self.viz_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 15))

        # 初期メッセージ
        self.viz_label = tk.Label(self.viz_frame,
                                 text="驗證実行後に比較グラフが表示されます",
                                 font=('BIZ UDPゴシック', 10),
                                 fg=self.colors['text_secondary'],
                                 bg=self.colors['bg_card'])
        self.viz_label.pack(expand=True)

        # matplotlib用変数
        self.viz_canvas = None
        self.viz_figure = None

    def display_initial_message(self):
        """初期メッセージを表示"""
        initial_msg = """🔍 座標驗證ツールへようこそ

📋 使用手順:
1. 元の座標ファイル(.txt/.csv)を選択
2. 生成されたDXFファイルを選択
3. 許容誤差を設定 (デフォルト: 0.001mm)
4. 「座標驗證實行」ボタンをクリック

🎯 検証内容:
• 座標点数の比較
• 各点の位置精度チェック
• 誤差統計分析
• 軌跡形状の整合性確認

📊 結果出力:
• 詳細な比較レポート
• 誤差分布の統計
• 視覚的な座標比較図
• エクスポート可能なレポート

💡 ファイルを選択して検証を開始してください。"""

        self.results_text.insert(tk.END, initial_msg)
        self.results_text.config(state='disabled')

    def select_txt_file(self):
        """元座標ファイルを選択"""
        file_path = filedialog.askopenfilename(
            title="元座標ファイルを選択",
            filetypes=[
                ("テキストファイル", "*.txt"),
                ("CSVファイル", "*.csv"),
                ("すべてのファイル", "*.*")
            ]
        )
        if file_path:
            self.txt_file_path.set(file_path)
            self.update_progress(10, f"元ファイル選択: {os.path.basename(file_path)}")

    def select_dxf_file(self):
        """DXFファイルを選択"""
        file_path = filedialog.askopenfilename(
            title="DXFファイルを選択",
            filetypes=[
                ("DXFファイル", "*.dxf"),
                ("すべてのファイル", "*.*")
            ]
        )
        if file_path:
            self.dxf_file_path.set(file_path)
            self.update_progress(20, f"DXFファイル選択: {os.path.basename(file_path)}")

    def update_progress(self, value, text):
        """進度を更新"""
        self.progress_var.set(value)
        self.progress_text.set(text)
        self.root.update()

    def read_txt_coordinates(self, file_path):
        """元座標ファイルを読み取り"""
        coordinates = []
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                lines = file.readlines()
                for line_num, line in enumerate(lines, 1):
                    parts = line.strip().split(',')
                    if len(parts) == 2:
                        try:
                            x = float(parts[0].strip())
                            y = float(parts[1].strip())
                            coordinates.append((x, y))
                        except ValueError:
                            continue
            return coordinates
        except Exception as e:
            raise Exception(f"元座標ファイル読み取りエラー: {str(e)}")

    def read_dxf_coordinates(self, file_path):
        """DXFファイルから座標を抽出"""
        coordinates = []
        entity_count = 0

        try:
            doc = ezdxf.readfile(file_path)
            msp = doc.modelspace()

            # デバッグ情報：DXFファイル内のエンティティをログ出力
            all_entities = list(msp)
            self.update_progress(55, f"DXF解析中...{len(all_entities)}個のエンティティを発見")

            for entity in all_entities:
                entity_count += 1
                entity_type = entity.dxftype()

                try:
                    if entity_type == 'LWPOLYLINE':
                        points = list(entity.get_points())
                        for point in points:
                            coordinates.append((float(point[0]), float(point[1])))

                    elif entity_type == 'POLYLINE':
                        if hasattr(entity, 'vertices'):
                            for vertex in entity.vertices:
                                loc = vertex.dxf.location
                                coordinates.append((float(loc[0]), float(loc[1])))

                    elif entity_type == 'SPLINE':
                        # スプライン曲線の座標抽出（複数の方法を試行）
                        spline_points = []

                        # 方法1: control_pointsを取得
                        try:
                            if hasattr(entity, 'control_points') and entity.control_points:
                                for point in entity.control_points:
                                    spline_points.append((float(point[0]), float(point[1])))
                        except Exception:
                            pass

                        # 方法2: fit_pointsを取得
                        if not spline_points:
                            try:
                                if hasattr(entity, 'fit_points') and entity.fit_points:
                                    for point in entity.fit_points:
                                        spline_points.append((float(point[0]), float(point[1])))
                            except Exception:
                                pass

                        # 方法3: DXF属性から直接取得
                        if not spline_points:
                            try:
                                # スプライン曲線を近似ポイントで表現
                                if hasattr(entity, 'construction_tool'):
                                    # ezdxfの新しいバージョンで利用可能な方法
                                    spline_points = entity.construction_tool().control_points
                                    spline_points = [(float(p[0]), float(p[1])) for p in spline_points]
                            except Exception:
                                pass

                        # 方法4: スプライン曲線をサンプルポイントで近似
                        if not spline_points:
                            try:
                                # スプライン曲線を等間隔で100点にサンプリング
                                from ezdxf.math import BSpline
                                if hasattr(entity.dxf, 'control_points'):
                                    control_points = entity.dxf.control_points
                                    if control_points:
                                        # BSplineオブジェクトを作成してサンプリング
                                        degree = getattr(entity.dxf, 'degree', 3)
                                        bspline = BSpline(control_points, order=degree+1)

                                        # 100点でサンプリング
                                        for i in range(101):
                                            t = i / 100.0
                                            point = bspline.point(t)
                                            spline_points.append((float(point[0]), float(point[1])))
                            except Exception:
                                pass

                        # 方法5: 最後の手段 - DXF生データから読み取り
                        if not spline_points:
                            try:
                                # 制御点の座標を直接読み取り
                                dxf_data = entity.dxf
                                for attr_name in dir(dxf_data):
                                    if 'control' in attr_name.lower() or 'point' in attr_name.lower():
                                        attr_value = getattr(dxf_data, attr_name, None)
                                        if attr_value and hasattr(attr_value, '__iter__'):
                                            try:
                                                for item in attr_value:
                                                    if hasattr(item, '__len__') and len(item) >= 2:
                                                        spline_points.append((float(item[0]), float(item[1])))
                                            except:
                                                continue
                            except Exception:
                                pass

                        if spline_points:
                            coordinates.extend(spline_points)
                        else:
                            # SPLINEから座標を取得できない場合の警告
                            print(f"SPLINE entity から座標を抽出できませんでした")
                            # SPLINEの詳細情報をログ出力
                            try:
                                attrs = [attr for attr in dir(entity.dxf) if not attr.startswith('_')]
                                print(f"SPLINE attributes: {attrs}")
                            except:
                                pass

                    elif entity_type == 'LINE':
                        start = entity.dxf.start
                        end = entity.dxf.end
                        coordinates.extend([
                            (float(start[0]), float(start[1])),
                            (float(end[0]), float(end[1]))
                        ])

                    elif entity_type == 'ARC':
                        # 円弧の場合、サンプルポイントを生成
                        center = entity.dxf.center
                        radius = entity.dxf.radius
                        start_angle = math.radians(entity.dxf.start_angle)
                        end_angle = math.radians(entity.dxf.end_angle)

                        # 円弧を20個のポイントに分割
                        num_points = 20
                        for i in range(num_points + 1):
                            angle = start_angle + (end_angle - start_angle) * i / num_points
                            x = center[0] + radius * math.cos(angle)
                            y = center[1] + radius * math.sin(angle)
                            coordinates.append((float(x), float(y)))

                    elif entity_type == 'CIRCLE':
                        # 円の場合、サンプルポイントを生成
                        center = entity.dxf.center
                        radius = entity.dxf.radius

                        # 円を36個のポイントに分割
                        num_points = 36
                        for i in range(num_points):
                            angle = 2 * math.pi * i / num_points
                            x = center[0] + radius * math.cos(angle)
                            y = center[1] + radius * math.sin(angle)
                            coordinates.append((float(x), float(y)))

                    elif entity_type == 'POINT':
                        # 点エンティティ
                        loc = entity.dxf.location
                        coordinates.append((float(loc[0]), float(loc[1])))

                except Exception as entity_error:
                    # 個別エンティティのエラーは継続
                    print(f"エンティティ {entity_type} 処理エラー: {entity_error}")
                    continue

            # 重複座標を除去
            if coordinates:
                unique_coords = []
                for coord in coordinates:
                    if not any(abs(coord[0] - existing[0]) < 1e-10 and
                             abs(coord[1] - existing[1]) < 1e-10 for existing in unique_coords):
                        unique_coords.append(coord)
                coordinates = unique_coords

            self.update_progress(65, f"座標抽出完了: {len(coordinates)}点")

            if not coordinates:
                # エンティティ情報をレポート
                entity_types = {}
                for entity in all_entities:
                    etype = entity.dxftype()
                    entity_types[etype] = entity_types.get(etype, 0) + 1

                type_list = ', '.join([f"{k}:{v}" for k, v in entity_types.items()])
                raise Exception(f"座標データが見つかりません。検出されたエンティティタイプ: {type_list}")

            return coordinates

        except Exception as e:
            raise Exception(f"DXFファイル読み取りエラー: {str(e)}")

    def calculate_distance(self, point1, point2):
        """2点間の距離を計算"""
        return math.sqrt((point1[0] - point2[0])**2 + (point1[1] - point2[1])**2)

    def find_nearest_point(self, target_point, point_list):
        """最近隣点を検索"""
        if not point_list:
            return None, float('inf')

        min_distance = float('inf')
        nearest_point = None

        for point in point_list:
            distance = self.calculate_distance(target_point, point)
            if distance < min_distance:
                min_distance = distance
                nearest_point = point

        return nearest_point, min_distance

    def analyze_coordinates(self):
        """座標の詳細分析"""
        tolerance = self.tolerance_var.get()

        analysis_results = {
            'txt_count': len(self.original_coords),
            'dxf_count': len(self.dxf_coords),
            'matches': 0,
            'errors': [],
            'distances': [],
            'max_error': 0,
            'min_error': float('inf'),
            'avg_error': 0,
            'within_tolerance': 0,
            'accuracy_percentage': 0
        }

        # 各元座標について最近隣DXF座標を検索
        for i, orig_point in enumerate(self.original_coords):
            nearest_dxf, distance = self.find_nearest_point(orig_point, self.dxf_coords)

            # 確保distance是float類型
            distance = float(distance)
            analysis_results['distances'].append(distance)

            if distance <= tolerance:
                analysis_results['within_tolerance'] += 1

            if distance > analysis_results['max_error']:
                analysis_results['max_error'] = distance

            if distance < analysis_results['min_error']:
                analysis_results['min_error'] = distance

            if distance > tolerance:
                analysis_results['errors'].append({
                    'index': i,
                    'original': orig_point,
                    'nearest_dxf': nearest_dxf,
                    'distance': distance
                })

        # 統計計算（使用安全的方法）
        if analysis_results['distances']:
            # 確保所有數值都是float類型
            distances = [float(d) for d in analysis_results['distances']]
            analysis_results['avg_error'] = sum(distances) / len(distances)
            analysis_results['accuracy_percentage'] = (analysis_results['within_tolerance'] / len(self.original_coords)) * 100

        return analysis_results

    def generate_validation_report(self, results):
        """驗證レポートを生成"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        tolerance = self.tolerance_var.get()

        report = f"""
═══════════════════════════════════════════════════
🔍 座標驗證レポート
═══════════════════════════════════════════════════
📅 検証実行日時: {timestamp}
📁 元座標ファイル: {os.path.basename(self.txt_file_path.get())}
📁 DXFファイル: {os.path.basename(self.dxf_file_path.get())}
📏 許容誤差: {tolerance} mm

📊 基本統計:
▪ 元座標点数: {results['txt_count']} 点
▪ DXF座標点数: {results['dxf_count']} 点
▪ 点数差: {abs(results['txt_count'] - results['dxf_count'])} 点

🎯 精度分析:
▪ 許容範囲内の点: {results['within_tolerance']} 点
▪ 精度: {results['accuracy_percentage']:.2f}%
▪ 最大誤差: {results['max_error']:.6f} mm
▪ 最小誤差: {results['min_error']:.6f} mm
▪ 平均誤差: {results['avg_error']:.6f} mm

"""

        if results['distances']:
            # 標準偏差計算（安全版本）
            try:
                if len(results['distances']) > 1:
                    # 手動計算標準偏差，避免statistics.stdev的類型問題
                    distances = [float(d) for d in results['distances']]
                    mean_val = sum(distances) / len(distances)
                    variance = sum((x - mean_val) ** 2 for x in distances) / (len(distances) - 1)
                    std_dev = math.sqrt(variance)
                else:
                    std_dev = 0
                report += f"▪ 誤差標準偏差: {std_dev:.6f} mm\n"
            except Exception as e:
                report += f"▪ 誤差標準偏差: 計算エラー\n"

        # 誤差分布
        error_ranges = [0.001, 0.01, 0.1, 1.0]
        report += "\n📈 誤差分布:\n"

        for i, threshold in enumerate(error_ranges):
            count = sum(1 for d in results['distances'] if d <= threshold)
            percentage = (count / len(results['distances'])) * 100 if results['distances'] else 0
            report += f"▪ {threshold} mm以下: {count} 点 ({percentage:.1f}%)\n"

        # エラーの詳細
        if results['errors']:
            report += f"\n❌ 許容範囲外の座標 ({len(results['errors'])} 点):\n"

            # 最大5個のエラーを表示
            for error in results['errors'][:5]:
                report += f"▪ 点{error['index']+1}: 誤差 {error['distance']:.6f} mm\n"
                report += f"  元座標: ({error['original'][0]:.6f}, {error['original'][1]:.6f})\n"
                if error['nearest_dxf']:
                    report += f"  DXF座標: ({error['nearest_dxf'][0]:.6f}, {error['nearest_dxf'][1]:.6f})\n"
                report += "\n"

            if len(results['errors']) > 5:
                report += f"... 他 {len(results['errors'])-5} 件のエラー\n"
        else:
            report += "\n✅ すべての座標が許容範囲内です！\n"

        # 総合評価
        report += "\n🏆 総合評価:\n"
        if results['accuracy_percentage'] >= 99:
            report += "▪ 評価: 優秀 - DXF軌跡は元座標を高精度で再現しています\n"
        elif results['accuracy_percentage'] >= 95:
            report += "▪ 評価: 良好 - 一般的な用途には十分な精度です\n"
        elif results['accuracy_percentage'] >= 90:
            report += "▪ 評価: 普通 - 用途によっては改善が必要かもしれません\n"
        else:
            report += "▪ 評価: 要改善 - DXF変換設定の見直しをお勧めします\n"

        report += "\n" + "="*55

        return report

    def create_visualization(self):
        """座標比較の視覚化"""
        if not (USE_PREVIEW and MATPLOTLIB_AVAILABLE):
            return

        try:
            # 日本語フォント設定
            selected_font = self.configure_matplotlib_fonts()

            # 既存のキャンバスを削除
            if self.viz_canvas:
                self.viz_canvas.get_tk_widget().destroy()

            if hasattr(self, 'viz_label'):
                self.viz_label.pack_forget()

            # データの有効性をチェック
            if not self.original_coords and not self.dxf_coords:
                self.show_visualization_message("座標データがありません")
                return

            if not self.dxf_coords:
                self.show_visualization_message("DXFファイルから座標が読み取れませんでした")
                return

            # 新しい図を作成
            self.viz_figure = Figure(figsize=(8, 6), dpi=80, facecolor='white')

            # 2つのサブプロット
            ax1 = self.viz_figure.add_subplot(121)
            ax2 = self.viz_figure.add_subplot(122)

            # 座標データを準備（型安全性を確保）
            plot_created = False

            if self.original_coords:
                orig_x = [float(p[0]) for p in self.original_coords]
                orig_y = [float(p[1]) for p in self.original_coords]

                # データの有効性をチェック
                if all(math.isfinite(x) for x in orig_x) and all(math.isfinite(y) for y in orig_y):
                    ax1.plot(orig_x, orig_y, 'bo-', markersize=3, linewidth=1,
                            alpha=0.7, label=f'元座標 ({len(self.original_coords)}点)')
                    plot_created = True

            if self.dxf_coords:
                dxf_x = [float(p[0]) for p in self.dxf_coords]
                dxf_y = [float(p[1]) for p in self.dxf_coords]

                # データの有効性をチェック
                if all(math.isfinite(x) for x in dxf_x) and all(math.isfinite(y) for y in dxf_y):
                    ax1.plot(dxf_x, dxf_y, 'r^-', markersize=3, linewidth=1,
                            alpha=0.7, label=f'DXF座標 ({len(self.dxf_coords)}点)')
                    plot_created = True

            if plot_created:
                ax1.set_title('座標重ね合わせ比較', fontsize=11, fontweight='bold')
                ax1.set_xlabel('X座標 (mm)', fontsize=10)
                ax1.set_ylabel('Y座標 (mm)', fontsize=10)
                ax1.grid(True, alpha=0.3)
                ax1.legend(fontsize=9)

                # 軸の範囲を安全に設定
                try:
                    ax1.set_aspect('equal', adjustable='box')
                except:
                    # aspect設定が失敗した場合はスキップ
                    pass
            else:
                ax1.text(0.5, 0.5, '有効な座標データがありません',
                        ha='center', va='center', transform=ax1.transAxes, fontsize=10)
                ax1.set_title('座標比較（データなし）', fontsize=11)

            # 右側: 誤差分布ヒストグラム
            histogram_created = False

            if (self.comparison_results and
                self.comparison_results.get('distances') and
                len(self.comparison_results['distances']) > 0):

                # 距離データを浮点数に変換し、有効な値のみを使用
                distances = [float(d) for d in self.comparison_results['distances']]
                valid_distances = [d for d in distances if math.isfinite(d)]

                if valid_distances:
                    # ヒストグラムのbins数を安全に計算
                    num_bins = min(20, max(5, len(valid_distances)//3 + 1))

                    ax2.hist(valid_distances, bins=num_bins, alpha=0.7, color='skyblue', edgecolor='black')

                    tolerance = float(self.tolerance_var.get())
                    if math.isfinite(tolerance) and tolerance > 0:
                        ax2.axvline(tolerance, color='red', linestyle='--',
                                   label=f'許容誤差: {tolerance} mm', linewidth=2)

                    ax2.set_title('誤差分布', fontsize=11, fontweight='bold')
                    ax2.set_xlabel('誤差 (mm)', fontsize=10)
                    ax2.set_ylabel('頻度', fontsize=10)
                    ax2.grid(True, alpha=0.3)
                    ax2.legend(fontsize=9)
                    histogram_created = True

            if not histogram_created:
                ax2.text(0.5, 0.5, '誤差データがありません',
                        ha='center', va='center', transform=ax2.transAxes, fontsize=10)
                ax2.set_title('誤差分布（データなし）', fontsize=11)

            # 図全体のレイアウト調整
            self.viz_figure.suptitle('座標驗證結果の視覚化', fontsize=13, fontweight='bold', y=0.95)
            self.viz_figure.tight_layout(rect=[0, 0, 1, 0.92])

            # キャンバスを作成
            self.viz_canvas = FigureCanvasTkAgg(self.viz_figure, self.viz_frame)
            self.viz_canvas.draw()
            self.viz_canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        except Exception as e:
            # エラーが発生した場合はエラーメッセージを表示
            self.show_visualization_error(f"視覚化エラー: {str(e)}")

    def show_visualization_message(self, message):
        """視覚化エリアにメッセージを表示"""
        if hasattr(self, 'viz_label'):
            self.viz_label.pack_forget()

        msg_label = tk.Label(self.viz_frame,
                            text=message,
                            font=('BIZ UDPゴシック', 10),
                            fg=self.colors['text_secondary'],
                            bg=self.colors['bg_card'])
        msg_label.pack(expand=True)

    def show_visualization_error(self, error_message):
        """視覚化エラーを表示"""
        if hasattr(self, 'viz_label'):
            self.viz_label.pack_forget()

        error_label = tk.Label(self.viz_frame,
                              text=error_message,
                              font=('BIZ UDPゴシック', 10),
                              fg=self.colors['error'],
                              bg=self.colors['bg_card'])
        error_label.pack(expand=True)

    def run_validation(self):
        """驗證を実行"""
        # 入力チェック
        if not self.txt_file_path.get():
            messagebox.showerror("エラー", "元座標ファイルを選択してください！")
            return

        if not self.dxf_file_path.get():
            messagebox.showerror("エラー", "DXFファイルを選択してください！")
            return

        # ボタンを無効化
        self.validate_btn.config(state='disabled')

        try:
            self.update_progress(30, "元座標ファイル読み取り中...")
            self.original_coords = self.read_txt_coordinates(self.txt_file_path.get())

            self.update_progress(50, "DXFファイル解析中...")
            self.dxf_coords = self.read_dxf_coordinates(self.dxf_file_path.get())

            self.update_progress(70, "座標比較分析中...")
            self.comparison_results = self.analyze_coordinates()

            self.update_progress(85, "レポート生成中...")
            self.validation_report = self.generate_validation_report(self.comparison_results)

            # 結果を表示
            self.results_text.config(state='normal')
            self.results_text.delete(1.0, tk.END)
            self.results_text.insert(tk.END, self.validation_report)
            self.results_text.config(state='disabled')

            self.update_progress(95, "視覚化作成中...")
            if USE_PREVIEW and MATPLOTLIB_AVAILABLE:
                self.create_visualization()

            self.update_progress(100, "驗證完了！")

            # 結果サマリーをメッセージボックスで表示
            accuracy = self.comparison_results['accuracy_percentage']
            messagebox.showinfo("驗證完了",
                               f"座標驗證が完了しました！\n\n"
                               f"📊 精度: {accuracy:.2f}%\n"
                               f"📏 平均誤差: {self.comparison_results['avg_error']:.6f} mm\n"
                               f"📈 許容範囲内: {self.comparison_results['within_tolerance']}/{self.comparison_results['txt_count']} 点\n\n"
                               f"詳細結果は右側のパネルをご確認ください。")

        except Exception as e:
            error_msg = f"驗證エラー: {str(e)}"
            self.update_progress(0, "エラー発生")
            messagebox.showerror("驗證エラー", error_msg)

            # エラーメッセージを結果エリアに表示
            self.results_text.config(state='normal')
            self.results_text.delete(1.0, tk.END)
            self.results_text.insert(tk.END, f"❌ {error_msg}\n\n")
            self.results_text.insert(tk.END, "📋 確認事項:\n")
            self.results_text.insert(tk.END, "• ファイルが正しく選択されているか\n")
            self.results_text.insert(tk.END, "• ファイル形式が適切か\n")
            self.results_text.insert(tk.END, "• ファイルが破損していないか\n")
            self.results_text.insert(tk.END, "• DXFファイルに軌跡データが含まれているか\n")
            self.results_text.config(state='disabled')
        finally:
            # ボタンを有効化
            self.validate_btn.config(state='normal')

    def export_report(self):
        """レポートをファイルに出力"""
        if not self.validation_report:
            messagebox.showwarning("警告", "まず驗證を実行してください！")
            return

        file_path = filedialog.asksaveasfilename(
            title="驗證レポートを保存",
            defaultextension=".txt",
            filetypes=[
                ("テキストファイル", "*.txt"),
                ("すべてのファイル", "*.*")
            ]
        )

        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as file:
                    file.write(self.validation_report)
                messagebox.showinfo("出力完了",
                                   f"驗證レポートを保存しました：\n{file_path}")
            except Exception as e:
                messagebox.showerror("出力エラー",
                                    f"レポート保存エラー：{str(e)}")

    def clear_all(self):
        """すべてをクリア"""
        self.txt_file_path.set("")
        self.dxf_file_path.set("")
        self.tolerance_var.set(0.001)

        self.original_coords = []
        self.dxf_coords = []
        self.comparison_results = {}
        self.validation_report = ""

        self.update_progress(0, "驗證準備完了")

        # 結果エリアをクリア
        self.results_text.config(state='normal')
        self.results_text.delete(1.0, tk.END)
        self.display_initial_message()

        # 視覚化をクリア
        if self.viz_canvas:
            self.viz_canvas.get_tk_widget().destroy()
            self.viz_canvas = None
            self.viz_figure = None

        if hasattr(self, 'viz_label'):
            self.viz_label.pack(expand=True)

def main():
    root = tk.Tk()
    app = CoordinateValidator(root)

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