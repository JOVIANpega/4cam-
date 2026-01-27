import tkinter as tk
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

class SplicingGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("動態拼接檢查系統 (Dynamic Splicing Check System) - V1.0")
        self.root.geometry("1400x900")
        
        # Global Default Parameters (Synchronized with User Screenshot)
        self.DEFAULT_DIFF = 18.0
        self.DEFAULT_RATE = 0.18
        self.DEFAULT_FAIL = 5
        self.auto_analyze_var = tk.BooleanVar(value=True)
        self.auto_clear_log_var = tk.BooleanVar(value=True)
        
        # Style
        self.style = ttk.Style(theme="darkly")
        
        self.processor = SplicingProcessor()
        self.current_image_path = None
        self.batch_files = []
        self.batch_index = 0
        self.is_analyzing = False
        self.stop_event = threading.Event()
        self.results_data = [] # Store analysis results
        self.config_path = os.path.join(os.path.dirname(__file__), "gui_config.json")
        self.load_config()
        
        self.setup_ui()
        self.root.bind("<Configure>", self.on_window_resize)

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
        
        btn_load_single = ttk.Button(btn_container, text="📂 載入單張照片", width=BTN_WIDTH, bootstyle=PRIMARY, command=self.load_image)
        btn_load_single.pack(pady=5)
        ToolTip(btn_load_single, text="選擇單個圖片檔案進行分析")
        
        btn_load_folder = ttk.Button(btn_container, text="📁 載入資料夾", width=BTN_WIDTH, bootstyle=SECONDARY, command=self.load_folder)
        btn_load_folder.pack(pady=5)
        ToolTip(btn_load_folder, text="選擇一個資料夾進行批次分析")
        
        self.analyze_btn = ttk.Button(btn_container, text="🚀 開始分析", width=BTN_WIDTH, bootstyle=SUCCESS, command=self.start_analysis)
        self.analyze_btn.pack(pady=15)
        ToolTip(self.analyze_btn, text="開始執行拼接分析流程")
        
        # Log Control Buttons (Horizontal row)
        log_btn_frame = ttk.Frame(btn_container)
        log_btn_frame.pack(fill=X, pady=5)
        
        self.copy_log_btn = ttk.Button(log_btn_frame, text="📋 複製日誌", width=11, bootstyle=INFO, command=self.copy_log)
        self.copy_log_btn.pack(side=LEFT, padx=2)
        ToolTip(self.copy_log_btn, text="將日誌內容複製到剪貼簿")
        
        self.clear_log_btn = ttk.Button(log_btn_frame, text="🗑️ 清空日誌", width=11, bootstyle=DANGER, command=self.clear_log)
        self.clear_log_btn.pack(side=RIGHT, padx=2)
        ToolTip(self.clear_log_btn, text="清除所有日誌文字")
        
        ttk.Separator(self.left_panel, orient=HORIZONTAL).pack(fill=X, pady=10)
        
        self.log_area = ttk.ScrolledText(self.left_panel, width=30, height=15, font=("Consolas", 10))
        self.log_area.pack(fill=BOTH, expand=YES, pady=5)
        # Setup tags for coloring PASS/FAIL results
        self.log_area.tag_config("pass_text", foreground="#00FF00", font=("Consolas", 10, "bold"))
        self.log_area.tag_config("fail_text", foreground="#FF0000", font=("Consolas", 10, "bold"))
        
        # Debug ROI Preview
        self.roi_preview_label = ttk.Label(self.left_panel, text="目標區塊預覽 (Target ROI Preview)", font=("Helvetica", 10, "bold"))
        self.roi_preview_label.pack(pady=(10, 0))
        self.roi_canvas = tk.Canvas(self.left_panel, width=280, height=100, bg="black", highlightthickness=1, highlightbackground="gray")
        self.roi_canvas.pack(pady=5)
        
        # Right Panel - Notebook with Tabs
        self.right_panel = ttk.Frame(self.paned)
        self.paned.add(self.right_panel, weight=4)
        
        # Use a standard ttk.Notebook
        self.notebook = ttk.Notebook(self.right_panel, bootstyle=PRIMARY)
        self.notebook.pack(fill=BOTH, expand=YES, padx=5, pady=5)
        
        # --- TAB 1: Image View ---
        self.img_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.img_tab, text=" [ 圖片顯示 (Image View) ] ")
        
        self.canvas = tk.Canvas(self.img_tab, bg="#1a1a1a", highlightthickness=0)
        self.canvas.pack(fill=BOTH, expand=YES)
        
        # --- TAB 2: Settings ---
        self.settings_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.settings_tab, text=" [ 參數設定 (Settings) ] ")
        
        # Parameters Container in Settings Tab
        settings_container = ttk.Frame(self.settings_tab, padding=30)
        settings_container.pack(fill=BOTH, expand=YES)
        
        param_frame = ttk.LabelFrame(settings_container, text="算法控制 (Algorithm Control)", padding=20)
        param_frame.pack(fill=X, pady=10)
        
        # Auto Analyze Toggle
        self.auto_chk = ttk.Checkbutton(param_frame, text="載入後自動分析 (Auto-Analyze)", 
                                       variable=self.auto_analyze_var, bootstyle="round-toggle")
        self.auto_chk.pack(anchor=W, pady=(0, 10))
        ToolTip(self.auto_chk, text="啟用後，選取圖片或資料夾將自動啟動分析。")
        
        self.auto_clear_chk = ttk.Checkbutton(param_frame, text="載入時自動清空日誌 (Auto-Clear Log)", 
                                             variable=self.auto_clear_log_var, bootstyle="round-toggle")
        self.auto_clear_chk.pack(anchor=W, pady=(0, 20))
        ToolTip(self.auto_clear_chk, text="啟用後，載入新圖片或資料夾時會自動清除之前的日誌內容。")
        
        # Differential Threshold
        ttk.Label(param_frame, text="差異閾值 (Diff Threshold):", font=("Helvetica", 10)).pack(anchor=W)
        self.diff_thd_var = tk.DoubleVar(value=self.DEFAULT_DIFF)
        self.diff_slider = ttk.Scale(param_frame, from_=0, to=50, variable=self.diff_thd_var, orient=HORIZONTAL)
        self.diff_slider.pack(fill=X, pady=5)
        ToolTip(self.diff_slider, text="調整邊緣檢測的靈敏度。建議值：18。")
        self.diff_label = ttk.Label(param_frame, text="18", font=("Helvetica", 12, "bold"))
        self.diff_label.pack(anchor=E)
        self.diff_thd_var.trace_add("write", lambda *args: self.update_labels())
        
        # Rate Threshold
        ttk.Label(param_frame, text="比率閾值 (Rate Threshold):", font=("Helvetica", 10)).pack(anchor=W, pady=(15, 0))
        self.rate_thd_var = tk.DoubleVar(value=self.DEFAULT_RATE)
        self.rate_slider = ttk.Scale(param_frame, from_=0.0, to=0.5, variable=self.rate_thd_var, orient=HORIZONTAL)
        self.rate_slider.pack(fill=X, pady=5)
        ToolTip(self.rate_slider, text="調整判定鬼影比例。建議值：0.18。")
        self.rate_label = ttk.Label(param_frame, text="0.18", font=("Helvetica", 12, "bold"))
        self.rate_label.pack(anchor=E)
        self.rate_thd_var.trace_add("write", lambda *args: self.update_labels())

        # Fail Threshold
        ttk.Label(param_frame, text="不合格判定值 (Fail Threshold px):", font=("Helvetica", 10)).pack(anchor=W, pady=(15, 0))
        self.fail_thd_var = tk.IntVar(value=self.DEFAULT_FAIL)
        self.fail_slider = ttk.Scale(param_frame, from_=1, to=15, variable=self.fail_thd_var, orient=HORIZONTAL)
        self.fail_slider.pack(fill=X, pady=5)
        ToolTip(self.fail_slider, text="設定判定為 '不合格' 的最小偏移。建議值：5。")
        self.fail_label = ttk.Label(param_frame, text="5", font=("Helvetica", 12, "bold"))
        self.fail_label.pack(anchor=E)
        self.fail_thd_var.trace_add("write", lambda *args: self.update_labels())
        
        # Status Bar
        self.status_var = tk.StringVar(value="就緒")
        self.status_bar = ttk.Label(self.root, textvariable=self.status_var, relief=SUNKEN, anchor=W, padding=5)
        self.status_bar.pack(side=BOTTOM, fill=X)

    def load_config(self):
        self.gui_config = {"sash_pos": 350, "auto_analyze": True, "auto_clear_log": True}
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r') as f:
                    self.gui_config.update(json.load(f))
                    # Apply persistent preferences
                    self.auto_analyze_var.set(self.gui_config.get("auto_analyze", True))
                    self.auto_clear_log_var.set(self.gui_config.get("auto_clear_log", True))
            except: pass

    def save_config(self):
        try:
            try:
                self.gui_config["sash_pos"] = self.left_panel.winfo_width()
                self.gui_config["auto_analyze"] = self.auto_analyze_var.get()
                self.gui_config["auto_clear_log"] = self.auto_clear_log_var.get()
            except: pass
            
            with open(self.config_path, 'w') as f:
                json.dump(self.gui_config, f)
        except: pass

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
            
            # Apply color tags based on content
            if "PASS" in message or "[OK]" in message:
                self.log_area.tag_add("pass_text", start_pos, "end-1c")
            elif "FAIL" in message or "[NG]" in message:
                self.log_area.tag_add("fail_text", start_pos, "end-1c")
                
            self.log_area.see(END)
        self.root.after(0, _log)

    def reset_defaults(self):
        self.diff_thd_var.set(self.DEFAULT_DIFF)
        self.rate_thd_var.set(self.DEFAULT_RATE)
        self.fail_thd_var.set(self.DEFAULT_FAIL)
        self.log("參數已恢復為預設值。")

    def update_labels(self):
        self.diff_label.config(text=f"{int(self.diff_thd_var.get())}")
        self.rate_label.config(text=f"{self.rate_thd_var.get():.2f}")
        self.fail_label.config(text=f"{int(self.fail_thd_var.get())}")

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
        path = filedialog.askopenfilename(filetypes=[("圖片檔案", "*.jpg *.png *.bmp")])
        if path:
            if self.auto_clear_log_var.get():
                self.clear_log()
            self.current_image_path = path
            self.batch_files = []
            self.display_image(path)
            self.log(f"已載入: {os.path.basename(path)}")
            if self.auto_analyze_var.get():
                self.start_analysis()

    def load_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            if self.auto_clear_log_var.get():
                self.clear_log()
            self.batch_files = [os.path.join(folder, f) for f in os.listdir(folder) 
                                if f.lower().endswith(('.jpg', '.png', '.bmp'))]
            if self.batch_files:
                self.batch_index = 0
                self.current_image_path = self.batch_files[0]
                self.display_image(self.current_image_path)
                self.log(f"已載入資料夾: {folder} ({len(self.batch_files)} 張照片)")
                if self.auto_analyze_var.get():
                    self.start_analysis()
            else:
                self.log("資料夾內未發現支援的照片格式。")

    def display_image(self, path, overlay_info=None):
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
            
            if overlay_info:
                draw = ImageDraw.Draw(img_resized)
                rect = overlay_info.get('rect') 
                status_text = overlay_info.get('text', "")
                status = overlay_info.get('status', 'checking') 
                
                color = "yellow"
                if status == 'pass': color = "#00FF00"
                if status == 'fail': color = "#FF0000"
                
                # Giant Final Result Overlay
                final_res = overlay_info.get('final_result')
                if final_res:
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
                    
                    # Center text
                    try:
                        tw, th = draw.textsize(res_text, font=font) if hasattr(draw, 'textsize') else (400, 200)
                    except:
                        # Fallback for newer Pillow
                        bbox = draw.textbbox((0, 0), res_text, font=font)
                        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
                    draw.text(((new_w - tw)//2, (new_h - th)//2), res_text, fill=res_color, font=font)
                
                else:
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

            self.tk_img = ImageTk.PhotoImage(img_resized)
            self.canvas.delete("all")
            self.canvas.create_image(canvas_w//2, canvas_h//2, image=self.tk_img, anchor=CENTER)
        except Exception as e:
            self.log(f"畫布顯示失敗: {str(e)}")

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

    def display_roi(self, cv_img):
        def _update_roi():
            # Convert BGR to RGB
            img_rgb = cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB)
            img_pil = Image.fromarray(img_rgb)
            
            # Resize to fit roi_canvas
            w, h = 280, 100
            img_resized = img_pil.resize((w, h), Image.NEAREST) # Use nearest for pixel-level debugging
            
            self.roi_tk_img = ImageTk.PhotoImage(img_resized)
            self.roi_canvas.delete("all")
            self.roi_canvas.create_image(w//2, h//2, image=self.roi_tk_img, anchor=CENTER)
        self.root.after(0, _update_roi)

    def start_analysis(self):
        if not self.current_image_path:
            self.log("尚未載入照片。")
            return
        
        if self.is_analyzing: return
        
        self.is_analyzing = True
        self.analyze_btn.config(state=DISABLED)
        self.status_var.set("分析中...")
        
        # Apply parameters
        self.processor.diff_thd = int(self.diff_thd_var.get())
        self.processor.rate_thd = self.rate_thd_var.get()
        
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
            self.root.after(0, lambda p=path: self.display_image(p))
            # Critical: Allow UI to draw the basic image first
            time.sleep(0.1) 
            self.log(f"正在分析: {os.path.basename(path)}...")
            
            result = self.processor.analyze_image_prepare(path)
            if not result:
                self.log(f"  [跳過] 在 {os.path.basename(path)} 中未發現任何可分析目標。")
                return
                
            cv_img, steps = result
            image_pass = True
            
            for step in steps:
                if self.stop_event.is_set(): return
                
                # Animation Start - Yellow Box
                overlay = {'rect': step['rect'], 'text': "SCANNING", 'status': 'checking'}
                self.root.after(0, self.safe_update_ui, path, overlay.copy())
                time.sleep(0.7) 
                
                # Actual calculation
                shift, debug_roi = self.processor.process_step(cv_img, step)
                
                # Determine PASS/FAIL
                is_pass = shift < int(self.fail_thd_var.get())
                if not is_pass: image_pass = False
                
                status_tag = 'pass' if is_pass else 'fail'
                status_text = f"SHIFT: {shift}px [{'OK' if is_pass else 'NG'}]"
                
                # Update ROI Preview
                self.display_roi(debug_roi)
                
                # Store result
                res = [os.path.basename(path), step['index'], shift, 
                       'PASS' if is_pass else 'FAIL', time.strftime("%H:%M:%S")]
                self.results_data.append(res)
                
                # Animation Done - Result Box
                overlay['text'] = status_text
                overlay['status'] = status_tag
                self.root.after(0, self.safe_update_ui, path, overlay.copy())
                
                fail_msg = "" if is_pass else f" (THRESHOLD {self.fail_thd_var.get()}px)"
                self.log(f"  Target {step['index']}: {shift} px -> {'PASS' if is_pass else 'FAIL'}{fail_msg}")
                time.sleep(1.0) 
            
            # Final Giant Result Overlay
            final_overlay = {'final_result': 'pass' if image_pass else 'fail'}
            self.root.after(0, self.safe_update_ui, path, final_overlay)
            time.sleep(1.2) # Extra time to see the big result
        except Exception as e:
            self.log(f"分析單張照片時發生錯誤: {str(e)}")

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
