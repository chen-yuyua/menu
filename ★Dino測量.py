# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════╗
║     Dino-Lite AM3111  多鏡頭精密測量系統                ║
║     Ver. 2.1.0                                          ║
║     支援多視訊同時顯示 / 條碼掃描 / 強制LED / 高對比UI  ║
╚══════════════════════════════════════════════════════════╝
"""

import cv2
import numpy as np
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import math
from datetime import datetime
import os
import sys
import json
import threading
import time

# ── 強制 UTF-8 輸出 ─────────────────────────────────────────────
if sys.platform == "win32":
    import codecs
    try:
        sys.stdout = codecs.getwriter("utf-8")(sys.stdout.buffer, "strict")
    except Exception:
        pass

# ── PIL ─────────────────────────────────────────────────────────
try:
    from PIL import Image, ImageTk
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

# ── 條碼掃描函式庫 ──────────────────────────────────────────────
BARCODE_AVAILABLE = False
BARCODE_LIBRARY   = None
try:
    import zxingcpp
    BARCODE_AVAILABLE = True
    BARCODE_LIBRARY   = "zxing-cpp"
except ImportError:
    try:
        from pyzbar import pyzbar
        BARCODE_AVAILABLE = True
        BARCODE_LIBRARY   = "pyzbar"
    except ImportError:
        pass

# ══════════════════════════════════════════════════════════════
#  版本 & 字型設定
# ══════════════════════════════════════════════════════════════
VERSION = "Ver. 2.4.1"

# 字型優先鏈：UD Digi Kyokasho NP-B → 備用日系等寬字型 → 通用後備
_FONT_PRIMARY = "UD Digi Kyokasho NP-B"
_FONT_FALLBACK = ["Yu Gothic UI", "Meiryo UI", "Microsoft JhengHei UI",
                  "Microsoft YaHei UI", "Segoe UI"]

def F(size: int, bold: bool = False, italic: bool = False) -> tuple:
    """建立字型 tuple，自動帶入主字型"""
    style_parts = []
    if bold:
        style_parts.append("bold")
    if italic:
        style_parts.append("italic")
    if style_parts:
        return (_FONT_PRIMARY, size, " ".join(style_parts))
    return (_FONT_PRIMARY, size)

# ══════════════════════════════════════════════════════════════
#  高對比護眼配色  (深藍石墨 + 明亮文字)
# ══════════════════════════════════════════════════════════════
P = {
    # ── 背景層次 ──────────────────────────────────────────────
    "bg"         : "#1A1D27",   # 最底層：深石墨藍
    "panel"      : "#22263A",   # 側面板底色
    "card"       : "#2C3150",   # 卡片 / 區塊
    "card_hover" : "#343862",   # 滑鼠懸停卡片
    "input_bg"   : "#1E2236",   # 輸入框背景
    "canvas_bg"  : "#0D0F18",   # 影像畫布底色

    # ── 主要強調色 ────────────────────────────────────────────
    "accent"     : "#4A9EFF",   # 主藍（高對比）
    "accent_dk"  : "#2B7FE8",   # 深藍（按壓）
    "accent_glow": "#7DC0FF",   # 淺藍（高亮）

    # ── 功能色 ────────────────────────────────────────────────
    "green"      : "#3DBA7A",   # 啟動 / 成功
    "green_dk"   : "#2A9A60",
    "green_txt"  : "#DFFFF0",   # 綠底文字
    "red"        : "#E85050",   # 停止 / 危險
    "red_dk"     : "#C83030",
    "red_txt"    : "#FFE0E0",
    "orange"     : "#F0A030",   # 警告
    "yellow"     : "#F5D060",   # 提示亮色

    # ── 文字層次（高對比）────────────────────────────────────
    "text_h1"    : "#FFFFFF",   # 標題 / 重要值：純白
    "text_h2"    : "#E8EEFF",   # 一般標籤：近白冷白
    "text_body"  : "#C4CCEF",   # 內文：中亮藍白
    "text_dim"   : "#8B96C8",   # 次要 / 說明：中藍灰
    "text_hint"  : "#5A6499",   # 最淡（hint）：深藍灰

    # ── 邊框 / 分隔線 ─────────────────────────────────────────
    "border"     : "#3A4070",
    "border_hi"  : "#4A9EFF",   # 高亮邊框（選中）
    "divider"    : "#2A2E48",

    # ── LED 指示 ──────────────────────────────────────────────
    "led_on"     : "#FFEE55",   # LED 亮起（暖黃）
    "led_off"    : "#44475A",
}

# 攝影機色標 (BGR for OpenCV, HEX for Tkinter)
CAM_COLORS_HEX = ["#FF7070", "#70C8FF", "#60F0A0", "#FFE050",
                  "#D070FF", "#70FFE0"]
CAM_COLORS_BGR = [
    (112, 112, 255), (255, 200, 112), (160, 240, 96),
    (80,  224, 255), (255, 112, 208), (224, 255, 112),
]

# ══════════════════════════════════════════════════════════════
#  CameraSession  — 單一攝影機所有狀態
# ══════════════════════════════════════════════════════════════
class CameraSession:
    """封裝單一攝影機的視訊流、測量狀態、條碼資料"""

    def __init__(self, cam_id: int):
        self.cam_id = cam_id
        self.cap    = None
        self.running = False
        self.current_frame  = None
        self.display_frame  = None

        # ── 測量 ──────────────────────────────────────────────
        self.measurement_mode    = "none"
        self.pending_points: list[tuple] = []
        self.measurement_results: list[dict] = []
        self.max_measurements    = 10
        self._rep_data: list[float] = []

        # ── 校準 ──────────────────────────────────────────────
        self.is_calibrated        = False
        self.scale_factor         = 1.0   # mm/pixel
        self.calibration_distance = 1.0   # mm
        self.pixel_size_um        = 5.0   # μm/pixel
        self.magnification        = 50.0

        # ── 條碼 ──────────────────────────────────────────────
        self.current_barcode   : str | None = None
        self.barcode_history   : list[str]  = []
        self.last_barcode_time : float      = 0.0
        self.frame_count       : int        = 0
        self.scan_interval     : int        = 4

        # ── 顯示縮放 ──────────────────────────────────────────
        self.display_scale  = 1.0
        self.display_offset = (0, 0)

        # ── 十字游標 ──────────────────────────────────────────
        self.crosshair_visible = False
        self.crosshair_x = 0
        self.crosshair_y = 0

    def release(self):
        self.running = False
        if self.cap:
            self.cap.release()
            self.cap = None


# ══════════════════════════════════════════════════════════════
#  DinoLiteApp  — 主應用程式
# ══════════════════════════════════════════════════════════════
class DinoLiteApp:

    # ── 初始化 ──────────────────────────────────────────────────
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title(f"Dino-Lite AM3111  多鏡頭精密測量系統  {VERSION}")
        self.root.geometry("1440x900")
        self.root.minsize(1100, 700)
        self.root.configure(bg=P["bg"])

        # ── 全域狀態 ─────────────────────────────────────────
        self.sessions          : list[CameraSession] = []
        self.available_cameras : list[dict]          = []
        self.active_session_idx: int                 = 0
        self.save_directory    : str                 = os.getcwd()

        # ── 手持掃描器 ───────────────────────────────────────
        self.handheld_enabled    = False
        self.handheld_buffer     = ""
        self.handheld_last_time  = 0.0
        self.handheld_timeout_ms = 100

        # ── 更新迴圈 ─────────────────────────────────────────
        self._update_after_id = None

        # ── 建立 UI ──────────────────────────────────────────
        self._apply_theme()
        self._build_ui()
        self._bind_keys()

    # ══════════════════════════════════════════════════════════
    #  TTK 主題套用
    # ══════════════════════════════════════════════════════════
    def _apply_theme(self):
        s = ttk.Style(self.root)
        s.theme_use("clam")

        # ── 基底 ────────────────────────────────────────────
        s.configure(".",
            background=P["bg"],
            foreground=P["text_h2"],
            font=F(10),
            borderwidth=0,
            focuscolor=P["accent"])

        # ── Frame 系列 ───────────────────────────────────────
        s.configure("TFrame",       background=P["bg"])
        s.configure("Panel.TFrame", background=P["panel"])
        s.configure("Card.TFrame",  background=P["card"])

        # ── Label 系列 ───────────────────────────────────────
        s.configure("TLabel",
            background=P["bg"], foreground=P["text_h2"], font=F(10))
        s.configure("H1.TLabel",
            background=P["bg"], foreground=P["text_h1"], font=F(13, bold=True))
        s.configure("H2.TLabel",
            background=P["panel"], foreground=P["text_h2"], font=F(10, bold=True))
        s.configure("Dim.TLabel",
            background=P["panel"], foreground=P["text_body"], font=F(9))
        s.configure("Hint.TLabel",
            background=P["panel"], foreground=P["text_dim"], font=F(9))
        s.configure("Value.TLabel",
            background=P["card"], foreground=P["accent_glow"], font=F(10, bold=True))
        s.configure("Good.TLabel",
            background=P["panel"], foreground=P["green"], font=F(10, bold=True))
        s.configure("Warn.TLabel",
            background=P["panel"], foreground=P["orange"], font=F(10, bold=True))
        s.configure("Bad.TLabel",
            background=P["panel"], foreground=P["red"], font=F(10, bold=True))

        # ── LabelFrame ───────────────────────────────────────
        s.configure("TLabelframe",
            background=P["panel"],
            foreground=P["accent_glow"],
            font=F(10, bold=True),
            bordercolor=P["border"],
            relief="groove",
            borderwidth=1)
        s.configure("TLabelframe.Label",
            background=P["panel"],
            foreground=P["accent_glow"],
            font=F(10, bold=True))

        # ── Button 系列 ──────────────────────────────────────
        s.configure("TButton",
            background=P["card"],
            foreground=P["text_h2"],
            font=F(10),
            borderwidth=1,
            relief="flat",
            padding=(10, 6))
        s.map("TButton",
            background=[("active", P["card_hover"]), ("pressed", P["accent_dk"])],
            foreground=[("active", P["text_h1"]),   ("pressed", P["text_h1"])],
            relief=[("pressed", "flat")])

        s.configure("Accent.TButton",
            background=P["accent"],
            foreground=P["text_h1"],
            font=F(10, bold=True),
            padding=(10, 6))
        s.map("Accent.TButton",
            background=[("active", P["accent_glow"]), ("pressed", P["accent_dk"])],
            foreground=[("active", P["bg"]),           ("pressed", P["text_h1"])])

        s.configure("Green.TButton",
            background=P["green"],
            foreground=P["green_txt"],
            font=F(10, bold=True),
            padding=(10, 6))
        s.map("Green.TButton",
            background=[("active", P["green_dk"]), ("pressed", "#1A7A48")],
            foreground=[("active", "#FFFFFF"),      ("pressed", "#FFFFFF")])

        s.configure("Red.TButton",
            background=P["red"],
            foreground=P["red_txt"],
            font=F(10, bold=True),
            padding=(10, 6))
        s.map("Red.TButton",
            background=[("active", P["red_dk"]), ("pressed", "#A01010")],
            foreground=[("active", "#FFFFFF"),    ("pressed", "#FFFFFF")])

        s.configure("Orange.TButton",
            background=P["orange"],
            foreground="#1A0A00",
            font=F(10, bold=True),
            padding=(10, 6))
        s.map("Orange.TButton",
            background=[("active", P["yellow"]), ("pressed", "#C07010")],
            foreground=[("active", "#1A0A00"),    ("pressed", "#1A0A00")])

        # ── Entry ────────────────────────────────────────────
        s.configure("TEntry",
            fieldbackground=P["input_bg"],
            foreground=P["text_h1"],
            insertcolor=P["accent_glow"],
            bordercolor=P["border"],
            font=F(10),
            padding=4)
        s.map("TEntry",
            bordercolor=[("focus", P["border_hi"])],
            fieldbackground=[("focus", P["card"])])

        # ── Combobox ─────────────────────────────────────────
        s.configure("TCombobox",
            fieldbackground=P["input_bg"],
            background=P["card"],
            foreground=P["text_h1"],
            selectbackground=P["accent"],
            selectforeground=P["text_h1"],
            arrowcolor=P["accent"],
            font=F(10),
            padding=4)
        s.map("TCombobox",
            fieldbackground=[("readonly", P["input_bg"])],
            foreground=[("readonly", P["text_h1"])],
            bordercolor=[("focus", P["border_hi"])])

        # ── Scale ────────────────────────────────────────────
        s.configure("TScale",
            background=P["panel"],
            troughcolor=P["card"],
            sliderlength=18,
            sliderrelief="flat")

        # ── Checkbutton ──────────────────────────────────────
        s.configure("TCheckbutton",
            background=P["panel"],
            foreground=P["text_h2"],
            indicatorcolor=P["input_bg"],
            font=F(10))
        s.map("TCheckbutton",
            indicatorcolor=[("selected", P["accent"]),
                            ("active",   P["accent_glow"])],
            foreground=[("active", P["text_h1"])])

        # ── Scrollbar ────────────────────────────────────────
        s.configure("TScrollbar",
            background=P["card"],
            troughcolor=P["panel"],
            arrowcolor=P["text_dim"],
            borderwidth=0,
            arrowsize=12)

        # ── Progressbar ──────────────────────────────────────
        s.configure("Horizontal.TProgressbar",
            troughcolor=P["card"],
            background=P["accent"],
            borderwidth=0)

    # ══════════════════════════════════════════════════════════
    #  UI 主架構
    # ══════════════════════════════════════════════════════════
    def _build_ui(self):
        self._build_topbar()

        body = ttk.Frame(self.root, style="TFrame")
        body.pack(fill="both", expand=True, padx=8, pady=(4, 0))

        # 左側控制面板  (固定寬 295px)
        self.left_panel = tk.Frame(body, bg=P["panel"], width=295)
        self.left_panel.pack(side="left", fill="y", padx=(0, 6))
        self.left_panel.pack_propagate(False)
        self._build_left_panel()

        # 右側影像區
        self.right_panel = ttk.Frame(body, style="TFrame")
        self.right_panel.pack(side="right", fill="both", expand=True)
        self._build_camera_area()

        self._build_statusbar()

    # ── 頂部工具列 ──────────────────────────────────────────────
    def _build_topbar(self):
        bar = tk.Frame(self.root, bg=P["card"], height=56)
        bar.pack(fill="x")
        bar.pack_propagate(False)

        # 左：圖示 + 標題
        lf = tk.Frame(bar, bg=P["card"])
        lf.pack(side="left", padx=16, pady=10)
        tk.Label(lf, text="🔬", font=(_FONT_PRIMARY, 22),
                 bg=P["card"], fg=P["accent_glow"]).pack(side="left")
        tk.Label(lf, text="  Dino-Lite  多鏡頭精密測量系統",
                 font=F(14, bold=True),
                 bg=P["card"], fg=P["text_h1"]).pack(side="left")

        # 右：功能按鈕
        rf = tk.Frame(bar, bg=P["card"])
        rf.pack(side="right", padx=14, pady=10)

        top_btns = [
            ("❓  使用說明",    self._show_help,          P["accent"],  P["text_h1"]),
            ("⚙   關閉其他程式", self._close_other_progs, P["card"],    P["text_dim"]),
        ]
        for txt, cmd, bg, fg in top_btns:
            tk.Button(rf, text=txt, command=cmd,
                      bg=bg, fg=fg,
                      font=F(10),
                      relief="flat", padx=12, pady=5,
                      activebackground=P["accent"],
                      activeforeground=P["text_h1"],
                      cursor="hand2",
                      bd=0).pack(side="right", padx=5)

    # ── 左側控制面板 ────────────────────────────────────────────
    def _build_left_panel(self):
        lp = self.left_panel

        # 捲軸容器
        wrap_canvas = tk.Canvas(lp, bg=P["panel"], highlightthickness=0)
        vsb = ttk.Scrollbar(lp, orient="vertical", command=wrap_canvas.yview)
        wrap_canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        wrap_canvas.pack(side="left", fill="both", expand=True)

        inner = tk.Frame(wrap_canvas, bg=P["panel"])
        win_id = wrap_canvas.create_window((0, 0), window=inner, anchor="nw")

        def _cfg_scroll(e):
            wrap_canvas.configure(scrollregion=wrap_canvas.bbox("all"))
        def _cfg_width(e):
            wrap_canvas.itemconfig(win_id, width=e.width)
        inner.bind("<Configure>", _cfg_scroll)
        wrap_canvas.bind("<Configure>", _cfg_width)

        def _on_wheel(e):
            wrap_canvas.yview_scroll(-1 if e.delta > 0 else 1, "units")
        wrap_canvas.bind_all("<MouseWheel>", _on_wheel)

        # ── § 共用樣式 helper ──────────────────────────────────
        def sec(title):
            return self._section(inner, title)

        def row(**kw):
            f = tk.Frame(inner, bg=P["panel"])
            f.pack(fill="x", padx=8, pady=3, **kw)
            return f

        def hline():
            tk.Frame(inner, bg=P["divider"], height=1).pack(
                fill="x", padx=8, pady=4)

        pad  = dict(padx=8, pady=3, fill="x")
        pad2 = dict(padx=8, pady=2, fill="x")

        # ══════════════════════════════════════════════════════
        #  § 1  攝影機管理
        # ══════════════════════════════════════════════════════
        f1 = sec("① 攝影機管理")

        self._btn(f1, "🔍  偵測所有攝影機",
                  self._detect_cameras, "Accent").pack(**pad)

        tk.Label(f1, text="選擇鏡頭：",
                 bg=P["panel"], fg=P["text_body"], font=F(9)).pack(
                     padx=8, pady=(4, 0), anchor="w")
        self.camera_list_var = tk.StringVar()
        self.camera_combo = ttk.Combobox(f1, textvariable=self.camera_list_var,
                                         state="readonly", font=F(10))
        self.camera_combo.pack(**pad2)

        btn_r1 = tk.Frame(f1, bg=P["panel"])
        btn_r1.pack(**pad2)
        self._btn(btn_r1, "▶  開啟", self._open_selected_camera,
                  "Green").pack(side="left", expand=True, fill="x", padx=(0, 4))
        self._btn(btn_r1, "■  關閉", self._close_selected_camera,
                  "Red").pack(side="left", expand=True, fill="x")

        self.cam_status_label = tk.Label(
            f1, text="● 無啟用鏡頭",
            bg=P["panel"], fg=P["red"], font=F(9, bold=True))
        self.cam_status_label.pack(padx=8, pady=2, anchor="w")

        tk.Label(f1, text="操作目標鏡頭：",
                 bg=P["panel"], fg=P["text_body"], font=F(9)).pack(
                     padx=8, pady=(4, 0), anchor="w")
        self.active_cam_var = tk.StringVar()
        self.active_cam_combo = ttk.Combobox(f1, textvariable=self.active_cam_var,
                                             state="readonly", font=F(10))
        self.active_cam_combo.pack(**pad2)
        self.active_cam_combo.bind("<<ComboboxSelected>>",
                                   self._on_active_cam_changed)

        hline()

        # ══════════════════════════════════════════════════════
        #  § 2  顯微鏡設定
        # ══════════════════════════════════════════════════════
        f2 = sec("② 顯微鏡設定")

        mf = tk.Frame(f2, bg=P["panel"])
        mf.pack(**pad2)
        tk.Label(mf, text="倍率：",
                 bg=P["panel"], fg=P["text_h2"], font=F(10)).pack(side="left")
        self.mag_var = tk.StringVar(value="50")
        ttk.Combobox(mf, textvariable=self.mag_var,
                     values=["20","30","50","70","100","150","200"],
                     width=7, state="readonly", font=F(10)).pack(
                         side="left", padx=6)
        self.mag_var.trace_add("write", lambda *_: self._update_mag())

        self.pixel_lbl = tk.Label(
            f2, text="像素尺寸：— μm",
            bg=P["panel"], fg=P["accent_glow"], font=F(9, bold=True))
        self.pixel_lbl.pack(padx=8, anchor="w")

        # LED 亮度（預設 100%，強制開啟）
        lf2 = tk.Frame(f2, bg=P["panel"])
        lf2.pack(**pad2)
        tk.Label(lf2, text="💡 LED 亮度：",
                 bg=P["panel"], fg=P["led_on"], font=F(10, bold=True)).pack(
                     side="left")
        self.led_val_lbl = tk.Label(
            lf2, text="100%",
            bg=P["panel"], fg=P["led_on"], font=F(10, bold=True))
        self.led_val_lbl.pack(side="right")

        self.led_var = tk.IntVar(value=100)   # ★ 預設 100
        self.led_scale = ttk.Scale(f2, from_=0, to=100, orient="horizontal",
                                   variable=self.led_var,
                                   command=lambda v: self._adjust_led(float(v)))
        self.led_scale.pack(padx=8, pady=2, fill="x")

        # LED 強制開啟按鈕
        self._btn(f2, "🔆  LED 強制全亮 (100%)",
                  self._force_led_on, "Orange").pack(**pad2)

        hline()

        # ══════════════════════════════════════════════════════
        #  § 3  校準
        # ══════════════════════════════════════════════════════
        f3 = sec("③ 校準")

        cf = tk.Frame(f3, bg=P["panel"])
        cf.pack(**pad2)
        tk.Label(cf, text="已知距離(mm)：",
                 bg=P["panel"], fg=P["text_h2"], font=F(10)).pack(side="left")
        self.cal_entry = ttk.Entry(cf, width=8, font=F(10))
        self.cal_entry.insert(0, "1.0")
        self.cal_entry.pack(side="left", padx=4)

        self._btn(f3, "🎯  開始校準（點選兩點）",
                  self._start_calibration).pack(**pad)

        self.cal_status_lbl = tk.Label(
            f3, text="● 尚未校準",
            bg=P["panel"], fg=P["orange"], font=F(9, bold=True))
        self.cal_status_lbl.pack(padx=8, anchor="w", pady=2)

        hline()

        # ══════════════════════════════════════════════════════
        #  § 4  測量工具
        # ══════════════════════════════════════════════════════
        f4 = sec("④ 測量工具")

        for label, mode in [
            ("📏  距離測量  (2點)", "distance"),
            ("📐  角度測量  (3點)", "angle"),
            ("⭕  直徑測量  (3點)", "diameter"),
        ]:
            self._btn(f4, label,
                      lambda m=mode: self._set_mode(m)).pack(**pad)

        ur = tk.Frame(f4, bg=P["panel"])
        ur.pack(**pad2)
        self._btn(ur, "↩  撤銷上次",
                  self._undo_last).pack(side="left", expand=True, fill="x",
                                         padx=(0, 4))
        self._btn(ur, "🗑  清除全部",
                  self._clear_all, "Red").pack(side="left", expand=True,
                                                fill="x")

        self.mode_lbl = tk.Label(
            f4, text="模式：無",
            bg=P["panel"], fg=P["text_dim"], font=F(9))
        self.mode_lbl.pack(padx=8, anchor="w", pady=2)

        hline()

        # ══════════════════════════════════════════════════════
        #  § 5  精度驗證
        # ══════════════════════════════════════════════════════
        f5 = sec("⑤ 精度驗證")
        self._btn(f5, "🔁  重複性測試（5次）",
                  self._start_repeatability).pack(**pad)
        self._btn(f5, "📖  精度指南",
                  self._show_accuracy_guide).pack(**pad)

        hline()

        # ══════════════════════════════════════════════════════
        #  § 6  條碼掃描
        # ══════════════════════════════════════════════════════
        f6 = sec("⑥ 條碼掃描")

        if BARCODE_AVAILABLE:
            self.barcode_cam_var  = tk.BooleanVar(value=False)
            self.barcode_hand_var = tk.BooleanVar(value=False)

            ttk.Checkbutton(
                f6,
                text=f"攝影機條碼掃描 ({BARCODE_LIBRARY})",
                variable=self.barcode_cam_var,
                command=self._update_scanner_status,
                style="TCheckbutton").pack(**pad2)
            ttk.Checkbutton(
                f6,
                text="手持掃描器輸入",
                variable=self.barcode_hand_var,
                command=self._toggle_handheld,
                style="TCheckbutton").pack(**pad2)

            self.scanner_status_lbl = tk.Label(
                f6, text="掃描器：待機",
                bg=P["panel"], fg=P["text_dim"], font=F(9))
            self.scanner_status_lbl.pack(padx=8, anchor="w")

            tk.Label(f6, text="最新條碼：",
                     bg=P["panel"], fg=P["text_body"], font=F(9)).pack(
                         padx=8, pady=(6, 0), anchor="w")
            self.barcode_display_lbl = tk.Label(
                f6, text="—",
                bg=P["card"], fg=P["accent_glow"], font=F(10, bold=True),
                anchor="w", padx=6, pady=3, relief="flat")
            self.barcode_display_lbl.pack(padx=8, fill="x")

            tk.Label(f6, text="掃描歷史：",
                     bg=P["panel"], fg=P["text_body"], font=F(9)).pack(
                         padx=8, pady=(6, 0), anchor="w")

            bc_f = tk.Frame(f6, bg=P["panel"])
            bc_f.pack(padx=8, pady=2, fill="x")
            self.barcode_listbox = tk.Listbox(
                bc_f, height=4,
                bg=P["input_bg"], fg=P["text_body"],
                selectbackground=P["accent"],
                selectforeground=P["text_h1"],
                font=("Consolas", 9),
                borderwidth=0, highlightthickness=0)
            bc_sb = ttk.Scrollbar(bc_f, command=self.barcode_listbox.yview)
            self.barcode_listbox.config(yscrollcommand=bc_sb.set)
            self.barcode_listbox.pack(side="left", fill="both", expand=True)
            bc_sb.pack(side="right", fill="y")

            self._btn(f6, "🗑  清除條碼歷史",
                      self._clear_barcode_history).pack(**pad2)
        else:
            tk.Label(
                f6,
                text="⚠ 條碼庫未安裝\npip install zxing-cpp",
                bg=P["panel"], fg=P["orange"], font=F(9),
                justify="left").pack(padx=8, pady=6, anchor="w")

        hline()

        # ══════════════════════════════════════════════════════
        #  § 7  檔案操作
        # ══════════════════════════════════════════════════════
        f7 = sec("⑦ 檔案操作")

        # 路徑顯示列
        tk.Label(f7, text="儲存位置：",
                 bg=P["panel"], fg=P["text_body"], font=F(9)).pack(
                     padx=8, pady=(4, 0), anchor="w")

        path_row = tk.Frame(f7, bg=P["panel"])
        path_row.pack(padx=8, pady=2, fill="x")

        self.savedir_lbl = tk.Label(
            path_row,
            text=self._short_path(self.save_directory),
            bg=P["input_bg"], fg=P["accent_glow"],
            font=F(9), anchor="w",
            padx=6, pady=4,
            wraplength=170, justify="left")
        self.savedir_lbl.pack(side="left", fill="x", expand=True)

        # ★ 明顯的「選擇路徑」按鈕（橙色，絕對看得清楚）
        tk.Button(
            path_row,
            text="📁\n選擇",
            command=self._select_savedir,
            bg=P["orange"], fg="#1A0800",
            font=F(8, bold=True),
            relief="flat",
            width=5, pady=2,
            activebackground=P["yellow"],
            activeforeground="#1A0800",
            cursor="hand2", bd=0
        ).pack(side="right", padx=(4, 0))

        # 功能按鈕列
        fr7 = tk.Frame(f7, bg=P["panel"])
        fr7.pack(padx=8, pady=(4, 6), fill="x")

        file_btns = [
            ("📷\n拍照",  self._capture,        P["green"],   P["green_txt"]),
            ("💾\n儲存",  self._save_image,      P["accent"],  P["text_h1"]),
            ("📤\n匯出",  self._export_results,  P["card"],    P["text_h2"]),
        ]
        for label, cmd, bg, fg in file_btns:
            tk.Button(
                fr7, text=label, command=cmd,
                bg=bg, fg=fg,
                font=F(9, bold=True),
                relief="flat", width=6, pady=4,
                activebackground=P["accent_glow"],
                activeforeground=P["bg"],
                cursor="hand2", bd=0
            ).pack(side="left", expand=True, fill="x", padx=2)

        hline()

        # ══════════════════════════════════════════════════════
        #  § 8  測量日誌
        # ══════════════════════════════════════════════════════
        f8 = sec("⑧ 測量日誌")

        log_f = tk.Frame(f8, bg=P["panel"])
        log_f.pack(padx=8, pady=4, fill="x")

        self.log_text = tk.Text(
            log_f, height=10, width=30,
            bg=P["input_bg"], fg=P["text_body"],
            insertbackground=P["accent_glow"],
            font=("Consolas", 9),
            borderwidth=0, highlightthickness=0,
            state="disabled", wrap="word")
        log_sb = ttk.Scrollbar(log_f, command=self.log_text.yview)
        self.log_text.config(yscrollcommand=log_sb.set)
        self.log_text.pack(side="left", fill="both", expand=True)
        log_sb.pack(side="right", fill="y")

    # ── 攝影機顯示區 ────────────────────────────────────────────
    def _build_camera_area(self):
        rp = self.right_panel

        # 工具列
        tb = tk.Frame(rp, bg=P["card"], height=36)
        tb.pack(fill="x")
        tb.pack_propagate(False)

        tk.Label(tb, text="影像顯示區",
                 bg=P["card"], fg=P["text_dim"], font=F(10)).pack(
                     side="left", padx=10, pady=8)
        tk.Button(tb, text="⏸  全部暫停 / 恢復",
                  command=self._toggle_all_cameras,
                  bg=P["card"], fg=P["text_h2"],
                  font=F(10), relief="flat",
                  activebackground=P["accent"],
                  activeforeground=P["text_h1"],
                  cursor="hand2", padx=10, bd=0).pack(
                      side="right", padx=10, pady=5)

        # 畫布格線容器
        self.canvas_container = tk.Frame(rp, bg=P["bg"])
        self.canvas_container.pack(fill="both", expand=True, pady=2)

        self.cam_canvases : dict[int, tk.Canvas] = {}
        self.cam_frames   : dict[int, tk.Frame]  = {}

        self._refresh_canvas_layout()

    def _refresh_canvas_layout(self):
        for w in self.canvas_container.winfo_children():
            w.destroy()
        self.cam_canvases.clear()
        self.cam_frames.clear()

        n    = max(1, len(self.sessions))
        cols = 2 if n >= 2 else 1
        rows = math.ceil(n / cols)

        for r in range(rows):
            self.canvas_container.rowconfigure(r, weight=1)
        for c in range(cols):
            self.canvas_container.columnconfigure(c, weight=1)

        if not self.sessions:
            holder = tk.Frame(self.canvas_container, bg=P["canvas_bg"])
            holder.grid(row=0, column=0, sticky="nsew", padx=4, pady=4)
            tk.Label(holder,
                     text="請先偵測攝影機後點選「▶ 開啟」",
                     bg=P["canvas_bg"], fg=P["text_hint"],
                     font=F(13)).place(relx=.5, rely=.5, anchor="center")
            return

        for i, sess in enumerate(self.sessions):
            r, c = divmod(i, cols)
            self._create_cam_frame(sess, r, c)

    def _create_cam_frame(self, sess: CameraSession, row: int, col: int):
        idx     = sess.cam_id
        is_act  = (idx == self.active_session_idx)
        brd_col = P["border_hi"] if is_act else P["border"]
        cam_hex = CAM_COLORS_HEX[idx % len(CAM_COLORS_HEX)]

        outer = tk.Frame(self.canvas_container,
                         bg=brd_col, bd=2, relief="flat")
        outer.grid(row=row, column=col, sticky="nsew", padx=4, pady=4)

        # 標題列
        hdr = tk.Frame(outer, bg=P["card"], height=30)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)

        tk.Label(hdr, text=f"  ● Camera {idx}",
                 bg=P["card"], fg=cam_hex,
                 font=F(10, bold=True)).pack(side="left", padx=6)
        tk.Label(hdr, text="( 點擊切換操作目標 )",
                 bg=P["card"], fg=P["text_hint"],
                 font=F(8)).pack(side="left")

        hdr.bind("<Button-1>", lambda e, i=idx: self._switch_active_cam(i))

        # 畫布
        cv = tk.Canvas(outer,
                       bg=P["canvas_bg"],
                       highlightthickness=0,
                       cursor="crosshair")
        cv.pack(fill="both", expand=True)
        cv.bind("<Button-1>", lambda e, s=sess: self._on_canvas_click(e, s))
        cv.bind("<Motion>",   lambda e, s=sess: self._on_mouse_move(e, s))
        cv.bind("<Enter>",    lambda e, s=sess: self._on_mouse_enter(e, s))
        cv.bind("<Leave>",    lambda e, s=sess: self._on_mouse_leave(e, s))

        self.cam_canvases[idx] = cv
        self.cam_frames[idx]   = outer

    def _switch_active_cam(self, cam_id: int):
        self.active_session_idx = cam_id
        for sid, frm in self.cam_frames.items():
            frm.config(bg=P["border_hi"] if sid == cam_id else P["border"])
        names = [f"Camera {s.cam_id}" for s in self.sessions]
        if f"Camera {cam_id}" in names:
            self.active_cam_combo.set(f"Camera {cam_id}")
        self._log(f"操作目標已切換至 Camera {cam_id}")

    # ── 狀態列 ──────────────────────────────────────────────────
    def _build_statusbar(self):
        bar = tk.Frame(self.root, bg=P["card"], height=30)
        bar.pack(fill="x", side="bottom")
        bar.pack_propagate(False)

        # 分隔線
        tk.Frame(self.root, bg=P["border"], height=1).pack(
            fill="x", side="bottom")

        self.status_lbl = tk.Label(
            bar, text="就緒",
            bg=P["card"], fg=P["text_body"],
            font=F(9), anchor="w")
        self.status_lbl.pack(side="left", padx=12, fill="x", expand=True)

        # 版本號（顯眼）
        tk.Label(bar, text=VERSION,
                 bg=P["card"], fg=P["accent_glow"],
                 font=F(10, bold=True)).pack(side="right", padx=14)

        # 分隔點
        tk.Label(bar, text="│",
                 bg=P["card"], fg=P["text_hint"],
                 font=F(10)).pack(side="right")

        # PIL 狀態
        pil_txt = "PIL ✓" if PIL_AVAILABLE else "PIL ✗"
        pil_col = P["green"] if PIL_AVAILABLE else P["red"]
        tk.Label(bar, text=pil_txt,
                 bg=P["card"], fg=pil_col,
                 font=F(9)).pack(side="right", padx=8)

        # 條碼庫狀態
        bc_txt = f"Barcode ✓ {BARCODE_LIBRARY}" if BARCODE_AVAILABLE else "Barcode ✗"
        bc_col = P["green"] if BARCODE_AVAILABLE else P["text_hint"]
        tk.Label(bar, text=bc_txt,
                 bg=P["card"], fg=bc_col,
                 font=F(9)).pack(side="right", padx=8)

    # ══════════════════════════════════════════════════════════
    #  Helper Widgets
    # ══════════════════════════════════════════════════════════
    def _btn(self, parent, text: str, cmd,
             style: str = "Normal") -> ttk.Button:
        """建立統一樣式的 ttk.Button"""
        styles = {
            "Accent" : "Accent.TButton",
            "Green"  : "Green.TButton",
            "Red"    : "Red.TButton",
            "Orange" : "Orange.TButton",
            "Normal" : "TButton",
        }
        return ttk.Button(parent, text=text, command=cmd,
                          style=styles.get(style, "TButton"))

    def _section(self, parent, title: str) -> tk.Frame:
        """建立帶標題的區塊 LabelFrame (tk 版，可精確控制顏色)"""
        lf = tk.LabelFrame(parent,
                           text=f"  {title}  ",
                           bg=P["panel"],
                           fg=P["accent_glow"],
                           font=F(10, bold=True),
                           bd=1,
                           relief="groove",
                           labelanchor="nw")
        lf.pack(fill="x", padx=8, pady=4)
        return lf

    def _short_path(self, path: str, n: int = 38) -> str:
        return path if len(path) <= n else "…" + path[-(n - 1):]

    # ══════════════════════════════════════════════════════════
    #  鍵盤綁定（手持掃描器）
    # ══════════════════════════════════════════════════════════
    def _bind_keys(self):
        self.root.bind("<KeyPress>", self._on_key_press)
        self.root.focus_set()

    def _on_key_press(self, event):
        if not self.handheld_enabled:
            return
        now_ms = time.time() * 1000
        if now_ms - self.handheld_last_time > self.handheld_timeout_ms:
            self.handheld_buffer = ""
        self.handheld_last_time = now_ms

        if event.keysym in ("Return", "KP_Enter"):
            if len(self.handheld_buffer) >= 3:
                self._process_barcode(
                    {"text": self.handheld_buffer.strip(),
                     "format": "HANDHELD", "source": "handheld"},
                    self._active_session())
            self.handheld_buffer = ""
        elif len(event.char) == 1 and event.char.isprintable():
            self.handheld_buffer += event.char
            if len(self.handheld_buffer) > 100:
                self.handheld_buffer = self.handheld_buffer[-50:]

    # ══════════════════════════════════════════════════════════
    #  攝影機管理
    # ══════════════════════════════════════════════════════════
    def _detect_cameras(self):
        self._log("偵測攝影機中…")
        self._set_status("偵測中，請稍候…")
        self.camera_combo["values"] = []
        self.available_cameras.clear()

        def worker():
            found = []
            for i in range(8):
                for bk in [cv2.CAP_DSHOW, cv2.CAP_MSMF, cv2.CAP_ANY]:
                    try:
                        cap = cv2.VideoCapture(i, bk)
                        if not cap.isOpened():
                            cap.release()
                            continue
                        ret, frm = cap.read()
                        if ret and frm is not None:
                            w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                            h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                            cap.release()
                            found.append({
                                "index"  : i,
                                "backend": bk,
                                "label"  : f"Camera {i}  ({w}×{h})",
                            })
                            break
                        cap.release()
                    except Exception:
                        pass
            self.root.after(0, lambda: self._on_detect_done(found))

        threading.Thread(target=worker, daemon=True).start()

    def _on_detect_done(self, found: list):
        self.available_cameras = found
        labels = [f["label"] for f in found]
        self.camera_combo["values"] = labels or ["未偵測到攝影機"]
        if labels:
            self.camera_combo.current(0)
        self._log(f"偵測完成：找到 {len(found)} 個攝影機")
        for cam in found:
            self._log(f"  ✓ {cam['label']}")
        if not found:
            self._log("  → 未偵測到任何裝置，請確認攝影機已連接並允許存取")
        self._set_status(f"找到 {len(found)} 個攝影機")

    def _open_selected_camera(self):
        sel = self.camera_combo.current()
        if sel < 0 or sel >= len(self.available_cameras):
            messagebox.showwarning("提示", "請先偵測並選擇攝影機")
            return
        info   = self.available_cameras[sel]
        cam_id = info["index"]

        if any(s.cam_id == cam_id for s in self.sessions):
            messagebox.showinfo("提示", f"Camera {cam_id} 已在運行中")
            return

        sess = CameraSession(cam_id)
        try:
            sess.cap = cv2.VideoCapture(cam_id, info["backend"])
            sess.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            ret, _ = sess.cap.read()
            if not ret:
                raise RuntimeError("無法讀取影格")
        except Exception as e:
            messagebox.showerror("錯誤", f"無法開啟 Camera {cam_id}：{e}")
            sess.release()
            return

        sess.running = True
        sess.magnification = float(self.mag_var.get())
        sess.pixel_size_um = self._calc_pixel_size(sess.magnification)
        self.sessions.append(sess)

        # ★ 偵測是否有內建 LED，有才嘗試啟用，不影響一般 Webcam 畫面
        led_ok = self._try_enable_led(sess)
        if led_ok:
            self._log(f"Camera {cam_id} 偵測到內建 LED，已自動開啟")
        else:
            self._log(f"Camera {cam_id} 無內建 LED 或不支援，畫面保持原始")

        names = [f"Camera {s.cam_id}" for s in self.sessions]
        self.active_cam_combo["values"] = names
        if len(self.sessions) == 1:
            self.active_session_idx = cam_id
            self.active_cam_combo.set(names[0])

        self._refresh_canvas_layout()
        self._update_cam_status()
        self._log(f"Camera {cam_id} 已啟動（LED 已強制全亮）")
        self._schedule_update()

    def _close_selected_camera(self):
        sel = self.active_cam_combo.current()
        if sel < 0 or sel >= len(self.sessions):
            return
        sess = self.sessions[sel]
        sess.release()
        self.sessions.pop(sel)

        names = [f"Camera {s.cam_id}" for s in self.sessions]
        self.active_cam_combo["values"] = names
        if self.sessions:
            self.active_session_idx = self.sessions[0].cam_id
            self.active_cam_combo.set(names[0])

        self._refresh_canvas_layout()
        self._update_cam_status()
        self._log(f"Camera {sess.cam_id} 已關閉")

    def _toggle_all_cameras(self):
        for s in self.sessions:
            s.running = not s.running
        state = "恢復" if any(s.running for s in self.sessions) else "暫停"
        self._log(f"所有攝影機已{state}")
        self._set_status(f"所有攝影機已{state}")

    def _update_cam_status(self):
        if self.sessions:
            names = "、".join(f"Cam{s.cam_id}" for s in self.sessions)
            self.cam_status_label.config(
                text=f"● 運行中：{names}", fg=P["green"])
        else:
            self.cam_status_label.config(
                text="● 無啟用鏡頭", fg=P["red"])

    # ══════════════════════════════════════════════════════════
    #  畫面更新主迴圈 (~30fps)
    # ══════════════════════════════════════════════════════════
    def _schedule_update(self):
        if self._update_after_id is not None:
            self.root.after_cancel(self._update_after_id)
        self._update_after_id = self.root.after(33, self._update_all)

    def _update_all(self):
        for sess in list(self.sessions):
            if sess.running and sess.cap and sess.cap.isOpened():
                self._update_session(sess)
        if self.sessions:
            self._update_after_id = self.root.after(33, self._update_all)

    def _update_session(self, sess: CameraSession):
        try:
            ret, frame = sess.cap.read()
            if not ret:
                return
            sess.current_frame = frame.copy()
            sess.display_frame = frame.copy()

            # 條碼掃描
            if (BARCODE_AVAILABLE
                    and hasattr(self, "barcode_cam_var")
                    and self.barcode_cam_var.get()):
                sess.frame_count += 1
                if sess.frame_count % sess.scan_interval == 0:
                    result = self._scan_barcode(frame)
                    if result:
                        result["source"] = "camera"
                        self._process_barcode(result, sess)
            else:
                sess.frame_count += 1

            self._draw_measurements(sess)
            self._draw_barcode_overlay(sess)
            self._render_to_canvas(sess)
        except Exception as e:
            print(f"[Session {sess.cam_id}] update error: {e}")

    def _render_to_canvas(self, sess: CameraSession):
        if sess.display_frame is None or not PIL_AVAILABLE:
            return
        cv_widget = self.cam_canvases.get(sess.cam_id)
        if not cv_widget:
            return
        try:
            cw = cv_widget.winfo_width()
            ch = cv_widget.winfo_height()
            if cw < 2 or ch < 2:
                return
            rgb = cv2.cvtColor(sess.display_frame, cv2.COLOR_BGR2RGB)
            h, w = rgb.shape[:2]
            scale  = min(cw / w, ch / h)
            nw, nh = max(1, int(w * scale)), max(1, int(h * scale))
            resized = cv2.resize(rgb, (nw, nh), interpolation=cv2.INTER_LINEAR)
            photo   = ImageTk.PhotoImage(Image.fromarray(resized))

            sess.display_scale  = scale
            sess.display_offset = ((cw - nw) // 2, (ch - nh) // 2)

            cv_widget.delete("all")
            cv_widget.create_image(*sess.display_offset,
                                   anchor="nw", image=photo)
            cv_widget.image = photo  # 防 GC

            # 十字游標
            if sess.crosshair_visible and sess.measurement_mode != "none":
                x, y = sess.crosshair_x, sess.crosshair_y
                cv_widget.create_line(x, 0, x, ch,
                                      fill="#FF5050", width=1, dash=(5, 3))
                cv_widget.create_line(0, y, cw, y,
                                      fill="#FF5050", width=1, dash=(5, 3))
                # 中心圓
                r = 6
                cv_widget.create_oval(x-r, y-r, x+r, y+r,
                                      outline="#FF5050", width=1)
        except Exception as e:
            print(f"[Render {sess.cam_id}] {e}")

    # ══════════════════════════════════════════════════════════
    #  滑鼠事件
    # ══════════════════════════════════════════════════════════
    def _on_canvas_click(self, event, sess: CameraSession):
        self._switch_active_cam(sess.cam_id)
        if sess.measurement_mode == "none" or sess.current_frame is None:
            return
        cx = event.x - sess.display_offset[0]
        cy = event.y - sess.display_offset[1]
        ox = int(cx / sess.display_scale)
        oy = int(cy / sess.display_scale)
        h, w = sess.current_frame.shape[:2]
        if 0 <= ox < w and 0 <= oy < h:
            sess.pending_points.append((ox, oy))
            self._process_measurement(sess)

    def _on_mouse_move(self, event, sess: CameraSession):
        if sess.measurement_mode != "none":
            sess.crosshair_x = event.x
            sess.crosshair_y = event.y
            sess.crosshair_visible = True

    def _on_mouse_enter(self, event, sess: CameraSession):
        sess.crosshair_visible = True

    def _on_mouse_leave(self, event, sess: CameraSession):
        sess.crosshair_visible = False

    # ══════════════════════════════════════════════════════════
    #  測量邏輯
    # ══════════════════════════════════════════════════════════
    def _active_session(self) -> CameraSession | None:
        for s in self.sessions:
            if s.cam_id == self.active_session_idx:
                return s
        return self.sessions[0] if self.sessions else None

    def _set_mode(self, mode: str):
        sess = self._active_session()
        if not sess:
            self._log("請先開啟攝影機")
            return
        sess.measurement_mode = mode
        sess.pending_points.clear()
        labels = {"distance": "距離測量（2點）",
                  "angle":    "角度測量（3點）",
                  "diameter": "直徑測量（3點）",
                  "calibration": "校準模式（2點）",
                  "repeatability": "重複性測試"}
        txt = labels.get(mode, mode)
        self.mode_lbl.config(text=f"模式：{txt}", fg=P["yellow"])
        self._set_status(f"[Camera {sess.cam_id}]  {txt}")

    def _process_measurement(self, sess: CameraSession):
        mode = sess.measurement_mode
        pts  = sess.pending_points
        try:
            if   mode == "distance"     and len(pts) >= 2:
                self._measure_distance(sess, pts[-2], pts[-1])
                sess.pending_points.clear()
            elif mode == "angle"        and len(pts) >= 3:
                self._measure_angle(sess, pts[-3], pts[-2], pts[-1])
                sess.pending_points.clear()
            elif mode == "diameter"     and len(pts) >= 3:
                self._measure_diameter(sess, pts[-3], pts[-2], pts[-1])
                sess.pending_points.clear()
            elif mode == "calibration"  and len(pts) >= 2:
                self._complete_calibration(sess, pts[-2], pts[-1])
                sess.pending_points.clear()
            elif mode == "repeatability" and len(pts) >= 2:
                self._process_repeatability(sess, pts[-2], pts[-1])
                sess.pending_points.clear()
        except Exception as e:
            print(f"Measurement error: {e}")

    def _px_to_mm(self, sess: CameraSession, pixels: float) -> float:
        if sess.is_calibrated:
            return pixels * sess.scale_factor
        return pixels * sess.pixel_size_um / 1000.0

    def _measure_distance(self, sess: CameraSession, p1, p2):
        d  = math.dist(p1, p2)
        mm = self._px_to_mm(sess, d)
        tag = "校準值" if sess.is_calibrated else "估算值"
        result = f"距離：{mm:.4f} mm  [{tag}]"
        self._add_meas(sess, {"type":"distance","p1":p1,"p2":p2,
                               "result":result,"value":f"{mm:.3f}mm"})
        self._log(f"[Cam{sess.cam_id}] {result}")

    def _measure_angle(self, sess: CameraSession, p1, p2, p3):
        v1 = (p1[0]-p2[0], p1[1]-p2[1])
        v2 = (p3[0]-p2[0], p3[1]-p2[1])
        m1, m2 = math.hypot(*v1), math.hypot(*v2)
        if m1 > 0 and m2 > 0:
            cos_a = max(-1.0, min(1.0,
                        (v1[0]*v2[0]+v1[1]*v2[1]) / (m1*m2)))
            angle  = math.degrees(math.acos(cos_a))
            result = f"角度：{angle:.2f}°"
            self._add_meas(sess, {"type":"angle",
                                   "points":[p1,p2,p3],
                                   "result":result,
                                   "value":f"{angle:.2f}deg"})
            self._log(f"[Cam{sess.cam_id}] {result}")

    def _measure_diameter(self, sess: CameraSession, p1, p2, p3):
        center, radius = self._circle_3pt(p1, p2, p3)
        if center and radius:
            d_mm   = self._px_to_mm(sess, radius * 2)
            tag    = "校準值" if sess.is_calibrated else "估算值"
            result = f"直徑：{d_mm:.4f} mm  [{tag}]"
            self._add_meas(sess, {"type":"diameter",
                                   "points":[p1,p2,p3],
                                   "center":center,"radius":radius,
                                   "result":result,
                                   "value":f"D:{d_mm:.3f}mm"})
            self._log(f"[Cam{sess.cam_id}] {result}")

    def _add_meas(self, sess: CameraSession, data: dict):
        if len(sess.measurement_results) >= sess.max_measurements:
            sess.measurement_results.clear()
            self._log(f"⚠ [Cam{sess.cam_id}] 已達上限({sess.max_measurements})，自動清除")
        sess.measurement_results.append(data)

    def _undo_last(self):
        sess = self._active_session()
        if sess and sess.measurement_results:
            m = sess.measurement_results.pop()
            sess.pending_points.clear()
            self._log(f"[Cam{sess.cam_id}] 撤銷：{m.get('result','')}")
        else:
            self._log("無可撤銷的測量記錄")

    def _clear_all(self):
        sess = self._active_session()
        if sess:
            sess.measurement_results.clear()
            sess.pending_points.clear()
            sess.measurement_mode = "none"
            self.mode_lbl.config(text="模式：無", fg=P["text_dim"])
            self._log(f"[Cam{sess.cam_id}] 清除所有測量標記")

    # ── 校準 ─────────────────────────────────────────────────
    def _start_calibration(self):
        sess = self._active_session()
        if not sess:
            self._log("請先開啟攝影機")
            return
        try:
            dist = float(self.cal_entry.get())
        except ValueError:
            messagebox.showerror("錯誤", "請輸入有效的數值（公釐）")
            return
        sess.calibration_distance = dist
        sess.measurement_mode     = "calibration"
        sess.pending_points.clear()
        self.mode_lbl.config(text="模式：校準中…", fg=P["yellow"])
        self._log(f"[Cam{sess.cam_id}] 校準模式：請在影像上點選"
                  f" {dist} mm 的兩個端點")

    def _complete_calibration(self, sess: CameraSession, p1, p2):
        d = math.dist(p1, p2)
        if d > 0:
            sess.scale_factor  = sess.calibration_distance / d
            sess.is_calibrated = True
            sess.measurement_mode = "none"
            self.cal_status_lbl.config(
                text=f"● 已校準  {sess.scale_factor:.6f} mm/px",
                fg=P["green"])
            self.mode_lbl.config(text="模式：無", fg=P["text_dim"])
            self._log(f"[Cam{sess.cam_id}] 校準完成："
                      f" {sess.scale_factor:.6f} mm/px")

    # ── 重複性測試 ───────────────────────────────────────────
    def _start_repeatability(self):
        sess = self._active_session()
        if not sess:
            return
        sess._rep_data = []
        sess.measurement_mode = "repeatability"
        sess.pending_points.clear()
        self.mode_lbl.config(text="模式：重複性測試", fg=P["yellow"])
        self._log(f"[Cam{sess.cam_id}] 重複性測試開始，請連續測量同一段距離 5 次")

    def _process_repeatability(self, sess: CameraSession, p1, p2):
        d  = math.dist(p1, p2)
        mm = self._px_to_mm(sess, d)
        if not hasattr(sess, "_rep_data") or sess._rep_data is None:
            sess._rep_data = []
        sess._rep_data.append(mm)
        n = len(sess._rep_data)
        self._log(f"[Cam{sess.cam_id}] 第 {n}/5 次：{mm:.4f} mm")

        if n >= 5:
            data  = sess._rep_data
            avg   = sum(data) / len(data)
            std   = math.sqrt(sum((x-avg)**2 for x in data) / len(data))
            cv    = (std / avg * 100) if avg > 0 else 0
            grade = ("優秀 ✅" if cv < 2
                     else "良好 🟡" if cv < 5
                     else "可接受 🟠" if cv < 10
                     else "需改善 🔴")
            self._log(f"[Cam{sess.cam_id}] 重複性結果："
                      f" 平均={avg:.4f}mm  σ={std:.4f}mm  CV={cv:.2f}%  {grade}")
            sess.measurement_mode = "none"
            sess._rep_data = []
            self.mode_lbl.config(text="模式：無", fg=P["text_dim"])

    # ── 幾何計算 ─────────────────────────────────────────────
    @staticmethod
    def _circle_3pt(p1, p2, p3):
        x1,y1 = p1; x2,y2 = p2; x3,y3 = p3
        d = 2*(x1*(y2-y3)+x2*(y3-y1)+x3*(y1-y2))
        if abs(d) < 1e-6:
            return None, None
        ux = ((x1**2+y1**2)*(y2-y3)+(x2**2+y2**2)*(y3-y1)+(x3**2+y3**2)*(y1-y2))/d
        uy = ((x1**2+y1**2)*(x3-x2)+(x2**2+y2**2)*(x1-x3)+(x3**2+y3**2)*(x2-x1))/d
        r  = math.sqrt((ux-x1)**2+(uy-y1)**2)
        return (int(ux), int(uy)), r

    # ══════════════════════════════════════════════════════════
    #  繪圖（OpenCV 圖層）
    # ══════════════════════════════════════════════════════════
    _MEAS_COLORS = [
        (255, 100, 100), (100, 200, 255), (80,  240, 140),
        (255, 220,  70), (220, 100, 255), (80,  255, 220),
    ]

    def _draw_measurements(self, sess: CameraSession):
        if sess.display_frame is None:
            return
        df = sess.display_frame
        for i, m in enumerate(sess.measurement_results):
            col = self._MEAS_COLORS[i % len(self._MEAS_COLORS)]
            self._draw_one(df, m, col)

        # 當前尚未完成的點
        for j, pt in enumerate(sess.pending_points):
            self._cross(df, pt, (0, 230, 255), 8, 2)
            cv2.putText(df, str(j+1),
                        (pt[0]+10, pt[1]-10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55,
                        (255, 255, 255), 1)

        # 計數器（左上角）
        n, mx = len(sess.measurement_results), sess.max_measurements
        bar_bg = (40, 44, 70)
        cv2.rectangle(df, (6, 6), (170, 28), bar_bg, -1)
        col_cnt = (80, 240, 140) if n < mx else (255, 100, 80)
        cv2.putText(df, f" Cam{sess.cam_id}  {n}/{mx} 筆測量",
                    (8, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                    col_cnt, 1)

    def _draw_one(self, df, m: dict, col: tuple):
        t = m["type"]
        if t == "distance":
            p1, p2 = m["p1"], m["p2"]
            cv2.line(df, p1, p2, col, 1)
            self._cross(df, p1, col)
            self._cross(df, p2, col)
            mid = ((p1[0]+p2[0])//2, (p1[1]+p2[1])//2)
            self._put_txt(df, m["value"], mid, col)

        elif t == "angle":
            p1,p2,p3 = m["points"]
            cv2.line(df, p2, p1, col, 1)
            cv2.line(df, p2, p3, col, 1)
            for p in (p1,p2,p3):
                self._cross(df, p, col)
            self._put_txt(df, m["value"], (p2[0]+14, p2[1]-14), col)

        elif t == "diameter":
            ctr = m["center"]
            r   = int(m["radius"])
            cv2.circle(df, ctr, r, col, 1)
            for p in m["points"]:
                self._cross(df, p, col)
            self._cross(df, ctr, col, 4, 1)
            self._put_txt(df, m["value"], (ctr[0]+r+8, ctr[1]), col)

    @staticmethod
    def _cross(img, pt, col, size=5, thick=1):
        x, y = pt
        cv2.line(img, (x-size, y), (x+size, y), col, thick)
        cv2.line(img, (x, y-size), (x, y+size), col, thick)
        cv2.circle(img, pt, 2, col, -1)

    @staticmethod
    def _put_txt(img, text: str, pos: tuple, col: tuple):
        font, sc, th = cv2.FONT_HERSHEY_SIMPLEX, 0.48, 1
        sz = cv2.getTextSize(text, font, sc, th)[0]
        h0, w0 = img.shape[:2]
        x  = max(2, min(pos[0], w0 - sz[0] - 2))
        y  = max(sz[1]+2, min(pos[1], h0 - 2))
        cv2.rectangle(img, (x-2, y-sz[1]-3), (x+sz[0]+2, y+3),
                      (15, 17, 30), -1)
        cv2.putText(img, text, (x, y), font, sc, (240, 240, 255), th)

    # ══════════════════════════════════════════════════════════
    #  條碼功能
    # ══════════════════════════════════════════════════════════
    def _scan_barcode(self, frame) -> dict | None:
        try:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            if BARCODE_LIBRARY == "zxing-cpp":
                results = zxingcpp.read_barcodes(gray)
                if results:
                    r = results[0]
                    return {"text": r.text, "format": r.format.name}
            elif BARCODE_LIBRARY == "pyzbar":
                results = pyzbar.decode(gray)
                if results:
                    r = results[0]
                    return {"text": r.data.decode("utf-8"), "format": r.type}
        except Exception:
            pass
        return None

    def _process_barcode(self, data: dict,
                          sess: CameraSession | None):
        if not data or not data.get("text"):
            return
        now  = time.time()
        text = data["text"]
        if sess:
            if (sess.current_barcode == text
                    and (now - sess.last_barcode_time) < 2.0):
                return
            sess.current_barcode   = text
            sess.last_barcode_time = now

        disp = text[:32] + ("…" if len(text) > 32 else "")
        if hasattr(self, "barcode_display_lbl"):
            self.barcode_display_lbl.config(text=disp)

        src_ico = "🔫" if data.get("source") == "handheld" else "📷"
        entry   = (f"[{datetime.now().strftime('%H:%M:%S')}]"
                   f" {src_ico} {data['format']}: {text}")

        if hasattr(self, "barcode_listbox"):
            self.barcode_listbox.insert(tk.END, entry)
            self.barcode_listbox.see(tk.END)
            if self.barcode_listbox.size() > 60:
                self.barcode_listbox.delete(0)
        if sess:
            sess.barcode_history.append(entry)

        self._set_status(f"條碼掃描：{disp}")
        self._log(entry)

    def _draw_barcode_overlay(self, sess: CameraSession):
        if not sess.current_barcode or sess.display_frame is None:
            return
        text = f"BC: {sess.current_barcode[:30]}"
        tw   = len(text) * 8 + 12
        cv2.rectangle(sess.display_frame, (6, 30), (6+tw, 52),
                      (15, 40, 30), -1)
        cv2.putText(sess.display_frame, text, (10, 47),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                    (80, 255, 180), 1)

    def _update_scanner_status(self):
        if not hasattr(self, "scanner_status_lbl"):
            return
        parts = []
        if hasattr(self, "barcode_cam_var") and self.barcode_cam_var.get():
            parts.append("攝影機")
        if self.handheld_enabled:
            parts.append("手持")
        txt = "掃描器啟用：" + " + ".join(parts) if parts else "掃描器：待機"
        col = P["green"] if parts else P["text_dim"]
        self.scanner_status_lbl.config(text=txt, fg=col)

    def _toggle_handheld(self):
        self.handheld_enabled = self.barcode_hand_var.get()
        self._update_scanner_status()
        self._log("手持掃描器" + ("已啟用" if self.handheld_enabled else "已停用"))

    def _clear_barcode_history(self):
        if hasattr(self, "barcode_listbox"):
            self.barcode_listbox.delete(0, tk.END)
        for s in self.sessions:
            s.barcode_history.clear()
            s.current_barcode = None
        if hasattr(self, "barcode_display_lbl"):
            self.barcode_display_lbl.config(text="—")
        self._log("條碼歷史已清除")

    # ══════════════════════════════════════════════════════════
    #  LED & 倍率
    # ══════════════════════════════════════════════════════════
    def _calc_pixel_size(self, mag: float) -> float:
        """AM3111 感光面 6.4mm / 640px → μm/px"""
        return (6.4 / mag * 1000.0) / 640.0

    def _update_mag(self):
        try:
            mag   = float(self.mag_var.get())
            px_um = self._calc_pixel_size(mag)
            self.pixel_lbl.config(text=f"像素尺寸：{px_um:.3f} μm  ({int(mag)}×)")
            sess = self._active_session()
            if sess:
                sess.magnification = mag
                sess.pixel_size_um = px_um
        except Exception:
            pass

    # ── LED 相關 ─────────────────────────────────────────────────
    @staticmethod
    def _probe_led_support(cap) -> bool:
        """偵測是否有 UVC Backlight 控制（Dino-Lite 內建 LED 指標）"""
        try:
            bl = cap.get(cv2.CAP_PROP_BACKLIGHT)
            if bl >= 0:
                return cap.set(cv2.CAP_PROP_BACKLIGHT, bl)
        except Exception:
            pass
        return False

    def _adjust_led(self, value: float):
        """
        LED 滑桿回呼：★ 僅更新 UI 顯示，完全不碰攝影機任何參數。
        CAP_PROP_BRIGHTNESS 直接影響曝光，不能拿來控 LED，已移除。
        """
        v = int(value)
        self.led_val_lbl.config(text=f"{v}%")
        col = P["led_on"] if v > 10 else P["led_off"]
        self.led_val_lbl.config(fg=col)

    def _try_enable_led(self, sess: "CameraSession") -> bool:
        """只對有內建 LED（CAP_PROP_BACKLIGHT 支援）的設備寫入，一般 Webcam 完全跳過"""
        if not (sess.cap and sess.cap.isOpened()):
            return False
        if not self._probe_led_support(sess.cap):
            return False
        try:
            return sess.cap.set(cv2.CAP_PROP_BACKLIGHT, 1)
        except Exception:
            return False

    def _force_led_on(self):
        """對所有 Session 嘗試啟用 LED；無支援的設備靜默跳過"""
        self.led_var.set(100)
        self._adjust_led(100.0)
        for sess in self.sessions:
            ok = self._try_enable_led(sess)
            self._log(
                f"Cam{sess.cam_id} LED {'已開啟（內建LED）' if ok else '跳過（無內建LED，畫面不受影響）'}"
            )

    # ══════════════════════════════════════════════════════════
    #  操作目標切換
    # ══════════════════════════════════════════════════════════
    def _on_active_cam_changed(self, event=None):
        sel = self.active_cam_combo.current()
        if 0 <= sel < len(self.sessions):
            self._switch_active_cam(self.sessions[sel].cam_id)
            self._update_mag()

    # ══════════════════════════════════════════════════════════
    #  檔案操作
    # ══════════════════════════════════════════════════════════
    def _select_savedir(self):
        d = filedialog.askdirectory(title="選擇照片保存資料夾",
                                    initialdir=self.save_directory)
        if d:
            self.save_directory = d
            self.savedir_lbl.config(text=self._short_path(d))
            self._log(f"保存路徑已更新：{d}")

    def _capture(self):
        sess = self._active_session()
        if not sess or sess.display_frame is None:
            messagebox.showwarning("提示", "請先開啟攝影機")
            return
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        fn = f"dino_cam{sess.cam_id}_{ts}.jpg"
        fp = os.path.join(self.save_directory, fn)
        cv2.imwrite(fp, sess.display_frame)
        self._save_meta(sess, ts, fn)
        messagebox.showinfo("拍照成功 ✓",
                            f"檔案已儲存至：\n{fp}")
        self._log(f"拍照：{fn}")

    def _save_image(self):
        sess = self._active_session()
        if not sess or sess.display_frame is None:
            messagebox.showwarning("提示", "請先開啟攝影機")
            return
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        fp = filedialog.asksaveasfilename(
            title="儲存影像",
            initialdir=self.save_directory,
            initialfile=f"dino_cam{sess.cam_id}_{ts}.jpg",
            defaultextension=".jpg",
            filetypes=[("JPEG","*.jpg"),("PNG","*.png"),("All","*.*")])
        if fp:
            cv2.imwrite(fp, sess.display_frame)
            messagebox.showinfo("儲存成功 ✓", f"已儲存：\n{fp}")
            self._log(f"儲存：{os.path.basename(fp)}")

    def _export_results(self):
        sess = self._active_session()
        if not sess:
            return
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        fp = filedialog.asksaveasfilename(
            title="匯出測量結果",
            initialdir=self.save_directory,
            initialfile=f"dino_cam{sess.cam_id}_results_{ts}.json",
            defaultextension=".json",
            filetypes=[("JSON","*.json"),("Text","*.txt"),("All","*.*")])
        if not fp:
            return
        data = {
            "export_time" : datetime.now().isoformat(),
            "camera_id"   : sess.cam_id,
            "magnification": sess.magnification,
            "calibrated"  : sess.is_calibrated,
            "scale_mm_per_px": sess.scale_factor if sess.is_calibrated else None,
            "pixel_size_um": sess.pixel_size_um,
            "barcode"     : sess.current_barcode,
            "barcode_history": sess.barcode_history,
            "measurements": [
                {k: v for k, v in m.items()
                 if k not in ("points","p1","p2","center")}
                for m in sess.measurement_results
            ],
        }
        with open(fp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        messagebox.showinfo("匯出完成 ✓", f"已匯出：\n{fp}")
        self._log(f"匯出：{os.path.basename(fp)}")

    def _save_meta(self, sess: CameraSession, ts: str, img_fn: str):
        if not sess.current_barcode and not sess.measurement_results:
            return
        meta = {"timestamp": ts, "camera_id": sess.cam_id,
                "barcode": sess.current_barcode, "image_file": img_fn,
                "measurements": [m["result"] for m in sess.measurement_results]}
        try:
            jfp = os.path.join(self.save_directory,
                               img_fn.replace(".jpg", "_meta.json"))
            with open(jfp, "w", encoding="utf-8") as f:
                json.dump(meta, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    # ══════════════════════════════════════════════════════════
    #  其他工具
    # ══════════════════════════════════════════════════════════
    def _close_other_progs(self):
        try:
            import psutil
            targets = ["DinoCapture","Skype","Teams","Zoom","OBS"]
            closed  = []
            for proc in psutil.process_iter(["name"]):
                for t in targets:
                    if t.lower() in proc.info["name"].lower():
                        proc.terminate()
                        closed.append(proc.info["name"])
            msg = f"已關閉：{', '.join(closed)}" if closed else "未找到需要關閉的程式"
            self._log(msg)
            self._set_status(msg)
        except ImportError:
            messagebox.showwarning("提示", "需安裝 psutil：\npip install psutil")

    def _show_accuracy_guide(self):
        messagebox.showinfo("AM3111 精度指南", (
            "校準建議\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "• 使用 1 mm 或 0.5 mm 標準距離\n"
            "• 確保良好照明、降低反光\n"
            "• 選擇高對比清晰的測量端點\n\n"
            "精度評估標準\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "  優秀   ✅  CV < 2%\n"
            "  良好   🟡  CV 2 – 5%\n"
            "  可接受 🟠  CV 5 – 10%\n"
            "  需改善 🔴  CV > 10%\n\n"
            "倍率建議\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "  一般量測   50× – 100×\n"
            "  精密量測  100× – 200×\n\n"
            "驗證物體\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "• 1 元硬幣（直徑 20 mm）\n"
            "• 標準尺規刻度\n"
            "• 電路板線寬（已知值）"
        ))

    def _show_help(self):
        messagebox.showinfo("使用說明", (
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "  Dino-Lite 多鏡頭精密測量系統\n"
            "  使用說明   Ver. 2.1\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "【快速開始】\n"
            "① 點擊「🔍 偵測所有攝影機」\n"
            "② 從下拉選單選擇鏡頭 → 點「▶ 開啟」\n"
            "③ 可重複步驟 ② 開啟多個鏡頭\n"
            "④ 點擊影像上方標題列切換操作目標\n"
            "   （高亮藍色邊框 = 目前操作鏡頭）\n\n"
            "【LED 燈】\n"
            "• 每次開啟攝影機自動強制 LED 100%\n"
            "• 可用滑桿手動調整亮度\n"
            "• 點「🔆 LED 強制全亮」快速還原\n\n"
            "【校準步驟】\n"
            "• 在「已知距離」欄輸入實際長度(mm)\n"
            "• 點「🎯 開始校準」→ 在影像上點選\n"
            "  兩個端點（已知距離的兩端）\n"
            "• 校準後測量精度大幅提升\n\n"
            "【測量工具】\n"
            "  📏 距離：在影像上點選 2 點\n"
            "  📐 角度：點選 起點→頂點→終點\n"
            "  ⭕ 直徑：點選圓弧上任意 3 點\n\n"
            "【條碼掃描】\n"
            "• 攝影機掃描：勾選後自動偵測\n"
            "• 手持掃描器：勾選後直接用掃描器掃\n"
            "  （請保持應用程式視窗焦點）\n\n"
            "【拍照 / 匯出】\n"
            "• 先點「📁 保存路徑」設定儲存位置\n"
            "• 「📷 拍照」：儲存含測量標記的截圖\n"
            "• 「📤 匯出」：輸出 JSON 測量報告\n\n"
            "【快捷操作】\n"
            "  ↩ 撤銷  → 移除最後一筆測量\n"
            "  🗑 清除  → 刪除該鏡頭所有標記\n"
        ))

    # ══════════════════════════════════════════════════════════
    #  日誌 & 狀態
    # ══════════════════════════════════════════════════════════
    def _log(self, msg: str):
        try:
            ts   = datetime.now().strftime("%H:%M:%S")
            line = f"[{ts}]  {msg}\n"
            self.log_text.config(state="normal")
            self.log_text.insert(tk.END, line)
            self.log_text.see(tk.END)
            # 限制行數避免記憶體膨脹
            lines = int(self.log_text.index("end-1c").split(".")[0])
            if lines > 500:
                self.log_text.delete("1.0", "100.0")
            self.log_text.config(state="disabled")
        except Exception:
            pass

    def _set_status(self, msg: str):
        try:
            self.status_lbl.config(text=msg)
        except Exception:
            pass

    # ── 關閉清理 ────────────────────────────────────────────
    def cleanup(self):
        if self._update_after_id:
            self.root.after_cancel(self._update_after_id)
        for s in self.sessions:
            s.release()


# ══════════════════════════════════════════════════════════════
#  入口點
# ══════════════════════════════════════════════════════════════
def main():
    root = tk.Tk()
    app  = DinoLiteApp(root)

    def on_close():
        app.cleanup()
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_close)

    # 初始化顯示
    app._update_mag()
    app._log(f"═══  Dino-Lite 多鏡頭精密測量系統  {VERSION}  啟動  ═══")
    app._log(f"字型：{_FONT_PRIMARY}  /  PIL：{'✓' if PIL_AVAILABLE else '✗'}  /  "
             f"條碼庫：{BARCODE_LIBRARY if BARCODE_AVAILABLE else '未安裝'}")
    if not PIL_AVAILABLE:
        app._log("⚠ 未安裝 Pillow → 影像無法顯示。請執行：pip install pillow")
    if not BARCODE_AVAILABLE:
        app._log("⚠ 未安裝條碼庫 → 請執行：pip install zxing-cpp")

    root.mainloop()


if __name__ == "__main__":
    print("=" * 60)
    print(f"  Dino-Lite AM3111  多鏡頭精密測量系統  {VERSION}")
    print("=" * 60)
    print(f"  Python  : {sys.version.split()[0]}")
    print(f"  OpenCV  : {cv2.__version__}")
    print(f"  PIL     : {'✓' if PIL_AVAILABLE else '✗  pip install pillow'}")
    print(f"  Barcode : "
          f"{'✓ ' + BARCODE_LIBRARY if BARCODE_AVAILABLE else '✗  pip install zxing-cpp'}")
    print(f"  字型    : {_FONT_PRIMARY}")
    print("=" * 60)
    main()
