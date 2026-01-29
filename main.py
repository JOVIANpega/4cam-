import tkinter as tk
import sys
import numpy as np
from tkinter import filedialog
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from ttkbootstrap.tooltip import ToolTip
from PIL import Image, ImageTk, ImageDraw
import cv2
import os
import time
import threading
import json
from splicing_logic import SplicingProcessor
import re
import zipfile
import py7zr
import tempfile
import shutil

VERSION = "1.2.0"

class SplicingGUI:
    def __init__(self, root):
        self.root = root
        self.root.title(f"動態拼接檢查系統 (Dynamic Splicing Check System) - V{VERSION}")
        self.root.geometry("1400x900")
        self.root.state('zoomed') # Default to full screen
        
        # Global Default Parameters (Synchronized with User Latest Request)
        self.DEFAULT_DIFF = 18.0
        self.DEFAULT_RATE = 0.18
        self.DEFAULT_FAIL = 4
        self.auto_analyze_var = tk.BooleanVar(value=True)
        self.auto_clear_log_var = tk.BooleanVar(value=True)
        self.gui_font_size_var = tk.IntVar(value=12)
        
        # Style
        self.style = ttk.Style(theme="darkly")
        
        self.processor = SplicingProcessor()
        
        # Robust path handling for EXE
        if getattr(sys, 'frozen', False):
            self.base_path = os.path.dirname(sys.executable)
        else:
            self.base_path = os.path.dirname(os.path.abspath(__file__))
            
        self.config_path = os.path.join(self.base_path, "gui_config.json")
        self.last_dir = self.base_path
        
        # Initialize variables for persistence
        self.diff_thd_var = tk.DoubleVar()
        self.rate_thd_var = tk.DoubleVar()
        self.fail_thd_var = tk.IntVar()
        self.check_distortion_var = tk.BooleanVar(value=False)
        self.dist_thd_var = tk.DoubleVar(value=1.12)
        self.mag_factor_var = tk.DoubleVar(value=1.5)
        self.version_var = tk.StringVar(value=VERSION)
        
        # Lists to store widgets for dynamic font updates
        self.font_widgets_labels = []
        self.font_widgets_buttons = []
        
        # State variables
        self.is_analyzing = False
        self.hide_overlay_for_mag = False
        self.stop_event = threading.Event()
        self.results_data = [] # CSV data
        self.current_image_path = None
        self.batch_files = []
        self.batch_index = 0
        self.analysis_history = {} # v1.2.0: Stores {path: {'overlay': info, 'snapshots': [...]}}
        self.global_mag_popups = [] # Track Toplevel windows for absolute cleanup
        self.hide_result_overlay = False # Temporary flag for hover
        self.hide_result_permanently = False # v1.2.9+: Persistent hide after first hover
        self.zip_filter_var = tk.StringVar(value="4cam_cam")
        self.temp_extract_dir = None # For ZIP extraction
        
        self.load_config()
        self.setup_ui()
        
        # Event bindings for persistence
        self.root.bind("<Configure>", self.on_window_resize)
        self.gui_font_size_var.trace_add("write", lambda *args: self.apply_ui_font())
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        
        # Magnifier Setup
        self.mag_canvas = None
        self.canvas.bind("<Motion>", self.update_magnifier)
        self.canvas.bind("<Leave>", self.hide_magnifier)
        
        self.apply_ui_font() # Initial font apply

    def setup_ui(self):
        # Paned Window for adjustable split
        self.paned = ttk.PanedWindow(self.root, orient=HORIZONTAL)
        self.paned.pack(fill=BOTH, expand=YES, padx=10, pady=10)
        
        # Left Panel - Controls
        self.left_panel = ttk.Frame(self.paned, padding=10)
        self.paned.add(self.left_panel, weight=1)
        
        ttk.Label(self.left_panel, text="控制面板 (Control Panel)", font=("Helvetica", 16, "bold")).pack(pady=10)
        
        # Center Frame for Buttons (Prevents stretching)
        btn_container = ttk.Frame(self.left_panel)
        btn_container.pack(pady=10)
        
        # Define a consistent width for all buttons
        BTN_WIDTH = 25
        
        btn_load_single = ttk.Button(btn_container, text="📂 載入單張照片", bootstyle=PRIMARY, command=self.load_image)
        btn_load_single.pack(fill=X, pady=5)
        self.font_widgets_buttons.append(btn_load_single)
        ToolTip(btn_load_single, text="選擇單個圖片檔案進行分析")
        
        btn_load_folder = ttk.Button(btn_container, text="📁 載入資料夾", bootstyle=SECONDARY, command=self.load_folder)
        btn_load_folder.pack(fill=X, pady=5)
        self.font_widgets_buttons.append(btn_load_folder)
        ToolTip(btn_load_folder, text="選擇一個資料夾進行批次分析")

        btn_load_zip = ttk.Button(btn_container, text="📦 載入壓縮檔 (ZIP/7z)", bootstyle=WARNING, command=self.load_zip)
        btn_load_zip.pack(fill=X, pady=5)
        self.font_widgets_buttons.append(btn_load_zip)
        ToolTip(btn_load_zip, text="選擇 ZIP 或 7z 檔案並篩選關鍵字進行分析")
        
        self.analyze_btn = ttk.Button(btn_container, text="🚀 開始分析", bootstyle=SUCCESS, command=self.start_analysis)
        self.analyze_btn.pack(fill=X, pady=15)
        self.font_widgets_buttons.append(self.analyze_btn)
        ToolTip(self.analyze_btn, text="開始執行拼接分析流程")
        
        # Log Control Buttons (Horizontal row)
        log_btn_frame = ttk.Frame(btn_container)
        log_btn_frame.pack(fill=X, pady=5)
        
        self.copy_log_btn = ttk.Button(log_btn_frame, text="📋 複製日誌", bootstyle=INFO, command=self.copy_log)
        self.copy_log_btn.pack(side=LEFT, fill=X, expand=YES, padx=2)
        self.font_widgets_buttons.append(self.copy_log_btn)
        ToolTip(self.copy_log_btn, text="將日誌內容複製到剪貼簿")
        
        self.clear_log_btn = ttk.Button(log_btn_frame, text="🗑️ 清空日誌", bootstyle=DANGER, command=self.clear_log)
        self.clear_log_btn.pack(side=RIGHT, fill=X, expand=YES, padx=2)
        self.font_widgets_buttons.append(self.clear_log_btn)
        ToolTip(self.clear_log_btn, text="清除所有日誌文字")
        
        ttk.Separator(self.left_panel, orient=HORIZONTAL).pack(fill=X, pady=10)
        
        # Log Area - Expanded (v1.1.7)
        self.log_area = ttk.ScrolledText(self.left_panel, width=30, font=("Microsoft JhengHei", 10))
        self.log_area.pack(fill=BOTH, expand=YES, pady=5)
        # Setup tags for coloring PASS/FAIL results (Microsoft JhengHei)
        self.log_area.tag_config("pass_text", foreground="#00FF00", font=("Microsoft JhengHei", 10, "bold"))
        self.log_area.tag_config("fail_text", foreground="#FF0000", font=("Microsoft JhengHei", 10, "bold"))
        self.log_area.tag_config("blue_text", foreground="#00BFFF", font=("Microsoft JhengHei", 10, "bold"))
        
        # Right Panel - Notebook with Tabs
        self.right_panel = ttk.Frame(self.paned)
        self.paned.add(self.right_panel, weight=4)
        
        # Use a standard ttk.Notebook (v1.2.7: Secondary style)
        self.notebook = ttk.Notebook(self.right_panel, bootstyle=SECONDARY)
        self.notebook.pack(fill=BOTH, expand=YES, padx=5, pady=5)

        # Restore Sash Position (v1.2.0)
        sash_pos = self.gui_config.get("sash_pos", 350)
        self.root.after(200, lambda: self.paned.sashpos(0, sash_pos))

        # Tab Change Binding (v1.2.1)
        self.notebook.bind("<<NotebookTabChanged>>", self.on_tab_change)
        
        # --- TAB 1: Image View ---
        self.img_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.img_tab, text=" [ 圖片顯示 (Image View) ] ")
        
        # Top: Canvas for main image
        self.canvas_frame = ttk.Frame(self.img_tab)
        self.canvas_frame.pack(fill=BOTH, expand=YES)
        
        self.canvas = tk.Canvas(self.canvas_frame, bg="#1a1a1a", highlightthickness=0)
        self.canvas.pack(fill=BOTH, expand=YES)

        # Image Navigation Bar (v1.2.0)
        self.nav_frame = ttk.Frame(self.img_tab, padding=(10, 2))
        self.nav_frame.pack(fill=X, side=TOP)
        
        self.nav_label = ttk.Label(self.nav_frame, text="0 / 0", font=("Helvetica", 10, "bold"))
        self.nav_label.pack(side=LEFT, padx=10)
        
        # Bookmark Area (Small status dots)
        self.bookmark_outer = ttk.Frame(self.nav_frame)
        self.bookmark_outer.pack(side=RIGHT, fill=Y)
        
        self.bookmark_canvas = tk.Canvas(self.bookmark_outer, height=30, width=400, bg="#1a1a1a", highlightthickness=0)
        self.bookmark_canvas.pack(side=RIGHT, padx=10)
        self.bookmark_widgets = []
        
        # Bottom: Preview Area for Targets
        self.preview_outer = ttk.Frame(self.img_tab, height=150) # Increased height
        self.preview_outer.pack(fill=X, side=BOTTOM, padx=5, pady=5)
        self.preview_outer.pack_propagate(False)
        
        lbl_preview = ttk.Label(self.preview_outer, text="🔍 目標區塊快照 (Target Snapshots):", font=("Helvetica", 9, "bold"))
        lbl_preview.pack(anchor=W, padx=5)
        
        # Horizontal Scrollbar for previews
        preview_scroll = ttk.Scrollbar(self.preview_outer, orient=HORIZONTAL)
        preview_scroll.pack(side=BOTTOM, fill=X)
        
        self.preview_canvas = tk.Canvas(self.preview_outer, height=100, bg="#2d2d2d", 
                                       highlightthickness=0, xscrollcommand=preview_scroll.set)
        self.preview_canvas.pack(fill=BOTH, expand=YES)
        preview_scroll.config(command=self.preview_canvas.xview)
        
        self.preview_frame = ttk.Frame(self.preview_canvas)
        self.preview_canvas.create_window((0, 0), window=self.preview_frame, anchor=NW)
        self.preview_frame.bind("<Configure>", lambda e: self.preview_canvas.configure(scrollregion=self.preview_canvas.bbox("all")))
        
        self.preview_widgets = [] # To keep track of thumbnails
        
        # --- TAB 2: Settings ---
        self.settings_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.settings_tab, text=" [ 參數設定 (Settings) ] ")
        
        # --- TAB 3: Help / Documentation ---
        self.help_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.help_tab, text=" [ 邏輯說明 (Manual) ] ")
        
        help_text_tab = ttk.ScrolledText(self.help_tab, font=("Microsoft JhengHei", 12))
        help_text_tab.pack(fill=BOTH, expand=YES, padx=20, pady=20)
        self.manual_text_widget = help_text_tab # Store for font update

        manual_content = """
■ 系統核心設計說明 (System Core Design)

本系統專為「四線條紋圖」(4-line stripe pattern) 進行精密的幾何與色彩一致性檢查而設計。

1. 檢查原理 - 為什麼是四線條紋？
--------------------------------------------
系統透過尋找標靶中的 紅(R)、綠(G)、藍(B) 及 白色(White/Gray) 條紋邊界來判讀拼接品質。
- 分段偵測：將條紋分為三組（紅綠、綠藍、藍白拼接處）獨立計算像素位移 (Pixel Shift)。
- 參數鎖定：系統內置了針對 100cm 測試距離設計的特定參數 (如 hlimit, Pitch)，以確保高精度。

2. 歪曲檢查 (Distortion) 的侷限性
--------------------------------------------
本系統為「拼接處對齊檢查員」，而非全圖「鏡頭畸變測試儀」。
- 能檢測到：若歪曲發生在四線標靶所在的局部區域，導致條紋斷裂、傾斜或錯位，系統會報 FAIL。
- 檢測不到：若歪曲發生在沒有標靶的區域（如全圖中間或邊緣偏置），即使有幾何變形，只要拼接點有對齊，系統仍可能判定為 PASS。

3. 常見狀態說明
--------------------------------------------
- ROI_SELECTOR_ERROR：代表系統找不到紅色標記點，可能是圖片太暗、位置偏移過大或完全沒拍到標靶。
- Pixel Shift 數值過大：若偵測到條紋邊緣不再垂直或有嚴重重影，Pixel Shift 會飆高，進而判定為 NG。

■ 核心參數說明 (Algorithm Parameters)

1. 差異閾值 (Diff Threshold)
--------------------------------------------
用於判定邊緣強度的門檻。數值愈小愈靈敏（易受雜訊干擾），數值愈大愈遲鈍。建議值：18。

2. 比率閾值 (Rate Threshold)
--------------------------------------------
用於判定「鬼影/重影」。分析主次波峰的比率，若重影超過此比例則計入位移。建議值：0.18。

3. 不合格判定值 (Fail Threshold px)
--------------------------------------------
判定為 FAIL 的臨界點。Pixel Shift >= 此值即顯示為紅色(NG)。建議值：4 px。

4. 定位邏輯 (Find_Center_ROI)
--------------------------------------------
利用「RGB 色彩過濾」鎖定紅色標記點，作為後續掃描條紋的基準座標。
        """
        help_text_tab.insert(END, manual_content)
        help_text_tab.config(state=DISABLED) # Make read-only
        
        # Parameters Container in Settings Tab
        settings_container = ttk.Frame(self.settings_tab, padding=30)
        settings_container.pack(fill=BOTH, expand=YES)
        
        # NEW: Font & Version Control (v1.1)
        ver_font_frame = ttk.LabelFrame(settings_container, text="系統與開發 (System & Version)", padding=20)
        ver_font_frame.pack(anchor=W, pady=(0, 10)) # Left-aligned and narrow
        self.font_widgets_labels.append(ver_font_frame)
        
        # Version Input
        ver_row = ttk.Frame(ver_font_frame)
        ver_row.pack(fill=X, pady=5)
        lbl_ver = ttk.Label(ver_row, text="目前系統版本 (System Version):", font=("Helvetica", 11))
        lbl_ver.pack(side=LEFT)
        self.font_widgets_labels.append(lbl_ver)
        
        self.ver_entry = ttk.Entry(ver_row, textvariable=self.version_var, width=15)
        self.ver_entry.pack(side=LEFT, padx=10)
        self.font_widgets_buttons.append(self.ver_entry) # Add entry for font update
        
        btn_update_ver = ttk.Button(ver_row, text="💾 更新版本號", bootstyle=INFO, command=self.update_version_source)
        btn_update_ver.pack(side=LEFT)
        self.font_widgets_buttons.append(btn_update_ver)
        ToolTip(btn_update_ver, text="將此版本號寫入原始碼並套用。下次打包 EXE 會自動讀取此值。")

        # Font size row with tight alignment (Left-aligned)
        font_row = ttk.Frame(ver_font_frame)
        font_row.pack(fill=X, pady=(15, 0))
        
        lbl_font = ttk.Label(font_row, text="全域字體大小 (Global Font Size):", font=("Helvetica", 11), width=40)
        lbl_font.grid(row=0, column=0, sticky=W)
        self.font_widgets_labels.append(lbl_font)
        
        font_slider = ttk.Scale(font_row, from_=9, to=15, variable=self.gui_font_size_var, orient=HORIZONTAL, length=250)
        font_slider.grid(row=0, column=1, sticky=W) 
        ToolTip(font_slider, text="範圍：9pt ~ 15pt，預設：12pt。調整後會即時對應到按鈕與說明文字。")
        
        self.font_size_label = ttk.Label(font_row, text="12", font=("Helvetica", 12, "bold"), width=5, anchor=W)
        self.font_size_label.grid(row=0, column=2, sticky=W, padx=(20, 0))
        self.font_widgets_labels.append(self.font_size_label)

        # Magnifier Scale row (Moved here)
        mag_row = ttk.Frame(ver_font_frame)
        mag_row.pack(fill=X, pady=(15, 0))
        
        lbl_mag = ttk.Label(mag_row, text="放大鏡倍率 (Magnifier Scale):", font=("Helvetica", 12), width=40)
        lbl_mag.grid(row=0, column=0, sticky=W)
        self.font_widgets_labels.append(lbl_mag)
        
        mag_slider = ttk.Scale(mag_row, from_=0.5, to=2.0, variable=self.mag_factor_var, orient=HORIZONTAL, length=250)
        mag_slider.grid(row=0, column=1, sticky=W) 
        ToolTip(mag_slider, text="[視覺輔助]\n調整檢視圖片時的局部放大倍率。\n範圍：0.5x ~ 2.0x")
        self.mag_factor_var.trace_add("write", lambda *args: self.mag_label.config(text=f"{self.mag_factor_var.get():.2f}x"))

        self.mag_label = ttk.Label(mag_row, text="1.50x", font=("Helvetica", 12, "bold"), width=5, anchor=W)
        self.mag_label.grid(row=0, column=2, sticky=W, padx=(20, 0))
        self.font_widgets_labels.append(self.mag_label)

        param_frame = ttk.LabelFrame(settings_container, text="算法控制 (Algorithm Control)", padding=20)
        param_frame.pack(anchor=W, pady=10) # Left-aligned and narrow
        self.font_widgets_labels.append(param_frame) # Added for title font
        
        # Auto Analyze Toggle
        self.auto_chk = ttk.Checkbutton(param_frame, text="載入後自動分析 (Auto-Analyze)", 
                                       variable=self.auto_analyze_var, bootstyle="round-toggle")
        self.auto_chk.pack(anchor=W, pady=(0, 10))
        self.font_widgets_labels.append(self.auto_chk)
        ToolTip(self.auto_chk, text="啟用後，選取圖片或資料夾將自動啟動分析。")
        
        self.auto_clear_chk = ttk.Checkbutton(param_frame, text="載入時自動清空日誌 (Auto-Clear Log)", 
                                             variable=self.auto_clear_log_var, bootstyle="round-toggle")
        self.auto_clear_chk.pack(anchor=W, pady=(0, 10))
        self.font_widgets_labels.append(self.auto_clear_chk)
        ToolTip(self.auto_clear_chk, text="啟用後，載入新圖片或資料夾時會自動清除之前的日誌內容。")

        # Distortion Check Toggle
        self.distortion_chk = ttk.Checkbutton(param_frame, text="✅ 檢查畸變 (Distortion Check)", 
                                             variable=self.check_distortion_var, bootstyle="round-toggle")
        self.distortion_chk.pack(anchor=W, pady=(0, 20))
        self.font_widgets_labels.append(self.distortion_chk)
        ToolTip(self.distortion_chk, text="額外掃描圖片其他區域，檢查幾何形狀是否發生不合理扭曲（例如圓形變橢圓）。")
        
        # Parameters Grid Container for tight alignment (Left-aligned)
        param_grid = ttk.Frame(param_frame)
        param_grid.pack(fill=X, pady=10)
        
        # Differential Threshold row
        lbl_diff = ttk.Label(param_grid, text="差異閾值 (Diff Threshold):", font=("Helvetica", 12), width=40)
        lbl_diff.grid(row=0, column=0, sticky=W, pady=10)
        self.font_widgets_labels.append(lbl_diff)
        
        self.diff_slider = ttk.Scale(param_grid, from_=0, to=50, variable=self.diff_thd_var, orient=HORIZONTAL, length=250)
        self.diff_slider.grid(row=0, column=1, sticky=W)
        ToolTip(self.diff_slider, text="[邊緣偵測靈敏度]\n數值愈小愈靈敏（易受雜訊影響），數值愈大愈遲鈍。\n用於判定條紋與背景之間的明暗邊界強度。建議：18")
        self.diff_thd_var.trace_add("write", lambda *args: self.update_labels())

        self.diff_label = ttk.Label(param_grid, text="18", font=("Helvetica", 12, "bold"), width=5, anchor=W)
        self.diff_label.grid(row=0, column=2, sticky=W, pady=10, padx=(20, 0))
        self.font_widgets_labels.append(self.diff_label)
        
        # Rate Threshold row
        lbl_rate = ttk.Label(param_grid, text="比率閾值 (Rate Threshold):", font=("Helvetica", 12), width=40)
        lbl_rate.grid(row=1, column=0, sticky=W, pady=10)
        self.font_widgets_labels.append(lbl_rate)
        
        self.rate_slider = ttk.Scale(param_grid, from_=0.0, to=0.5, variable=self.rate_thd_var, orient=HORIZONTAL, length=250)
        self.rate_slider.grid(row=1, column=1, sticky=W)
        ToolTip(self.rate_slider, text="[鬼影判定強度]\n分析條紋剖面的次要波峰比率。\n若重影訊號超過此比例，則計入位移偏差。建議：0.18")
        self.rate_thd_var.trace_add("write", lambda *args: self.update_labels())

        self.rate_label = ttk.Label(param_grid, text="0.18", font=("Helvetica", 12, "bold"), width=5, anchor=W)
        self.rate_label.grid(row=1, column=2, sticky=W, pady=10, padx=(20, 0))
        self.font_widgets_labels.append(self.rate_label)

        # Distortion Threshold row
        lbl_dist_thd = ttk.Label(param_grid, text="畸變判定閾值 (Distortion Threshold):", font=("Helvetica", 12), width=40)
        lbl_dist_thd.grid(row=2, column=0, sticky=W, pady=10)
        self.font_widgets_labels.append(lbl_dist_thd)
        
        self.dist_thd_slider = ttk.Scale(param_grid, from_=1.01, to=1.50, variable=self.dist_thd_var, orient=HORIZONTAL, length=250)
        self.dist_thd_slider.grid(row=2, column=1, sticky=W)
        ToolTip(self.dist_thd_slider, text="[畸變容忍門檻]\n判定區域內幾何形狀（如圓形度或Pitch）的誤差比例。\n1.10 代表 10% 變形量。數值愈小愈嚴格。建議：1.12")
        self.dist_thd_var.trace_add("write", lambda *args: self.update_labels())

        self.dist_thd_label = ttk.Label(param_grid, text="1.12", font=("Helvetica", 12, "bold"), width=5, anchor=W)
        self.dist_thd_label.grid(row=2, column=2, sticky=W, pady=10, padx=(20, 0))
        self.font_widgets_labels.append(self.dist_thd_label)

        # Fail Threshold row
        lbl_fail = ttk.Label(param_grid, text="不合格判定值 (Fail Threshold px):", font=("Helvetica", 12), width=40)
        lbl_fail.grid(row=3, column=0, sticky=W, pady=10)
        self.font_widgets_labels.append(lbl_fail)
        
        self.fail_slider = ttk.Scale(param_grid, from_=1, to=15, variable=self.fail_thd_var, orient=HORIZONTAL, length=250)
        self.fail_slider.grid(row=3, column=1, sticky=W)
        ToolTip(self.fail_slider, text="[判定標準線]\n單點 Pixel Shift 允許的最大像素位移。\n超過此值(NG)該點標示為紅色。建議：4")
        self.fail_thd_var.trace_add("write", lambda *args: self.update_labels())

        self.fail_label = ttk.Label(param_grid, text="4", font=("Helvetica", 12, "bold"), width=5, anchor=W)
        self.fail_label.grid(row=3, column=2, sticky=W, pady=10, padx=(20, 0))
        self.font_widgets_labels.append(self.fail_label)

        # Reset Button (Moved inside Algorithm Control frame)
        btn_reset = ttk.Button(param_frame, text="🔄 恢復預設參數", bootstyle=WARNING, 
                               command=self.reset_defaults)
        btn_reset.pack(pady=(10, 0))
        self.font_widgets_buttons.append(btn_reset)

        # Version Label
        self.ver_label = ttk.Label(settings_container, text=f"Version: {VERSION}", font=("Helvetica", 10), foreground="gray")
        self.ver_label.pack(side=BOTTOM, pady=10)
        self.font_widgets_labels.append(self.ver_label)
        
        # Status Bar
        self.status_var = tk.StringVar(value="就緒")
        self.status_bar = ttk.Label(self.root, textvariable=self.status_var, relief=SUNKEN, anchor=W, padding=5)
        self.status_bar.pack(side=BOTTOM, fill=X)

    def load_config(self):
        # Default configuration
        self.gui_config = {
            "sash_pos": 350, 
            "auto_analyze": True, 
            "auto_clear_log": True,
            "window_geometry": "1400x900",
            "last_dir": self.last_dir,
            "diff_thd": self.DEFAULT_DIFF,
            "rate_thd": self.DEFAULT_RATE,
            "fail_thd": self.DEFAULT_FAIL,
            "gui_font_size": 12,
            "check_distortion": False,
            "dist_thd": 1.12,
            "mag_factor": 1.5
        }
        
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r') as f:
                    self.gui_config.update(json.load(f))
            except: pass
        
        # Apply configurations to variables
        self.auto_analyze_var.set(self.gui_config.get("auto_analyze", True))
        self.auto_clear_log_var.set(self.gui_config.get("auto_clear_log", True))
        self.diff_thd_var.set(self.gui_config.get("diff_thd", self.DEFAULT_DIFF))
        self.rate_thd_var.set(self.gui_config.get("rate_thd", self.DEFAULT_RATE))
        self.fail_thd_var.set(self.gui_config.get("fail_thd", self.DEFAULT_FAIL))
        self.gui_font_size_var.set(self.gui_config.get("gui_font_size", 12))
        self.check_distortion_var.set(self.gui_config.get("check_distortion", False))
        self.dist_thd_var.set(self.gui_config.get("dist_thd", 1.12))
        self.mag_factor_var.set(self.gui_config.get("mag_factor", 1.5))
        self.last_dir = self.gui_config.get("last_dir", self.last_dir)
        
        # Apply window geometry
        try:
            self.root.geometry(self.gui_config.get("window_geometry", "1400x900"))
        except: pass

    def save_config(self):
        try:
            self.gui_config["sash_pos"] = self.left_panel.winfo_width()
            self.gui_config["auto_analyze"] = self.auto_analyze_var.get()
            self.gui_config["auto_clear_log"] = self.auto_clear_log_var.get()
            self.gui_config["window_geometry"] = self.root.geometry()
            self.gui_config["last_dir"] = self.last_dir
            self.gui_config["diff_thd"] = self.diff_thd_var.get()
            self.gui_config["rate_thd"] = self.rate_thd_var.get()
            self.gui_config["fail_thd"] = self.fail_thd_var.get()
            self.gui_config["gui_font_size"] = self.gui_font_size_var.get()
            self.gui_config["check_distortion"] = self.check_distortion_var.get()
            self.gui_config["dist_thd"] = self.dist_thd_var.get()
            self.gui_config["mag_factor"] = self.mag_factor_var.get()
            
            with open(self.config_path, 'w') as f:
                json.dump(self.gui_config, f)
        except: pass

    def on_close(self):
        self.save_config()
        if self.temp_extract_dir and os.path.exists(self.temp_extract_dir):
            try: shutil.rmtree(self.temp_extract_dir)
            except: pass
        self.root.destroy()

    def restore_sash(self):
        try:
            # ttk.PanedWindow sash setting
            self.paned.sashpos(0, self.gui_config["sash_pos"])
        except: pass

    def on_window_resize(self, event):
        # Triggered on any resize, but we only care about redraw if image exists
        if self.current_image_path and event.widget == self.root:
            if not hasattr(self, '_resize_job'):
                self._resize_job = None
            if self._resize_job:
                self.root.after_cancel(self._resize_job)
            self._resize_job = self.root.after(200, self.redraw_current)

    def redraw_current(self):
        if self.current_image_path:
            self.display_image(self.current_image_path)
            self.save_config()

    def log(self, message):
        def _log():
            # Get current end position before insertion
            start_pos = self.log_area.index("end-1c")
            self.log_area.insert(END, message + "\n")
            
            is_fail = False
            # 1. Check for explicit FAIL keywords
            if "FAIL" in message or "[NG]" in message:
                is_fail = True
            
            # 2. Smart numeric check for spec_issue lines (e.g., PixelsShift_0=15.0)
            if "PixelsShift" in message and "=" in message:
                try:
                    # Extract the value after '='
                    val_str = message.split("=")[-1].strip()
                    val = float(val_str)
                    # Compare with current Fail Threshold from the slider
                    if val >= self.fail_thd_var.get():
                        is_fail = True
                except (ValueError, IndexError):
                    pass
            
            # Apply color tags
            if "=================" in message or "參數值:" in message:
                self.log_area.tag_add("blue_text", start_pos, "end-1c")
            elif "PASS" in message or "[OK]" in message:
                self.log_area.tag_add("pass_text", start_pos, "end-1c")
            elif is_fail:
                self.log_area.tag_add("fail_text", start_pos, "end-1c")
                
            self.log_area.see(END)
        self.root.after(0, _log)

    def reset_defaults(self):
        self.diff_thd_var.set(self.DEFAULT_DIFF)
        self.rate_thd_var.set(self.DEFAULT_RATE)
        self.fail_thd_var.set(self.DEFAULT_FAIL)
        self.gui_font_size_var.set(12)
        self.log("參數已恢復為預設值。")

    def apply_ui_font(self):
        size = self.gui_font_size_var.get()
        self.font_size_label.config(text=str(size))
        
        # Update Global Styles
        self.style.configure(".", font=("Helvetica", size))
        # v1.2.6: Add generous padding to tabs to prevent them from sticking together
        self.style.configure("TNotebook.Tab", font=("Helvetica", size, "bold"), padding=[30, 10])
        self.style.configure("TLabelframe.Label", font=("Helvetica", size, "bold"))
        
        # Update labels & Checkbuttons
        for lbl in self.font_widgets_labels:
            try:
                # Keep bold for status labels and results
                is_bold = False
                try:
                    current_font = lbl.cget("font")
                    if current_font:
                        is_bold = "bold" in str(current_font).lower()
                except: pass
                
                # Special check for widgets that might have specific font needs (like Checkbuttons)
                if isinstance(lbl, (ttk.Checkbutton, ttk.RadioButton)):
                     style_name = lbl.cget("style")
                     if style_name:
                         self.style.configure(style_name, font=("Helvetica", size))
                
                # Try standard config for text-based widgets
                lbl.config(font=("Helvetica", size, "bold" if is_bold else "normal"))
            except: 
                # If direct config fails, try styling
                try:
                    style_name = lbl.cget("style")
                    if style_name:
                        self.style.configure(style_name, font=("Helvetica", size))
                except: pass
            
        # Update buttons & Entries font
        for btn in self.font_widgets_buttons:
            try:
                style_name = btn.cget("style")
                if style_name:
                    self.style.configure(style_name, font=("Helvetica", size))
                
                btn.configure(font=("Helvetica", size))
            except: pass
            
        # Update Manual tab font (Microsoft JhengHei)
        if hasattr(self, 'manual_text_widget'):
            self.manual_text_widget.configure(font=("Microsoft JhengHei", size))
            
        # Update Status Bar
        if hasattr(self, 'status_bar'):
            self.status_bar.configure(font=("Helvetica", size))
            
        # Update Log font (Microsoft JhengHei)
        if hasattr(self, 'log_area'):
            self.log_area.configure(font=("Microsoft JhengHei", size))
            self.log_area.tag_config("pass_text", font=("Microsoft JhengHei", size, "bold"))
            self.log_area.tag_config("fail_text", font=("Microsoft JhengHei", size, "bold"))
            self.log_area.tag_config("blue_text", font=("Microsoft JhengHei", size, "bold"))

    def update_labels(self):
        self.diff_label.config(text=f"{int(self.diff_thd_var.get())}")
        self.rate_label.config(text=f"{self.rate_thd_var.get():.2f}")
        self.dist_thd_label.config(text=f"{self.dist_thd_var.get():.2f}")
        self.fail_label.config(text=f"{int(self.fail_thd_var.get())}")

    def update_version_source(self):
        new_ver = self.version_var.get().strip()
        if not new_ver: return
        
        try:
            # Meta-update: Rewrite main.py to sync version for build_exe.bat
            with open(__file__, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            with open(__file__, 'w', encoding='utf-8') as f:
                for line in lines:
                    if line.startswith('VERSION ='):
                        f.write(f'VERSION = "{new_ver}"\n')
                    else:
                        f.write(line)
            
            self.ver_label.config(text=f"Version: {new_ver}")
            tk.messagebox.showinfo("成功", f"版本號已更新為 {new_ver}\n下次打包 EXE 將會生效。")
        except Exception as e:
            tk.messagebox.showerror("錯誤", f"無法更新版本號文件: {str(e)}")

    def clear_log(self):
        self.log_area.delete('1.0', END)

    def copy_log(self):
        try:
            content = self.log_area.get('1.0', END)
            self.root.clipboard_clear()
            self.root.clipboard_append(content)
            self.status_var.set("日誌已複製到剪貼簿")
        except Exception as e:
            self.log(f"複製失敗: {str(e)}")

    def load_pil_image(self, path):
        try:
            # Simple loading, handle special characters by reading bytes
            with open(path, 'rb') as f:
                img = Image.open(f)
                img.load() # Load into memory
            return img
        except Exception:
            return Image.open(path)

    def load_image(self):
        path = filedialog.askopenfilename(
            initialdir=self.last_dir,
            filetypes=[("圖片檔案", "*.jpg *.png *.bmp")]
        )
        if path:
            self.last_dir = os.path.dirname(path)
            if self.auto_clear_log_var.get():
                self.clear_log()
            self.current_image_path = path
            self.batch_files = [path]
            self.batch_index = 0
            self.analysis_history = {}
            self.update_nav_ui()
            self.display_image(path)
            self.notebook.select(0) 
            self.log(f"已載入: {os.path.basename(path)}")
            if self.auto_analyze_var.get():
                self.start_analysis()
            else:
                self.clear_previews()

    def load_zip(self):
        """Load images from ZIP/7z with keyword filtering (v1.2.1-archive)"""
        archive_paths = filedialog.askopenfilenames(filetypes=[("壓縮檔案", "*.zip *.7z"), ("所有檔案", "*.*")])
        if not archive_paths: return

        # Create Keyword Input Popup
        popup = tk.Toplevel(self.root)
        popup.title("篩選關鍵字")
        popup.geometry("350x180")
        popup.resizable(False, False)
        popup.attributes("-topmost", True)
        
        # Center popup
        pw = self.root.winfo_screenwidth()
        ph = self.root.winfo_screenheight()
        popup.geometry(f"350x180+{pw//2-175}+{ph//2-90}")

        ttk.Label(popup, text="輸入檔名過濾關鍵字:", font=("Helvetica", 10)).pack(pady=15)
        entry = ttk.Entry(popup, textvariable=self.zip_filter_var, width=30)
        entry.pack(pady=5)
        entry.select_range(0, tk.END)
        entry.focus_set()

        def confirm(event=None):
            keyword = self.zip_filter_var.get().strip()
            popup.destroy()
            self._process_archive_files(archive_paths, keyword)

        btn_frame = ttk.Frame(popup)
        btn_frame.pack(pady=15)

        btn_ok = ttk.Button(btn_frame, text="確定 (Confirm)", bootstyle=SUCCESS, command=confirm)
        btn_ok.pack(side=LEFT, padx=10)

        btn_cancel = ttk.Button(btn_frame, text="取消 (Cancel)", bootstyle=SECONDARY, command=popup.destroy)
        btn_cancel.pack(side=LEFT, padx=10)
        
        popup.bind("<Return>", confirm)
        popup.bind("<Escape>", lambda e: popup.destroy())

    def _get_unique_temp_path(self, fname):
        """Generate a unique path in temp directory (v1.2.1)"""
        if not self.temp_extract_dir:
            self.temp_extract_dir = tempfile.mkdtemp(prefix="splicing_tool_")
        target_path = os.path.join(self.temp_extract_dir, fname)
        counter = 1
        name_part, ext_part = os.path.splitext(fname)
        while os.path.exists(target_path):
            target_path = os.path.join(self.temp_extract_dir, f"{name_part}_{counter}{ext_part}")
            counter += 1
        return target_path

    def _process_archive_files(self, archive_paths, keyword):
        """Extract filtered files from ZIP or 7z to temp directory (Robust Flatten Logic)."""
        if not self.temp_extract_dir:
            self.temp_extract_dir = tempfile.mkdtemp(prefix="splicing_tool_")
        
        extracted_files = []
        exts = ('.jpg', '.jpeg', '.png', '.bmp')
        
        for ap in archive_paths:
            ext = os.path.splitext(ap)[1].lower()
            a_name = os.path.basename(ap)
            self.log(f"正在分析壓縮檔: {a_name} ...")
            
            archives_found = 0
            archives_matched = 0
            
            try:
                if ext == '.zip':
                    with zipfile.ZipFile(ap, 'r') as z:
                        for info in z.infolist():
                            if info.is_dir(): continue
                            archives_found += 1
                            f_in_zip = info.filename
                            fname = os.path.basename(f_in_zip)
                            
                            if any(fname.lower().endswith(e) for e in exts):
                                if not keyword or keyword.lower() in fname.lower():
                                    archives_matched += 1
                                    target_path = self._get_unique_temp_path(fname)
                                    with z.open(f_in_zip) as source, open(target_path, "wb") as target:
                                        shutil.copyfileobj(source, target)
                                    extracted_files.append(target_path)
                                    
                elif ext == '.7z':
                    with py7zr.SevenZipFile(ap, mode='r') as z:
                        # 1. Scan and find matches
                        to_extract = []
                        members = z.list()
                        for m in members:
                            if m.is_directory: continue
                            archives_found += 1
                            fname = os.path.basename(m.filename)
                            if any(fname.lower().endswith(e) for e in exts):
                                if not keyword or keyword.lower() in fname.lower():
                                    archives_matched += 1
                                    to_extract.append(m.filename)
                        
                        if to_extract:
                            # 2. Extract matches in ONE GO to a sub-temporary folder
                            sub_root = tempfile.mkdtemp(dir=self.temp_extract_dir)
                            z.extract(targets=to_extract, path=sub_root)
                            
                            # 3. Walk and Flatten
                            for root, dirs, files in os.walk(sub_root):
                                for f in files:
                                    if any(f.lower().endswith(e) for e in exts):
                                        if not keyword or keyword.lower() in f.lower():
                                            src_path = os.path.join(root, f)
                                            dst_path = self._get_unique_temp_path(f)
                                            shutil.move(src_path, dst_path)
                                            extracted_files.append(dst_path)
                            
                            # 4. Clean up sub-root
                            try: shutil.rmtree(sub_root)
                            except: pass
                
                self.log(f"  -> {a_name}: 總計 {archives_found} 檔案, 符合篩選 {archives_matched} 個。")
                                
            except Exception as e:
                self.log(f"讀取壓縮檔 {a_name} 失敗: {str(e)}")

        if extracted_files:
            self.analysis_history = {} # Reset for new batch
            self.batch_files = extracted_files
            self.batch_index = 0
            self.current_image_path = self.batch_files[0]
            self.display_image(self.current_image_path)
            self.update_nav_ui()
            
            msg = f"載入成功！共從壓縮檔中提取 {len(extracted_files)} 張符合關鍵字 '{keyword}' 的圖片。\n\n是否立即開始分析？"
            self.log(msg)
            
            # Use askokcancel to allow user to stop here if count is wrong (v1.2.1)
            if tk.messagebox.askokcancel("載入完成", msg):
                if self.auto_analyze_var.get():
                    self.start_analysis()
            else:
                self.log("使用者取消自動分析。")
        else:
            self.log(f"找不到符合關鍵字 '{keyword}' 的影像檔案。")

    def load_folder(self):
        folder = filedialog.askdirectory(initialdir=self.last_dir)
        if folder:
            self.last_dir = folder
            if self.auto_clear_log_var.get():
                self.clear_log()
            self.batch_files = [os.path.join(folder, f) for f in os.listdir(folder) 
                                if f.lower().endswith(('.jpg', '.png', '.bmp'))]
            if self.batch_files:
                self.analysis_history = {}
                self.update_nav_ui()
                self.display_image(self.current_image_path)
                self.notebook.select(0)
                msg = f"已載入資料夾: {folder} (共 {len(self.batch_files)} 張照片)"
                self.log(msg)
                tk.messagebox.showinfo("載入成功", msg)
                
                if self.auto_analyze_var.get():
                    self.start_analysis()
                else:
                    self.clear_previews()
            else:
                self.log("資料夾內未發現支援的照片格式。")

    def display_image(self, path, overlay_info=None):
        # Recall history only if this is a fresh file load.
        # CRITICAL: If hide_result_permanently is True, we are in a REDRAW for hover,
        # so we MUST NOT reload history (which calls add_preview_thumbnail and causes duplicates).
        if overlay_info is None and not self.hide_result_permanently and path in self.analysis_history:
            hist = self.analysis_history[path]
            overlay_info = hist.get('overlay')
            # Restore snapshots for this image
            self.clear_previews()
            for snap in hist.get('snapshots', []):
                self.add_preview_thumbnail(snap['img'], snap['index'], snap['status'], snap['shift'], snap['rect'])

        try:
            # Use cached image if possible to speed up animation
            if hasattr(self, '_cached_path') and self._cached_path == path:
                img_original = self._cached_img
            else:
                img_original = self.load_pil_image(path)
                self._cached_path = path
                self._cached_img = img_original
            
            # Use canvas dimensions
            canvas_w = self.canvas.winfo_width()
            canvas_h = self.canvas.winfo_height()
            
            if canvas_w < 100: canvas_w = 1200 
            if canvas_h < 100: canvas_h = 800
            
            img_w, img_h = img_original.size
            ratio = min(canvas_w / img_w, canvas_h / img_h)
            new_w = int(img_w * ratio)
            new_h = int(img_h * ratio)
            
            # Always ensure a new object for drawing
            img_resized = img_original.resize((new_w, new_h), Image.LANCZOS)
            
            # If magnifier is active, skip the overlay to allow clear view
            if self.hide_overlay_for_mag:
                overlay_info = None

            if overlay_info:
                draw = ImageDraw.Draw(img_resized)

                # 1. Draw Distortion Debug Boxes first (Bottom layer)
                dist_boxes = overlay_info.get('dist_boxes', [])
                for db in dist_boxes:
                    dbx1, dby1, dbx2, dby2 = db
                    dbx1, dby1 = int(dbx1 * ratio), int(dby1 * ratio)
                    dbx2, dby2 = int(dbx2 * ratio), int(dby2 * ratio)
                    draw.rectangle([dbx1, dby1, dbx2, dby2], outline="#00FFFF", width=2)

                # 2. Draw normal detection rects
                rect = overlay_info.get('rect')
                status_text = overlay_info.get('text', "")
                status = overlay_info.get('status', 'checking') 
                
                color = "yellow"
                if status == 'pass': color = "#00FF00"
                if status == 'fail': color = "#FF0000"
                
                # Regular per-target status text - Scale font size with image
                try:
                    from PIL import ImageFont
                    # Make scanning text bigger as requested
                    font_size = max(28, int(50 * ratio))
                    target_font = None
                    font_paths = ["C:\\Windows\\Fonts\\arialbd.ttf", "arial.ttf"]
                    for fp in font_paths:
                        if os.path.exists(fp):
                            target_font = ImageFont.truetype(fp, font_size)
                            break
                except:
                    target_font = None
                
                if rect:
                    rx1, ry1, rx2, ry2 = rect
                    rx1 = int(rx1 * ratio)
                    ry1 = int(ry1 * ratio)
                    rx2 = int(rx2 * ratio)
                    ry2 = int(ry2 * ratio)
                    
                    if (rx2 - rx1) < 20: rx1, rx2 = rx1 - 10, rx2 + 10
                    if (ry2 - ry1) < 20: ry1, ry2 = ry1 - 10, ry2 + 10

                    for i in range(4):
                        draw.rectangle([rx1-i, ry1-i, rx2+i, ry2+i], outline=color, width=3)
                    
                    # Draw high-contrast black background for text
                    text_str = status_text
                    try:
                        t_bbox = draw.textbbox((rx1, ry1 - font_size - 10), text_str, font=target_font)
                        # Add some padding to the background box
                        bg_padding = 5
                        bg_label = [t_bbox[0]-bg_padding, t_bbox[1]-bg_padding, t_bbox[2]+bg_padding, t_bbox[3]+bg_padding]
                        draw.rectangle(bg_label, fill=(0, 0, 0, 180)) # Semi-transparent black
                    except:
                        # Fallback if textbbox is missing
                        draw.rectangle([rx1, ry1 - font_size - 15, rx1 + 300, ry1 - 5], fill=(0, 0, 0, 180))
                        
                    # Draw status text on top of the black box
                    draw.text((rx1, ry1 - font_size - 10), text_str, fill=color, font=target_font)

                # 3. Draw Watermark Final Result (Top Layer)
                final_res = overlay_info.get('final_result')
                if final_res and not self.hide_result_permanently:
                    # Draw semi-transparent black overlay
                    overlay_layer = Image.new('RGBA', (new_w, new_h), (0, 0, 0, 200))
                    img_resized.paste(overlay_layer, (0, 0), overlay_layer)
                    
                    # Need to rebuild draw object after paste
                    draw = ImageDraw.Draw(img_resized)
                    res_text = "PASS" if final_res == 'pass' else "FAIL"
                    res_color = "#00FF00" if final_res == 'pass' else "#FF0000"
                    
                    try:
                        from PIL import ImageFont
                        font_paths = ["C:\\Windows\\Fonts\\arialbd.ttf", "arial.ttf"]
                        font = None
                        for fp in font_paths:
                            if os.path.exists(fp):
                                font = ImageFont.truetype(fp, 180)
                                break
                        if not font: font = ImageFont.load_default()
                    except:
                        font = None
                    
                    # Center text (v1.2.1: Filename + Result)
                    try:
                        fname = os.path.basename(path)
                        # Load smaller font for filename
                        small_font = None
                        for fp in font_paths:
                            if os.path.exists(fp):
                                small_font = ImageFont.truetype(fp, 60)
                                break
                        if not small_font: small_font = ImageFont.load_default()
                        
                        # Get dimensions
                        f_bbox = draw.textbbox((0, 0), fname, font=small_font)
                        wf, hf = f_bbox[2] - f_bbox[0], f_bbox[3] - f_bbox[1]
                        
                        t_bbox = draw.textbbox((0, 0), res_text, font=font)
                        wt, ht = t_bbox[2] - t_bbox[0], t_bbox[3] - t_bbox[1]
                        
                        # Calculate vertical stack
                        spacing = 30
                        total_h = hf + wt + spacing
                        start_y = (new_h - total_h) // 2
                        
                        # Draw Filename (White)
                        draw.text(((new_w - wf) // 2, start_y), fname, fill="white", font=small_font)
                        # Draw Result (Green/Red)
                        draw.text(((new_w - wt) // 2, start_y + hf + spacing), res_text, fill=res_color, font=font)
                    except Exception as e:
                        print(f"Overlay drawing error: {e}")
                        draw.text((new_w//2 - 100, new_h//2), res_text, fill=res_color)
                

            self.tk_img = ImageTk.PhotoImage(img_resized)
            self.canvas.delete("all")
            # Anchor to North (top) instead of CENTER to leave space below
            self.canvas.create_image(canvas_w//2, 10, image=self.tk_img, anchor=N)
            
            # Store resized image for magnifier source
            self.current_resized_img = img_resized
            self.current_ratio = ratio
            
        except Exception as e:
            self.log(f"畫布顯示失敗: {str(e)}")

    def update_magnifier(self, event):
        if not hasattr(self, 'current_resized_img') or self.is_analyzing:
            return
            
        x, y = event.x, event.y
        # Get canvas center offset
        cw = self.canvas.winfo_width()
        ch = self.canvas.winfo_height()
        base_x = (cw - self.current_resized_img.width) // 2
        base_y = (ch - self.current_resized_img.height) // 2
        
        # Check if cursor is on image
        if base_x <= x < base_x + self.current_resized_img.width and \
           base_y <= y < base_y + self.current_resized_img.height:
            
            # Source coordinates on the resized image
            src_x = x - base_x
            src_y = y - base_y
            
            mag_w = 400 # Longer width
            mag_h = 200 # Height
            mag = self.mag_factor_var.get()
            
            # Temporary hide overlay and redraw main image if needed
            if not self.hide_overlay_for_mag:
                self.hide_overlay_for_mag = True
                self.redraw_current() # Redraw without overlay
            
            # Crop area on original image for better quality
            # First map to original image coords
            orig_x = src_x / self.current_ratio
            orig_y = src_y / self.current_ratio
            
            # Crop dimensions in original pixels
            rw = int((mag_w / 2) / mag / self.current_ratio)
            rh = int((mag_h / 2) / mag / self.current_ratio)
            
            try:
                # Need the original image
                orig_img = self._cached_img
                crop = orig_img.crop((orig_x - rw, orig_y - rh, orig_x + rw, orig_y + rh))
                crop_resized = crop.resize((mag_w, mag_h), Image.LANCZOS)
                
                self.mag_tk_img = ImageTk.PhotoImage(crop_resized)
                
                if not self.mag_canvas:
                    self.mag_canvas = self.canvas.create_image(x + 20, y + 20, image=self.mag_tk_img, anchor=NW)
                else:
                    self.canvas.coords(self.mag_canvas, x + 20, y + 20)
                    self.canvas.itemconfig(self.mag_canvas, image=self.mag_tk_img)
            except:
                pass
        else:
            self.hide_magnifier()

    def hide_magnifier(self, event=None):
        if self.mag_canvas:
            self.canvas.delete(self.mag_canvas)
            self.mag_canvas = None
        
        if self.hide_overlay_for_mag:
            self.hide_overlay_for_mag = False
            # We don't necessarily need to redraw every time we move out, 
            # only if we want the overlay back immediately.
            # However, typically people use mag to see details, then move out to see result.
            self.redraw_current()

    def safe_update_ui(self, path, overlay):
        try:
            # Sanitize overlay text to prevent Tcl/Tk Latin-1 encoding errors with Chinese characters
            if 'text' in overlay:
                # Convert descriptive status back to simple tags for internal display if needed, 
                # but better to just handle the encoding by keeping it simple
                raw_text = overlay['text']
                # If we need Chinese in the image but ASCII in the Tcl call, 
                # we keep it in the dict and handle drawing separately, or just sanitize
                pass 
            
            self.display_image(path, overlay)
            self.root.update_idletasks()
            self.root.update()
        except Exception as e:
            self.log(f"UI Update Error: {str(e)}")


    def start_analysis(self):
        if not self.current_image_path:
            self.log("尚未載入照片。")
            return
        
        if self.is_analyzing: return
        
        self.hide_result_permanently = False # Reset on new analysis
        self.is_analyzing = True
        self.notebook.select(0) # Auto-switch to Image View tab
        self.analyze_btn.config(state=DISABLED)
        self.status_var.set("分析中...")
        
        # Apply parameters
        self.processor.diff_thd = int(self.diff_thd_var.get())
        self.processor.rate_thd = self.rate_thd_var.get()
        self.processor.dist_thd = self.dist_thd_var.get()
        
        self.clear_previews()
        threading.Thread(target=self.run_analysis_pipeline, daemon=True).start()

    def run_analysis_pipeline(self):
        try:
            self.stop_event.clear()
            if self.batch_files:
                for i in range(self.batch_index, len(self.batch_files)):
                    if self.stop_event.is_set(): break
                    self.current_image_path = self.batch_files[i]
                    self.batch_index = i
                    self.process_single_image(self.current_image_path)
            else:
                self.process_single_image(self.current_image_path)
        except Exception as e:
            self.log(f"執行分析時發生錯誤: {str(e)}")
        finally:
            self.root.after(0, self.analysis_done)

    def process_single_image(self, path):
        try:
            self.root.after(0, self.clear_previews) # v1.2.4: Clear previous snapshots when moving to next file
            self.root.after(0, lambda p=path: self.display_image(p))
            # Critical: Allow UI to draw the basic image first
            time.sleep(0.1) 
            
            # Print current parameter info in the log (v1.1)
            p_diff = int(self.diff_thd_var.get())
            p_rate = self.rate_thd_var.get()
            p_fail = int(self.fail_thd_var.get())
            self.log(f"==================================")
            self.log(f"參數值: Diff={p_diff}, Rate={p_rate:.2f}, Fail={p_fail}px")
            self.log(f"==================================")
            
            self.log(f"正在分析: {os.path.basename(path)}...")
            
            result = self.processor.analyze_image_prepare(path)
            if not result:
                self.log(f"  [NG] 在 {os.path.basename(path)} 中發生嚴重錯誤，無法載入影像。")
                return
                
            cv_img, steps = result
            image_pass = True
            fail_reasons = [] # Collector for diagnostic info
            
            # Collectors for final spec_issue log
            shift_vals = []
            disc_vals = [] # List of tuples: (white, red, green, blue)
            
            for step in steps:
                if self.stop_event.is_set(): return
                
                # Check for forced failure (ROI_SELECTOR_ERROR replication)
                force_fail = step.get('force_fail')
                
                # Animation Start - Yellow Box
                # Use viz_rect if available for drawing, but calculation stays the same
                overlay = {'rect': step.get('viz_rect', step['rect']), 'text': "SCANNING", 'status': 'checking'}
                self.root.after(0, self.safe_update_ui, path, overlay.copy())
                time.sleep(0.7) 
                
                if force_fail is not None:
                    shift, debug_roi, discs = self.processor.process_step(cv_img, step)
                    msg = step.get('msg', "ERROR")
                    status_text = f"SHIFT: {shift}px [{msg}]"
                    is_pass = False
                    # Create a blank/error ROI for preview
                    debug_roi = np.zeros((100, 280, 3), dtype=np.uint8)
                    cv2.putText(debug_roi, msg, (50, 60), cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0, 0, 255), 3)
                else:
                    # Actual calculation
                    shift, debug_roi, discs = self.processor.process_step(cv_img, step)
                    # Determine PASS/FAIL
                    is_pass = shift < int(self.fail_thd_var.get())
                    status_text = f"SHIFT: {shift}px [{'OK' if is_pass else 'NG'}]"
                
                shift_vals.append(shift)
                disc_vals.append(discs)
                
                if not is_pass: 
                    image_pass = False
                    if force_fail is not None:
                        fail_reasons.append(f"目標 {step['index']}: 定位失敗 (ROI ERROR) - 找不到紅點或條紋特徵。")
                    else:
                        fail_reasons.append(f"目標 {step['index']}: 位移超標 ({shift}px) - 超過門檻值 {int(self.fail_thd_var.get())}px。")
                status_tag = 'pass' if is_pass else 'fail'
                
                
                # Store result for CSV
                res = [os.path.basename(path), step['index'], shift, 
                       'PASS' if is_pass else 'FAIL', time.strftime("%H:%M:%S")]
                self.results_data.append(res)
                
                # Animation Done - Result Box
                overlay['text'] = status_text
                overlay['status'] = status_tag
                self.root.after(0, self.safe_update_ui, path, overlay.copy())
                
                fail_msg = "" if is_pass else f" (THRESHOLD {self.fail_thd_var.get()}px)"
                self.log(f"  Target {step['index']}: {shift} px -> {'PASS' if is_pass else 'FAIL'}{fail_msg}")
                
                # Add to Bottom Preview Area (v1.1.8: Horizontal + Arrow)
                self.add_preview_thumbnail(debug_roi, step['index'], status_tag, shift, step['rect'])
                
                # Store snapshot in history for navigation recall
                if path not in self.analysis_history:
                    self.analysis_history[path] = {'snapshots': [], 'overlay': None}
                self.analysis_history[path]['snapshots'].append({
                    'img': debug_roi.copy(), 'index': step['index'], 'status': status_tag, 'shift': shift, 'rect': step['rect']
                })
                
                time.sleep(1.0) 
            
            # --- FINAL SPEC ISSUE LOGGING ---
            cam_id = "cam"
            import re
            name_match = re.search(r'cam(\d+)', os.path.basename(path).lower())
            if name_match: cam_id = f"cam{name_match.group(1)}"
            
            self.log("\nspec_issue:")
            for i, s in enumerate(shift_vals):
                self.log(f"{cam_id}:MAX_PixelsShift_{i}={float(s)}")
            
            for i, d in enumerate(disc_vals):
                w, r, g, b = d
                self.log(f"{cam_id}:Brightness_discontinue_{i}={w*100.0:.1f}")
                self.log(f"{cam_id}:red_discontinue_{i}={r*100.0:.1f}")
                self.log(f"{cam_id}:green_discontinue_{i}={g*100.0:.1f}")
                self.log(f"{cam_id}:blue_discontinue_{i}={b*100.0:.1f}")
            
            avg_shift = sum(shift_vals) / len(shift_vals) if shift_vals else 0
            self.log(f"pixel_shift_avg = {avg_shift}")
            
            # --- GLOBAL DISTORTION CHECK ---
            if self.check_distortion_var.get():
                self.log("\n正在執行快速畸變掃描 (Global Distortion Scan)...")
                is_distorted, max_ecc, found_cnt, dist_boxes = self.processor.check_distortion(cv_img)
                
                # Show detected boxes in the GUI for transparency
                dist_steps = []
                for box in dist_boxes:
                    bx, by, bw, bh = box
                    dist_steps.append((bx, by, bx+bw, by+bh))
                
                final_overlay = {
                    'final_result': 'pass' if image_pass and not is_distorted else 'fail',
                    'dist_boxes': dist_steps
                }
                self.root.after(0, self.safe_update_ui, path, final_overlay)

                if is_distorted:
                    self.log(f"  [NG] 偵測到明顯畸變 (最大變形比率: {max_ecc}, 樣本數: {found_cnt})")
                    image_pass = False
                else:
                    self.log(f"  [OK] 幾何形狀正常 (最大變形比率: {max_ecc}, 樣本數: {found_cnt})")

            self.log("SPEC_PASS" if image_pass else "SPEC_FAIL")
            
            # --- DIAGNOSTIC SUMMARY (v1.1.9) ---
            if not image_pass:
                self.log("\n【分析故障診斷】(Diagnostic Summary):")
                if not fail_reasons and self.check_distortion_var.get():
                    self.log("- 拼接位移正常，但發現幾何畸變程度過高。")
                for reason in fail_reasons:
                    self.log(f"- {reason}")
                self.log("💡 建議：檢查光源是否均勻，或標靶是否被遮擋/模糊。")
            
            self.log("----------------------------------")

            # Final Giant Result Overlay
            final_overlay = {'final_result': 'pass' if image_pass else 'fail'}
            if path in self.analysis_history:
                self.analysis_history[path]['overlay'] = final_overlay.copy()
                self.analysis_history[path]['is_pass'] = image_pass
            
            self.root.after(0, self.update_nav_ui)
            self.root.after(0, self.safe_update_ui, path, final_overlay)
            time.sleep(1.2) 
        except Exception as e:
            self.log(f"分析單張照片時發生錯誤: {str(e)}")

    def clear_previews(self):
        def _clear():
            for widget in self.preview_widgets:
                widget.destroy()
            self.preview_widgets = []
            self.preview_canvas.xview_moveto(0.0)
        self.root.after(0, _clear)

    def update_nav_ui(self):
        """Update the navigation label and PASS/FAIL bookmarks."""
        total = len(self.batch_files)
        curr = self.batch_index + 1 if total > 0 else 0
        self.nav_label.config(text=f"{curr} / {total}")
        
        # Clear and redraw bookmarks
        self.bookmark_canvas.delete("all")
        dot_w = 20
        gap = 5
        for i, path in enumerate(self.batch_files):
            color = "#444444" # Unprocessed
            if path in self.analysis_history:
                color = "#00FF00" if self.analysis_history[path].get('is_pass') else "#FF0000"
            
            x = i * (dot_w + gap)
            # Highlight current
            outline = "white" if i == self.batch_index else ""
            width = 2 if i == self.batch_index else 0
            
            rect_id = self.bookmark_canvas.create_rectangle(x, 5, x + dot_w, 25, 
                                                           fill=color, outline=outline, width=width)
            # Simple jump on click
            self.bookmark_canvas.tag_bind(rect_id, "<Button-1>", lambda e, idx=i: self.jump_to_image(idx))
        
        self.bookmark_canvas.config(scrollregion=self.bookmark_canvas.bbox("all"))

    def prev_image(self):
        if self.is_analyzing or not self.batch_files: return
        self.hide_result_permanently = False # Reset for new image
        self.batch_index = (self.batch_index - 1) % len(self.batch_files)
        self.current_image_path = self.batch_files[self.batch_index]
        self.display_image(self.current_image_path)
        self.update_nav_ui()

    def next_image(self):
        if self.is_analyzing or not self.batch_files: return
        self.hide_result_permanently = False # Reset for new image
        self.batch_index = (self.batch_index + 1) % len(self.batch_files)
        self.current_image_path = self.batch_files[self.batch_index]
        self.display_image(self.current_image_path)
        self.update_nav_ui()

    def jump_to_image(self, index):
        if self.is_analyzing: return
        self.hide_result_permanently = False # Reset for new image
        self.batch_index = index
        self.current_image_path = self.batch_files[self.batch_index]
        self.display_image(self.current_image_path)
        self.update_nav_ui()

    def on_tab_change(self, event):
        """Clear overlays and popups when leaving Image View tab."""
        # index 0 is Image View
        if self.notebook.index("current") != 0:
            self.hide_target_arrow()
            self.hide_magnifier()
            self.hide_result_overlay = False
            self.clear_all_popups()
            self.redraw_current()

    def clear_all_popups(self):
        """Forcefully destroy all tracking toplevel windows (v1.2.3)"""
        for win in list(self.global_mag_popups):
            try:
                if win.winfo_exists():
                    win.destroy()
            except: pass
        self.global_mag_popups.clear()

    def add_preview_thumbnail(self, cv_img, index, status, shift, rect):
        def _add():
            try:
                if len(cv_img.shape) == 3:
                    img_rgb = cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB)
                else:
                    img_rgb = cv2.cvtColor(cv_img, cv2.COLOR_GRAY2RGB)
                
                img_pil = Image.fromarray(img_rgb)
                
                # High-res copy for magnifier
                large_w, large_h = 450, 160
                img_large = img_pil.resize((large_w, large_h), Image.LANCZOS)
                tk_large = ImageTk.PhotoImage(img_large)

                # Thumbnail Image (Larger)
                thumb_w, thumb_h = 220, 85
                img_thumb = img_pil.resize((thumb_w, thumb_h), Image.LANCZOS)
                tk_thumb = ImageTk.PhotoImage(img_thumb)
                
                # Container
                item_frame = ttk.Frame(self.preview_frame, padding=5, bootstyle="secondary")
                item_frame.pack(side=LEFT, padx=10)
                item_frame.tk_large = tk_large # v1.2.4: Keep strong reference to prevent garbage collection
                
                # Image on Left
                border_color = "#00FF00" if status == 'pass' else "#FF0000"
                lbl_img = tk.Label(item_frame, image=tk_thumb, bg=border_color, bd=2)
                lbl_img.image = tk_thumb 
                lbl_img.pack(side=LEFT)
                
                # Info on Right
                info_frame = ttk.Frame(item_frame)
                info_frame.pack(side=LEFT, padx=10)
                
                status_zh = "通過" if status == 'pass' else "不合格"
                lbl_index = ttk.Label(info_frame, text=f"目標 T{index}", font=("Helvetica", 10, "bold"))
                lbl_index.pack(anchor=W)
                
                lbl_shift_x = ttk.Label(info_frame, text=f"位移: {shift}px", font=("Helvetica", 9))
                lbl_shift_x.pack(anchor=W)
                
                # Keep references to prevent GC
                item_frame.tk_large = tk_large

                # Hover Arrow & Magnifier Logic (Singleton v1.2.7 Fix)
                def show_hover(event):
                    # 1. Kill any existing popups first
                    self.clear_all_popups()
                    
                    # 2. Set PERMANENT hide flag and Redraw
                    self.hide_result_permanently = True
                    self.redraw_current()
                    
                    # 3. Draw Arrow
                    self.show_target_arrow(rect)
                    
                    # 4. Create NEW single popup magnifier
                    mag = tk.Toplevel(self.root)
                    mag.overrideredirect(True)
                    mag.attributes("-topmost", True)
                    self.global_mag_popups.append(mag)
                    
                    l = tk.Label(mag, image=tk_large, bg="white", bd=2)
                    l.image = tk_large
                    l.pack()
                    
                    x_p, y_p = event.x_root + 20, event.y_root - 180
                    mag.geometry(f"+{x_p}+{y_p}")

                def hide_hover(event):
                    self.hide_target_arrow()
                    # Do NOT reset hide_result_permanently here
                    # Do NOT redraw_current here (keep it hidden)
                    self.clear_all_popups()

                def move_mag(event):
                    for mag in self.global_mag_popups:
                        try:
                            if mag.winfo_exists():
                                x_p, y_p = event.x_root + 20, event.y_root - 180
                                mag.geometry(f"+{x_p}+{y_p}")
                        except: pass

                # Bind to all elements in the thumbnail for reliability (v1.2.9)
                for w in [item_frame, lbl_img, info_frame, lbl_index, lbl_shift_x]:
                    w.bind("<Enter>", show_hover)
                    w.bind("<Leave>", hide_hover)
                    w.bind("<Motion>", move_mag)
                
                # Double insurance on references
                item_frame.img_ref_l = tk_large
                item_frame.img_ref_t = tk_thumb
                lbl_img.img_ref = tk_thumb

                self.preview_widgets.append(item_frame)
                self.preview_canvas.update_idletasks()
                self.preview_canvas.configure(scrollregion=self.preview_canvas.bbox("all"))
                self.preview_canvas.xview_moveto(1.0)
            except Exception as e:
                print(f"Thumbnail Error: {e}")
                
        self.root.after(0, _add)

    def show_target_arrow(self, rect):
        """Draw a high-visibility diagonal arrow and a box around the target area."""
        if not hasattr(self, 'current_ratio'): return
        
        rx1, ry1, rx2, ry2 = rect
        ratio = self.current_ratio
        
        # Canvas coordinates (North anchor +10 offset)
        tx1, ty1 = int(rx1 * ratio), int(ry1 * ratio) + 10
        tx2, ty2 = int(rx2 * ratio), int(ry2 * ratio) + 10
        center_x = (tx1 + tx2) // 2
        center_y = (ty1 + ty2) // 2
        
        # Clear previous indicators
        self.canvas.delete("target_arrow")
        
        # 1. Draw a big high-visibility dashed box around the area
        # Outline with black first for contrast, then bright yellow
        padding = 10
        self.canvas.create_rectangle(tx1-padding-2, ty1-padding-2, tx2+padding+2, ty2+padding+2, 
                                    outline="black", width=5, tags="target_arrow")
        self.canvas.create_rectangle(tx1-padding, ty1-padding, tx2+padding, ty2+padding, 
                                    outline="#FFFF00", width=3, dash=(8, 4), tags="target_arrow")
        
        # 2. Draw a thick diagonal arrow pointing to the corner
        # Starting from top-left offset
        start_x, start_y = tx1 - 80, ty1 - 80
        end_x, end_y = tx1 - 5, ty1 - 5
        
        # Shadow for arrow
        self.canvas.create_line(start_x+2, start_y+2, end_x+2, end_y+2, 
                                arrow=LAST, fill="black", width=8, tags="target_arrow", arrowshape=(25, 30, 12))
        # Main arrow
        self.canvas.create_line(start_x, start_y, end_x, end_y, 
                                arrow=LAST, fill="#FF6600", width=6, tags="target_arrow", arrowshape=(25, 30, 12))
        
        # Label with shadow
        self.canvas.create_text(start_x+2, start_y-18, text="FOCUS", fill="black", 
                                font=("Helvetica", 16, "bold"), tags="target_arrow")
        self.canvas.create_text(start_x, start_y-20, text="FOCUS", fill="#FFFF00", 
                                font=("Helvetica", 16, "bold"), tags="target_arrow")

    def hide_target_arrow(self):
        self.canvas.delete("target_arrow")

    def analysis_done(self):
        self.is_analyzing = False
        self.stop_event.set()
        self.analyze_btn.config(state=NORMAL)
        self.status_var.set("分析完成")

    def export_results(self):
        if not self.results_data:
            self.log("沒有資料可以匯出。")
            return
            
        save_path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV 檔案", "*.csv")],
            initialfile=f"splicing_results_{time.strftime('%Y%m%d_%H%M%S')}.csv"
        )
        
        if save_path:
            import csv
            try:
                with open(save_path, 'w', newline='', encoding='utf-8-sig') as f:
                    writer = csv.writer(f)
                    writer.writerow(["檔案名稱", "目標索引", "像素偏移 (px)", "狀態", "時間戳記"])
                    writer.writerows(self.results_data)
                self.log(f"結果已儲存至: {os.path.basename(save_path)}")
            except Exception as e:
                self.log(f"匯出失敗: {str(e)}")

if __name__ == "__main__":
    root = ttk.Window(themename="darkly")
    app = SplicingGUI(root)
    root.mainloop()
