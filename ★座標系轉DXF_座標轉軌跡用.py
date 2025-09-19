import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import ezdxf
import os
import threading
import time

class ModernDXFConverterGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("座標ファイル → DXF コンバーター")
        self.root.geometry("750x600")
        self.root.resizable(True, True)
        self.root.minsize(700, 550)

        # モダンな配色テーマ
        self.colors = {
            'bg_primary': '#f5f6fa',
            'bg_secondary': '#ffffff',
            'bg_card': '#ffffff',
            'accent': '#3742fa',
            'accent_hover': '#2f3542',
            'success': '#2ed573',
            'success_hover': '#1dd15f',
            'warning': '#ffa502',
            'danger': '#ff3838',
            'text_primary': '#2f3542',
            'text_secondary': '#57606f',
            'border': '#dfe4ea',
            'shadow': '#c7d2fe'
        }

        # 進度相關變数
        self.progress_var = tk.DoubleVar()
        self.progress_text = tk.StringVar(value="変換準備完了")

        # カスタムスタイルの設定
        self.setup_styles()

        # 背景色を設定
        self.root.configure(bg=self.colors['bg_primary'])

        # ファイルパス変数
        self.input_file_path = tk.StringVar()
        self.output_file_path = tk.StringVar()

        # 単位オプション
        self.unit_options = {
            "ミリメートル (mm)": 4,
            "センチメートル (cm)": 5,
            "メートル (m)": 6,
            "インチ (inch)": 1,
            "フィート (feet)": 2
        }
        self.selected_unit = tk.StringVar(value="ミリメートル (mm)")

        self.setup_ui()

    def setup_styles(self):
        """モダンなスタイルを設定"""
        style = ttk.Style()
        style.theme_use('clam')

        # BIZ UDPゴシックフォントを使用
        default_font = ('BIZ UDPゴシック', 9)
        title_font = ('BIZ UDPゴシック', 16, 'bold')
        button_font = ('BIZ UDPゴシック', 10, 'bold')

        # カードスタイル
        style.configure('Card.TFrame',
                       background=self.colors['bg_card'],
                       relief='flat',
                       borderwidth=1,
                       lightcolor=self.colors['border'],
                       darkcolor=self.colors['border'])

        style.configure('Card.TLabelframe',
                       background=self.colors['bg_card'],
                       relief='solid',
                       borderwidth=1,
                       lightcolor=self.colors['border'],
                       darkcolor=self.colors['border'])

        style.configure('Card.TLabelframe.Label',
                       background=self.colors['bg_card'],
                       foreground=self.colors['text_primary'],
                       font=('BIZ UDPゴシック', 10, 'bold'))

        # ボタンスタイル
        style.configure('Primary.TButton',
                       background=self.colors['accent'],
                       foreground='white',
                       borderwidth=0,
                       focuscolor='none',
                       font=button_font,
                       padding=(15, 8))

        style.map('Primary.TButton',
                 background=[('active', self.colors['accent_hover']),
                           ('pressed', self.colors['accent_hover'])])

        style.configure('Success.TButton',
                       background=self.colors['success'],
                       foreground='white',
                       borderwidth=0,
                       focuscolor='none',
                       font=button_font,
                       padding=(20, 10))

        style.map('Success.TButton',
                 background=[('active', self.colors['success_hover']),
                           ('pressed', self.colors['success_hover'])])

        # エントリーとコンボボックス
        style.configure('Modern.TEntry',
                       fieldbackground='white',
                       borderwidth=1,
                       relief='solid',
                       bordercolor=self.colors['border'],
                       padding=8,
                       font=default_font)

        style.configure('Modern.TCombobox',
                       fieldbackground='white',
                       borderwidth=1,
                       relief='solid',
                       bordercolor=self.colors['border'],
                       padding=8,
                       font=default_font)

        # ラベル
        style.configure('Modern.TLabel',
                       background=self.colors['bg_card'],
                       foreground=self.colors['text_primary'],
                       font=default_font)

        style.configure('Title.TLabel',
                       background=self.colors['bg_primary'],
                       foreground=self.colors['text_primary'],
                       font=title_font)

        # プログレスバー
        style.configure('Modern.Horizontal.TProgressbar',
                       background=self.colors['success'],
                       troughcolor=self.colors['border'],
                       borderwidth=0,
                       lightcolor=self.colors['success'],
                       darkcolor=self.colors['success'],
                       thickness=12)

    def setup_ui(self):
        # スクロール可能なメインフレーム
        canvas = tk.Canvas(self.root, bg=self.colors['bg_primary'], highlightthickness=0)
        scrollbar = ttk.Scrollbar(self.root, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        # メインコンテナ
        main_container = tk.Frame(scrollable_frame, bg=self.colors['bg_primary'])
        main_container.pack(fill=tk.BOTH, expand=True, padx=25, pady=25)

        # ヘッダーセクション
        self.create_header(main_container)

        # 入力ファイルセクション
        self.create_input_section(main_container)

        # 出力設定セクション
        self.create_output_section(main_container)

        # 進度バーセクション
        self.create_progress_section(main_container)

        # 実行ボタンセクション
        self.create_button_section(main_container)

        # ステータスセクション
        self.create_status_section(main_container)

        # キャンバスとスクロールバーを配置
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # マウスホイールでスクロール
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)

    def create_header(self, parent):
        """ヘッダーセクションを作成"""
        header_frame = tk.Frame(parent, bg=self.colors['bg_primary'])
        header_frame.pack(fill=tk.X, pady=(0, 30))

        title_label = tk.Label(header_frame,
                              text="📐 座標ファイル → DXF コンバーター",
                              font=('BIZ UDPゴシック', 20, 'bold'),
                              fg=self.colors['text_primary'],
                              bg=self.colors['bg_primary'])
        title_label.pack()

        subtitle_label = tk.Label(header_frame,
                                 text="座標データを高精度のDXFファイルに変換します",
                                 font=('BIZ UDPゴシック', 11),
                                 fg=self.colors['text_secondary'],
                                 bg=self.colors['bg_primary'])
        subtitle_label.pack(pady=(8, 0))

    def create_input_section(self, parent):
        """入力ファイルセクションを作成"""
        input_card = ttk.LabelFrame(parent, text="  📁 入力ファイル  ",
                                   style='Card.TLabelframe', padding=25)
        input_card.pack(fill=tk.X, pady=(0, 20))

        # ファイル選択行
        file_frame = ttk.Frame(input_card)
        file_frame.pack(fill=tk.X, pady=(5, 15))
        file_frame.columnconfigure(1, weight=1)

        ttk.Label(file_frame, text="座標ファイル:", style='Modern.TLabel').grid(
            row=0, column=0, sticky=tk.W, padx=(0, 15), pady=8)

        self.input_entry = ttk.Entry(file_frame, textvariable=self.input_file_path,
                                    state="readonly", style='Modern.TEntry')
        self.input_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(0, 15), pady=8)

        ttk.Button(file_frame, text="参照...", command=self.select_input_file,
                  style='Primary.TButton').grid(row=0, column=2, pady=8)

        # ファイル形式説明
        info_frame = tk.Frame(input_card, bg=self.colors['bg_card'])
        info_frame.pack(fill=tk.X)

        info_text = "📝 対応形式: TXT, CSV  |  📐 座標形式: x,y (カンマ区切り)"
        tk.Label(info_frame, text=info_text,
                font=('BIZ UDPゴシック', 9),
                fg=self.colors['text_secondary'],
                bg=self.colors['bg_card']).pack(anchor=tk.W)

    def create_output_section(self, parent):
        """出力設定セクションを作成"""
        output_card = ttk.LabelFrame(parent, text="  💾 出力設定  ",
                                    style='Card.TLabelframe', padding=25)
        output_card.pack(fill=tk.X, pady=(0, 20))

        # 保存先選択
        save_frame = ttk.Frame(output_card)
        save_frame.pack(fill=tk.X, pady=(5, 20))
        save_frame.columnconfigure(1, weight=1)

        ttk.Label(save_frame, text="保存先:", style='Modern.TLabel').grid(
            row=0, column=0, sticky=tk.W, padx=(0, 15), pady=8)

        self.output_entry = ttk.Entry(save_frame, textvariable=self.output_file_path,
                                     state="readonly", style='Modern.TEntry')
        self.output_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(0, 15), pady=8)

        ttk.Button(save_frame, text="参照...", command=self.select_output_file,
                  style='Primary.TButton').grid(row=0, column=2, pady=8)

        # 単位選択
        unit_frame = ttk.Frame(output_card)
        unit_frame.pack(fill=tk.X)

        ttk.Label(unit_frame, text="出力単位:", style='Modern.TLabel').grid(
            row=0, column=0, sticky=tk.W, padx=(0, 15), pady=8)

        unit_combo = ttk.Combobox(unit_frame, textvariable=self.selected_unit,
                                 values=list(self.unit_options.keys()),
                                 state="readonly", style='Modern.TCombobox', width=25)
        unit_combo.grid(row=0, column=1, sticky=tk.W, pady=8)

    def create_progress_section(self, parent):
        """進度バーセクションを作成"""
        progress_card = ttk.LabelFrame(parent, text="  📊 変換進度  ",
                                      style='Card.TLabelframe', padding=25)
        progress_card.pack(fill=tk.X, pady=(0, 20))

        # 進度テキスト
        progress_label = tk.Label(progress_card, textvariable=self.progress_text,
                                 font=('BIZ UDPゴシック', 10),
                                 fg=self.colors['text_primary'],
                                 bg=self.colors['bg_card'])
        progress_label.pack(anchor=tk.W, pady=(0, 10))

        # 進度バー
        self.progress_bar = ttk.Progressbar(progress_card,
                                           style='Modern.Horizontal.TProgressbar',
                                           length=400,
                                           variable=self.progress_var)
        self.progress_bar.pack(fill=tk.X, pady=(0, 5))

    def create_button_section(self, parent):
        """実行ボタンセクションを作成"""
        button_frame = ttk.Frame(parent)
        button_frame.pack(fill=tk.X, pady=(10, 20))

        button_container = ttk.Frame(button_frame)
        button_container.pack()

        # メイン実行ボタン
        self.convert_btn = ttk.Button(button_container, text="🚀 DXFに変換",
                                     command=self.convert_to_dxf,
                                     style='Success.TButton')
        self.convert_btn.pack(side=tk.LEFT, padx=(0, 20))

        ttk.Button(button_container, text="🗑 クリア", command=self.clear_all,
                  style='Primary.TButton').pack(side=tk.LEFT)

    def create_status_section(self, parent):
        """ステータスセクションを作成"""
        status_card = ttk.LabelFrame(parent, text="  📋 実行ログ  ",
                                    style='Card.TLabelframe', padding=25)
        status_card.pack(fill=tk.BOTH, expand=True)

        # ステータステキストエリア
        text_container = ttk.Frame(status_card)
        text_container.pack(fill=tk.BOTH, expand=True)
        text_container.columnconfigure(0, weight=1)
        text_container.rowconfigure(0, weight=1)

        self.status_text = tk.Text(text_container, height=10, wrap=tk.WORD,
                                  bg='#fafbfc', fg=self.colors['text_primary'],
                                  font=('BIZ UDPゴシック', 9), relief='flat',
                                  borderwidth=1, highlightthickness=1,
                                  highlightcolor=self.colors['border'],
                                  highlightbackground=self.colors['border'],
                                  padx=15, pady=10)

        scrollbar = ttk.Scrollbar(text_container, orient=tk.VERTICAL,
                                 command=self.status_text.yview)
        self.status_text.configure(yscrollcommand=scrollbar.set)

        self.status_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(0, 5))
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))

        # 初期メッセージ
        self.log_message("💡 座標ファイルと保存先を選択してから変換ボタンをクリックしてください")
        self.log_message("📝 使用方法:")
        self.log_message("   1. 座標ファイル（TXT/CSV）を選択")
        self.log_message("   2. DXFファイルの保存先を指定")
        self.log_message("   3. 出力単位を選択")
        self.log_message("   4. 変換ボタンをクリック")
        self.log_message("")

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
            self.log_message(f"✅ 入力ファイル選択: {os.path.basename(file_path)}")
            self.update_progress(0, "ファイル選択完了")

    def select_output_file(self):
        """出力DXFファイルの保存先を選択"""
        file_path = filedialog.asksaveasfilename(
            title="DXFファイルを保存",
            defaultextension=".dxf",
            filetypes=[
                ("DXFファイル", "*.dxf"),
                ("すべてのファイル", "*.*")
            ]
        )
        if file_path:
            self.output_file_path.set(file_path)
            self.log_message(f"✅ 保存先選択: {os.path.basename(file_path)}")
            self.update_progress(0, "保存先設定完了")

    def clear_all(self):
        """すべての選択をクリア"""
        self.input_file_path.set("")
        self.output_file_path.set("")
        self.selected_unit.set("ミリメートル (mm)")
        self.status_text.delete(1.0, tk.END)
        self.update_progress(0, "変換準備完了")
        self.log_message("🗑 すべての選択がクリアされました")

    def log_message(self, message):
        """ステータスエリアにメッセージを表示"""
        self.status_text.insert(tk.END, message + "\n")
        self.status_text.see(tk.END)
        self.root.update()

    def convert_to_dxf(self):
        """DXF変換を実行"""
        # 必要な入力をチェック
        if not self.input_file_path.get():
            messagebox.showerror("エラー", "入力ファイルを選択してください！")
            return

        if not self.output_file_path.get():
            messagebox.showerror("エラー", "保存先を選択してください！")
            return

        # ボタンを無効化
        self.convert_btn.config(state='disabled')

        try:
            self.log_message("=" * 60)
            self.log_message("🚀 変換処理を開始します...")
            self.update_progress(10, "DXFファイル初期化中...")

            # DXFファイルを作成
            doc = ezdxf.new('R2010')
            msp = doc.modelspace()

            # 単位を設定
            unit_code = self.unit_options[self.selected_unit.get()]
            doc.header['$INSUNITS'] = unit_code
            self.log_message(f"📏 DXF単位設定: {self.selected_unit.get()}")
            self.update_progress(20, "単位設定完了...")

            # 座標ファイルを読み込み
            coordinates = []
            input_file = self.input_file_path.get()
            self.log_message(f"📖 ファイル読み込み中: {os.path.basename(input_file)}")
            self.update_progress(30, "ファイル読み込み中...")

            with open(input_file, 'r', encoding='utf-8') as file:
                lines = file.readlines()
                total_lines = len(lines)
                line_count = 0
                valid_count = 0

                for i, line in enumerate(lines):
                    line_count += 1
                    # 進度更新
                    progress = 30 + (i / total_lines) * 40
                    self.update_progress(progress, f"データ解析中... {i+1}/{total_lines}")

                    parts = line.strip().split(',')
                    if len(parts) == 2:
                        try:
                            x = float(parts[0].strip())
                            y = float(parts[1].strip())
                            coordinates.append((x, y))
                            valid_count += 1
                        except ValueError:
                            self.log_message(f"⚠️ 無効な行をスキップ {line_count}: {line.strip()}")
                    else:
                        if line.strip():
                            self.log_message(f"⚠️ 形式不正な行をスキップ {line_count}: {line.strip()}")

            self.log_message(f"📊 読み込み完了: {valid_count}/{line_count} 行")
            self.update_progress(70, "座標データ処理中...")

            if coordinates:
                # ポリラインを作成
                msp.add_lwpolyline(coordinates)
                self.log_message(f"✨ {len(coordinates)} 個の座標点でポリラインを作成しました")
                self.update_progress(80, "ポリライン作成完了...")

                # 輪郭を閉じるかどうか
                if len(coordinates) > 2:
                    first_point = coordinates[0]
                    last_point = coordinates[-1]

                    distance = ((first_point[0] - last_point[0])**2 + (first_point[1] - last_point[1])**2)**0.5
                    if distance > 1e-6:
                        response = messagebox.askyesno(
                            "輪郭を閉じる",
                            "始点と終点を結んで輪郭を閉じますか？"
                        )
                        if response:
                            msp.add_line(first_point, last_point)
                            self.log_message("🔗 始点と終点を結んで輪郭を閉じました")

                self.update_progress(90, "DXFファイル保存中...")

                # DXFファイルを保存
                output_file = self.output_file_path.get()
                doc.saveas(output_file)

                self.update_progress(100, "変換完了！")
                self.log_message("💾 DXFファイルの保存が完了しました！")
                self.log_message(f"📍 保存場所: {output_file}")
                self.log_message("🎉 変換処理が正常に完了しました！")

                messagebox.showinfo("変換完了",
                                   f"DXFファイルの生成が完了しました！\n\n"
                                   f"📁 保存場所:\n{output_file}\n\n"
                                   f"📊 処理した座標点数: {len(coordinates)} 個")

            else:
                error_msg = "エラー: ファイル内に有効な座標データが見つかりませんでした。"
                self.log_message(f"❌ {error_msg}")
                self.update_progress(0, "エラー発生")
                messagebox.showerror("データエラー", error_msg)

        except FileNotFoundError:
            error_msg = f"ファイルが見つかりません: '{self.input_file_path.get()}'"
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
    app = ModernDXFConverterGUI(root)

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