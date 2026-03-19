# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════════╗
║     Dino-Lite AM3111  多鏡頭精密測量系統                    ║
║     Ver. 2.5.0                                              ║
║     支援多視訊同時顯示 / 條碼掃描 / 曝光手動控制 / 高對比UI ║
║                                                              ║
║  v2.5 變更說明：                                            ║
║  • 新增「手動曝光控制」取代原 LED 亮度滑桿                  ║
║    - 開啟攝影機後自動關閉 AE（Auto Exposure）               ║
║    - 同步關閉 AWB（Auto White Balance）                     ║
║    - 提供曝光值 / 增益 / 亮度補償三組滑桿                   ║
║  • 移除 LED 亮度滑桿 / LED 強制全亮按鈕（UVC 無效）         ║
║  • 修正 UPG650 PLUS 等電子顯微鏡畫面暗沉問題                ║
╚══════════════════════════════════════════════════════════════╝

【畫面暗沉根本原因】
  電子顯微鏡的鏡頭視野極小，攝影機內建的「自動曝光」(AE)
  演算法將顯微放大的高亮樣品誤判為「整體過亮場景」，
  自動壓低曝光值，造成畫面整體暗沉。
  普通網路攝影機拍攝正常場景，AE 運作正常所以明亮。
  解法：開啟攝影機後立即鎖定手動曝光，避免 AE 干擾。
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
VERSION      = "Ver. 2.8.0"
VERSION_DATE = "更新日：2026/03/19　作成：分室"

_FONT_PRIMARY  = "UD Digi Kyokasho NP-B"
_FONT_FALLBACK = ["Yu Gothic UI", "Meiryo UI", "Microsoft JhengHei UI",
                  "Microsoft YaHei UI", "Segoe UI"]

def F(size: int, bold: bool = False, italic: bool = False) -> tuple:
    style_parts = []
    if bold:   style_parts.append("bold")
    if italic: style_parts.append("italic")
    if style_parts:
        return (_FONT_PRIMARY, size, " ".join(style_parts))
    return (_FONT_PRIMARY, size)

# ══════════════════════════════════════════════════════════════
#  高對比護眼配色
# ══════════════════════════════════════════════════════════════
P = {
    "bg"         : "#1A1D27",
    "panel"      : "#22263A",
    "card"       : "#2C3150",
    "card_hover" : "#343862",
    "input_bg"   : "#1E2236",
    "canvas_bg"  : "#0D0F18",
    "accent"     : "#4A9EFF",
    "accent_dk"  : "#2B7FE8",
    "accent_glow": "#7DC0FF",
    "green"      : "#3DBA7A",
    "green_dk"   : "#2A9A60",
    "green_txt"  : "#DFFFF0",
    "red"        : "#E85050",
    "red_dk"     : "#C83030",
    "red_txt"    : "#FFE0E0",
    "orange"     : "#F0A030",
    "yellow"     : "#F5D060",
    "text_h1"    : "#FFFFFF",
    "text_h2"    : "#E8EEFF",
    "text_body"  : "#C4CCEF",
    "text_dim"   : "#8B96C8",
    "text_hint"  : "#5A6499",
    "border"     : "#3A4070",
    "border_hi"  : "#4A9EFF",
    "divider"    : "#2A2E48",
    "led_on"     : "#FFEE55",
    "led_off"    : "#44475A",
}

CAM_COLORS_HEX = ["#FF7070", "#70C8FF", "#60F0A0", "#FFE050",
                  "#D070FF", "#70FFE0"]
CAM_COLORS_BGR = [
    (112, 112, 255), (255, 200, 112), (160, 240, 96),
    (80,  224, 255), (255, 112, 208), (224, 255, 112),
]

# ══════════════════════════════════════════════════════════════
#  曝光預設值
#  CAP_PROP_AUTO_EXPOSURE：DirectShow 下 1=手動 / 3=自動
#  CAP_PROP_EXPOSURE：對數尺度，-1 ~ -13（數值越小越暗）
# ══════════════════════════════════════════════════════════════
EXPOSURE_DEFAULT = -5    # 建議顯微鏡初始曝光值
GAIN_DEFAULT     = 64    # 增益 0~100
BRIGHT_DEFAULT   = 128   # 亮度補償 0~255

# ══════════════════════════════════════════════════════════════
#  CameraSession
# ══════════════════════════════════════════════════════════════

# ══════════════════════════════════════════════════════════════
#  圓角按鈕元件
#  用 Canvas 繪製圓角矩形背景，套用於工具列所有 tk.Button
# ══════════════════════════════════════════════════════════════
class RoundButton(tk.Canvas):
    """
    以 Canvas 實作的圓角按鈕。
    支援 text、command、bg、fg、font、padx、pady、radius 參數。
    hover / press 時自動變色。
    """
    def __init__(self, parent, text="", command=None,
                 bg="#2C3150", fg="#FFFFFF",
                 hover_bg=None, press_bg=None,
                 font=None, padx=14, pady=6,
                 radius=8, **kwargs):
        # 先用暫定尺寸初始化，之後依文字量測後更新
        super().__init__(parent, highlightthickness=0,
                         bd=0, relief="flat",
                         bg=parent.cget("bg"), **kwargs)

        self._text    = text
        self._command = command
        self._bg      = bg
        self._fg      = fg
        self._hbg     = hover_bg or self._lighten(bg, 30)
        self._pbg     = press_bg or self._darken(bg, 30)
        self._font    = font or F(12, bold=True)
        self._padx    = padx
        self._pady    = pady
        self._radius  = radius
        self._current_bg = bg

        # 量測文字尺寸後設定 Canvas 大小
        import tkinter.font as tkfont
        try:
            fobj = tkfont.Font(font=self._font)
            tw = fobj.measure(text)
            th = fobj.metrics("linespace")
        except Exception:
            tw, th = len(text) * 10, 18
        w = tw + padx * 2
        h = th + pady * 2
        self.config(width=w, height=h)

        self._draw(bg)

        self.bind("<Enter>",          self._on_enter)
        self.bind("<Leave>",          self._on_leave)
        self.bind("<ButtonPress-1>",  self._on_press)
        self.bind("<ButtonRelease-1>",self._on_release)
        self.config(cursor="hand2")

    # ── 色彩工具 ──────────────────────────────────────────────
    @staticmethod
    def _adjust(hex_color: str, delta: int) -> str:
        hex_color = hex_color.lstrip("#")
        r, g, b = (int(hex_color[i:i+2], 16) for i in (0, 2, 4))
        r = max(0, min(255, r + delta))
        g = max(0, min(255, g + delta))
        b = max(0, min(255, b + delta))
        return f"#{r:02x}{g:02x}{b:02x}"

    def _lighten(self, c, d): return self._adjust(c,  d)
    def _darken (self, c, d): return self._adjust(c, -d)

    # ── 繪製 ──────────────────────────────────────────────────
    def _draw(self, bg_color: str):
        self.delete("all")
        w = self.winfo_reqwidth()
        h = self.winfo_reqheight()
        r = self._radius
        # 圓角矩形（用多邊形近似）
        self.create_polygon(
            r, 0,  w-r, 0,
            w, 0,  w, r,
            w, h-r, w, h,
            w-r, h, r, h,
            0, h,  0, h-r,
            0, r,  0, 0,
            r, 0,
            fill=bg_color, outline="", smooth=True)
        self.create_text(w//2, h//2,
                         text=self._text,
                         fill=self._fg,
                         font=self._font,
                         anchor="center")
        self._current_bg = bg_color

    def _on_enter(self, e):  self._draw(self._hbg)
    def _on_leave(self, e):  self._draw(self._bg)
    def _on_press(self, e):  self._draw(self._pbg)
    def _on_release(self, e):
        self._draw(self._hbg)
        if self._command:
            self._command()

    def config(self, **kw):
        # 允許外部更新 text
        if "text" in kw:
            self._text = kw.pop("text")
            self.after_idle(lambda: self._draw(self._current_bg))
        super().config(**kw)

    # 讓 pack/grid/place 正常工作
    def pack(self, **kw):   super().pack(**kw)
    def grid(self, **kw):   super().grid(**kw)
    def place(self, **kw):  super().place(**kw)


class CameraSession:
    def __init__(self, cam_id: int):
        self.cam_id  = cam_id
        self.cap     = None
        self.running = False
        self.current_frame = None
        self.display_frame = None

        self.measurement_mode    = "none"
        self.pending_points: list[tuple] = []
        self.measurement_results: list[dict] = []
        self.max_measurements    = 10
        self._rep_data: list[float] = []

        self.is_calibrated        = False
        self.scale_factor         = 1.0
        self.calibration_distance = 1.0
        self.pixel_size_um        = 5.0
        self.magnification        = 50.0

        self.current_barcode   : str | None = None
        self.barcode_history   : list[str]  = []
        self.last_barcode_time : float      = 0.0
        self.frame_count       : int        = 0
        self.scan_interval     : int        = 4

        self.display_scale  = 1.0
        self.display_offset = (0, 0)

        self.crosshair_visible = False
        self.crosshair_x = 0
        self.crosshair_y = 0

        # ── 曝光狀態 ──────────────────────────────────────────
        self.manual_exposure_applied = False   # 是否已套用手動曝光
        self.microscope_mode         = False   # True=顯微鏡模式(關AE/AWB) False=一般模式(保留AWB)

    def release(self):
        self.running = False
        if self.cap:
            self.cap.release()
            self.cap = None


