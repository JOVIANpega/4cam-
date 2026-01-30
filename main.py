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
from ttkbootstrap.scrolled import ScrolledFrame

VERSION = "1.5.0"

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
        
        # v1.2.1: Custom Tab Styling (Premium Hover / Selection Effect)
        self.style.configure("Custom.TNotebook", background="#1a1a1a", borderwidth=0)
        self.style.configure("Custom.TNotebook.Tab", 
                             padding=[15, 8], 
                             font=("Microsoft JhengHei", 10, "bold"),
                             background="#323232",
                             foreground="#aaaaaa",
                             borderwidth=0)
        self.style.map("Custom.TNotebook.Tab",
                       background=[("selected", "#007bff"), ("active", "#4e5d6c")], 
                       foreground=[("selected", "#ffffff"), ("active", "#ffffff")])
        
        # v1.2.6: Premium Button Handover (Hover) Effects
        # We increase the brightness/contrast on hover for all major button types
        self.style.map("primary.TButton", background=[("active", "#0056b3"), ("pressed", "#004085")])
        self.style.map("secondary.TButton", background=[("active", "#5a6268"), ("pressed", "#4e555b")])
        self.style.map("success.TButton", background=[("active", "#218838"), ("pressed", "#1e7e34")])
        self.style.map("warning.TButton", background=[("active", "#e0a800"), ("pressed", "#d39e00")])
        self.style.map("danger.TButton", background=[("active", "#c82333"), ("pressed", "#bd2130")])
        self.style.map("info.TButton", background=[("active", "#138496"), ("pressed", "#117a8b")])
        
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
        self.file_source_map = {} # v1.7.5: Map filepath -> source name (folder or zip)
        self._hover_timer = None # v1.7.5: Timer for grid hover delay
        
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
        
        # Center Frame for Buttons (Bookmark-style Grid)
        btn_container = ttk.Frame(self.left_panel)
        btn_container.pack(fill=X, pady=10)
        
        # Row 1: Load Actions (3 columns)
        row1 = ttk.Frame(btn_container)
        row1.pack(fill=X)
        
        btn_load_single = ttk.Button(row1, text="📂 單張照片", bootstyle=PRIMARY, command=self.load_image, cursor="hand2")
        btn_load_single.pack(side=LEFT, fill=X, expand=YES, padx=1, pady=2)
        self.font_widgets_buttons.append(btn_load_single)
        ToolTip(btn_load_single, text="選擇單個圖片檔案進行分析")
        
        btn_load_folder = ttk.Button(row1, text="📁 載入資料夾", bootstyle=SECONDARY, command=self.load_folder, cursor="hand2")
        btn_load_folder.pack(side=LEFT, fill=X, expand=YES, padx=1, pady=2)
        self.font_widgets_buttons.append(btn_load_folder)
        ToolTip(btn_load_folder, text="選擇一個資料夾進行批次分析")
        
        btn_load_zip = ttk.Button(row1, text="📦 載入壓縮檔", bootstyle=WARNING, command=self.load_zip, cursor="hand2")
        btn_load_zip.pack(side=LEFT, fill=X, expand=YES, padx=1, pady=2)
        self.font_widgets_buttons.append(btn_load_zip)
        ToolTip(btn_load_zip, text="選擇 ZIP/7z 檔案進行分析")
        
        # Row 2: Control & Utils (4 columns)
        row2 = ttk.Frame(btn_container)
        row2.pack(fill=X)
        
        self.analyze_btn = ttk.Button(row2, text="🚀 開始分析", bootstyle=SUCCESS, command=self.start_analysis, cursor="hand2")
        self.analyze_btn.pack(side=LEFT, fill=X, expand=YES, padx=1, pady=2)
        self.font_widgets_buttons.append(self.analyze_btn)
        ToolTip(self.analyze_btn, text="啟動自動化檢測流程")
        
        self.copy_log_btn = ttk.Button(row2, text="📋 複製", bootstyle=INFO, command=self.copy_log, cursor="hand2")
        self.copy_log_btn.pack(side=LEFT, fill=X, expand=YES, padx=1, pady=2)
        self.font_widgets_buttons.append(self.copy_log_btn)
        ToolTip(self.copy_log_btn, text="複製日誌文字")
        
        self.clear_log_btn = ttk.Button(row2, text="🗑️ 清空", bootstyle=DANGER, command=self.clear_log, cursor="hand2")
        self.clear_log_btn.pack(side=LEFT, fill=X, expand=YES, padx=1, pady=2)
        self.font_widgets_buttons.append(self.clear_log_btn)
        ToolTip(self.clear_log_btn, text="清除目前日誌")
        
        # v1.8.0: Enable Stats Dashboard Button
        self.stat_btn = ttk.Button(row2, text="📊 數據統計", bootstyle=INFO, command=lambda: self.notebook.select(3), cursor="hand2")
        self.stat_btn.pack(side=LEFT, fill=X, expand=YES, padx=1, pady=2)
        self.font_widgets_buttons.append(self.stat_btn)
        ToolTip(self.stat_btn, text="查看批次分析數據總覽與良率統計")
        
        ttk.Separator(self.left_panel, orient=HORIZONTAL).pack(fill=X, pady=10)
        
        # Log Area - Restored to left_panel
        self.log_area = ttk.ScrolledText(self.left_panel, width=30, font=("Microsoft JhengHei", 10))
        self.log_area.pack(fill=BOTH, expand=YES, pady=5)
        
        self.log_area.tag_config("pass_text", foreground="#00FF00", font=("Microsoft JhengHei", 10, "bold"))
        self.log_area.tag_config("fail_text", foreground="#FF0000", font=("Microsoft JhengHei", 10, "bold"))
        self.log_area.tag_config("blue_text", foreground="#00BFFF", font=("Microsoft JhengHei", 10, "bold"))
        
        # Right Panel - Notebook with Tabs
        self.right_panel = ttk.Frame(self.paned)
        self.paned.add(self.right_panel, weight=4)
        
        # Revert to standard notebook to restore theme inheritance
        self.notebook = ttk.Notebook(self.right_panel, cursor="hand2")
        self.notebook.pack(fill=BOTH, expand=YES, padx=5, pady=5)

        # Restore Sash Position (v1.2.0)
        sash_pos = self.gui_config.get("sash_pos", 350)
        self.root.after(200, lambda: self.paned.sashpos(0, sash_pos))

        # Tab Change Binding (v1.2.1)
        self.notebook.bind("<<NotebookTabChanged>>", self.on_tab_change)
        
        # --- TAB 1: Image View ---
        self.img_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.img_tab, text=" [ 圖片顯示 (Image View) ] ")
        
        # v1.9.1: Main Layout Split using PanedWindow (Left: Image+Snaps, Right: Grid Sidebar)
        self.img_paned = ttk.PanedWindow(self.img_tab, orient=HORIZONTAL)
        self.img_paned.pack(fill=BOTH, expand=YES)

        # Left main area (Navigation bar + Image + Snapshots)
        self.img_left_area = ttk.Frame(self.img_paned)
        self.img_paned.add(self.img_left_area, weight=5)

        # Right sidebar for the navigation grid
        # v1.9.6: Use a safer default and minimum width
        self.saved_sidebar_w = self.gui_config.get("img_sidebar_width", 350)
        if self.saved_sidebar_w < 50: self.saved_sidebar_w = 350
        
        self.sidebar_outer = ttk.Frame(self.img_paned, width=self.saved_sidebar_w)
        self.img_paned.add(self.sidebar_outer, weight=0)

        # Restore img_paned sash (v1.9.6: More robust multi-stage restoration)
        def _do_restore():
             try:
                 self.root.update_idletasks()
                 total_w = self.img_paned.winfo_width()
                 if total_w > 100:
                     # Calculate X position from right
                     target_x = total_w - self.saved_sidebar_w
                     if 50 < target_x < total_w - 50:
                        self.img_paned.sashpos(0, target_x)
             except: pass

        # Try once soon, and once later after window fully settles
        self.root.after(400, _do_restore)
        self.root.after(1000, _do_restore)

        # 1. Navigation at TOP
        self.nav_frame = ttk.Frame(self.img_left_area, padding=(10, 2))
        self.nav_frame.pack(fill=X, side=TOP)
        
        self.nav_label = ttk.Label(self.nav_frame, text="0 / 0", font=("Helvetica", 11, "bold"))
        self.nav_label.pack_forget() # Watermark will handle this (v1.5.3)
        
        # v1.5.2: Source Title
        self.source_label = ttk.Label(self.nav_frame, text="[ 未載入 ]", font=("Microsoft JhengHei", 10))
        self.source_label.pack_forget() # Watermark will handle this (v1.5.3)
        
        # 2. Console Area at BOTTOM (Snapshots ONLY - Reduced height v1.9.0)
        self.preview_outer = ttk.Frame(self.img_left_area, height=160) 
        self.preview_outer.pack(fill=X, side=BOTTOM, padx=5, pady=5)
        self.preview_outer.pack_propagate(False)
        
        # --- Section A: Target Snapshots ---
        lbl_preview = ttk.Label(self.preview_outer, text="🔍 目前目標區塊快照 (Target Snapshots):", font=("Helvetica", 12, "bold"))
        lbl_preview.pack(anchor=W, padx=5, pady=(5, 2))
        self.font_widgets_labels.append(lbl_preview)
        
        preview_scroll = ttk.Scrollbar(self.preview_outer, orient=HORIZONTAL)
        preview_scroll.pack(side=TOP, fill=X) # Scrollbar for snapshots
        
        self.preview_canvas = tk.Canvas(self.preview_outer, height=100, bg="#2d2d2d", 
                                       highlightthickness=0, xscrollcommand=preview_scroll.set)
        self.preview_canvas.pack(side=TOP, fill=X, pady=2)
        preview_scroll.config(command=self.preview_canvas.xview)
        
        self.preview_frame = ttk.Frame(self.preview_canvas)
        self.preview_canvas.create_window((0, 0), window=self.preview_frame, anchor=NW)
        self.preview_frame.bind("<Configure>", lambda e: self.preview_canvas.configure(scrollregion=self.preview_canvas.bbox("all")))
        self.preview_widgets = []

        # 3. Canvas in the MIDDLE
        self.canvas_frame = ttk.Frame(self.img_left_area)
        self.canvas_frame.pack(fill=BOTH, expand=YES)
        
        self.canvas = tk.Canvas(self.canvas_frame, bg="#1a1a1a", highlightthickness=0)
        self.canvas.pack(fill=BOTH, expand=YES)

        # --- Section B: Image Navigation Grid (Now inside Sidebar) ---
        grid_header = ttk.Frame(self.sidebar_outer)
        grid_header.pack(fill=X, pady=(5, 5))
        lbl_grid = ttk.Label(grid_header, text="📑 批次清單 (Batch List):", font=("Helvetica", 12, "bold"))
        lbl_grid.pack(side=LEFT, padx=5)
        self.font_widgets_labels.append(lbl_grid)
        
        # Helper label for context
        lbl_sub = ttk.Label(self.sidebar_outer, text="[點擊可快速切換圖片]", font=("Microsoft JhengHei", 9), foreground="gray")
        lbl_sub.pack(anchor=W, padx=10, pady=(0, 5))
        self.font_widgets_labels.append(lbl_sub)
        
        self.bookmark_outer = ttk.Frame(self.sidebar_outer)
        self.bookmark_outer.pack(fill=BOTH, expand=YES, padx=5, pady=5)
        
        # Grid Scrollbar (Vertical - Standard for sidebars)
        bookmark_scroll = ttk.Scrollbar(self.bookmark_outer, orient=VERTICAL)
        bookmark_scroll.pack(side=RIGHT, fill=Y)
        
        self.bookmark_canvas = tk.Canvas(self.bookmark_outer, bg="#1a1a1a", highlightthickness=0,
                                         yscrollcommand=bookmark_scroll.set)
        self.bookmark_canvas.pack(side=LEFT, fill=BOTH, expand=YES)
        bookmark_scroll.config(command=self.bookmark_canvas.yview)
        self.bookmark_widgets = []

        # Bind resize event to reflow grid items
        self.bookmark_canvas.bind("<Configure>", lambda e: self.update_nav_ui())
        
        # --- TAB 2: Settings ---
        self.settings_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.settings_tab, text=" [ 參數設定 (Settings) ] ")
        
        # --- TAB 5: Dashboard (v1.8.3: Restored to Right Panel) ---
        self.dashboard_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.dashboard_tab, text=" [ 數據總覽 (Dashboard) ] ")
        
        dash_scroll = ScrolledFrame(self.dashboard_tab, autohide=True)
        dash_scroll.pack(fill=BOTH, expand=YES)
        self.dash_content = dash_scroll
        
        self.dash_summary_frame = ttk.Frame(self.dash_content.container, padding=20)
        self.dash_summary_frame.pack(fill=X)
        self.dash_detail_frame = ttk.Frame(self.dash_content.container, padding=20)
        self.dash_detail_frame.pack(fill=BOTH, expand=YES)
        self.update_dashboard_empty()

        # --- TAB 6: User Manual (v2.3.0: Moved to Rightmost, HTML Based) ---
        self.help_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.help_tab, text=" [ 操作須知 (Guide) ] ")
        
        guide_frame = ttk.Frame(self.help_tab, padding=50)
        guide_frame.pack(fill=BOTH, expand=YES)
        
        ttk.Label(guide_frame, text="📖 系統操作維護手冊", font=("Helvetica", 24, "bold"), bootstyle=PRIMARY).pack(pady=(50, 20))
        ttk.Label(guide_frame, text="點擊下方按鈕以瀏覽詳細的圖文操作說明 (HTML 格式)。", font=("Microsoft JhengHei", 14)).pack(pady=10)
        
        btn_open_manual = ttk.Button(guide_frame, text="🌐 開啟完整操作手冊", 
                                    bootstyle=INFO, 
                                    command=self.open_html_manual, cursor="hand2", width=30)
        btn_open_manual.pack(pady=40)
        self.font_widgets_buttons.append(btn_open_manual)
        

        self.update_dashboard_empty()

        
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

        # v1.2.6: Archive Filter Keyword Setting
        ttk.Separator(param_frame, orient=HORIZONTAL).pack(fill=X, pady=15)
        
        filter_frame = ttk.Frame(param_frame)
        filter_frame.pack(fill=X, pady=5)
        
        lbl_filter = ttk.Label(filter_frame, text="🔍 影像名稱關鍵字 (Filename Keyword):", font=("Helvetica", 12, "bold"))
        lbl_filter.pack(side=LEFT, padx=(0, 10))
        self.font_widgets_labels.append(lbl_filter)
        
        self.keyword_entry = ttk.Entry(filter_frame, textvariable=self.zip_filter_var, width=15)
        self.keyword_entry.pack(side=LEFT)
        ToolTip(self.keyword_entry, text="載入 資料夾 或 壓縮檔 時，僅會提取檔名包含此關鍵字的檔案。\n例如: 4cam_cam (留空則不篩選)")

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
            "mag_factor": 1.5,
            "img_sidebar_width": 240
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
            
            # CRITICAL: Only save width if the widget is actually drawn (>10px)
            # This prevents saving 1px width when closing while on a different tab.
            curr_w = self.sidebar_outer.winfo_width()
            if curr_w > 50:
                self.gui_config["img_sidebar_width"] = curr_w
            
            # Legacy cleanup
            if "img_sash_pos" in self.gui_config: del self.gui_config["img_sash_pos"]
            
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
        # v1.3.0: Per-Image Log Isolation logic
        tag = None
        is_fail = False
        
        # Determine Tag and Pass/Fail status
        if "FAIL" in message or "[NG]" in message:
            is_fail = True
        
        if "PixelsShift" in message and "=" in message:
            try:
                val_str = message.split("=")[-1].strip()
                val = float(val_str)
                if val >= self.fail_thd_var.get():
                    is_fail = True
            except: pass
            
        if "=================" in message or "參數值:" in message:
            tag = "blue_text"
        elif "PASS" in message or "[OK]" in message:
            tag = "pass_text"
        elif is_fail:
            tag = "fail_text"
            
        # 1. Store in History if currently analyzing a specific file
        # We check both is_analyzing and current_image_path
        if self.is_analyzing and self.current_image_path in self.analysis_history:
            if 'log_entries' not in self.analysis_history[self.current_image_path]:
                self.analysis_history[self.current_image_path]['log_entries'] = []
            self.analysis_history[self.current_image_path]['log_entries'].append((message, tag))

        # 2. Update UI Real-time
        def _log():
            start_pos = self.log_area.index("end-1c")
            self.log_area.insert(END, message + "\n")
            if tag:
                self.log_area.tag_add(tag, start_pos, "end-1c")
            # v1.4.0: Always keep scrolling to the end for the persistent session log
            self.log_area.see(END)
        self.root.after(0, _log)

    def reset_defaults(self):
        self.diff_thd_var.set(self.DEFAULT_DIFF)
        self.rate_thd_var.set(self.DEFAULT_RATE)
        self.fail_thd_var.set(self.DEFAULT_FAIL)
        self.zip_filter_var.set("4cam_cam")
        self.gui_font_size_var.set(12)
        self.log("參數與關鍵字已恢復為預設值。")

    def apply_ui_font(self):
        size = self.gui_font_size_var.get()
        self.font_size_label.config(text=str(size))
        
        # v1.7.1: Apply to global TNotebook.Tab class for maximum compatibility
        # Using string format "50 25" which is most stable in Tcl
        self.style.configure("TNotebook.Tab", 
                            font=("Helvetica", size, "bold"), 
                            padding="50 25")
        
        # Ensure the styling stays even when clicked
        self.style.map("TNotebook.Tab",
                      padding=[("selected", "50 25"), ("active", "50 25")],
                      background=[("active", "#6f42c1"), ("selected", "#502ba0")]) # Premium Purple handover
        
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
            
        # Update Manual tab font (Microsoft JhengHei) - Deprecated in v2.3.0 as using HTML
        pass
            
        # Update Status Bar
        if hasattr(self, 'status_bar'):
            self.status_bar.configure(font=("Helvetica", size))
            
        self.log_area.tag_config("blue_text", font=("Microsoft JhengHei", size, "bold"))
        
        # v1.8.5: Refresh Dashboard if it exists
        if hasattr(self, 'dash_summary_frame'):
            self.update_dashboard()

    def open_html_manual(self):
        """v2.3.0: Open external HTML manual in default browser"""
        manual_path = os.path.abspath("MANUAL.html")
        if os.path.exists(manual_path):
            import webbrowser
            webbrowser.open(f"file://{manual_path}")
        else:
            tk.messagebox.showerror("錯誤", "找不到 MANUAL.html 文件，請確認檔案是否存在於程式目錄。")

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
        """Full System Reset (v1.8.7): Restore GUI to 'just opened' state"""
        # 1. Clear Data States
        self.log_area.delete('1.0', END)
        self.batch_files = []
        self.batch_index = 0
        self.current_image_path = None
        self.analysis_history = {}
        self.file_source_map = {}
        self.results_data = [] # Clear CSV data
        
        # 2. Reset UI Labels
        self.source_label.config(text="[ 未載入 ]")
        self.status_var.set("就緒")
        self.nav_label.config(text="0 / 0")
        
        # 3. Clear Visual Components
        self.canvas.delete("all")      # Clear Image
        self.clear_previews()          # Clear Snapshots
        self.bookmark_canvas.delete("all") # Clear Grid
        self.update_dashboard_empty() # Reset Statistics
        
        # 4. Clean temp refs
        if self.temp_extract_dir and os.path.exists(self.temp_extract_dir):
            try: shutil.rmtree(self.temp_extract_dir)
            except: pass
        self.temp_extract_dir = None
        
        self.log("系統已全面清空並恢復初始化狀態。")

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
        """Load images from ZIP/7z using the keyword from Settings (v1.2.6)"""
        archive_paths = filedialog.askopenfilenames(filetypes=[("壓縮檔案", "*.zip *.7z"), ("所有檔案", "*.*")])
        if not archive_paths: return
        
        keyword = self.zip_filter_var.get().strip()
        self.log(f"開始載入壓縮檔，使用設定值過濾: '{keyword}'")
        self._process_archive_files(archive_paths, keyword)

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
        
        self.file_source_map = {} # v1.7.5 Reset mapping
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
                                    self.file_source_map[target_path] = a_name
                                    
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
                                            self.file_source_map[dst_path] = a_name
                            
                            # 4. Clean up sub-root
                            try: shutil.rmtree(sub_root)
                            except: pass
                
                self.log(f"  -> {a_name}: 總計 {archives_found} 檔案, 符合篩選 {archives_matched} 個。")
                                
            except Exception as e:
                self.log(f"讀取壓縮檔 {a_name} 失敗: {str(e)}")

        if extracted_files:
            # Update source label for archives
            if len(archive_paths) == 1:
                self.source_label.config(text=f"📦 當前壓縮檔: {os.path.basename(archive_paths[0])}")
            else:
                self.source_label.config(text=f"📦 多重壓縮檔 ({len(archive_paths)} 個)")
                
            self.analysis_history = {} # Reset for new batch
            self.batch_files = extracted_files
            self.batch_index = 0
            self.current_image_path = self.batch_files[0]
            self.display_image(self.current_image_path)
            self.update_nav_ui()
            self.notebook.select(0)
            
            msg = f"載入成功！共從壓縮檔中提取 {len(extracted_files)} 張符合關鍵字 '{keyword}' 的圖片。"
            self.log(msg)
            
            if self.auto_analyze_var.get():
                self.start_analysis(mode="all")
            else:
                self.clear_previews()
        else:
            self.log(f"找不到符合關鍵字 '{keyword}' 的影像檔案。")

    def load_folder(self):
        folder = filedialog.askdirectory(initialdir=self.last_dir)
        if not folder: return
        
        try:
            self.last_dir = folder
            if self.auto_clear_log_var.get():
                self.clear_log()
            
            # Update source label immediately for feedback
            self.source_label.config(text=f"📂 當前資料夾: {os.path.basename(folder)}")
            
            # v1.6.1: Improved Diagnostic - list ALL files first for troubleshooting
            # Added .jpeg support
            itms = os.listdir(folder)
            all_files_cnt = len([f for f in itms if os.path.isfile(os.path.join(folder, f))])
            valid_exts = ('.jpg', '.jpeg', '.png', '.bmp')
            all_imgs = [f for f in itms if f.lower().endswith(valid_exts)]
            
            self.log(f"正在掃描資料夾: {folder} (共找到 {all_files_cnt} 個檔案)")
            
            keyword = self.zip_filter_var.get().strip().lower()
            self.file_source_map = {} # v1.7.5 Reset mapping
            if keyword:
                self.batch_files = [os.path.join(folder, f) for f in all_imgs if keyword in f.lower()]
            else:
                self.batch_files = [os.path.join(folder, f) for f in all_imgs]
            
            # Populate mapping for folder mode
            folder_name = os.path.basename(folder)
            for path in self.batch_files:
                self.file_source_map[path] = folder_name

            if self.batch_files:
                self.analysis_history = {}
                self.batch_index = 0
                self.current_image_path = self.batch_files[0]
                
                # Force UI Update sequence
                self.update_nav_ui()
                self.display_image(self.current_image_path)
                self.notebook.select(0)
                
                filter_msg = f" (關鍵字篩選: '{keyword}')" if keyword else ""
                log_msg = f"載入成功: 已從 {len(all_imgs)} 張符合格式的照片中，載入 {len(self.batch_files)} 張{filter_msg}"
                self.log(log_msg)
                self.status_var.set(f"載入成功: {len(self.batch_files)} 張")
                
                if self.auto_analyze_var.get():
                    self.start_analysis(mode="all")
                else:
                    self.clear_previews()
            else:
                if keyword and all_imgs:
                    msg = f"資料夾內有 {len(all_imgs)} 張照片，但檔名皆不包含關鍵字 '{keyword}'。"
                    self.log(msg)
                    tk.messagebox.showwarning("篩選結果為空", msg)
                else:
                    # v1.6.2: Add hint of what WAS found to help user realize if they chose wrong folder
                    other_files = [f for f in itms if os.path.isfile(os.path.join(folder, f))][:3]
                    hint = f"\n資料夾內的前幾個檔案為: {', '.join(other_files)}" if other_files else "\n資料夾完全為空。"
                    msg = f"未發現支援格式 (*.jpg, *.jpeg, *.png, *.bmp)。\n資料夾檔案總數: {all_files_cnt}{hint}"
                    self.log(msg)
                    tk.messagebox.showerror("載入失敗", msg)
                    self.status_var.set("無效資料夾")
        except Exception as e:
            self.log(f"載入資料夾時發生未預期錯誤: {str(e)}")
            self.status_var.set("載入異常")

    def display_image(self, path, overlay_info=None, refresh_log=False):
        if path is None:
            self.log("畫布顯示失敗: 路徑為空 (Path is None)")
            return
            
        # v1.4.0: SESSION LOG PERSISTENCE
        # We NO LONGER clear the log_area here. 
        # The main log stays as a full record of the session.
        # Specific image details will be drawn as an OVERLAY on the image.
            
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
            self.root.update_idletasks() # Ensure accurate layout for measurement
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

                    if not self.hide_result_permanently and not self.is_analyzing:
                        # Create a transparent layer for the text background
                        try:
                            # v1.5.8: Use alpha 60 for clean transparency (approx. 75% transparent)
                            text_str = status_text
                            t_bbox = draw.textbbox((rx1, ry1 - font_size - 10), text_str, font=target_font)
                            bg_w, bg_h = img_resized.size
                            overlay = Image.new('RGBA', (bg_w, bg_h), (0, 0, 0, 0))
                            overlay_draw = ImageDraw.Draw(overlay)
                            
                            bg_padding = 5
                            bg_label = [t_bbox[0]-bg_padding, t_bbox[1]-bg_padding, t_bbox[2]+bg_padding, t_bbox[3]+bg_padding]
                            # v1.5.8: High transparency (Alpha 60)
                            overlay_draw.rectangle(bg_label, fill=(0, 0, 0, 60)) 
                            img_resized.paste(overlay, (0, 0), overlay)
                            
                            # Re-bind draw object and write text
                            draw = ImageDraw.Draw(img_resized)
                            draw.text((rx1, ry1 - font_size - 10), text_str, fill=color, font=target_font)
                        except:
                            pass

                    # Always draw the bounding boxes
                    for i in range(4):
                        draw.rectangle([rx1-i, ry1-i, rx2+i, ry2+i], outline=color, width=3)

                # 3. Draw Watermark Final Result (Top Layer)
                final_res = overlay_info.get('final_result')
                if final_res and not self.hide_result_permanently:
                    overlay_layer = Image.new('RGBA', (new_w, new_h), (0, 0, 0, 200))
                    img_resized.paste(overlay_layer, (0, 0), overlay_layer)
                    draw = ImageDraw.Draw(img_resized)
                    
                    res_text = "PASS" if final_res == 'pass' else "FAIL"
                    res_color = "#00FF00" if final_res == 'pass' else "#FF0000"
                    
                    try:
                        font_paths = ["C:\\Windows\\Fonts\\arialbd.ttf", "arial.ttf"]
                        f_giant = None
                        for fp in font_paths:
                            if os.path.exists(fp):
                                f_giant = ImageFont.truetype(fp, 180)
                                break
                        if not f_giant: f_giant = ImageFont.load_default()
                        
                        f_small = None
                        for fp in font_paths:
                            if os.path.exists(fp):
                                f_small = ImageFont.truetype(fp, 60)
                                break
                        if not f_small: f_small = ImageFont.load_default()
                        
                        # Source/Index fonts
                        try:
                            f_src = ImageFont.truetype("msjhbd.ttc", 35) # Blueish Source
                            f_nav = ImageFont.truetype("arialbd.ttf", 45) # Grey Index
                        except:
                            f_src = ImageFont.load_default()
                            f_nav = ImageFont.load_default()

                        fname = os.path.basename(path)
                        # v1.7.5: Use dynamic mapping to show exact ZIP/Folder name
                        source_raw = self.file_source_map.get(path, self.source_label.cget("text"))
                        nav_text = f"{self.batch_index + 1} / {len(self.batch_files)}"
                        
                        # Decide if we show source/index
                        show_source = len(self.batch_files) > 1 and "[ 未載入 ]" not in source_raw
                        show_index = len(self.batch_files) > 1

                        # Get all dimensions
                        ws, hs = (0, 0)
                        if show_source:
                            s_bbox = draw.textbbox((0,0), source_raw, font=f_src)
                            ws, hs = s_bbox[2]-s_bbox[0], s_bbox[3]-s_bbox[1]
                        
                        f_bbox = draw.textbbox((0,0), fname, font=f_small)
                        wf, hf = f_bbox[2]-f_bbox[0], f_bbox[3]-f_bbox[1]
                        
                        t_bbox = draw.textbbox((0,0), res_text, font=f_giant)
                        wt, ht = t_bbox[2]-t_bbox[0], t_bbox[3]-t_bbox[1]
                        
                        # Layout spacing
                        spacing = 30
                        total_h = hf + ht + spacing
                        if show_source: total_h += hs + spacing
                        
                        current_y = (new_h - total_h) // 2
                        
                        # 1. Source (Cyan) - Conditional
                        if show_source:
                            draw.text(((new_w - ws) // 2, current_y), source_raw, fill="#00CED1", font=f_src)
                            current_y += hs + spacing
                        
                        # 2. Filename (White)
                        draw.text(((new_w - wf) // 2, current_y), fname, fill="white", font=f_small)
                        current_y += hf + spacing
                        
                        # 3. Main Result (Green/Red)
                        draw.text(((new_w - wt) // 2, current_y), res_text, fill=res_color, font=f_giant)
                        
                        # 4. Large Index (Grey) - Conditional
                        if show_index:
                            draw.text(((new_w + wt) // 2 + 35, current_y + 40), nav_text, fill="#AAAAAA", font=f_nav)

                    except Exception as e:
                        print(f"Result Overlay Error: {e}")

                # --- SPEC ISSUE LOG ---
                if not self.is_analyzing and path in self.analysis_history and 'log_entries' in self.analysis_history[path]:
                    log_info = []
                    for msg, tag in self.analysis_history[path]['log_entries']:
                        if any(x in msg for x in ["=====", "正在分析", "參數值", "已載入", "----------"]):
                            continue
                        log_info.append((msg, tag))
                    
                    if log_info:
                        try:
                            d_font = ImageFont.truetype("msjhbd.ttc", 18) 
                            pad, tx, ty = 15, 30, 120 
                            
                            total_w, total_h = 0, 0
                            for msg, tag in log_info:
                                box = draw.textbbox((0, 0), msg, font=d_font)
                                total_w = max(total_w, box[2]-box[0])
                                total_h += (box[3]-box[1]) + 5
                            
                            # v1.5.8: Alpha 60 for truly subtle transparency
                            log_overlay = Image.new('RGBA', (new_w, new_h), (0, 0, 0, 0))
                            lo_draw = ImageDraw.Draw(log_overlay)
                            lo_draw.rectangle([tx-pad, ty-pad, tx+total_w+pad+20, ty+total_h+pad], fill=(0, 0, 0, 60)) 
                            img_resized.paste(log_overlay, (0, 0), log_overlay)
                            
                            draw = ImageDraw.Draw(img_resized)
                            curr_log_y = ty
                            for msg, tag in log_info:
                                lc = "#e0e0e0"
                                if tag == "pass_text": lc = "#00FF00"
                                elif tag == "fail_text": lc = "#FF0000"
                                elif tag == "blue_text": lc = "#00BFFF"
                                draw.text((tx, curr_log_y), msg, fill=lc, font=d_font)
                                b = draw.textbbox((0,0), msg, font=d_font)
                                curr_log_y += (b[3]-b[1]) + 5
                        except Exception as e:
                            print(f"Spec Log Overlay Error: {e}")
                

            self.tk_img = ImageTk.PhotoImage(img_resized)
            self.canvas.delete("all")
            # Anchor to CENTER (v1.4.3: Fixed tiny image/centering issue)
            self.canvas.create_image(canvas_w//2, canvas_h//2, image=self.tk_img, anchor=CENTER)
            
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

    def safe_update_ui(self, path, overlay, rect_for_arrow=None):
        try:
            self.display_image(path, overlay)
            if rect_for_arrow:
                self.show_target_arrow(rect_for_arrow)
            self.root.update_idletasks()
            self.root.update()
        except Exception as e:
            self.log(f"UI Update Error: {str(e)}")


    def start_analysis(self, mode="single"):
        """Start analysis. mode='all' for batch, mode='single' for current image only (v1.3.2)"""
        if not self.current_image_path:
            self.log("尚未載入照片。")
            return
        
        if self.is_analyzing: return
        
        # v1.5.9: If multiple files are loaded, clicking Start Analysis should re-check everything
        if len(self.batch_files) > 1:
            self.analysis_mode = "all"
            self.batch_index = 0 # Reset to start for full re-check
        else:
            self.analysis_mode = "single"
            
        self.hide_result_permanently = False 
        self.is_analyzing = True
        self.notebook.select(0) 
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
            if self.batch_files and self.analysis_mode == "all":
                # Batch mode: Analyze from current index to the end
                for i in range(self.batch_index, len(self.batch_files)):
                    if self.stop_event.is_set(): break
                    self.current_image_path = self.batch_files[i]
                    self.batch_index = i
                    self.process_single_image(self.current_image_path)
            else:
                # Single mode: Only analyze the currently selected image
                self.process_single_image(self.current_image_path)
        except Exception as e:
            self.log(f"執行分析時發生錯誤: {str(e)}")
        finally:
            self.root.after(0, self.analysis_done)

    def process_single_image(self, path):
        try:
            # v1.2.1: Always ensure history entry exists so navigation squares update
            if path not in self.analysis_history:
                self.analysis_history[path] = {'snapshots': [], 'overlay': None, 'log_entries': []}
            else:
                # v1.3.1: CRITICAL - Clear previous snapshots to prevent duplicates in preview area
                self.analysis_history[path]['snapshots'] = []
                # v1.3.0: Clear previous log entries for this path when re-analyzing
                self.analysis_history[path]['log_entries'] = []
                self.log_area.delete('1.0', END)
            
            # v1.3.1: We must NOT recall old thumbnails during analysis redraw
            self.root.after(0, self.clear_previews) 
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
                self.analysis_history[path]['is_pass'] = False
                return
                
            cv_img, steps = result
            if not steps:
                self.log(f"  [NG] 在 {os.path.basename(path)} 中未偵測到任何分析目標 (No targets found).")
                self.analysis_history[path]['is_pass'] = False
                self.root.after(0, self.safe_update_ui, path, {'final_result': 'fail'})
                return

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
                overlay = {'rect': step.get('viz_rect', step['rect']), 'text': "SCANNING", 'status': 'checking'}
                # v1.5.9: Pass rect to show FOCUS arrow during scan
                self.root.after(0, self.safe_update_ui, path, overlay.copy(), step['rect'])
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
                # v1.5.9: Maintain arrow visibility on result step
                self.root.after(0, self.safe_update_ui, path, overlay.copy(), step['rect'])
                
                fail_msg = "" if is_pass else f" (THRESHOLD {self.fail_thd_var.get()}px)"
                self.log(f"  Target {step['index']}: {shift} px -> {'PASS' if is_pass else 'FAIL'}{fail_msg}")
                
                # Add to Bottom Preview Area (v1.1.8: Horizontal + Arrow)
                self.add_preview_thumbnail(debug_roi, step['index'], status_tag, shift, step['rect'])
                
                # Store snapshot in history for navigation recall
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
            # Final Giant Overlay - Hide scan arrow
            self.root.after(0, self.hide_target_arrow) 
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
        """Update the navigation label and PASS/FAIL bookmarks (Grid Layout v1.5.0)"""
        total = len(self.batch_files)
        curr = self.batch_index + 1 if total > 0 else 0
        self.nav_label.config(text=f"{curr} / {total}")
        
        # Clear and redraw bookmarks
        self.bookmark_canvas.delete("all")
        
        # v1.9.4: Sidebar optimized layout (Text below square)
        dot_w = 38 
        dot_h = 38
        gap_y = 25 # Increase gap to fit text below
        
        canvas_w = self.bookmark_canvas.winfo_width()
        if canvas_w < 50: canvas_w = 240 
        
        # Calculate columns: Items are narrower because text is below
        # Logic: 38(square) + 15(horizontal gap) ~= 55px width per column
        cols = max(1, (canvas_w - 10) // 55)
        item_w = (canvas_w - 10) // cols
        
        start_offset_x = 10
        for i, path in enumerate(self.batch_files):
            color = "#444444" # Unprocessed
            if path in self.analysis_history:
                color = "#00FF00" if self.analysis_history[path].get('is_pass') else "#FF0000"
            
            # Grid coordinates
            row = i // cols
            col = i % cols
            
            x = start_offset_x + col * item_w
            y = row * (dot_h + gap_y) + 10
            
            # Highlight current
            outline = "#007bff" if i == self.batch_index else "#333333"
            width = 3 if i == self.batch_index else 1
            
            tag_name = f"btn_{i}"
            # Draw square
            self.bookmark_canvas.create_rectangle(x, y, x + dot_w, y + dot_h, 
                                                fill=color, outline=outline, width=width, tags=tag_name)
            
            # Add number
            self.bookmark_canvas.create_text(x + dot_w/2, y + dot_h/2, text=str(i+1), 
                                            fill="white", font=("Helvetica", 11, "bold"), tags=tag_name)
            
            # v1.9.4: Add filename suffix BELOW square
            fname = os.path.basename(path)
            parts = fname.replace('.', '_').split('_')
            cam_parts = [p for p in parts if p.lower().startswith('cam')]
            suffix = cam_parts[-1] if cam_parts else (parts[-2] if len(parts) > 1 else parts[0][:5])
            
            if len(suffix) > 8: suffix = suffix[:7] + ".."
            
            text_x = x + dot_w / 2
            text_y = y + dot_h + 12 # Directly below square
            self.bookmark_canvas.create_text(text_x, text_y, text=suffix, anchor=CENTER,
                                            fill="#9eaab7", font=("Helvetica", 8), tags=tag_name)
            
            # Interaction Bindings
            self.bookmark_canvas.tag_bind(tag_name, "<Button-1>", lambda e, idx=i: self.jump_to_image(idx))
            self.bookmark_canvas.tag_bind(tag_name, "<Enter>", lambda e, idx=i: self.bookmark_hover_enter(idx))
            self.bookmark_canvas.tag_bind(tag_name, "<Leave>", lambda e: self.on_bookmark_leave())
        
        # Dynamic Scroll Region (Vertical)
        self.bookmark_canvas.config(scrollregion=self.bookmark_canvas.bbox("all"))

    def bookmark_hover_enter(self, index):
        """Handle mouse hover over bookmark squares (v1.2.2)"""
        self.bookmark_canvas.config(cursor="hand2")
        # v1.7.5: Implement 0.5s delay before switching to prevent rapid flickering
        if not self.is_analyzing and index != self.batch_index:
            if self._hover_timer:
                self.root.after_cancel(self._hover_timer)
            self._hover_timer = self.root.after(500, lambda: self.jump_to_image(index))

    def on_bookmark_leave(self):
        """Cancel the pending jump if mouse leaves before delay"""
        self.bookmark_canvas.config(cursor="")
        if self._hover_timer:
            self.root.after_cancel(self._hover_timer)
            self._hover_timer = None

    def prev_image(self):
        if self.is_analyzing or not self.batch_files: return
        self.hide_result_permanently = False # Reset for new image
        self.batch_index = (self.batch_index - 1) % len(self.batch_files)
        self.current_image_path = self.batch_files[self.batch_index]
        self.display_image(self.current_image_path, refresh_log=True)
        self.update_nav_ui()

    def next_image(self):
        if self.is_analyzing or not self.batch_files: return
        self.hide_result_permanently = False # Reset for new image
        self.batch_index = (self.batch_index + 1) % len(self.batch_files)
        self.current_image_path = self.batch_files[self.batch_index]
        self.display_image(self.current_image_path, refresh_log=True)
        self.update_nav_ui()

    def jump_to_image(self, index):
        if self.is_analyzing: return
        self.hide_result_permanently = False # Reset for new image
        self.batch_index = index
        self.current_image_path = self.batch_files[self.batch_index]
        self.display_image(self.current_image_path, refresh_log=True)
        self.update_nav_ui()

    def on_tab_change(self, event):
        # v1.9.6: Force save config when switching tabs to capture sizes while visible
        self.save_config()
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
                lbl_index = ttk.Label(info_frame, text=f"目標 T{index}", font=("Helvetica", 16, "bold"))
                lbl_index.pack(anchor=W)
                
                lbl_shift_x = ttk.Label(info_frame, text=f"位移: {shift}px", font=("Helvetica", 12))
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
        """Draw a high-visibility diagonal arrow and a box around the target area (v1.5.1)."""
        if not hasattr(self, 'current_ratio'): return
        
        rx1, ry1, rx2, ry2 = rect
        ratio = self.current_ratio
        
        # v1.5.1: Calculate accurate offsets based on centered image (v1.4.3 layout)
        canvas_w = self.canvas.winfo_width()
        canvas_h = self.canvas.winfo_height()
        
        # We need original img_w/h to know the resized w/h
        if not hasattr(self, '_cached_img'): return
        img_w, img_h = self._cached_img.size
        new_w, new_h = int(img_w * ratio), int(img_h * ratio)
        
        off_x = (canvas_w - new_w) // 2
        off_y = (canvas_h - new_h) // 2
        
        # Canvas coordinates with offsets
        tx1, ty1 = int(rx1 * ratio) + off_x, int(ry1 * ratio) + off_y
        tx2, ty2 = int(rx2 * ratio) + off_x, int(ry2 * ratio) + off_y
        
        # Clear previous indicators
        self.canvas.delete("target_arrow")
        
        # 1. Draw a big high-visibility dashed box 
        padding = 12
        self.canvas.create_rectangle(tx1-padding-2, ty1-padding-2, tx2+padding+2, ty2+padding+2, 
                                    outline="black", width=5, tags="target_arrow")
        self.canvas.create_rectangle(tx1-padding, ty1-padding, tx2+padding, ty2+padding, 
                                    outline="#FFFF00", width=3, dash=(8, 4), tags="target_arrow")
        
        # 2. Draw a thick diagonal arrow (v1.5.1: Pointing from Right-Top to prevent Left Clipping)
        # Starting from top-right offset, pointing down-left to the top-right corner
        start_x, start_y = tx2 + 80, ty1 - 80
        end_x, end_y = tx2 + 10, ty1 - 10
        
        # Shadow for arrow
        self.canvas.create_line(start_x+2, start_y+2, end_x+2, end_y+2, 
                                arrow=LAST, fill="black", width=10, tags="target_arrow", arrowshape=(25, 30, 12))
        # Main arrow (Bright Orange for visibility)
        self.canvas.create_line(start_x, start_y, end_x, end_y, 
                                arrow=LAST, fill="#FF6600", width=8, tags="target_arrow", arrowshape=(25, 30, 12))
        
        # Label with shadow (Centered above the start of the arrow)
        self.canvas.create_text(start_x+2, start_y-18, text="FOCUS", fill="black", 
                                font=("Helvetica", 18, "bold"), tags="target_arrow")
        self.canvas.create_text(start_x, start_y-20, text="FOCUS", fill="#FFFF00", 
                                font=("Helvetica", 18, "bold"), tags="target_arrow")

    def hide_target_arrow(self):
        self.canvas.delete("target_arrow")

    def analysis_done(self):
        self.is_analyzing = False
        self.stop_event.set()
        self.root.after(0, self.hide_target_arrow)
        self.root.after(0, lambda: self.analyze_btn.config(state=NORMAL))
        self.root.after(0, lambda: self.status_var.set("分析完成"))
        self.root.after(0, self.update_dashboard) # v1.8.0

    def update_dashboard_empty(self):
        size = self.gui_font_size_var.get()
        for w in self.dash_summary_frame.winfo_children(): w.destroy()
        for w in self.dash_detail_frame.winfo_children(): w.destroy()
        ttk.Label(self.dash_summary_frame, text="📊 尚無分析數據", font=("Helvetica", int(size*1.6), "bold")).pack(pady=50)
        ttk.Label(self.dash_summary_frame, text="請先執行「開始分析」以產生統計資料。", font=("Microsoft JhengHei", size)).pack()

    def update_dashboard(self):
        """v1.8.0: Generate high-level batch analytics"""
        size = self.gui_font_size_var.get()
        if len(self.batch_files) <= 1:
            self.update_dashboard_empty()
            return
            
        # Clear existing
        for w in self.dash_summary_frame.winfo_children(): w.destroy()
        for w in self.dash_detail_frame.winfo_children(): w.destroy()
        
        # 1. Statistics Calculation
        total = len(self.batch_files)
        analyzed = len(self.analysis_history)
        pass_cnt = sum(1 for h in self.analysis_history.values() if h.get('is_pass'))
        fail_cnt = analyzed - pass_cnt
        yield_rate = (pass_cnt / analyzed * 100) if analyzed > 0 else 0
        
        # 2. Render Summary Cards
        card_container = ttk.Frame(self.dash_summary_frame)
        card_container.pack(fill=X)
        
        def create_card(parent, title, value, color):
            f = ttk.Frame(parent, bootstyle=color, padding=2, borderwidth=1, relief="solid")
            f.pack(side=LEFT, expand=YES, fill=BOTH, padx=10)
            inner = ttk.Frame(f, padding=20)
            inner.pack(fill=BOTH, expand=YES)
            ttk.Label(inner, text=title, font=("Helvetica", size)).pack()
            ttk.Label(inner, text=value, font=("Helvetica", int(size*2.2), "bold"), bootstyle=color).pack()
            return f

        create_card(card_container, "總影像數", str(total), SECONDARY)
        create_card(card_container, "已分析", str(analyzed), INFO)
        create_card(card_container, "通過 (PASS)", str(pass_cnt), SUCCESS)
        create_card(card_container, "不合格 (FAIL)", str(fail_cnt), DANGER)
        create_card(card_container, "良率 (Yield)", f"{yield_rate:.1f}%", WARNING if yield_rate < 95 else SUCCESS)

        # 3. Distribution Analysis (Which T fails most?)
        target_fail_map = {}
        fail_files = []
        for path, hist in self.analysis_history.items():
            if not hist.get('is_pass'):
                fail_files.append(path)
                for snap in hist.get('snapshots', []):
                    if snap['status'] == 'fail':
                        idx = snap['index']
                        target_fail_map[idx] = target_fail_map.get(idx, 0) + 1
        
        # 4. Render Distribution (Heatmap style)
        ttk.Label(self.dash_detail_frame, text="🎯 目標失敗頻率 (Failure Frequency per Target):", 
                  font=("Helvetica", size + 2, "bold")).pack(anchor=W, pady=(20, 10))
        
        dist_box = ttk.Frame(self.dash_detail_frame)
        dist_box.pack(fill=X)
        if not target_fail_map:
            ttk.Label(dist_box, text="（目前無失敗目標）", foreground="gray", font=("Helvetica", size)).pack(anchor=W)
        else:
            sorted_targets = sorted(target_fail_map.items(), key=lambda x: x[0])
            for idx, count in sorted_targets:
                item = ttk.Frame(dist_box, padding=5)
                item.pack(side=LEFT, padx=5)
                # Small circle/box with count
                lbl = ttk.Label(item, text=f"T{idx}", font=("Helvetica", size, "bold"), bootstyle=DANGER, width=5, anchor=CENTER)
                lbl.pack()
                ttk.Label(item, text=f"{count} 次", font=("Helvetica", size - 2)).pack()

        # 5. NG Quick-Jump Gallery (Thumbnail list of failures)
        ttk.Label(self.dash_detail_frame, text=f"🚨 不合格清單 ({len(fail_files)}):", 
                  font=("Helvetica", size + 2, "bold")).pack(anchor=W, pady=(30, 10))
        
        gallery_outer = ttk.Frame(self.dash_detail_frame)
        gallery_outer.pack(fill=X)
        
        if not fail_files:
            ttk.Label(gallery_outer, text="（目前無不合格項目，恭喜！）", bootstyle=SUCCESS, font=("Helvetica", size)).pack(anchor=W)
        else:
            gal_scroll = ttk.Scrollbar(gallery_outer, orient=HORIZONTAL)
            gal_scroll.pack(side=BOTTOM, fill=X)
            
            gal_canvas = tk.Canvas(gallery_outer, height=150 + (size-12)*3, bg="#1a1a1a", highlightthickness=0, xscrollcommand=gal_scroll.set)
            gal_canvas.pack(fill=X)
            gal_inner = ttk.Frame(gal_canvas)
            gal_canvas.create_window((0,0), window=gal_inner, anchor=NW)
            gal_scroll.config(command=gal_canvas.xview)
            
            def jump_from_dash(p):
                idx = self.batch_files.index(p)
                self.jump_to_image(idx)
                self.notebook.select(0)

            for p in fail_files[:50]: # Limit for performance
                f_name = os.path.basename(p)
                src_name = self.file_source_map.get(p, "未知來源")
                
                f_box = ttk.Frame(gal_inner, padding=5, cursor="hand2")
                f_box.pack(side=LEFT, padx=10)
                
                # v1.8.6: Show Source + Filename with enlarged font
                lbl_src = ttk.Label(f_box, text=f"📦 {src_name}", font=("Helvetica", size - 2), foreground="#AAAAAA")
                lbl_src.pack()
                
                lbl_name = ttk.Label(f_box, text=f_name[:25], font=("Helvetica", size, "bold"), bootstyle=DANGER)
                lbl_name.pack()
                
                # Button to Go
                btn_go = ttk.Button(f_box, text="🔍 檢視", bootstyle=(DANGER, OUTLINE), 
                                   command=lambda path=p: jump_from_dash(path), cursor="hand2")
                btn_go.pack(pady=5)
                self.font_widgets_buttons.append(btn_go)
                
            gal_inner.update_idletasks()
            gal_canvas.config(scrollregion=gal_canvas.bbox("all"))

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