# ══════════════════════════════════════════════════════════════
#  DinoLiteApp
# ══════════════════════════════════════════════════════════════
class DinoLiteApp:

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title(f"多鏡頭測量系統  {VERSION}")
        self.root.geometry("1440x960")
        self.root.minsize(1150, 760)
        self.root.configure(bg=P["bg"])

        self.sessions          : list[CameraSession] = []
        self.available_cameras : list[dict]          = []
        self.active_session_idx: int                 = 0
        self.save_directory    : str                 = os.getcwd()

        self.handheld_enabled    = False
        self.handheld_buffer     = ""
        self.handheld_last_time  = 0.0
        self.handheld_timeout_ms = 100

        self._update_after_id = None
        self._capture_mode    = "single"   # "single" | "all_merged" | "all_individual"

        self._apply_theme()
        self._build_ui()
        self._bind_keys()

    # ══════════════════════════════════════════════════════════
    #  TTK 主題
    # ══════════════════════════════════════════════════════════
    def _apply_theme(self):
        s = ttk.Style(self.root)
        s.theme_use("clam")

        s.configure(".",
            background=P["bg"], foreground=P["text_h2"],
            font=F(12), borderwidth=0, focuscolor=P["accent"])

        s.configure("TFrame",       background=P["bg"])
        s.configure("Panel.TFrame", background=P["panel"])
        s.configure("Card.TFrame",  background=P["card"])

        s.configure("TLabel",
            background=P["bg"], foreground=P["text_h2"], font=F(12))
        s.configure("H1.TLabel",
            background=P["bg"], foreground=P["text_h1"], font=F(15, bold=True))
        s.configure("H2.TLabel",
            background=P["panel"], foreground=P["text_h2"], font=F(12, bold=True))
        s.configure("Dim.TLabel",
            background=P["panel"], foreground=P["text_body"], font=F(11))
        s.configure("Hint.TLabel",
            background=P["panel"], foreground=P["text_dim"], font=F(11))
        s.configure("Value.TLabel",
            background=P["card"], foreground=P["accent_glow"], font=F(12, bold=True))
        s.configure("Good.TLabel",
            background=P["panel"], foreground=P["green"], font=F(12, bold=True))
        s.configure("Warn.TLabel",
            background=P["panel"], foreground=P["orange"], font=F(12, bold=True))
        s.configure("Bad.TLabel",
            background=P["panel"], foreground=P["red"], font=F(12, bold=True))

        s.configure("TLabelframe",
            background=P["panel"], foreground=P["accent_glow"],
            font=F(12, bold=True), bordercolor=P["border"],
            relief="groove", borderwidth=1)
        s.configure("TLabelframe.Label",
            background=P["panel"], foreground=P["accent_glow"],
            font=F(12, bold=True))

        s.configure("TButton",
            background=P["card"], foreground=P["text_h2"],
            font=F(12), borderwidth=1, relief="flat", padding=(10, 6))
        s.map("TButton",
            background=[("active", P["card_hover"]), ("pressed", P["accent_dk"])],
            foreground=[("active", P["text_h1"]),    ("pressed", P["text_h1"])],
            relief=[("pressed", "flat")])

        s.configure("Accent.TButton",
            background=P["accent"], foreground=P["text_h1"],
            font=F(12, bold=True), padding=(10, 6))
        s.map("Accent.TButton",
            background=[("active", P["accent_glow"]), ("pressed", P["accent_dk"])],
            foreground=[("active", P["bg"]),           ("pressed", P["text_h1"])])

        s.configure("Green.TButton",
            background=P["green"], foreground=P["green_txt"],
            font=F(12, bold=True), padding=(10, 6))
        s.map("Green.TButton",
            background=[("active", P["green_dk"]), ("pressed", "#1A7A48")],
            foreground=[("active", "#FFFFFF"),      ("pressed", "#FFFFFF")])

        s.configure("Red.TButton",
            background=P["red"], foreground=P["red_txt"],
            font=F(12, bold=True), padding=(10, 6))
        s.map("Red.TButton",
            background=[("active", P["red_dk"]), ("pressed", "#A01010")],
            foreground=[("active", "#FFFFFF"),    ("pressed", "#FFFFFF")])

        s.configure("Orange.TButton",
            background=P["orange"], foreground="#1A0A00",
            font=F(12, bold=True), padding=(10, 6))
        s.map("Orange.TButton",
            background=[("active", P["yellow"]), ("pressed", "#C07010")],
            foreground=[("active", "#1A0A00"),    ("pressed", "#1A0A00")])

        s.configure("TEntry",
            fieldbackground=P["input_bg"], foreground=P["text_h1"],
            insertcolor=P["accent_glow"], bordercolor=P["border"],
            font=F(12), padding=4)
        s.map("TEntry",
            bordercolor=[("focus", P["border_hi"])],
            fieldbackground=[("focus", P["card"])])

        s.configure("TCombobox",
            fieldbackground=P["input_bg"], background=P["card"],
            foreground=P["text_h1"], selectbackground=P["accent"],
            selectforeground=P["text_h1"], arrowcolor=P["accent"],
            font=F(12), padding=4)
        s.map("TCombobox",
            fieldbackground=[("readonly", P["input_bg"])],
            foreground=[("readonly", P["text_h1"])],
            bordercolor=[("focus", P["border_hi"])])

        s.configure("TScale",
            background=P["panel"], troughcolor=P["card"],
            sliderlength=18, sliderrelief="flat")

        s.configure("TCheckbutton",
            background=P["panel"], foreground=P["text_h2"],
            indicatorcolor=P["input_bg"], font=F(12))
        s.map("TCheckbutton",
            indicatorcolor=[("selected", P["accent"]), ("active", P["accent_glow"])],
            foreground=[("active", P["text_h1"])])

        s.configure("TScrollbar",
            background=P["card"], troughcolor=P["panel"],
            arrowcolor=P["text_dim"], borderwidth=0, arrowsize=12)

        s.configure("Horizontal.TProgressbar",
            troughcolor=P["card"], background=P["accent"], borderwidth=0)

    # ══════════════════════════════════════════════════════════
    #  UI 主架構
    # ══════════════════════════════════════════════════════════
    def _build_ui(self):
        # ── 語言狀態（預設中文） ──────────────────────────────
        self._lang = "zh"   # "zh" | "jp"

        self._build_topbar()
        self._build_toolbar_strip()   # ★ 新：頂部檔案操作橫列

        body = ttk.Frame(self.root, style="TFrame")
        body.pack(fill="both", expand=True, padx=8, pady=(4, 0))

        self.left_panel = tk.Frame(body, bg=P["panel"], width=320)
        self.left_panel.pack(side="left", fill="y", padx=(0, 6))
        self.left_panel.pack_propagate(False)
        self._build_left_panel()

        self.right_panel = ttk.Frame(body, style="TFrame")
        self.right_panel.pack(side="right", fill="both", expand=True)
        self._build_camera_area()

        self._build_statusbar()

    # ── 頂部工具列 ──────────────────────────────────────────────
    def _build_topbar(self):
        bar = tk.Frame(self.root, bg=P["card"], height=64)
        bar.pack(fill="x")
        bar.pack_propagate(False)

        lf = tk.Frame(bar, bg=P["card"])
        lf.pack(side="left", padx=16, pady=10)
        tk.Label(lf, text="🔬", font=(_FONT_PRIMARY, 22),
                 bg=P["card"], fg=P["accent_glow"]).pack(side="left")
        self.title_lbl = tk.Label(lf, text="  多鏡頭測量系統",
                 font=F(16, bold=True),
                 bg=P["card"], fg=P["text_h1"])
        self.title_lbl.pack(side="left")

        rf = tk.Frame(bar, bg=P["card"])
        rf.pack(side="right", padx=14, pady=10)

        # 日語切換按鈕
        self.lang_btn = tk.Button(
            rf, text="🇯🇵  日語切換",
            command=self._toggle_language,
            bg=P["card"], fg=P["text_dim"],
            font=F(12), relief="flat", padx=10, pady=5,
            activebackground=P["card_hover"],
            activeforeground=P["text_h1"],
            cursor="hand2", bd=1,
            highlightbackground=P["border"],
            highlightthickness=1)
        self.lang_btn.pack(side="right", padx=5)

        # 使用說明按鈕
        self.help_btn = tk.Button(
            rf, text="❓  使用說明",
            command=self._show_help,
            bg=P["accent"], fg=P["text_h1"],
            font=F(12), relief="flat", padx=12, pady=5,
            activebackground=P["accent_glow"],
            activeforeground=P["bg"],
            cursor="hand2", bd=0)
        self.help_btn.pack(side="right", padx=5)

        # 關閉其他程式按鈕
        self.close_other_btn = tk.Button(
            rf, text="⚙   關閉其他程式",
            command=self._close_other_progs,
            bg=P["card"], fg=P["text_dim"],
            font=F(12), relief="flat", padx=12, pady=5,
            activebackground=P["accent"],
            activeforeground=P["text_h1"],
            cursor="hand2", bd=0)
        self.close_other_btn.pack(side="right", padx=5)

    # ── 頂部檔案操作橫列 ────────────────────────────────────────
    def _build_toolbar_strip(self):
        """
        檔案操作工具列：固定在視窗頂部（標題列下方），
        使用者不需要捲動左側面板即可存取所有檔案功能。
        """
        strip = tk.Frame(self.root, bg=P["card"], height=54)
        strip.pack(fill="x")
        strip.pack_propagate(False)

        # 分隔線
        tk.Frame(self.root, bg=P["border"], height=1).pack(fill="x")

        # ── 儲存路徑區 ────────────────────────────────────────
        path_wrap = tk.Frame(strip, bg=P["card"])
        path_wrap.pack(side="left", padx=10, pady=6, fill="x")

        self.tb_path_icon = tk.Label(
            path_wrap, text="📁",
            bg=P["card"], fg=P["orange"], font=F(13))
        self.tb_path_icon.pack(side="left")

        self.savedir_lbl = tk.Label(
            path_wrap,
            text=self._short_path(self.save_directory, 45),
            bg=P["input_bg"], fg=P["accent_glow"],
            font=F(11), anchor="w", padx=8, pady=3,
            width=38)
        self.savedir_lbl.pack(side="left", padx=(4, 0))

        self.tb_sel_btn = RoundButton(
            path_wrap, text="選擇路徑",
            command=self._select_savedir,
            bg=P["orange"], fg="#1A0800",
            hover_bg=P["yellow"], press_bg="#C07010",
            font=F(11, bold=True), padx=10, pady=4,
            radius=8)
        self.tb_sel_btn.pack(side="left", padx=(6, 0))

        # ── 分隔線 ────────────────────────────────────────────
        tk.Frame(strip, bg=P["border"], width=1).pack(
            side="left", fill="y", pady=8, padx=8)

        # ── 操作按鈕群 ────────────────────────────────────────
        cap_outer = tk.Frame(strip, bg=P["card"])
        cap_outer.pack(side="left", padx=4, pady=3)

        cap_frame = tk.Frame(cap_outer, bg=P["card"])
        cap_frame.pack()

        self._cap_main_btn = RoundButton(
            cap_frame, text="📷  拍照",
            command=self._do_capture,
            bg=P["green"], fg=P["green_txt"],
            hover_bg=P["green_dk"], press_bg="#1A7A48",
            font=F(12, bold=True), padx=12, pady=5,
            radius=8)
        self._cap_main_btn.pack(side="left")

        self._cap_arrow_btn = RoundButton(
            cap_frame, text="▼",
            command=self._show_capture_menu,
            bg=P["green_dk"], fg=P["green_txt"],
            hover_bg=P["green"], press_bg="#1A7A48",
            font=F(10, bold=True), padx=7, pady=5,
            radius=8)
        self._cap_arrow_btn.pack(side="left", padx=(2, 0))

        self._cap_mode_lbl = tk.Label(
            cap_outer,
            text="▸ 目前鏡頭",
            bg=P["card"], fg=P["text_dim"],
            font=F(9))
        self._cap_mode_lbl.pack(pady=(1, 0))

        self._tb_action_btns = {"capture_main": self._cap_main_btn,
                                 "capture_arrow": self._cap_arrow_btn}

        btn_round_defs = [
            ("💾  儲存",  "save",   self._save_image,     P["accent"],  P["text_h1"],  P["accent_glow"], P["accent_dk"]),
            ("📤  匯出",  "export", self._export_results, P["card"],    P["text_h2"],  P["card_hover"],  P["bg"]),
        ]
        for label, key, cmd, bg, fg, hbg, pbg in btn_round_defs:
            f = tk.Frame(strip, bg=P["card"])
            f.pack(side="left", padx=4, pady=5)
            btn = RoundButton(
                f, text=label,
                command=cmd,
                bg=bg, fg=fg,
                hover_bg=hbg, press_bg=pbg,
                font=F(12, bold=True), padx=12, pady=5,
                radius=8)
            btn.pack()
            self._tb_action_btns[key] = btn

    # ── 左側控制面板 ────────────────────────────────────────────
    def _build_left_panel(self):
        # ── 語言對照 Registry（供 _apply_language 批次更新） ──
        self._sec_map  = {}   # {LabelFrame: key}
        self._lbl_map  = {}   # {Label: key}
        self._btn_map  = {}   # {Button/ttk.Button: key}

        lp = self.left_panel

        wrap_canvas = tk.Canvas(lp, bg=P["panel"], highlightthickness=0)
        vsb = ttk.Scrollbar(lp, orient="vertical", command=wrap_canvas.yview)
        wrap_canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        wrap_canvas.pack(side="left", fill="both", expand=True)

        inner  = tk.Frame(wrap_canvas, bg=P["panel"])
        win_id = wrap_canvas.create_window((0, 0), window=inner, anchor="nw")

        def _cfg_scroll(e):
            wrap_canvas.configure(scrollregion=wrap_canvas.bbox("all"))
        def _cfg_width(e):
            wrap_canvas.itemconfig(win_id, width=e.width)
        inner.bind("<Configure>", _cfg_scroll)
        wrap_canvas.bind("<Configure>", _cfg_width)

        def _on_wheel(e):
            wrap_canvas.yview_scroll(-1 if e.delta > 0 else 1, "units")

        # ★ 使用 bind（非 bind_all），並配合 Enter/Leave 動態掛載/卸載，
        #   確保滾輪只在滑鼠進入左側面板時才作用，
        #   不影響使用說明視窗或其他元件的捲動。
        def _on_enter(e):
            wrap_canvas.bind_all("<MouseWheel>", _on_wheel)
        def _on_leave(e):
            wrap_canvas.unbind_all("<MouseWheel>")

        wrap_canvas.bind("<Enter>", _on_enter)
        wrap_canvas.bind("<Leave>", _on_leave)
        inner.bind("<Enter>", _on_enter)
        inner.bind("<Leave>", _on_leave)

        def sec(title, key=""):
            return self._section(inner, title, key)

        pad  = dict(padx=8, pady=3, fill="x")
        pad2 = dict(padx=8, pady=2, fill="x")

        def hline():
            tk.Frame(inner, bg=P["divider"], height=1).pack(
                fill="x", padx=8, pady=4)

        # ══════════════════════════════════════════════════════
        #  § 1  攝影機管理
        # ══════════════════════════════════════════════════════
        f1 = sec("① 攝影機管理", "sec1")

        _detect_btn = self._btn(f1, "🔍  偵測所有攝影機",
                  self._detect_cameras, "Accent")
        _detect_btn.pack(**pad)
        self._btn_map[_detect_btn] = "detect"

        self._cam_sel_lbl = tk.Label(f1, text="選擇鏡頭：",
                 bg=P["panel"], fg=P["text_body"], font=F(11))
        self._cam_sel_lbl.pack(padx=8, pady=(4, 0), anchor="w")
        self._lbl_map[self._cam_sel_lbl] = "cam_sel"
        self.camera_list_var = tk.StringVar()
        self.camera_combo = ttk.Combobox(f1, textvariable=self.camera_list_var,
                                         state="readonly", font=F(12))
        self.camera_combo.pack(**pad2)

        btn_r1 = tk.Frame(f1, bg=P["panel"])
        btn_r1.pack(**pad2)
        _open_btn = self._btn(btn_r1, "▶  開啟", self._open_selected_camera, "Green")
        _open_btn.pack(side="left", expand=True, fill="x", padx=(0, 4))
        self._btn_map[_open_btn] = "open"
        _close_btn = self._btn(btn_r1, "■  關閉", self._close_selected_camera, "Red")
        _close_btn.pack(side="left", expand=True, fill="x")
        self._btn_map[_close_btn] = "close"

        self.cam_status_label = tk.Label(
            f1, text="● 無啟用鏡頭",
            bg=P["panel"], fg=P["red"], font=F(11, bold=True))
        self.cam_status_label.pack(padx=8, pady=2, anchor="w")

        self._active_lbl = tk.Label(f1, text="操作目標鏡頭：",
                 bg=P["panel"], fg=P["text_body"], font=F(11))
        self._active_lbl.pack(padx=8, pady=(4, 0), anchor="w")
        self._lbl_map[self._active_lbl] = "active"
        self.active_cam_var = tk.StringVar()
        self.active_cam_combo = ttk.Combobox(f1, textvariable=self.active_cam_var,
                                             state="readonly", font=F(12))
        self.active_cam_combo.pack(**pad2)
        self.active_cam_combo.bind("<<ComboboxSelected>>",
                                   self._on_active_cam_changed)

        hline()

        # ══════════════════════════════════════════════════════
        #  § 2  鏡頭設定
        # ══════════════════════════════════════════════════════
        f2 = sec("② 鏡頭設定", "sec2")

        # ── 曝光控制區塊 ─────────────────────────────────────
        tk.Frame(f2, bg=P["divider"], height=1).pack(
            fill="x", padx=8, pady=(6, 4))

        self._exp_title_lbl = tk.Label(f2,
                 text="📷 畫面曝光控制",
                 bg=P["panel"], fg=P["yellow"], font=F(11, bold=True))
        self._exp_title_lbl.pack(padx=8, anchor="w")
        self._lbl_map[self._exp_title_lbl] = "exp_title"

        # ★ 模式切換：一般攝影機 / 顯微鏡
        mode_row = tk.Frame(f2, bg=P["panel"])
        mode_row.pack(padx=8, pady=(2, 4), fill="x")
        self.cam_mode_var = tk.IntVar(value=0)

        self._rb_normal = tk.Radiobutton(
            mode_row, text="一般攝影機",
            variable=self.cam_mode_var, value=0,
            command=self._on_cam_mode_changed,
            bg=P["panel"], fg=P["text_h2"],
            selectcolor=P["card"],
            activebackground=P["panel"],
            activeforeground=P["text_h1"],
            font=F(11))
        self._rb_normal.pack(side="left", padx=(0, 8))

        self._rb_micro = tk.Radiobutton(
            mode_row, text="顯微鏡（關閉 AE+AWB）",
            variable=self.cam_mode_var, value=1,
            command=self._on_cam_mode_changed,
            bg=P["panel"], fg=P["yellow"],
            selectcolor=P["card"],
            activebackground=P["panel"],
            activeforeground=P["yellow"],
            font=F(11))
        self._rb_micro.pack(side="left")

        self.cam_mode_hint = tk.Label(
            f2,
            text="💡 一般攝影機請選「一般」；電子顯微鏡請選「顯微鏡」",
            bg=P["panel"], fg=P["text_hint"], font=F(10),
            wraplength=260, justify="left")
        self.cam_mode_hint.pack(padx=8, anchor="w")

        # 曝光值滑桿  -13（暗）~ -1（亮）
        ef = tk.Frame(f2, bg=P["panel"])
        ef.pack(**pad2)
        self._exp_lbl = tk.Label(ef, text="曝光值：",
                 bg=P["panel"], fg=P["text_h2"], font=F(11))
        self._exp_lbl.pack(side="left")
        self._lbl_map[self._exp_lbl] = "exp_lbl"
        self.exp_val_lbl = tk.Label(ef, text=str(EXPOSURE_DEFAULT),
                                    bg=P["panel"], fg=P["accent_glow"],
                                    font=F(11, bold=True), width=4)
        self.exp_val_lbl.pack(side="right")

        self.exp_var = tk.IntVar(value=EXPOSURE_DEFAULT)
        self.exp_scale = ttk.Scale(f2, from_=-13, to=-1, orient="horizontal",
                                   variable=self.exp_var,
                                   command=lambda v: self._on_exp_change(v))
        self.exp_scale.pack(padx=8, pady=2, fill="x")

        self._exp_hint_lbl = tk.Label(f2, text="  ← 暗（-13）          亮（-1）→",
                 bg=P["panel"], fg=P["text_hint"], font=F(10))
        self._exp_hint_lbl.pack(padx=8, anchor="w")
        self._lbl_map[self._exp_hint_lbl] = "exp_hint"

        # 增益滑桿  0 ~ 100
        gf = tk.Frame(f2, bg=P["panel"])
        gf.pack(**pad2)
        self._gain_lbl = tk.Label(gf, text="增益 Gain：",
                 bg=P["panel"], fg=P["text_h2"], font=F(11))
        self._gain_lbl.pack(side="left")
        self._lbl_map[self._gain_lbl] = "gain_lbl"
        self.gain_val_lbl = tk.Label(gf, text=str(GAIN_DEFAULT),
                                     bg=P["panel"], fg=P["accent_glow"],
                                     font=F(11, bold=True), width=4)
        self.gain_val_lbl.pack(side="right")

        self.gain_var = tk.IntVar(value=GAIN_DEFAULT)
        self.gain_scale = ttk.Scale(f2, from_=0, to=100, orient="horizontal",
                                    variable=self.gain_var,
                                    command=lambda v: self._on_gain_change(v))
        self.gain_scale.pack(padx=8, pady=2, fill="x")

        # 亮度補償  0 ~ 255
        bf2 = tk.Frame(f2, bg=P["panel"])
        bf2.pack(**pad2)
        self._bright_lbl = tk.Label(bf2, text="亮度補償：",
                 bg=P["panel"], fg=P["text_h2"], font=F(11))
        self._bright_lbl.pack(side="left")
        self._lbl_map[self._bright_lbl] = "bright_lbl"
        self.bright_val_lbl = tk.Label(bf2, text=str(BRIGHT_DEFAULT),
                                       bg=P["panel"], fg=P["accent_glow"],
                                       font=F(11, bold=True), width=4)
        self.bright_val_lbl.pack(side="right")

        self.bright_var = tk.IntVar(value=BRIGHT_DEFAULT)
        self.bright_scale = ttk.Scale(f2, from_=0, to=255, orient="horizontal",
                                      variable=self.bright_var,
                                      command=lambda v: self._on_bright_change(v))
        self.bright_scale.pack(padx=8, pady=2, fill="x")

        # 套用按鈕
        _apply_btn = self._btn(f2, "✅  套用曝光設定至目標鏡頭",
                  self._apply_exposure_to_active, "Accent")
        _apply_btn.pack(**pad)
        self._btn_map[_apply_btn] = "apply_exp"

        self.exp_sliders_note = tk.Label(
            f2,
            text="↑ 曝光/增益滑桿僅對「顯微鏡模式」有效",
            bg=P["panel"], fg=P["text_hint"], font=F(10))
        self.exp_sliders_note.pack(padx=8, anchor="w")
        self._lbl_map[self.exp_sliders_note] = "exp_note"

        # 曝光狀態標籤
        self.exp_status_lbl = tk.Label(
            f2, text="● 曝光：尚未設定",
            bg=P["panel"], fg=P["text_dim"], font=F(11))
        self.exp_status_lbl.pack(padx=8, anchor="w", pady=2)

        hline()

        # ══════════════════════════════════════════════════════
        #  § 3  校準
        # ══════════════════════════════════════════════════════
        f3 = sec("③ 校準", "sec3")

        cf = tk.Frame(f3, bg=P["panel"])
        cf.pack(**pad2)
        self._cal_dist_lbl = tk.Label(cf, text="已知距離(mm)：",
                 bg=P["panel"], fg=P["text_h2"], font=F(12))
        self._cal_dist_lbl.pack(side="left")
        self._lbl_map[self._cal_dist_lbl] = "cal_dist"
        self.cal_entry = ttk.Entry(cf, width=8, font=F(12))
        self.cal_entry.insert(0, "1.0")
        self.cal_entry.pack(side="left", padx=4)

        _cal_btn = self._btn(f3, "🎯  開始校準（點選兩點）", self._start_calibration)
        _cal_btn.pack(**pad)
        self._btn_map[_cal_btn] = "cal_btn"

        self.cal_status_lbl = tk.Label(
            f3, text="● 尚未校準",
            bg=P["panel"], fg=P["orange"], font=F(11, bold=True))
        self.cal_status_lbl.pack(padx=8, anchor="w", pady=2)

        hline()

        # ══════════════════════════════════════════════════════
        #  § 4  測量工具
        # ══════════════════════════════════════════════════════
        f4 = sec("④ 測量工具", "sec4")

        for label, mode, key in [
            ("📏  距離測量  (2點)", "distance", "m_dist"),
            ("📐  角度測量  (3點)", "angle",    "m_angle"),
            ("⭕  直徑測量  (3點)", "diameter", "m_diam"),
        ]:
            _mb = self._btn(f4, label, lambda m=mode: self._set_mode(m))
            _mb.pack(**pad)
            self._btn_map[_mb] = key

        ur = tk.Frame(f4, bg=P["panel"])
        ur.pack(**pad2)
        _undo_btn = self._btn(ur, "↩  撤銷上次", self._undo_last)
        _undo_btn.pack(side="left", expand=True, fill="x", padx=(0, 4))
        self._btn_map[_undo_btn] = "undo"
        _clear_btn = self._btn(ur, "🗑  清除全部", self._clear_all, "Red")
        _clear_btn.pack(side="left", expand=True, fill="x")
        self._btn_map[_clear_btn] = "clear"

        self.mode_lbl = tk.Label(
            f4, text="模式：無",
            bg=P["panel"], fg=P["text_dim"], font=F(11))
        self.mode_lbl.pack(padx=8, anchor="w", pady=2)

        hline()

        # ══════════════════════════════════════════════════════
        #  § 5  精度驗證
        # ══════════════════════════════════════════════════════
        f5 = sec("⑤ 精度驗證", "sec5")
        _rep_btn = self._btn(f5, "🔁  重複性測試（5次）", self._start_repeatability)
        _rep_btn.pack(**pad)
        self._btn_map[_rep_btn] = "rep_btn"
        _acc_btn = self._btn(f5, "📖  精度指南", self._show_accuracy_guide)
        _acc_btn.pack(**pad)
        self._btn_map[_acc_btn] = "acc_btn"

        hline()

        # ══════════════════════════════════════════════════════
        #  § 6  條碼掃描
        # ══════════════════════════════════════════════════════
        f6 = sec("⑥ 條碼掃描", "sec6")

        if BARCODE_AVAILABLE:
            self.barcode_cam_var  = tk.BooleanVar(value=False)
            self.barcode_hand_var = tk.BooleanVar(value=False)

            self._cb_cam_scan = ttk.Checkbutton(
                f6,
                text=f"攝影機條碼掃描 ({BARCODE_LIBRARY})",
                variable=self.barcode_cam_var,
                command=self._update_scanner_status,
                style="TCheckbutton")
            self._cb_cam_scan.pack(**pad2)

            self._cb_hand_scan = ttk.Checkbutton(
                f6,
                text="手持掃描器輸入",
                variable=self.barcode_hand_var,
                command=self._toggle_handheld,
                style="TCheckbutton")
            self._cb_hand_scan.pack(**pad2)

            self.scanner_status_lbl = tk.Label(
                f6, text="掃描器：待機",
                bg=P["panel"], fg=P["text_dim"], font=F(11))
            self.scanner_status_lbl.pack(padx=8, anchor="w")

            self._bc_latest_lbl = tk.Label(f6, text="最新條碼：",
                     bg=P["panel"], fg=P["text_body"], font=F(11))
            self._bc_latest_lbl.pack(padx=8, pady=(6, 0), anchor="w")
            self._lbl_map[self._bc_latest_lbl] = "bc_latest"
            self.barcode_display_lbl = tk.Label(
                f6, text="—",
                bg=P["card"], fg=P["accent_glow"], font=F(12, bold=True),
                anchor="w", padx=6, pady=3, relief="flat")
            self.barcode_display_lbl.pack(padx=8, fill="x")

            self._bc_history_lbl = tk.Label(f6, text="掃描歷史：",
                     bg=P["panel"], fg=P["text_body"], font=F(11))
            self._bc_history_lbl.pack(padx=8, pady=(6, 0), anchor="w")
            self._lbl_map[self._bc_history_lbl] = "bc_history"

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

            _bcc_btn = self._btn(f6, "🗑  清除條碼歷史",
                      self._clear_barcode_history)
            _bcc_btn.pack(**pad2)
            self._btn_map[_bcc_btn] = "bc_clear"
        else:
            tk.Label(
                f6,
                text="⚠ 條碼庫未安裝\npip install zxing-cpp",
                bg=P["panel"], fg=P["orange"], font=F(11),
                justify="left").pack(padx=8, pady=6, anchor="w")

        hline()

        # ══════════════════════════════════════════════════════
        #  § 7  測量日誌  （原§8，檔案操作已移至頂部橫列）
        # ══════════════════════════════════════════════════════
        f8 = sec("⑦ 測量日誌", "sec7")

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

        tb = tk.Frame(rp, bg=P["card"], height=42)
        tb.pack(fill="x")
        tb.pack_propagate(False)

        self._img_area_lbl = tk.Label(tb, text="影像顯示區",
                 bg=P["card"], fg=P["text_dim"], font=F(12))
        self._img_area_lbl.pack(side="left", padx=10, pady=8)

        self._pause_btn = tk.Button(tb, text="⏸  全部暫停 / 恢復",
                  command=self._toggle_all_cameras,
                  bg=P["card"], fg=P["text_h2"],
                  font=F(12), relief="flat",
                  activebackground=P["accent"],
                  activeforeground=P["text_h1"],
                  cursor="hand2", padx=10, bd=0)
        self._pause_btn.pack(side="right", padx=10, pady=5)

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
                     font=F(15)).place(relx=.5, rely=.5, anchor="center")
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

        hdr = tk.Frame(outer, bg=P["card"], height=34)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)

        tk.Label(hdr, text=f"  ● Camera {idx}",
                 bg=P["card"], fg=cam_hex,
                 font=F(12, bold=True)).pack(side="left", padx=6)
        tk.Label(hdr, text="( 點擊切換操作目標 )",
                 bg=P["card"], fg=P["text_hint"],
                 font=F(10)).pack(side="left")

        hdr.bind("<Button-1>", lambda e, i=idx: self._switch_active_cam(i))

        cv = tk.Canvas(outer, bg=P["canvas_bg"],
                       highlightthickness=0, cursor="crosshair")
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
        bar = tk.Frame(self.root, bg=P["card"], height=34)
        bar.pack(fill="x", side="bottom")
        bar.pack_propagate(False)

        tk.Frame(self.root, bg=P["border"], height=1).pack(
            fill="x", side="bottom")

        self.status_lbl = tk.Label(
            bar, text="就緒",
            bg=P["card"], fg=P["text_body"],
            font=F(11), anchor="w")
        self.status_lbl.pack(side="left", padx=12, fill="x", expand=True)

        self.ver_lbl = tk.Label(bar, text=f"{VERSION}  {VERSION_DATE}",
                 bg=P["card"], fg=P["accent_glow"],
                 font=F(11, bold=True))
        self.ver_lbl.pack(side="right", padx=14)
        tk.Label(bar, text="│",
                 bg=P["card"], fg=P["text_hint"],
                 font=F(12)).pack(side="right")

        pil_txt = "PIL ✓" if PIL_AVAILABLE else "PIL ✗"
        pil_col = P["green"] if PIL_AVAILABLE else P["red"]
        tk.Label(bar, text=pil_txt,
                 bg=P["card"], fg=pil_col,
                 font=F(11)).pack(side="right", padx=8)

        bc_txt = f"Barcode ✓ {BARCODE_LIBRARY}" if BARCODE_AVAILABLE else "Barcode ✗"
        bc_col = P["green"] if BARCODE_AVAILABLE else P["text_hint"]
        tk.Label(bar, text=bc_txt,
                 bg=P["card"], fg=bc_col,
                 font=F(11)).pack(side="right", padx=8)

    # ══════════════════════════════════════════════════════════
    #  Helper Widgets
    # ══════════════════════════════════════════════════════════
    def _btn(self, parent, text: str, cmd,
             style: str = "Normal") -> RoundButton:
        """建立圓角按鈕，顏色依 style 參數對應"""
        style_map = {
            "Accent": (P["accent"],  P["text_h1"],  P["accent_glow"], P["accent_dk"]),
            "Green":  (P["green"],   P["green_txt"],P["green_dk"],    "#1A7A48"),
            "Red":    (P["red"],     P["red_txt"],  P["red_dk"],      "#A01010"),
            "Orange": (P["orange"],  "#1A0A00",     P["yellow"],      "#C07010"),
            "Normal": (P["card"],    P["text_h2"],  P["card_hover"],  P["accent_dk"]),
        }
        bg, fg, hbg, pbg = style_map.get(style, style_map["Normal"])
        return RoundButton(parent, text=text, command=cmd,
                           bg=bg, fg=fg,
                           hover_bg=hbg, press_bg=pbg,
                           font=F(12, bold=True),
                           padx=10, pady=5,
                           radius=8)

    def _section(self, parent, title: str, lang_key: str = "") -> tk.Frame:
        lf = tk.LabelFrame(parent,
                           text=f"  {title}  ",
                           bg=P["panel"],
                           fg=P["accent_glow"],
                           font=F(12, bold=True),
                           bd=1, relief="groove",
                           labelanchor="nw")
        lf.pack(fill="x", padx=8, pady=4)
        if lang_key and hasattr(self, "_sec_map"):
            self._sec_map[lf] = lang_key
        return lf

    def _short_path(self, path: str, n: int = 38) -> str:
        return path if len(path) <= n else "…" + path[-(n - 1):]

    # ══════════════════════════════════════════════════════════
    #  曝光控制
    # ══════════════════════════════════════════════════════════
    def _on_cam_mode_changed(self):
        """模式 Radio 切換：自動對目前操作鏡頭套用對應設定"""
        sess = self._active_session()
        if not sess:
            return
        if self.cam_mode_var.get() == 1:
            self._apply_microscope_exposure(sess)
        else:
            self._reset_to_auto(sess)

    def _reset_to_auto(self, sess: CameraSession):
        """
        一般攝影機模式：恢復自動曝光 + 自動白平衡。
        解決強制關 AWB 導致的青綠色偏問題。
        """
        if not (sess.cap and sess.cap.isOpened()):
            return
        cap = sess.cap
        cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 3)   # 3=自動
        cap.set(cv2.CAP_PROP_AUTO_WB, 1)          # 開啟 AWB
        cap.set(cv2.CAP_PROP_GAIN, -1)            # 交給驅動
        cap.set(cv2.CAP_PROP_BRIGHTNESS, 128)     # 中間值

        sess.manual_exposure_applied = False
        sess.microscope_mode         = False
        self.exp_status_lbl.config(
            text="● 曝光：自動 AE+AWB（一般模式）",
            fg=P["text_dim"])
        self._log(f"[Cam{sess.cam_id}] 恢復自動曝光 + 自動白平衡（一般模式）")

    def _apply_microscope_exposure(self, sess: CameraSession):
        """
        顯微鏡模式：關閉 AE + AWB，套用手動曝光值。

        ★ 為什麼要做這件事：
          電子顯微鏡鏡頭視野小，AE 將高亮樣品誤判為「整體過亮」
          並自動壓暗，造成畫面暗沉。鎖定手動曝光可完全消除此問題。

        ⚠ 一般攝影機請勿在此模式下使用，關 AWB 會造成色偏。
        """
        if not (sess.cap and sess.cap.isOpened()):
            return

        cap  = sess.cap
        exp  = self.exp_var.get()
        gain = self.gain_var.get()
        bri  = self.bright_var.get()
        results = []

        ae_ok   = cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 1)    # 1=手動
        results.append(f"AE關閉={'✓' if ae_ok else '△'}")

        exp_ok  = cap.set(cv2.CAP_PROP_EXPOSURE, exp)
        results.append(f"EXP={exp}({'✓' if exp_ok else '△'})")

        awb_ok  = cap.set(cv2.CAP_PROP_AUTO_WB, 0)
        results.append(f"AWB關閉={'✓' if awb_ok else '△'}")

        gain_ok = cap.set(cv2.CAP_PROP_GAIN, gain)
        results.append(f"Gain={gain}({'✓' if gain_ok else '△'})")

        bri_ok  = cap.set(cv2.CAP_PROP_BRIGHTNESS, bri)
        results.append(f"Bright={bri}({'✓' if bri_ok else '△'})")

        sess.manual_exposure_applied = True
        sess.microscope_mode         = True
        self._log(f"[Cam{sess.cam_id}] 顯微鏡曝光套用：{'  '.join(results)}")

        ok_count = sum(1 for r in [ae_ok, exp_ok, gain_ok] if r)
        txt = (f"● 曝光：顯微鏡手動 EXP={exp}  Gain={gain}"
               if ok_count >= 2
               else "● 曝光：顯微鏡模式（部分設定 △）")
        self.exp_status_lbl.config(
            text=txt,
            fg=P["green"] if ok_count >= 2 else P["orange"])

    def _apply_exposure_to_active(self):
        """UI 套用按鈕：依目前模式 Radio 對目標鏡頭套用設定"""
        sess = self._active_session()
        if not sess:
            messagebox.showwarning("提示", "請先開啟攝影機")
            return
        if self.cam_mode_var.get() == 1:
            self._apply_microscope_exposure(sess)
        else:
            self._reset_to_auto(sess)
        self._set_status(f"[Camera {sess.cam_id}] 曝光設定已更新")

    def _on_exp_change(self, v):
        val = int(float(v))
        self.exp_val_lbl.config(text=str(val))

    def _on_gain_change(self, v):
        val = int(float(v))
        self.gain_val_lbl.config(text=str(val))

    def _on_bright_change(self, v):
        val = int(float(v))
        self.bright_val_lbl.config(text=str(val))

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
        self.sessions.append(sess)

        # ★ v2.6：開啟時不自動套用任何曝光設定，由使用者依裝置類型選擇模式
        #   顯微鏡 → 選「顯微鏡模式」再點套用（關 AE+AWB）
        #   一般攝影機 → 保持預設 Auto（AWB 正常，不會色偏）

        names = [f"Camera {s.cam_id}" for s in self.sessions]
        self.active_cam_combo["values"] = names
        if len(self.sessions) == 1:
            self.active_session_idx = cam_id
            self.active_cam_combo.set(names[0])

        self._refresh_canvas_layout()
        self._update_cam_status()
        self._log(f"Camera {cam_id} 已啟動 ─ 請在§2選擇「一般攝影機」或「顯微鏡」模式")
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
            rgb     = cv2.cvtColor(sess.display_frame, cv2.COLOR_BGR2RGB)
            h, w    = rgb.shape[:2]
            scale   = min(cw / w, ch / h)
            nw, nh  = max(1, int(w * scale)), max(1, int(h * scale))
            resized = cv2.resize(rgb, (nw, nh), interpolation=cv2.INTER_LINEAR)
            photo   = ImageTk.PhotoImage(Image.fromarray(resized))

            sess.display_scale  = scale
            sess.display_offset = ((cw - nw) // 2, (ch - nh) // 2)

            cv_widget.delete("all")
            cv_widget.create_image(*sess.display_offset,
                                   anchor="nw", image=photo)
            cv_widget.image = photo

            if sess.crosshair_visible and sess.measurement_mode != "none":
                x, y = sess.crosshair_x, sess.crosshair_y
                cv_widget.create_line(x, 0, x, ch,
                                      fill="#FF5050", width=1, dash=(5, 3))
                cv_widget.create_line(0, y, cw, y,
                                      fill="#FF5050", width=1, dash=(5, 3))
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
                  "calibration":   "校準模式（2點）",
                  "repeatability": "重複性測試"}
        txt = labels.get(mode, mode)
        self.mode_lbl.config(text=f"模式：{txt}", fg=P["yellow"])
        self._set_status(f"[Camera {sess.cam_id}]  {txt}")

    def _process_measurement(self, sess: CameraSession):
        mode = sess.measurement_mode
        pts  = sess.pending_points
        try:
            if   mode == "distance"      and len(pts) >= 2:
                self._measure_distance(sess, pts[-2], pts[-1])
                sess.pending_points.clear()
            elif mode == "angle"         and len(pts) >= 3:
                self._measure_angle(sess, pts[-3], pts[-2], pts[-1])
                sess.pending_points.clear()
            elif mode == "diameter"      and len(pts) >= 3:
                self._measure_diameter(sess, pts[-3], pts[-2], pts[-1])
                sess.pending_points.clear()
            elif mode == "calibration"   and len(pts) >= 2:
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
        return pixels * 0.005  # 未校準時使用預設估算值 5μm/px

    def _measure_distance(self, sess: CameraSession, p1, p2):
        d   = math.dist(p1, p2)
        mm  = self._px_to_mm(sess, d)
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
            cos_a  = max(-1.0, min(1.0,
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
            sess.scale_factor     = sess.calibration_distance / d
            sess.is_calibrated    = True
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

        for j, pt in enumerate(sess.pending_points):
            self._cross(df, pt, (0, 230, 255), 8, 2)
            cv2.putText(df, str(j+1),
                        (pt[0]+10, pt[1]-10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55,
                        (255, 255, 255), 1)

        n, mx   = len(sess.measurement_results), sess.max_measurements
        bar_bg  = (40, 44, 70)
        cv2.rectangle(df, (6, 6), (210, 28), bar_bg, -1)
        col_cnt = (80, 240, 140) if n < mx else (255, 100, 80)

        if sess.microscope_mode:
            mode_tag = f"EXP={self.exp_var.get()}"
        else:
            mode_tag = "Auto"
        cv2.putText(df, f" Cam{sess.cam_id}  {n}/{mx}  [{mode_tag}]",
                    (8, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.45,
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
        sz  = cv2.getTextSize(text, font, sc, th)[0]
        h0, w0 = img.shape[:2]
        x   = max(2, min(pos[0], w0 - sz[0] - 2))
        y   = max(sz[1]+2, min(pos[1], h0 - 2))
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

    def _process_barcode(self, data: dict, sess: CameraSession | None):
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
        text  = f"BC: {sess.current_barcode[:26]}"
        font  = cv2.FONT_HERSHEY_SIMPLEX
        scale = 1.1          # ★ 原 0.5 → 放大至 1.1
        thick = 2
        (tw, th), baseline = cv2.getTextSize(text, font, scale, thick)
        x, y = 8, 38 + th    # 文字基線 y 座標
        # 背景框（依實際文字尺寸計算）
        cv2.rectangle(sess.display_frame,
                      (x - 6, y - th - 8),
                      (x + tw + 6, y + baseline + 4),
                      (10, 35, 25), -1)
        cv2.putText(sess.display_frame, text,
                    (x, y), font, scale,
                    (80, 255, 180), thick, cv2.LINE_AA)

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
    #  操作目標切換
    # ══════════════════════════════════════════════════════════
    def _on_active_cam_changed(self, event=None):
        sel = self.active_cam_combo.current()
        if 0 <= sel < len(self.sessions):
            self._switch_active_cam(self.sessions[sel].cam_id)

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

    def _update_capture_mode_label(self):
        """更新拍照模式提示標籤文字"""
        if not hasattr(self, "_cap_mode_lbl"):
            return
        if self._lang == "jp":
            labels = {
                "single":         "▸ 現在のレンズ",
                "all_merged":     "▸ 全レンズ（合成）",
                "all_individual": "▸ 全レンズ（個別）",
            }
        else:
            labels = {
                "single":         "▸ 目前鏡頭",
                "all_merged":     "▸ 全部（合併）",
                "all_individual": "▸ 全部（個別）",
            }
        self._cap_mode_lbl.config(text=labels.get(self._capture_mode, ""))

    def _show_capture_menu(self):
        """▼ 按鈕：選擇拍照模式（不立即拍攝，設定後按主按鈕才拍）"""
        menu = tk.Menu(self.root, tearoff=0,
                       bg=P["card"], fg=P["text_h2"],
                       activebackground=P["accent"],
                       activeforeground=P["text_h1"],
                       font=F(11),
                       bd=0, relief="flat")

        def _set(mode):
            self._capture_mode = mode
            self._update_capture_mode_label()

        if self._lang == "jp":
            menu.add_command(
                label="📷  現在のレンズ",
                command=lambda: _set("single"))
            menu.add_separator()
            menu.add_command(
                label="🖼  全レンズ 合成して1枚",
                command=lambda: _set("all_merged"))
            menu.add_command(
                label="📂  全レンズ 個別に保存",
                command=lambda: _set("all_individual"))
        else:
            menu.add_command(
                label="📷  拍攝目前鏡頭",
                command=lambda: _set("single"))
            menu.add_separator()
            menu.add_command(
                label="🖼  全部鏡頭（合併為一張）",
                command=lambda: _set("all_merged"))
            menu.add_command(
                label="📂  全部鏡頭（分別儲存）",
                command=lambda: _set("all_individual"))

        hint = ("※ 選択後「📷 拍照」ボタンで撮影" if self._lang == "jp"
                else "※ 選擇後按「📷 拍照」執行拍攝")
        menu.add_separator()
        menu.add_command(label=hint, state="disabled")

        btn = self._cap_arrow_btn
        x = btn.winfo_rootx()
        y = btn.winfo_rooty() + btn.winfo_height()
        menu.tk_popup(x, y)

    def _do_capture(self):
        """主拍照按鈕：依目前 _capture_mode 執行對應拍攝動作"""
        if self._capture_mode == "all_merged":
            self._capture_all_merged()
        elif self._capture_mode == "all_individual":
            self._capture_all_individual()
        else:
            self._capture()

    def _capture(self):
        """拍攝目前操作鏡頭"""
        sess = self._active_session()
        if not sess or sess.display_frame is None:
            msg = "カメラを先に起動してください" if self._lang == "jp" else "請先開啟攝影機"
            messagebox.showwarning("⚠", msg)
            return
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        fn = f"cam{sess.cam_id}_{ts}.jpg"
        fp = os.path.join(self.save_directory, fn)
        cv2.imwrite(fp, sess.display_frame)
        self._save_meta(sess, ts, fn)
        ok_msg = f"保存：\n{fp}" if self._lang == "jp" else f"檔案已儲存至：\n{fp}"
        messagebox.showinfo("✓", ok_msg)
        self._log(f"拍照：{fn}")

    def _capture_all_merged(self):
        """
        拍攝全部鏡頭，橫向拼接成一張大圖後儲存。
        各鏡頭高度統一為最小高度，橫向排列，之間留 4px 黑色分隔線。
        """
        active_sessions = [s for s in self.sessions
                           if s.display_frame is not None]
        if not active_sessions:
            msg = "カメラが起動していません" if self._lang == "jp" else "目前沒有已啟動的鏡頭"
            messagebox.showwarning("⚠", msg)
            return

        # 統一高度（取最小高度）
        min_h = min(s.display_frame.shape[0] for s in active_sessions)
        frames = []
        for s in active_sessions:
            f = s.display_frame
            h, w = f.shape[:2]
            if h != min_h:
                scale = min_h / h
                f = cv2.resize(f, (max(1, int(w * scale)), min_h))
            frames.append(f)

        # 加 4px 黑色分隔線
        sep = np.zeros((min_h, 4, 3), dtype=np.uint8)
        merged_parts = []
        for i, f in enumerate(frames):
            merged_parts.append(f)
            if i < len(frames) - 1:
                merged_parts.append(sep)
        merged = np.hstack(merged_parts)

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        fn = f"all_cams_merged_{ts}.jpg"
        fp = os.path.join(self.save_directory, fn)
        cv2.imwrite(fp, merged)

        cam_ids = "+".join(str(s.cam_id) for s in active_sessions)
        ok_msg = (f"全カメラ合成保存完了 (Cam {cam_ids})\n{fp}"
                  if self._lang == "jp"
                  else f"全部鏡頭合併儲存完成 (Cam {cam_ids})\n{fp}")
        messagebox.showinfo("✓", ok_msg)
        self._log(f"全部拍照（合併）：{fn}  [{cam_ids}]")

    def _capture_all_individual(self):
        """
        拍攝全部鏡頭，每個鏡頭各存一個獨立檔案。
        """
        active_sessions = [s for s in self.sessions
                           if s.display_frame is not None]
        if not active_sessions:
            msg = "カメラが起動していません" if self._lang == "jp" else "目前沒有已啟動的鏡頭"
            messagebox.showwarning("⚠", msg)
            return

        ts  = datetime.now().strftime("%Y%m%d_%H%M%S")
        saved = []
        for s in active_sessions:
            fn = f"cam{s.cam_id}_{ts}.jpg"
            fp = os.path.join(self.save_directory, fn)
            cv2.imwrite(fp, s.display_frame)
            self._save_meta(s, ts, fn)
            saved.append(fn)
            self._log(f"拍照（個別）：{fn}")

        names = "\n".join(saved)
        ok_msg = (f"全カメラ個別保存完了：\n{names}"
                  if self._lang == "jp"
                  else f"全部鏡頭已分別儲存：\n{names}")
        messagebox.showinfo("✓", ok_msg)

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
            "export_time"     : datetime.now().isoformat(),
            "camera_id"       : sess.cam_id,
            "calibrated"      : sess.is_calibrated,
            "scale_mm_per_px" : sess.scale_factor if sess.is_calibrated else None,
            "exposure_value"  : self.exp_var.get(),
            "gain"            : self.gain_var.get(),
            "barcode"         : sess.current_barcode,
            "barcode_history" : sess.barcode_history,
            "measurements"    : [
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

    # ══════════════════════════════════════════════════════════
    #  語言切換
    # ══════════════════════════════════════════════════════════
    _ZH = {
        "title":"  多鏡頭測量系統","help_btn":"❓  使用說明",
        "lang_btn":"🇯🇵  日語切換","close_other_btn":"⚙   關閉其他程式",
        "tb_sel":"選擇路徑","tb_cap":"📷  拍照","tb_save":"💾  儲存","tb_export":"📤  匯出",
        "sec1":"① 攝影機管理","detect":"🔍  偵測所有攝影機","cam_sel":"選擇鏡頭：",
        "open":"▶  開啟","close":"■  關閉","no_cam":"● 無啟用鏡頭","active":"操作目標鏡頭：",
        "sec2":"② 鏡頭設定","exp_title":"📷 畫面曝光控制",
        "mode_normal":"一般攝影機","mode_micro":"顯微鏡（關閉 AE+AWB）",
        "mode_hint":"💡 一般攝影機請選「一般」；電子顯微鏡請選「顯微鏡」",
        "exp_lbl":"曝光值：","exp_hint":"  ← 暗（-13）          亮（-1）→",
        "gain_lbl":"增益 Gain：","bright_lbl":"亮度補償：",
        "apply_exp":"✅  套用曝光設定至目標鏡頭",
        "exp_note":"↑ 曝光/增益滑桿僅對「顯微鏡模式」有效","exp_none":"● 曝光：尚未設定",
        "sec3":"③ 校準","cal_dist":"已知距離(mm)：","cal_btn":"🎯  開始校準（點選兩點）",
        "cal_none":"● 尚未校準",
        "sec4":"④ 測量工具","m_dist":"📏  距離測量  (2點)",
        "m_angle":"📐  角度測量  (3點)","m_diam":"⭕  直徑測量  (3點)",
        "undo":"↩  撤銷上次","clear":"🗑  清除全部","mode_none":"模式：無",
        "sec5":"⑤ 精度驗證","rep_btn":"🔁  重複性測試（5次）","acc_btn":"📖  精度指南",
        "sec6":"⑥ 條碼掃描","bc_cam":"攝影機條碼掃描","bc_hand":"手持掃描器輸入",
        "bc_status":"掃描器：待機","bc_latest":"最新條碼：","bc_history":"掃描歷史：",
        "bc_clear":"🗑  清除條碼歷史",
        "sec7":"⑦ 測量日誌",
        "ready":"就緒","img_area":"影像顯示區","pause_all":"⏸  全部暫停 / 恢復",
    }
    _JP = {
        "title":"  多眼鏡測定システム","help_btn":"❓  使い方",
        "lang_btn":"🇹🇼  中文切替","close_other_btn":"⚙   他プログラムを終了",
        "tb_sel":"保存先選択","tb_cap":"📷  撮影","tb_save":"💾  保存","tb_export":"📤  出力",
        "sec1":"① カメラ管理","detect":"🔍  カメラを検出","cam_sel":"レンズ選択：",
        "open":"▶  開く","close":"■  閉じる","no_cam":"● カメラなし","active":"操作対象レンズ：",
        "sec2":"② レンズ設定","exp_title":"📷 露出制御",
        "mode_normal":"通常カメラ","mode_micro":"顕微鏡（AE+AWB無効）",
        "mode_hint":"💡 通常カメラ→「通常」；顕微鏡→「顕微鏡」を選択",
        "exp_lbl":"露出値：","exp_hint":"  ← 暗（-13）          明（-1）→",
        "gain_lbl":"ゲイン Gain：","bright_lbl":"輝度補正：",
        "apply_exp":"✅  露出設定を対象レンズに適用",
        "exp_note":"↑ 露出/ゲインは「顕微鏡モード」のみ有効","exp_none":"● 露出：未設定",
        "sec3":"③ キャリブレーション","cal_dist":"既知距離(mm)：",
        "cal_btn":"🎯  キャリブ開始（2点選択）","cal_none":"● 未キャリブ",
        "sec4":"④ 測定ツール","m_dist":"📏  距離測定  (2点)",
        "m_angle":"📐  角度測定  (3点)","m_diam":"⭕  直径測定  (3点)",
        "undo":"↩  元に戻す","clear":"🗑  全消去","mode_none":"モード：なし",
        "sec5":"⑤ 精度検証","rep_btn":"🔁  繰り返しテスト（5回）","acc_btn":"📖  精度ガイド",
        "sec6":"⑥ バーコードスキャン","bc_cam":"カメラスキャン","bc_hand":"ハンドスキャナ入力",
        "bc_status":"スキャナ：待機中","bc_latest":"最新バーコード：","bc_history":"スキャン履歴：",
        "bc_clear":"🗑  バーコード履歴削除",
        "sec7":"⑦ 測定ログ",
        "ready":"準備完了","img_area":"映像表示エリア","pause_all":"⏸  全カメラ 一時停止 / 再開",
    }

    def _T(self, key: str) -> str:
        d = self._JP if self._lang == "jp" else self._ZH
        return d.get(key, self._ZH.get(key, key))

    def _toggle_language(self):
        self._lang = "jp" if self._lang == "zh" else "zh"
        self._apply_language()

    def _apply_language(self):
        T = self._T
        # 頂部
        self.title_lbl.config(text=T("title"))
        self.help_btn.config(text=T("help_btn"))
        self.lang_btn.config(text=T("lang_btn"))
        self.close_other_btn.config(text=T("close_other_btn"))
        # 工具列
        self.tb_sel_btn.config(text=T("tb_sel"))
        if "capture_main" in self._tb_action_btns:
            self._tb_action_btns["capture_main"].config(text=T("tb_cap"))
        self._tb_action_btns["save"].config(text=T("tb_save"))
        self._tb_action_btns["export"].config(text=T("tb_export"))
        # 狀態列
        self.status_lbl.config(text=T("ready"))
        # 影像區
        if hasattr(self, "_img_area_lbl"):
            self._img_area_lbl.config(text=T("img_area"))
        if hasattr(self, "_pause_btn"):
            self._pause_btn.config(text=T("pause_all"))
        # Section LabelFrames
        for sec_widget, key in self._sec_map.items():
            try:
                sec_widget.config(text=f"  {T(key)}  ")
            except Exception:
                pass
        # 動態標籤
        for lbl, key in self._lbl_map.items():
            try:
                lbl.config(text=T(key))
            except Exception:
                pass
        # 按鈕
        for btn, key in self._btn_map.items():
            try:
                btn.config(text=T(key))
            except Exception:
                pass
        # Radiobuttons
        if hasattr(self, "_rb_normal"):
            self._rb_normal.config(text=T("mode_normal"))
        if hasattr(self, "_rb_micro"):
            self._rb_micro.config(text=T("mode_micro"))
        if hasattr(self, "cam_mode_hint"):
            self.cam_mode_hint.config(text=T("mode_hint"))
        # Checkbuttons
        if hasattr(self, "_cb_cam_scan") and BARCODE_AVAILABLE:
            lib = BARCODE_LIBRARY or ""
            self._cb_cam_scan.config(text=f"{T('bc_cam')} ({lib})" if lib else T("bc_cam"))
        if hasattr(self, "_cb_hand_scan"):
            self._cb_hand_scan.config(text=T("bc_hand"))
        # 模式標籤（若為「無」狀態才翻譯，避免覆蓋正在測量的模式名）
        if hasattr(self, "mode_lbl"):
            cur = self.mode_lbl.cget("text")
            if "無" in cur or "なし" in cur or cur.startswith("模式") or cur.startswith("モード"):
                self.mode_lbl.config(text=T("mode_none"))

    def _show_accuracy_guide(self):
        if self._lang == "jp":
            messagebox.showinfo("精度ガイド", (
                "キャリブレーション推奨\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "• 1mm または 0.5mm の標準距離を使用\n"
                "• 十分な照明を確保し、反射を抑える\n"
                "• コントラストの高い端点を選択\n\n"
                "精度評価基準\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "  優秀   ✅  CV < 2%\n"
                "  良好   🟡  CV 2 – 5%\n"
                "  許容   🟠  CV 5 – 10%\n"
                "  要改善 🔴  CV > 10%\n\n"
                "検証対象\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "• 標準ルーラーの目盛り\n"
                "• 既知の線幅を持つ基板パターン"
            ))
        else:
            messagebox.showinfo("精度指南", (
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
                "驗證物體\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "• 標準尺規刻度\n"
                "• 電路板線寬（已知值）"
            ))

    def _show_help(self):
        """使用說明：以自訂視窗呈現，字體放大、可捲動"""
        win = tk.Toplevel(self.root)
        win.title("使い方" if self._lang == "jp" else "使用說明")
        win.geometry("780x640")
        win.minsize(640, 480)
        win.configure(bg=P["bg"])
        win.grab_set()   # modal

        # ── 標題列 ──────────────────────────────────────────
        hdr = tk.Frame(win, bg=P["card"], height=52)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        tk.Label(hdr,
                 text="📖  " + ("使い方" if self._lang == "jp" else "使用說明"),
                 bg=P["card"], fg=P["text_h1"],
                 font=F(16, bold=True)).pack(side="left", padx=16, pady=12)
        tk.Label(hdr,
                 text=f"{VERSION}  {VERSION_DATE}",
                 bg=P["card"], fg=P["accent_glow"],
                 font=F(11)).pack(side="right", padx=16)

        # ── 捲動內容區 ───────────────────────────────────────
        body = tk.Frame(win, bg=P["bg"])
        body.pack(fill="both", expand=True, padx=16, pady=12)

        sb = ttk.Scrollbar(body, orient="vertical")
        sb.pack(side="right", fill="y")

        txt = tk.Text(body,
                      bg=P["input_bg"], fg=P["text_h2"],
                      font=F(13),
                      wrap="word",
                      padx=18, pady=14,
                      spacing1=4, spacing2=2, spacing3=6,
                      relief="flat",
                      borderwidth=0,
                      yscrollcommand=sb.set,
                      state="normal",
                      cursor="arrow")
        txt.pack(side="left", fill="both", expand=True)
        sb.config(command=txt.yview)

        # 使用說明視窗滾輪：進入 Text 時接管，離開時釋放
        def _help_wheel(e):
            txt.yview_scroll(-1 if e.delta > 0 else 1, "units")
            return "break"
        def _help_enter(e):
            txt.bind_all("<MouseWheel>", _help_wheel)
        def _help_leave(e):
            txt.unbind_all("<MouseWheel>")
        txt.bind("<Enter>", _help_enter)
        txt.bind("<Leave>", _help_leave)

        # ── tag 樣式 ─────────────────────────────────────────
        txt.tag_config("h1",   font=F(15, bold=True), foreground=P["accent_glow"],
                       spacing1=10, spacing3=4)
        txt.tag_config("step", font=F(13, bold=True), foreground=P["yellow"],
                       spacing1=8, spacing3=2)
        txt.tag_config("body", font=F(13),             foreground=P["text_h2"],
                       spacing1=2)
        txt.tag_config("note", font=F(12),             foreground=P["text_dim"],
                       lmargin1=24, lmargin2=24, spacing1=2)
        txt.tag_config("sep",  font=F(10),             foreground=P["divider"])

        def ins(text, tag="body"):
            txt.insert(tk.END, text, tag)

        if self._lang == "jp":
            ins("多眼鏡測定システム  操作ガイド\n", "h1")
            ins("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n", "sep")

            ins("\nSTEP 1　カメラ検出と起動\n", "step")
            ins("① 左パネル「カメラ管理」→「🔍 カメラを検出」をクリック\n", "body")
            ins("② ドロップダウンからレンズを選択し「▶ 開く」をクリック\n", "body")
            ins("③ 複数レンズを使う場合は ② を繰り返す\n", "body")
            ins("④ 映像上部タイトルバーをクリックして操作対象を切替\n", "body")
            ins("   （明るい青枠 = 現在の操作対象レンズ）\n", "note")

            ins("\nSTEP 2　露出設定（画面が暗い場合）\n", "step")
            ins("① 左パネル「レンズ設定」の露出モードを選択\n", "body")
            ins("   • 通常カメラ  →「通常カメラ」を選択（AWB維持）\n", "note")
            ins("   • 電子顕微鏡 →「顕微鏡」を選択（AE+AWB無効化）\n", "note")
            ins("② 顕微鏡モード時は「露出値」スライダーを右に動かして調整\n", "body")
            ins("③「✅ 露出設定を対象レンズに適用」をクリックして確定\n", "body")

            ins("\nSTEP 3　キャリブレーション（精密測定に必須）\n", "step")
            ins("① 既知の実寸（mm）を「既知距離」欄に入力\n", "body")
            ins("②「🎯 キャリブ開始」をクリック\n", "body")
            ins("③ 映像上でその距離の両端点を 2回クリック\n", "body")
            ins("④「● キャリブ済」と表示されれば完了\n", "body")

            ins("\nSTEP 4　寸法測定\n", "step")
            ins("📏 距離測定：映像上の 2点をクリック → 距離が表示\n", "body")
            ins("📐 角度測定：起点 → 頂点 → 終点 の順に 3点クリック\n", "body")
            ins("⭕ 直径測定：円弧上の任意の 3点をクリック → 直径を算出\n", "body")
            ins("↩  「元に戻す」で直前の測定を取消\n", "note")
            ins("🗑  「全消去」で全マーカーを削除\n", "note")

            ins("\nSTEP 5　バーコードスキャン（オプション）\n", "step")
            ins("• 「カメラスキャン」にチェック → 自動検出\n", "body")
            ins("• ハンドスキャナ使用時は「ハンドスキャナ入力」にチェック\n", "body")
            ins("  （アプリにフォーカスが必要）\n", "note")

            ins("\nSTEP 6　撮影・保存・出力\n", "step")
            ins("• 上部バー「保存先選択」で保存フォルダを指定\n", "body")
            ins("• 「📷 拍照」ボタン左部：現在のレンズを撮影\n", "body")
            ins("• 「📷 ▼」ボタン右部（▼）：撮影メニューを開く\n", "body")
            ins("     🖼  全レンズ 合成して 1枚保存\n", "note")
            ins("     📂  全レンズ 個別に保存\n", "note")
            ins("• 「💾 保存」：名前を指定して保存\n", "body")
            ins("• 「📤 出力」：測定結果を JSON ファイルで出力\n", "body")

            ins("\nSTEP 7　精度検証（オプション）\n", "step")
            ins("• 「🔁 繰り返しテスト（5回）」で再現性を確認\n", "body")
            ins("• CV < 2% → 優秀　　CV < 5% → 良好\n", "body")

        else:
            ins("多鏡頭測量系統  操作指南\n", "h1")
            ins("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n", "sep")

            ins("\nSTEP 1　偵測鏡頭並啟動\n", "step")
            ins("① 左側面板「攝影機管理」→ 點「🔍 偵測所有攝影機」\n", "body")
            ins("② 從下拉選單選擇鏡頭 → 點「▶ 開啟」\n", "body")
            ins("③ 需使用多個鏡頭時，重複步驟 ② 開啟多個\n", "body")
            ins("④ 點擊影像上方標題列切換操作目標鏡頭\n", "body")
            ins("   （亮藍色邊框 = 目前操作中的鏡頭）\n", "note")

            ins("\nSTEP 2　畫面曝光設定（畫面暗沉時）\n", "step")
            ins("① 左側「鏡頭設定」選擇曝光模式\n", "body")
            ins("   • 普通攝影機 → 選「一般攝影機」（保留自動白平衡）\n", "note")
            ins("   • 電子顯微鏡 → 選「顯微鏡」（關閉 AE+AWB）\n", "note")
            ins("② 顯微鏡模式時，將「曝光值」滑桿向右拉以增加亮度\n", "body")
            ins("③ 點「✅ 套用曝光設定至目標鏡頭」確認套用\n", "body")

            ins("\nSTEP 3　校準（精密測量必做）\n", "step")
            ins("① 在「已知距離(mm)」欄位輸入實際距離值\n", "body")
            ins("②  點「🎯 開始校準」\n", "body")
            ins("③ 在影像上點選該距離的兩個端點\n", "body")
            ins("④ 顯示「● 已校準」即完成\n", "body")

            ins("\nSTEP 4　尺寸測量\n", "step")
            ins("📏 距離測量：在影像上點 2 點 → 自動顯示距離\n", "body")
            ins("📐 角度測量：依序點 起點 → 頂點 → 終點 共 3 點\n", "body")
            ins("⭕ 直徑測量：點選圓弧上任意 3 點 → 自動計算直徑\n", "body")
            ins("↩  「撤銷上次」可移除最後一筆測量\n", "note")
            ins("🗑  「清除全部」移除所有標記\n", "note")

            ins("\nSTEP 5　條碼掃描（選用）\n", "step")
            ins("• 勾選「攝影機條碼掃描」→ 自動偵測畫面中的條碼\n", "body")
            ins("• 使用手持掃描器時勾選「手持掃描器輸入」\n", "body")
            ins("  （需保持程式視窗為焦點視窗）\n", "note")

            ins("\nSTEP 6　拍照、儲存與匯出\n", "step")
            ins("• 上方工具列「選擇路徑」先指定儲存資料夾\n", "body")
            ins("• 「📷 拍照」按鈕左側：拍攝目前鏡頭\n", "body")
            ins("• 「📷 ▼」按鈕右側（▼）：開啟拍照選單\n", "body")
            ins("     🖼  拍攝全部鏡頭，合併為一張大圖儲存\n", "note")
            ins("     📂  拍攝全部鏡頭，每個鏡頭分別儲存\n", "note")
            ins("• 「💾 儲存」：指定檔名另存影像\n", "body")
            ins("• 「📤 匯出」：將測量結果輸出為 JSON 報告\n", "body")

            ins("\nSTEP 7　精度驗證（選用）\n", "step")
            ins("• 點「🔁 重複性測試（5次）」可確認測量再現性\n", "body")
            ins("• CV < 2% → 優秀　　CV < 5% → 良好\n", "body")

        txt.config(state="disabled")

        # ── 關閉按鈕 ─────────────────────────────────────────
        bot = tk.Frame(win, bg=P["card"], height=48)
        bot.pack(fill="x", side="bottom")
        bot.pack_propagate(False)
        tk.Button(bot,
                  text="✕  " + ("閉じる" if self._lang == "jp" else "關閉"),
                  command=win.destroy,
                  bg=P["accent"], fg=P["text_h1"],
                  font=F(12, bold=True), relief="flat",
                  padx=20, pady=6,
                  activebackground=P["accent_dk"],
                  activeforeground=P["text_h1"],
                  cursor="hand2", bd=0).pack(pady=8)

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

    app._log(f"═══  多鏡頭測量系統  {VERSION}  啟動  ═══")
    app._log(f"字型：{_FONT_PRIMARY}  /  PIL：{'✓' if PIL_AVAILABLE else '✗'}  /  "
             f"條碼庫：{BARCODE_LIBRARY if BARCODE_AVAILABLE else '未安裝'}")
    app._log("★ v2.6：曝光模式分離─一般攝影機保留 AWB，顯微鏡關閉 AE+AWB")
    if not PIL_AVAILABLE:
        app._log("⚠ 未安裝 Pillow → 影像無法顯示。請執行：pip install pillow")
    if not BARCODE_AVAILABLE:
        app._log("⚠ 未安裝條碼庫 → 請執行：pip install zxing-cpp")

    root.mainloop()


if __name__ == "__main__":
    print("=" * 60)
    print(f"  多鏡頭測量系統  {VERSION}")
    print("=" * 60)
    print(f"  Python  : {sys.version.split()[0]}")
    print(f"  OpenCV  : {cv2.__version__}")
    print(f"  PIL     : {'✓' if PIL_AVAILABLE else '✗  pip install pillow'}")
    print(f"  Barcode : "
          f"{'✓ ' + BARCODE_LIBRARY if BARCODE_AVAILABLE else '✗  pip install zxing-cpp'}")
    print(f"  字型    : {_FONT_PRIMARY}")
    print("=" * 60)
    main()
