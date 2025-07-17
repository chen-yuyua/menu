# -*- coding: utf-8 -*-
"""
Dino-Lite AM3111 Safe Chinese Version
Avoid all encoding issues
"""

import cv2
import numpy as np
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import math
from datetime import datetime
import os
import sys

# Force UTF-8 encoding for stdout
if sys.platform == "win32":
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')

# Check PIL availability
try:
    from PIL import Image, ImageTk
    PIL_AVAILABLE = True
    print("PIL available")
except ImportError:
    PIL_AVAILABLE = False
    print("PIL not available")

class DinoLiteApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Dino-Lite AM3111 Measurement System")
        self.root.geometry("1000x700")

        print("Initializing...")

        # Basic variables
        self.cap = None
        self.is_running = False
        self.current_frame = None
        self.display_frame = None

        # Measurement variables
        self.measurement_mode = "none"
        self.measurement_points = []
        self.all_measurement_points = []
        self.measurement_results = []
        self.max_measurements = 5
        self.is_calibrated = False
        self.scale_factor = 1.0
        self.calibration_distance = 1.0

        # AM3111 settings
        self.current_magnification = 50.0
        self.pixel_size_um = 5.0

        # Display variables
        self.display_scale = 1.0
        self.display_offset = (0, 0)

        print("Setup UI...")
        self.setup_ui()
        self.calculate_pixel_size()
        print("Init complete")

    def setup_ui(self):
        """Setup UI with Chinese text"""
        try:
            # Main frame
            main_frame = ttk.Frame(self.root)
            main_frame.pack(fill="both", expand=True, padx=10, pady=10)

            # Left control panel
            control_frame = ttk.LabelFrame(main_frame, text="控制面板", width=250)
            control_frame.pack(side="left", fill="y", padx=(0, 10))
            control_frame.pack_propagate(False)

            # Camera control
            camera_frame = ttk.LabelFrame(control_frame, text="攝影機控制")
            camera_frame.pack(fill="x", padx=5, pady=5)

            # Camera selection
            ttk.Label(camera_frame, text="選擇攝影機:").pack(pady=2)
            self.camera_var = tk.StringVar()
            self.camera_combo = ttk.Combobox(camera_frame, textvariable=self.camera_var,
                                           state="readonly", width=30)
            self.camera_combo.pack(pady=2, fill="x")
            self.camera_combo.bind("<<ComboboxSelected>>", self.on_camera_selected)

            # Refresh cameras button
            self.refresh_btn = ttk.Button(camera_frame, text="step①:重新偵測攝影機", command=self.detect_cameras)
            self.refresh_btn.pack(pady=2, fill="x")

            self.start_btn = ttk.Button(camera_frame, text="step②:開啟攝影機", command=self.start_camera)
            self.start_btn.pack(pady=5, fill="x")

            self.stop_btn = ttk.Button(camera_frame, text="停止攝影機", command=self.stop_camera)
            self.stop_btn.pack(pady=5, fill="x")

            self.close_programs_btn = ttk.Button(camera_frame, text="關閉其他程式", command=self.close_camera_programs)
            self.close_programs_btn.pack(pady=5, fill="x")

            self.camera_status = ttk.Label(camera_frame, text="攝影機未啟動", foreground="red")
            self.camera_status.pack(pady=5)

            # AM3111 settings
            settings_frame = ttk.LabelFrame(control_frame, text="AM3111 設定")
            settings_frame.pack(fill="x", padx=5, pady=5)

            ttk.Label(settings_frame, text="倍率:").pack()
            self.mag_var = tk.StringVar(value="50")
            mag_combo = ttk.Combobox(settings_frame, textvariable=self.mag_var,
                                    values=["20", "30", "50", "70", "100", "150", "200"])
            mag_combo.pack(pady=2, fill="x")
            mag_combo.bind("<<ComboboxSelected>>", self.update_magnification)

            self.pixel_info = ttk.Label(settings_frame, text="像素尺寸: 計算中...")
            self.pixel_info.pack(pady=2)

            # LED control
            led_frame = ttk.LabelFrame(control_frame, text="LED 控制")
            led_frame.pack(fill="x", padx=5, pady=5)

            ttk.Label(led_frame, text="亮度調整:").pack()
            self.led_scale = ttk.Scale(led_frame, from_=0, to=100, orient="horizontal",
                                      command=self.adjust_led)
            self.led_scale.set(50)
            self.led_scale.pack(fill="x", pady=2)

            self.led_value_label = ttk.Label(led_frame, text="50%")
            self.led_value_label.pack()

            # Calibration
            cal_frame = ttk.LabelFrame(control_frame, text="校準")
            cal_frame.pack(fill="x", padx=5, pady=5)

            ttk.Label(cal_frame, text="已知距離 (mm):").pack()
            self.cal_entry = ttk.Entry(cal_frame)
            self.cal_entry.pack(pady=2, fill="x")
            self.cal_entry.insert(0, "1.0")

            self.cal_btn = ttk.Button(cal_frame, text="step③:開始校準", command=self.start_calibration)
            self.cal_btn.pack(pady=2, fill="x")

            self.cal_status = ttk.Label(cal_frame, text="未校準", foreground="red")
            self.cal_status.pack(pady=2)

            # Measurement tools
            measure_frame = ttk.LabelFrame(control_frame, text="step⑤:測量工具")
            measure_frame.pack(fill="x", padx=5, pady=5)

            self.distance_btn = ttk.Button(measure_frame, text="距離測量",
                                         command=lambda: self.set_mode("distance"))
            self.distance_btn.pack(pady=2, fill="x")

            self.angle_btn = ttk.Button(measure_frame, text="角度測量",
                                       command=lambda: self.set_mode("angle"))
            self.angle_btn.pack(pady=2, fill="x")

            self.diameter_btn = ttk.Button(measure_frame, text="直徑測量",
                                         command=lambda: self.set_mode("diameter"))
            self.diameter_btn.pack(pady=2, fill="x")

            # Clear measurements button with additional features
            clear_frame = ttk.Frame(measure_frame)
            clear_frame.pack(fill="x", pady=2)

            self.clear_btn = ttk.Button(clear_frame, text="清除測量", command=self.clear_measurements, width=12)
            self.clear_btn.pack(side="left", padx=1)

            self.clear_last_btn = ttk.Button(clear_frame, text="撤銷上次", command=self.undo_last_measurement, width=12)
            self.clear_last_btn.pack(side="right", padx=1)

            self.mode_label = ttk.Label(measure_frame, text="模式: 無")
            self.mode_label.pack(pady=2)

            # Accuracy verification
            verify_frame = ttk.LabelFrame(control_frame, text="精度驗證")
            verify_frame.pack(fill="x", padx=5, pady=5)

            self.repeatability_btn = ttk.Button(verify_frame, text="step④:重複性測試", command=self.start_repeatability)
            self.repeatability_btn.pack(pady=2, fill="x")

            self.accuracy_btn = ttk.Button(verify_frame, text="精度指南", command=self.show_accuracy_guide)
            self.accuracy_btn.pack(pady=2, fill="x")

            # Results display
            results_frame = ttk.LabelFrame(control_frame, text="測量結果")
            results_frame.pack(fill="both", expand=True, padx=5, pady=5)

            self.results_text = tk.Text(results_frame, width=30, height=10, font=("Consolas", 9))
            scrollbar = ttk.Scrollbar(results_frame, orient="vertical", command=self.results_text.yview)
            self.results_text.configure(yscrollcommand=scrollbar.set)

            self.results_text.pack(side="left", fill="both", expand=True)
            scrollbar.pack(side="right", fill="y")

            # File operations
            file_frame = ttk.Frame(control_frame)
            file_frame.pack(fill="x", padx=5, pady=5)

            self.save_btn = ttk.Button(file_frame, text="儲存影像", command=self.save_image, width=12)
            self.save_btn.pack(side="left", padx=2)

            self.export_btn = ttk.Button(file_frame, text="匯出結果", command=self.export_results, width=12)
            self.export_btn.pack(side="right", padx=2)

            # Right side image display
            self.image_frame = ttk.LabelFrame(main_frame, text="影像顯示")
            self.image_frame.pack(side="right", fill="both", expand=True)

            # Toolbar
            toolbar = ttk.Frame(self.image_frame)
            toolbar.pack(fill="x", padx=5, pady=5)

            self.info_label = ttk.Label(toolbar, text="點擊影像進行測量", foreground="blue")
            self.info_label.pack(side="left")

            self.capture_btn = ttk.Button(toolbar, text="拍照", command=self.capture_image)
            self.capture_btn.pack(side="right")

            # Canvas
            self.canvas = tk.Canvas(self.image_frame, bg="black", width=600, height=500)
            self.canvas.pack(fill="both", expand=True, padx=5, pady=5)
            self.canvas.bind("<Button-1>", self.on_canvas_click)
            self.canvas.bind("<Motion>", self.on_mouse_move)
            self.canvas.bind("<Enter>", self.on_mouse_enter)
            self.canvas.bind("<Leave>", self.on_mouse_leave)

            # Mouse crosshair variables
            self.crosshair_visible = False
            self.crosshair_x = 0
            self.crosshair_y = 0

            # Status bar
            self.status_bar = ttk.Label(self.root, text="準備就緒")
            self.status_bar.pack(side="bottom", fill="x")

            print("UI setup complete")

        except Exception as e:
            print(f"UI setup error: {str(e)}")
            try:
                messagebox.showerror("Error", "UI setup failed")
            except:
                print("Cannot show error message")

    def calculate_pixel_size(self):
        """Calculate pixel size"""
        try:
            mag = float(self.mag_var.get())

            # AM3111 specifications
            sensor_width_mm = 6.4
            image_width_pixels = 640

            # Calculate pixel size
            fov_mm = sensor_width_mm / mag
            self.pixel_size_um = (fov_mm * 1000) / image_width_pixels
            self.current_magnification = mag

            # Safe text formatting
            info_text = f"像素: {self.pixel_size_um:.2f} μm ({int(mag)}x)"
            self.pixel_info.config(text=info_text)

        except Exception as e:
            print(f"Pixel size calculation error: {str(e)}")
            self.pixel_info.config(text="計算錯誤")

    def close_camera_programs(self):
        """Close other camera programs"""
        try:
            import psutil
            programs = ['DinoCapture', 'Skype', 'Teams', 'Zoom', 'OBS']
            closed = []

            for proc in psutil.process_iter(['name']):
                try:
                    name = proc.info['name']
                    for program in programs:
                        if program.lower() in name.lower():
                            proc.terminate()
                            closed.append(name)
                except:
                    pass

            if closed:
                msg = f"已關閉程式: {', '.join(closed)}"
                self.log_message(msg)
                try:
                    messagebox.showinfo("Success", "Programs closed successfully")
                except:
                    print("Cannot show success message")
            else:
                self.log_message("未發現需要關閉的程式")

        except ImportError:
            try:
                messagebox.showwarning("Warning", "Need psutil package: pip install psutil")
            except:
                print("Need psutil package")
        except Exception as e:
            print(f"Close programs error: {str(e)}")

    def detect_cameras(self):
        """偵測所有可用的攝影機"""
        try:
            print("Detecting available cameras...")
            self.available_cameras = []
            camera_list = []

            # 測試多個攝影機索引 (0-9)
            for i in range(10):
                try:
                    # 嘗試不同的後端
                    backends = [cv2.CAP_DSHOW, cv2.CAP_MSMF, cv2.CAP_ANY]

                    for backend in backends:
                        try:
                            cap = cv2.VideoCapture(i, backend)
                            if cap.isOpened():
                                # 嘗試讀取一幀來確認攝影機可用
                                ret, frame = cap.read()
                                if ret and frame is not None:
                                    # 獲取攝影機資訊
                                    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                                    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                                    fps = int(cap.get(cv2.CAP_PROP_FPS))

                                    # 嘗試獲取攝影機名稱 (如果可能)
                                    camera_name = self.get_camera_name(i)

                                    camera_info = {
                                        'index': i,
                                        'backend': backend,
                                        'name': camera_name,
                                        'resolution': f"{width}x{height}",
                                        'fps': fps if fps > 0 else "Unknown"
                                    }

                                    # 避免重複添加相同的攝影機
                                    if not any(cam['index'] == i for cam in self.available_cameras):
                                        self.available_cameras.append(camera_info)

                                        # 創建顯示文字
                                        display_text = f"Camera {i}: {camera_name} ({width}x{height})"
                                        camera_list.append(display_text)

                                        print(f"Found camera {i}: {camera_name} - {width}x{height}")
                                        break  # 找到可用的後端就停止

                                cap.release()
                            else:
                                cap.release()
                        except Exception as e:
                            try:
                                cap.release()
                            except:
                                pass
                            continue

                except Exception as e:
                    continue

            # 更新下拉選單
            if camera_list:
                self.camera_combo['values'] = camera_list
                if not self.camera_var.get() and camera_list:
                    self.camera_combo.current(0)  # 選擇第一個攝影機
                    self.selected_camera_index = self.available_cameras[0]['index']
                self.log_message(f"偵測到 {len(camera_list)} 個可用攝影機")
            else:
                self.camera_combo['values'] = ["未偵測到可用攝影機"]
                self.camera_var.set("未偵測到可用攝影機")
                self.log_message("未偵測到可用攝影機")

        except Exception as e:
            print(f"Camera detection error: {str(e)}")
            self.log_message("攝影機偵測發生錯誤")

    def get_camera_name(self, index):
        """嘗試獲取攝影機名稱"""
        try:
            # Windows 系統嘗試獲取設備名稱
            if sys.platform == "win32":
                try:
                    import subprocess
                    result = subprocess.run(['powershell',
                                           'Get-WmiObject -Class Win32_PnPEntity | Where-Object {$_.Name -like "*camera*" -or $_.Name -like "*webcam*" -or $_.Name -like "*dino*"} | Select-Object Name'],
                                          capture_output=True, text=True, timeout=5)
                    if result.stdout:
                        lines = result.stdout.strip().split('\n')
                        if len(lines) > index + 2:  # 跳過標題行
                            name = lines[index + 2].strip()
                            if name and name != "----":
                                return name
                except:
                    pass

            # 檢查是否為 Dino-Lite
            test_cap = cv2.VideoCapture(index)
            if test_cap.isOpened():
                # 嘗試通過解析度判斷可能的設備類型
                width = int(test_cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                height = int(test_cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

                # Dino-Lite 常見解析度
                if (width, height) in [(640, 480), (1280, 1024), (1600, 1200), (2592, 1944)]:
                    test_cap.release()
                    return f"Dino-Lite (推測)"

                test_cap.release()

            return f"Camera Device {index}"

        except Exception as e:
            return f"Unknown Camera {index}"

    def on_camera_selected(self, event=None):
        """當選擇攝影機時的回調函數"""
        try:
            selection = self.camera_combo.current()
            if selection >= 0 and selection < len(self.available_cameras):
                selected_camera = self.available_cameras[selection]
                self.selected_camera_index = selected_camera['index']

                # 如果攝影機正在運行，停止後重新啟動
                if self.is_running:
                    self.stop_camera()
                    self.root.after(500, self.start_camera)  # 延遲500ms後重新啟動

                self.log_message(f"已選擇攝影機 {self.selected_camera_index}: {selected_camera['name']}")

        except Exception as e:
            print(f"Camera selection error: {str(e)}")

    def start_camera(self):
        """Start camera using selected camera index"""
        try:
            print(f"Attempting to start camera {self.selected_camera_index}...")

            # 如果沒有可用攝影機，先偵測
            if not self.available_cameras:
                self.detect_cameras()

            if not self.available_cameras:
                self.camera_status.config(text="無可用攝影機", foreground="red")
                try:
                    messagebox.showwarning("Warning", "未偵測到可用攝影機，請檢查設備連接")
                except:
                    print("No available cameras detected")
                return

            # 找到對應的攝影機資訊
            selected_camera = None
            for cam in self.available_cameras:
                if cam['index'] == self.selected_camera_index:
                    selected_camera = cam
                    break

            if not selected_camera:
                selected_camera = self.available_cameras[0]
                self.selected_camera_index = selected_camera['index']

            # 嘗試開啟選定的攝影機
            try:
                print(f"Opening camera {selected_camera['index']} with backend {selected_camera['backend']}")
                self.cap = cv2.VideoCapture(selected_camera['index'], selected_camera['backend'])

                if self.cap.isOpened():
                    # Set parameters
                    self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

                    # Test read
                    ret, frame = self.cap.read()
                    if ret:
                        print(f"Successfully opened camera {selected_camera['index']}: {selected_camera['name']}")
                        self.is_running = True
                        self.camera_status.config(text=f"攝影機 {selected_camera['index']} 運行中", foreground="green")
                        self.log_message(f"攝影機啟動成功: {selected_camera['name']}")
                        self.update_frame()
                        return
                    else:
                        self.cap.release()

            except Exception as e:
                print(f"Failed to open selected camera {selected_camera['index']}: {str(e)}")
                if self.cap:
                    self.cap.release()

            # 如果選定的攝影機失敗，嘗試其他可用攝影機
            print("Selected camera failed, trying other available cameras...")
            for cam in self.available_cameras:
                if cam['index'] != self.selected_camera_index:
                    try:
                        print(f"Trying fallback camera {cam['index']}")
                        self.cap = cv2.VideoCapture(cam['index'], cam['backend'])

                        if self.cap.isOpened():
                            ret, frame = self.cap.read()
                            if ret:
                                print(f"Successfully opened fallback camera {cam['index']}")
                                self.is_running = True
                                self.selected_camera_index = cam['index']
                                self.camera_status.config(text=f"攝影機 {cam['index']} 運行中", foreground="green")
                                self.log_message(f"攝影機啟動成功: {cam['name']} (備用)")

                                # 更新下拉選單選擇
                                for i, available_cam in enumerate(self.available_cameras):
                                    if available_cam['index'] == cam['index']:
                                        self.camera_combo.current(i)
                                        break

                                self.update_frame()
                                return
                            else:
                                self.cap.release()

                    except Exception as e:
                        print(f"Fallback camera {cam['index']} failed: {str(e)}")
                        if self.cap:
                            self.cap.release()
                        continue

            # 所有攝影機都失敗
            print("All available cameras failed")
            self.camera_status.config(text="攝影機啟動失敗", foreground="red")
            try:
                msg = "無法開啟任何攝影機。請檢查:\n1. 設備連接\n2. 驅動程式安裝\n3. 其他程式是否占用攝影機\n\n嘗試點擊「關閉其他程式」或「重新偵測攝影機」"
                messagebox.showwarning("Warning", msg)
            except:
                print("Cannot show warning message")

        except Exception as e:
            print(f"Start camera error: {str(e)}")
            try:
                messagebox.showerror("Error", "攝影機初始化失敗")
            except:
                print("Cannot show error message")

    def stop_camera(self):
        """Stop camera"""
        try:
            self.is_running = False
            if self.cap:
                self.cap.release()
                self.cap = None
            self.camera_status.config(text="攝影機已停止", foreground="orange")
            self.log_message("攝影機已停止")
            print("Camera stopped")
        except Exception as e:
            print(f"Stop camera error: {str(e)}")

    def adjust_led(self, value):
        """Adjust LED brightness"""
        try:
            brightness = float(value)
            self.led_value_label.config(text=f"{int(brightness)}%")

            # Apply software LED effect
            if self.cap and self.cap.isOpened():
                try:
                    brightness_value = 128 + (brightness - 50) * 2
                    self.cap.set(cv2.CAP_PROP_BRIGHTNESS, brightness_value)
                    self.cap.set(cv2.CAP_PROP_CONTRAST, 128 + (brightness - 50))
                except:
                    pass
        except Exception as e:
            print(f"LED adjustment error: {str(e)}")

    def update_frame(self):
        """Update frame"""
        if self.is_running and self.cap and self.cap.isOpened():
            try:
                ret, frame = self.cap.read()
                if ret:
                    self.current_frame = frame.copy()
                    self.display_frame = frame.copy()

                    # Draw measurement marks
                    self.draw_measurements()

                    # Show image
                    self.show_frame()

                # Continue updating
                self.root.after(50, self.update_frame)

            except Exception as e:
                print(f"Frame update error: {str(e)}")

    def show_frame(self):
        """Show frame"""
        if self.display_frame is None:
            return

        try:
            if PIL_AVAILABLE:
                # Use PIL for display
                frame_rgb = cv2.cvtColor(self.display_frame, cv2.COLOR_BGR2RGB)

                # Calculate scaling
                canvas_width = self.canvas.winfo_width()
                canvas_height = self.canvas.winfo_height()

                if canvas_width > 1 and canvas_height > 1:
                    h, w = frame_rgb.shape[:2]
                    scale = min(canvas_width/w, canvas_height/h)

                    new_w = int(w * scale)
                    new_h = int(h * scale)

                    if new_w > 0 and new_h > 0:
                        frame_resized = cv2.resize(frame_rgb, (new_w, new_h))

                        image = Image.fromarray(frame_resized)
                        self.photo = ImageTk.PhotoImage(image)

                        self.canvas.delete("all")
                        x = (canvas_width - new_w) // 2
                        y = (canvas_height - new_h) // 2
                        self.canvas.create_image(x, y, anchor="nw", image=self.photo)

                        # Store display parameters
                        self.display_scale = scale
                        self.display_offset = (x, y)

                        # Draw crosshair if visible and in measurement mode
                        self.draw_crosshair()
            else:
                # Simple display when PIL is not available
                self.canvas.delete("all")
                text = "Image display requires PIL\nPlease install: pip install pillow"
                self.canvas.create_text(
                    self.canvas.winfo_width()//2,
                    self.canvas.winfo_height()//2,
                    text=text, fill="white", font=("Arial", 14))

        except Exception as e:
            print(f"Show frame error: {str(e)}")

    def draw_crosshair(self):
        """Draw crosshair lines on canvas"""
        try:
            if self.crosshair_visible and self.measurement_mode != "none":
                canvas_width = self.canvas.winfo_width()
                canvas_height = self.canvas.winfo_height()

                # Draw vertical line (full height) - 1px thickness
                self.canvas.create_line(
                    self.crosshair_x, 0,
                    self.crosshair_x, canvas_height,
                    fill="red", width=1, tags="crosshair"
                )

                # Draw horizontal line (full width) - 1px thickness
                self.canvas.create_line(
                    0, self.crosshair_y,
                    canvas_width, self.crosshair_y,
                    fill="red", width=1, tags="crosshair"
                )

        except Exception as e:
            print(f"Draw crosshair error: {str(e)}")

    def update_magnification(self, event=None):
        """Update magnification"""
        try:
            self.calculate_pixel_size()
            msg = f"倍率更新為 {int(self.current_magnification)}x"
            self.log_message(msg)
        except Exception as e:
            print(f"Update magnification error: {str(e)}")

    def start_calibration(self):
        """Start calibration"""
        try:
            distance = float(self.cal_entry.get())
            self.calibration_distance = distance
            self.set_mode("calibration")
            msg = f"校準模式: 請點擊已知距離 {distance} mm 的兩點"
            self.log_message(msg)
        except ValueError:
            try:
                messagebox.showerror("Error", "Please enter a valid calibration distance")
            except:
                print("Invalid calibration distance")

    def start_repeatability(self):
        """Start repeatability test"""
        try:
            self.repeatability_data = []
            self.repeatability_count = 0
            self.set_mode("repeatability")
            self.log_message("重複性測試: 對同一物體測量5次")
        except Exception as e:
            print(f"Start repeatability error: {str(e)}")

    def show_accuracy_guide(self):
        """Show accuracy guide"""
        try:
            guide = """AM3111 測量精度指南:

校準建議:
• 使用1mm或0.5mm標準距離
• 確保良好照明
• 選擇清晰的測量點

精度標準:
• 優秀: ±2% 誤差
• 良好: ±5% 誤差
• 可接受: ±10% 誤差

驗證物體建議:
• 1元硬幣 (直徑20mm)
• 標準尺規刻度
• 電路板線寬
• 紙張厚度 (0.1mm)

倍率建議:
• 一般測量: 50x-100x
• 精密測量: 100x-200x

提高精度方法:
• 使用校準功能
• 適當的LED照明
• 多次測量取平均值
• 選擇合適的倍率"""

            messagebox.showinfo("精度指南", guide)
        except Exception as e:
            print(f"Show accuracy guide error: {str(e)}")

    def set_mode(self, mode):
        """Set mode"""
        try:
            self.measurement_mode = mode
            self.measurement_points = []

            mode_dict = {
                "distance": "距離測量",
                "angle": "角度測量",
                "diameter": "直徑測量",
                "calibration": "校準模式",
                "repeatability": "重複性測試"
            }
            mode_text = mode_dict.get(mode, "無")

            self.mode_label.config(text=f"模式: {mode_text}")
            self.status_bar.config(text=f"當前模式: {mode_text}")

            # Update crosshair visibility based on mode
            if mode == "none":
                self.crosshair_visible = False
                if self.current_frame is not None:
                    self.show_frame()

        except Exception as e:
            print(f"Set mode error: {str(e)}")

    def on_canvas_click(self, event):
        """Handle click"""
        if self.measurement_mode == "none" or self.current_frame is None:
            return

        try:
            # Convert coordinates
            canvas_x = event.x - self.display_offset[0]
            canvas_y = event.y - self.display_offset[1]

            orig_x = int(canvas_x / self.display_scale)
            orig_y = int(canvas_y / self.display_scale)

            # Ensure coordinates are within range
            h, w = self.current_frame.shape[:2]
            if 0 <= orig_x < w and 0 <= orig_y < h:
                self.measurement_points.append((orig_x, orig_y))
                self.process_measurement()

        except Exception as e:
            print(f"Click processing error: {str(e)}")

    def on_mouse_move(self, event):
        """Handle mouse movement for crosshair"""
        try:
            if self.measurement_mode != "none" and self.current_frame is not None:
                self.crosshair_x = event.x
                self.crosshair_y = event.y
                self.crosshair_visible = True
                # Redraw frame with crosshair
                self.show_frame()
        except Exception as e:
            print(f"Mouse move error: {str(e)}")

    def on_mouse_enter(self, event):
        """Handle mouse entering canvas"""
        try:
            if self.measurement_mode != "none":
                self.crosshair_visible = True
        except Exception as e:
            print(f"Mouse enter error: {str(e)}")

    def on_mouse_leave(self, event):
        """Handle mouse leaving canvas"""
        try:
            self.crosshair_visible = False
            # Redraw frame without crosshair
            if self.current_frame is not None:
                self.show_frame()
        except Exception as e:
            print(f"Mouse leave error: {str(e)}")

    def process_measurement(self):
        """Process measurement"""
        try:
            if self.measurement_mode == "distance" and len(self.measurement_points) == 2:
                self.measure_distance()
            elif self.measurement_mode == "angle" and len(self.measurement_points) == 3:
                self.measure_angle()
            elif self.measurement_mode == "diameter" and len(self.measurement_points) == 3:
                self.measure_diameter()
            elif self.measurement_mode == "calibration" and len(self.measurement_points) == 2:
                self.complete_calibration()
            elif self.measurement_mode == "repeatability" and len(self.measurement_points) == 2:
                self.process_repeatability()
        except Exception as e:
            print(f"Measurement processing error: {str(e)}")

    def measure_distance(self):
        """Measure distance"""
        try:
            if len(self.measurement_points) >= 2:
                p1, p2 = self.measurement_points[-2:]
                pixel_dist = math.sqrt((p2[0] - p1[0])**2 + (p2[1] - p1[1])**2)

                if self.is_calibrated:
                    real_dist_mm = pixel_dist * self.scale_factor
                    real_dist_um = real_dist_mm * 1000
                    result = f"Distance: {real_dist_mm:.2f} mm ({real_dist_um:.0f} μm) [Calibrated]"
                    value_text = f"{real_dist_mm:.2f}mm"
                else:
                    real_dist_um = pixel_dist * self.pixel_size_um
                    real_dist_mm = real_dist_um / 1000
                    result = f"Distance: {real_dist_mm:.2f} mm ({real_dist_um:.0f} μm) [Estimated]"
                    value_text = f"{real_dist_mm:.2f}mm*"

                self.add_result(result)

                # 檢查是否超過最大測量數量
                if len(self.measurement_results) >= self.max_measurements:
                    self.clear_all_measurements()
                    self.log_message("已達到最大測量數量，自動清除所有數據")

                # 儲存測量結果資訊
                self.measurement_results.append({
                    'type': 'distance',
                    'points': [p1, p2],
                    'result': result,
                    'value': value_text
                })

                self.measurement_points = []
        except Exception as e:
            print(f"Distance measurement error: {str(e)}")

    def measure_angle(self):
        """Measure angle"""
        try:
            if len(self.measurement_points) >= 3:
                p1, p2, p3 = self.measurement_points[-3:]

                # Calculate vectors
                v1 = (p1[0] - p2[0], p1[1] - p2[1])
                v2 = (p3[0] - p2[0], p3[1] - p2[1])

                # Calculate angle
                dot = v1[0]*v2[0] + v1[1]*v2[1]
                mag1 = math.sqrt(v1[0]**2 + v1[1]**2)
                mag2 = math.sqrt(v2[0]**2 + v2[1]**2)

                if mag1 > 0 and mag2 > 0:
                    cos_angle = max(-1, min(1, dot / (mag1 * mag2)))
                    angle = math.degrees(math.acos(cos_angle))
                    result = f"Angle: {angle:.2f} degrees"
                    value_text = f"{angle:.2f}deg"
                    self.add_result(result)

                    # 檢查是否超過最大測量數量
                    if len(self.measurement_results) >= self.max_measurements:
                        self.clear_all_measurements()
                        self.log_message("已達到最大測量數量，自動清除所有數據")

                    # 儲存測量結果資訊
                    self.measurement_results.append({
                        'type': 'angle',
                        'points': [p1, p2, p3],
                        'result': result,
                        'value': value_text
                    })

                self.measurement_points = []
        except Exception as e:
            print(f"Angle measurement error: {str(e)}")

    def measure_diameter(self):
        """Measure diameter using 3 points to form a circle"""
        try:
            if len(self.measurement_points) >= 3:
                p1, p2, p3 = self.measurement_points[-3:]

                # Calculate circle center and radius from 3 points
                center, radius = self.calculate_circle_from_3_points(p1, p2, p3)

                if center is not None and radius is not None:
                    diameter_pixels = radius * 2

                    if self.is_calibrated:
                        diameter_mm = diameter_pixels * self.scale_factor
                        radius_mm = diameter_mm / 2
                        diameter_um = diameter_mm * 1000
                        radius_um = radius_mm * 1000
                        result = f"Diameter: {diameter_mm:.2f} mm ({diameter_um:.0f} μm) [Calibrated]\nRadius: {radius_mm:.2f} mm ({radius_um:.0f} μm)"
                        value_text = f"D:{diameter_mm:.2f}mm R:{radius_mm:.2f}mm"
                    else:
                        diameter_um = diameter_pixels * self.pixel_size_um
                        diameter_mm = diameter_um / 1000
                        radius_mm = diameter_mm / 2
                        radius_um = radius_mm * 1000
                        result = f"Diameter: {diameter_mm:.2f} mm ({diameter_um:.0f} μm) [Estimated]\nRadius: {radius_mm:.2f} mm ({radius_um:.0f} μm)"
                        value_text = f"D:{diameter_mm:.2f}mm R:{radius_mm:.2f}mm*"

                    self.add_result(result)

                    # 檢查是否超過最大測量數量
                    if len(self.measurement_results) >= self.max_measurements:
                        self.clear_all_measurements()
                        self.log_message("已達到最大測量數量，自動清除所有數據")

                    # 儲存測量結果資訊
                    self.measurement_results.append({
                        'type': 'diameter',
                        'points': [p1, p2, p3],
                        'center': center,
                        'radius': radius,
                        'result': result,
                        'value': value_text
                    })

                self.measurement_points = []
        except Exception as e:
            print(f"Diameter measurement error: {str(e)}")

    def calculate_circle_from_3_points(self, p1, p2, p3):
        """Calculate circle center and radius from 3 points"""
        try:
            x1, y1 = p1
            x2, y2 = p2
            x3, y3 = p3

            # Check if points are collinear
            area = abs((x1*(y2-y3) + x2*(y3-y1) + x3*(y1-y2))/2.0)
            if area < 0.001:  # Points are nearly collinear
                return None, None

            # Calculate perpendicular bisectors
            d = 2 * (x1 * (y2 - y3) + x2 * (y3 - y1) + x3 * (y1 - y2))

            if abs(d) < 0.001:  # Points are collinear
                return None, None

            # Calculate center coordinates
            ux = ((x1*x1 + y1*y1)*(y2-y3) + (x2*x2 + y2*y2)*(y3-y1) + (x3*x3 + y3*y3)*(y1-y2)) / d
            uy = ((x1*x1 + y1*y1)*(x3-x2) + (x2*x2 + y2*y2)*(x1-x3) + (x3*x3 + y3*y3)*(x2-x1)) / d

            center = (int(ux), int(uy))

            # Calculate radius
            radius = math.sqrt((ux - x1)**2 + (uy - y1)**2)

            return center, radius

        except Exception as e:
            print(f"Circle calculation error: {str(e)}")
            return None, None

    def complete_calibration(self):
        """Complete calibration"""
        try:
            if len(self.measurement_points) >= 2:
                p1, p2 = self.measurement_points[-2:]
                pixel_dist = math.sqrt((p2[0] - p1[0])**2 + (p2[1] - p1[1])**2)

                if pixel_dist > 0:
                    self.scale_factor = self.calibration_distance / pixel_dist
                    self.is_calibrated = True
                    self.cal_status.config(text="已校準", foreground="green")

                    result = f"Calibration complete: {self.scale_factor:.6f} mm/pixel"
                    self.add_result(result)

                    self.set_mode("none")
                    self.measurement_points = []
        except Exception as e:
            print(f"Calibration error: {str(e)}")

    def process_repeatability(self):
        """Process repeatability test"""
        try:
            p1, p2 = self.measurement_points[-2:]
            pixel_dist = math.sqrt((p2[0] - p1[0])**2 + (p2[1] - p1[1])**2)

            if self.is_calibrated:
                distance = pixel_dist * self.scale_factor
            else:
                distance = pixel_dist * self.pixel_size_um / 1000

            self.repeatability_data.append(distance)
            self.repeatability_count += 1

            msg = f"Measurement {self.repeatability_count}/5: {distance:.2f} mm"
            self.log_message(msg)

            if self.repeatability_count >= 5:
                self.calculate_repeatability()

            self.measurement_points = []
        except Exception as e:
            print(f"Repeatability processing error: {str(e)}")

    def calculate_repeatability(self):
        """Calculate repeatability statistics"""
        try:
            data = self.repeatability_data
            avg = sum(data) / len(data)
            variance = sum((x - avg)**2 for x in data) / len(data)
            std = math.sqrt(variance)
            cv = (std / avg) * 100

            assessment = "優秀" if cv < 2 else "良好" if cv < 5 else "可接受" if cv < 10 else "需改善"

            result = f"""Repeatability Test Results:
Average: {avg:.2f} mm
Std Dev: {std:.2f} mm
CV: {cv:.2f}%
Assessment: {assessment}"""

            self.add_result(result)
            self.set_mode("none")
        except Exception as e:
            print(f"Repeatability calculation error: {str(e)}")

    def draw_measurements(self):
        """Draw measurement marks with cross style and persistent display"""
        if self.display_frame is None:
            return

        try:
            # 繪製所有歷史測量結果（線條和數值）
            for i, result_info in enumerate(self.measurement_results):
                if result_info['type'] == 'distance':
                    p1, p2 = result_info['points']
                    # 每組測量使用不同顏色
                    colors = [(255, 100, 100), (100, 255, 100), (100, 100, 255),
                             (255, 255, 100), (255, 100, 255)]
                    color = colors[i % len(colors)]

                    # 繪製連接線
                    cv2.line(self.display_frame, p1, p2, color, 2)

                    # 繪製測量點（十字標記）
                    self.draw_cross_marker(p1, color, size=6, thickness=1)
                    self.draw_cross_marker(p2, color, size=6, thickness=1)

                    # 在線中點顯示測量數值
                    self.draw_distance_value_on_line(p1, p2, result_info['value'], color)

                elif result_info['type'] == 'angle':
                    p1, p2, p3 = result_info['points']
                    colors = [(255, 100, 100), (100, 255, 100), (100, 100, 255),
                             (255, 255, 100), (255, 100, 255)]
                    color = colors[i % len(colors)]

                    # 繪製角度線
                    cv2.line(self.display_frame, p2, p1, color, 2)
                    cv2.line(self.display_frame, p2, p3, color, 2)

                    # 繪製測量點
                    self.draw_cross_marker(p1, color, size=6, thickness=1)
                    self.draw_cross_marker(p2, color, size=6, thickness=1)
                    self.draw_cross_marker(p3, color, size=6, thickness=1)

                    # 在頂點顯示角度數值
                    self.draw_angle_value_on_vertex(p1, p2, p3, result_info['value'], color)

                elif result_info['type'] == 'diameter':
                    p1, p2, p3 = result_info['points']
                    center = result_info['center']
                    radius = result_info['radius']
                    colors = [(255, 100, 100), (100, 255, 100), (100, 100, 255),
                             (255, 255, 100), (255, 100, 255)]
                    color = colors[i % len(colors)]

                    # 繪製圓弧和測量點
                    cv2.circle(self.display_frame, center, int(radius), color, 2)

                    # 繪製測量點
                    self.draw_cross_marker(p1, color, size=6, thickness=1)
                    self.draw_cross_marker(p2, color, size=6, thickness=1)
                    self.draw_cross_marker(p3, color, size=6, thickness=1)

                    # 繪製圓心標記
                    self.draw_center_marker(center, color)

                    # 繪製直徑線
                    diameter_start = (int(center[0] - radius), center[1])
                    diameter_end = (int(center[0] + radius), center[1])
                    cv2.line(self.display_frame, diameter_start, diameter_end, color, 1)

                    # 顯示直徑數值
                    self.draw_diameter_value(center, result_info['value'], color)

            # 繪製當前測量中的點（較大的十字）
            current_colors = [(0, 0, 255), (0, 255, 0), (255, 0, 0)]  # 紅、綠、藍

            for i, point in enumerate(self.measurement_points):
                color = current_colors[i % len(current_colors)]
                # 繪製較大的十字標記
                self.draw_cross_marker(point, color, size=8, thickness=2)

                # 添加點編號
                cv2.putText(self.display_frame, str(i+1),
                           (point[0]+12, point[1]-12),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

            # 繪製當前測量線條
            if len(self.measurement_points) >= 2:
                if self.measurement_mode in ["distance", "calibration", "repeatability"]:
                    cv2.line(self.display_frame,
                            self.measurement_points[-2],
                            self.measurement_points[-1],
                            (0, 255, 255), 3)  # 黃色粗線表示當前測量

                    # 顯示即時測量值
                    if self.measurement_mode == "distance":
                        self.draw_realtime_distance_info(self.measurement_points[-2], self.measurement_points[-1])

                elif self.measurement_mode == "angle" and len(self.measurement_points) >= 3:
                    p1, p2, p3 = self.measurement_points[-3:]
                    cv2.line(self.display_frame, p2, p1, (0, 255, 255), 3)
                    cv2.line(self.display_frame, p2, p3, (0, 255, 255), 3)

                    # 顯示即時角度值
                    self.draw_realtime_angle_info(p1, p2, p3)

                elif self.measurement_mode == "diameter" and len(self.measurement_points) >= 3:
                    p1, p2, p3 = self.measurement_points[-3:]

                    # 計算即時圓弧
                    center, radius = self.calculate_circle_from_3_points(p1, p2, p3)
                    if center and radius:
                        cv2.circle(self.display_frame, center, int(radius), (0, 255, 255), 2)
                        self.draw_center_marker(center, (0, 255, 255))

                        # 顯示即時直徑值
                        self.draw_realtime_diameter_info(center, radius)

            # 在畫面左上角顯示測量數量
            self.draw_measurement_counter()

        except Exception as e:
            print(f"Drawing error: {str(e)}")

    def draw_cross_marker(self, point, color, size=8, thickness=2):
        """繪製細線十字標記"""
        try:
            x, y = point

            # 繪製十字線（更細）
            # 水平線
            cv2.line(self.display_frame, (x-size, y), (x+size, y), color, thickness)
            # 垂直線
            cv2.line(self.display_frame, (x, y-size), (x, y+size), color, thickness)

            # 繪製中心圓點（更小）
            cv2.circle(self.display_frame, point, 2, color, -1)

        except Exception as e:
            print(f"Draw cross marker error: {str(e)}")

    def draw_distance_value_on_line(self, p1, p2, value_text, color):
        """在距離線上顯示測量數值 - 智慧定位避免超出畫面"""
        try:
            # 計算線中點
            mid_x = (p1[0] + p2[0]) // 2
            mid_y = (p1[1] + p2[1]) // 2

            # 計算線的角度，調整文字位置避免重疊
            dx = p2[0] - p1[0]
            dy = p2[1] - p1[1]

            # 獲取畫面尺寸
            frame_height, frame_width = self.display_frame.shape[:2]

            # 計算文字尺寸
            font = cv2.FONT_HERSHEY_SIMPLEX
            font_scale = 0.5
            thickness = 1
            text_size = cv2.getTextSize(value_text, font, font_scale, thickness)[0]
            text_width, text_height = text_size

            # 文字偏移位置（垂直於線條）
            offset_distance = 25  # 增加偏移距離
            if abs(dx) > abs(dy):  # 水平線偏向
                offset_x = 0
                offset_y = -offset_distance if dy >= 0 else offset_distance
            else:  # 垂直線偏向
                offset_x = offset_distance if dx >= 0 else -offset_distance
                offset_y = 0

            text_x = mid_x + offset_x
            text_y = mid_y + offset_y

            # 確保文字在畫面範圍內 - 水平調整
            if text_x + text_width > frame_width:
                text_x = frame_width - text_width - 5
            if text_x < 5:
                text_x = 5

            # 確保文字在畫面範圍內 - 垂直調整
            if text_y - text_height < 5:
                text_y = text_height + 5
            if text_y > frame_height - 5:
                text_y = frame_height - 5

            # 繪製帶背景的文字
            self.draw_text_with_background(value_text, (text_x, text_y), color)

        except Exception as e:
            print(f"Draw distance value error: {str(e)}")

    def draw_angle_value_on_vertex(self, p1, p2, p3, value_text, color):
        """在角度頂點顯示角度數值 - 智慧定位避免超出畫面"""
        try:
            # 獲取畫面尺寸
            frame_height, frame_width = self.display_frame.shape[:2]

            # 計算文字尺寸
            font = cv2.FONT_HERSHEY_SIMPLEX
            font_scale = 0.5
            thickness = 1
            text_size = cv2.getTextSize(value_text, font, font_scale, thickness)[0]
            text_width, text_height = text_size

            # 多個可能的位置（優先順序）
            possible_positions = [
                (p2[0] + 20, p2[1] - 20),  # 右上
                (p2[0] - text_width - 20, p2[1] - 20),  # 左上
                (p2[0] + 20, p2[1] + text_height + 20),  # 右下
                (p2[0] - text_width - 20, p2[1] + text_height + 20),  # 左下
                (p2[0] - text_width // 2, p2[1] - 30),  # 正上方
                (p2[0] - text_width // 2, p2[1] + 30)   # 正下方
            ]

            # 選擇第一個在畫面範圍內的位置
            selected_pos = None
            for pos_x, pos_y in possible_positions:
                if (5 <= pos_x <= frame_width - text_width - 5 and
                    text_height + 5 <= pos_y <= frame_height - 5):
                    selected_pos = (pos_x, pos_y)
                    break

            # 如果沒有完美位置，使用調整後的位置
            if selected_pos is None:
                text_x = max(5, min(frame_width - text_width - 5, p2[0] + 15))
                text_y = max(text_height + 5, min(frame_height - 5, p2[1] - 15))
                selected_pos = (text_x, text_y)

            # 繪製帶背景的文字
            self.draw_text_with_background(value_text, selected_pos, color)

        except Exception as e:
            print(f"Draw angle value error: {str(e)}")

    def draw_text_with_background(self, text, position, color):
        """繪製帶背景的文字 - 處理特殊字符顯示問題並確保在畫面範圍內"""
        try:
            x, y = position

            # 處理度數符號顯示問題
            if "°" in text:
                # 將度數符號替換為 "deg" 以避免顯示問題
                text = text.replace("°", "deg")

            # 檢查文字是否包含中文，如果有則轉換為英文
            if any('\u4e00' <= char <= '\u9fff' for char in text):
                # 如果是中文的測量值，保留數值部分
                if "mm" in text or "deg" in text:
                    # 保留測量數值
                    pass
                else:
                    # 其他中文文字暫時不顯示，避免亂碼
                    return

            # 計算文字尺寸
            font = cv2.FONT_HERSHEY_SIMPLEX
            font_scale = 0.5
            thickness = 1
            text_size = cv2.getTextSize(text, font, font_scale, thickness)[0]

            # 獲取畫面尺寸
            frame_height, frame_width = self.display_frame.shape[:2]

            # 調整位置確保文字在畫面範圍內
            padding = 3
            text_width = text_size[0] + 2 * padding
            text_height = text_size[1] + 2 * padding

            # 水平位置調整
            if x + text_width > frame_width:
                x = frame_width - text_width
            if x < 0:
                x = 0

            # 垂直位置調整
            if y - text_height < 0:
                y = text_height
            if y > frame_height:
                y = frame_height - 5

            # 繪製半透明背景框
            cv2.rectangle(self.display_frame,
                         (x - padding, y - text_size[1] - padding),
                         (x + text_size[0] + padding, y + padding),
                         (0, 0, 0), -1)

            # 繪製文字
            cv2.putText(self.display_frame, text, (x, y),
                       font, font_scale, (255, 255, 255), thickness)

        except Exception as e:
            print(f"Draw text with background error: {str(e)}")

    def draw_realtime_distance_info(self, p1, p2):
        """顯示即時距離測量資訊 - 智慧定位避免超出畫面"""
        try:
            # 計算中點
            mid_x = (p1[0] + p2[0]) // 2
            mid_y = (p1[1] + p2[1]) // 2

            # 計算距離
            pixel_dist = math.sqrt((p2[0] - p1[0])**2 + (p2[1] - p1[1])**2)

            if self.is_calibrated:
                real_dist_mm = pixel_dist * self.scale_factor
                text = f"{real_dist_mm:.2f}mm"
            else:
                real_dist_um = pixel_dist * self.pixel_size_um
                real_dist_mm = real_dist_um / 1000
                text = f"{real_dist_mm:.2f}mm*"  # * 表示估算值

            # 獲取畫面尺寸
            frame_height, frame_width = self.display_frame.shape[:2]

            # 計算文字尺寸
            font = cv2.FONT_HERSHEY_SIMPLEX
            font_scale = 0.5
            thickness = 1
            text_size = cv2.getTextSize(text, font, font_scale, thickness)[0]
            text_width, text_height = text_size

            # 調整位置確保在畫面範圍內
            text_x = max(5, min(frame_width - text_width - 5, mid_x - text_width // 2))
            text_y = max(text_height + 5, min(frame_height - 5, mid_y - 15))

            # 繪製即時測量值（使用特殊顏色）
            self.draw_text_with_background(text, (text_x, text_y), (0, 255, 255))

        except Exception as e:
            print(f"Draw realtime distance info error: {str(e)}")

    def draw_realtime_angle_info(self, p1, p2, p3):
        """顯示即時角度測量資訊 - 智慧定位避免超出畫面"""
        try:
            # 計算角度
            v1 = (p1[0] - p2[0], p1[1] - p2[1])
            v2 = (p3[0] - p2[0], p3[1] - p2[1])

            dot = v1[0]*v2[0] + v1[1]*v2[1]
            mag1 = math.sqrt(v1[0]**2 + v1[1]**2)
            mag2 = math.sqrt(v2[0]**2 + v2[1]**2)

            if mag1 > 0 and mag2 > 0:
                cos_angle = max(-1, min(1, dot / (mag1 * mag2)))
                angle = math.degrees(math.acos(cos_angle))
                text = f"{angle:.2f}deg"

                # 獲取畫面尺寸
                frame_height, frame_width = self.display_frame.shape[:2]

                # 計算文字尺寸
                font = cv2.FONT_HERSHEY_SIMPLEX
                font_scale = 0.5
                thickness = 1
                text_size = cv2.getTextSize(text, font, font_scale, thickness)[0]
                text_width, text_height = text_size

                # 調整位置確保在畫面範圍內
                text_x = max(5, min(frame_width - text_width - 5, p2[0] + 15))
                text_y = max(text_height + 5, min(frame_height - 5, p2[1] - 15))

                # 繪製即時角度值
                self.draw_text_with_background(text, (text_x, text_y), (0, 255, 255))

        except Exception as e:
            print(f"Draw realtime angle info error: {str(e)}")

    def draw_center_marker(self, center, color):
        """繪製圓心標記"""
        try:
            x, y = center
            # 繪製圓心十字標記
            cv2.line(self.display_frame, (x-8, y), (x+8, y), color, 2)
            cv2.line(self.display_frame, (x, y-8), (x, y+8), color, 2)
            # 繪製中心圓點
            cv2.circle(self.display_frame, center, 3, color, -1)
        except Exception as e:
            print(f"Draw center marker error: {str(e)}")

    def draw_diameter_value(self, center, value_text, color):
        """在圓心附近顯示直徑數值 - 智慧定位避免超出畫面"""
        try:
            # 獲取畫面尺寸
            frame_height, frame_width = self.display_frame.shape[:2]

            # 計算文字尺寸
            font = cv2.FONT_HERSHEY_SIMPLEX
            font_scale = 0.5
            thickness = 1
            text_size = cv2.getTextSize(value_text, font, font_scale, thickness)[0]
            text_width, text_height = text_size

            # 多個可能的位置（優先順序）
            possible_positions = [
                (center[0] + 25, center[1] - 25),  # 右上
                (center[0] - text_width - 25, center[1] - 25),  # 左上
                (center[0] + 25, center[1] + text_height + 25),  # 右下
                (center[0] - text_width - 25, center[1] + text_height + 25),  # 左下
                (center[0] - text_width // 2, center[1] - 35),  # 正上方
                (center[0] - text_width // 2, center[1] + 35)   # 正下方
            ]

            # 選擇第一個在畫面範圍內的位置
            selected_pos = None
            for pos_x, pos_y in possible_positions:
                if (5 <= pos_x <= frame_width - text_width - 5 and
                    text_height + 5 <= pos_y <= frame_height - 5):
                    selected_pos = (pos_x, pos_y)
                    break

            # 如果沒有完美位置，使用調整後的位置
            if selected_pos is None:
                text_x = max(5, min(frame_width - text_width - 5, center[0] + 20))
                text_y = max(text_height + 5, min(frame_height - 5, center[1] - 20))
                selected_pos = (text_x, text_y)

            self.draw_text_with_background(value_text, selected_pos, color)
        except Exception as e:
            print(f"Draw diameter value error: {str(e)}")

    def draw_realtime_diameter_info(self, center, radius):
        """顯示即時直徑測量資訊"""
        try:
            diameter_pixels = radius * 2

            if self.is_calibrated:
                diameter_mm = diameter_pixels * self.scale_factor
                radius_mm = diameter_mm / 2
                text = f"D:{diameter_mm:.2f}mm R:{radius_mm:.2f}mm"
            else:
                diameter_um = diameter_pixels * self.pixel_size_um
                diameter_mm = diameter_um / 1000
                radius_mm = diameter_mm / 2
                text = f"D:{diameter_mm:.2f}mm R:{radius_mm:.2f}mm*"

            # 獲取畫面尺寸
            frame_height, frame_width = self.display_frame.shape[:2]

            # 計算文字尺寸
            font = cv2.FONT_HERSHEY_SIMPLEX
            font_scale = 0.5
            thickness = 1
            text_size = cv2.getTextSize(text, font, font_scale, thickness)[0]
            text_width, text_height = text_size

            # 調整位置確保在畫面範圍內
            text_x = max(5, min(frame_width - text_width - 5, center[0] + 20))
            text_y = max(text_height + 5, min(frame_height - 5, center[1] - 20))

            # 顯示即時直徑值
            self.draw_text_with_background(text, (text_x, text_y), (0, 255, 255))
        except Exception as e:
            print(f"Draw realtime diameter info error: {str(e)}")

    def draw_measurement_counter(self):
        """顯示測量數量計數器"""
        try:
            # 修正為中文顯示
            counter_text = f"Record Size Count: {len(self.measurement_results)}/{self.max_measurements}"

            # 在左上角顯示計數器
            cv2.rectangle(self.display_frame, (10, 10), (280, 40), (0, 0, 0), -1)
            cv2.putText(self.display_frame, counter_text, (15, 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)

            # 如果接近上限，顯示警告
            if len(self.measurement_results) >= self.max_measurements - 1:
                warning_text = "Next measurement will clear all data"
                cv2.putText(self.display_frame, warning_text, (15, 55),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 255), 1)

        except Exception as e:
            print(f"Draw measurement counter error: {str(e)}")

    def clear_all_measurements(self):
        """清除所有測量數據（當達到上限時自動調用）"""
        try:
            self.measurement_points = []
            self.all_measurement_points = []
            self.measurement_results = []
        except Exception as e:
            print(f"Clear all measurements error: {str(e)}")

    def undo_last_measurement(self):
        """撤銷上次測量"""
        try:
            if self.measurement_results:
                # 移除最後一次測量結果
                last_result = self.measurement_results.pop()
                self.log_message("已撤銷上次測量")
            else:
                self.log_message("沒有可撤銷的測量")
        except Exception as e:
            print(f"Undo last measurement error: {str(e)}")

    def clear_measurements(self):
        """Clear all measurements"""
        try:
            self.measurement_points = []
            self.all_measurement_points = []  # 清除所有歷史測量點
            self.measurement_results = []     # 清除所有測量結果
            self.set_mode("none")
            self.log_message("所有測量已清除")
        except Exception as e:
            print(f"Clear measurements error: {str(e)}")

    def capture_image(self):
        """Capture image"""
        try:
            if self.current_frame is not None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"dinolite_capture_{timestamp}.jpg"
                cv2.imwrite(filename, self.display_frame)
                self.status_bar.config(text=f"影像已儲存: {filename}")
        except Exception as e:
            print(f"Capture image error: {str(e)}")

    def save_image(self):
        """Save image"""
        try:
            if self.current_frame is not None:
                filename = filedialog.asksaveasfilename(
                    defaultextension=".jpg",
                    filetypes=[("JPEG files", "*.jpg"), ("PNG files", "*.png"), ("All files", "*.*")]
                )
                if filename:
                    cv2.imwrite(filename, self.display_frame)
                    self.log_message(f"影像已儲存: {filename}")
        except Exception as e:
            print(f"Save image error: {str(e)}")

    def export_results(self):
        """Export results"""
        try:
            filename = filedialog.asksaveasfilename(
                defaultextension=".txt",
                filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
            )
            if filename:
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write("Dino-Lite AM3111 測量結果\n")
                    f.write("=" * 40 + "\n")
                    f.write(f"匯出時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                    f.write("設備型號: AM3111\n")
                    f.write(f"倍率: {int(self.current_magnification)}x\n")
                    cal_status = "已校準" if self.is_calibrated else "未校準"
                    f.write(f"校準狀態: {cal_status}\n")
                    if self.is_calibrated:
                        f.write(f"比例因子: {self.scale_factor:.6f} mm/pixel\n")
                    f.write(f"像素尺寸: {self.pixel_size_um:.3f} μm\n")
                    f.write("\n測量結果:\n")
                    f.write("-" * 30 + "\n")
                    f.write(self.results_text.get(1.0, tk.END))
                self.log_message(f"結果已匯出: {filename}")
        except Exception as e:
            print(f"Export results error: {str(e)}")

    def add_result(self, result):
        """Add result"""
        try:
            timestamp = datetime.now().strftime("%H:%M:%S")
            text = f"[{timestamp}] {result}\n"
            self.results_text.insert(tk.END, text)
            self.results_text.see(tk.END)
        except Exception as e:
            print(f"Add result error: {str(e)}")

    def log_message(self, message):
        """Log message"""
        try:
            timestamp = datetime.now().strftime("%H:%M:%S")
            text = f"[{timestamp}] {message}\n"
            self.results_text.insert(tk.END, text)
            self.results_text.see(tk.END)
            self.root.update()
        except Exception as e:
            print(f"Log message error: {str(e)}")

    def cleanup(self):
        """Cleanup resources"""
        try:
            self.is_running = False
            if self.cap:
                self.cap.release()
        except Exception as e:
            print(f"Cleanup error: {str(e)}")

def main():
    """Main function"""
    try:
        print("Starting application...")

        # Create root window
        root = tk.Tk()
        print("Tkinter root window created")

        # Create application
        app = DinoLiteApp(root)
        print("Application created")

        # Set close event
        def on_closing():
            print("Closing application")
            app.cleanup()
            root.destroy()

        root.protocol("WM_DELETE_WINDOW", on_closing)

        # Show welcome message (safe version)
        try:
            welcome_text = """Dino-Lite AM3111 測量系統

功能特色:
• 攝影機控制與影像顯示
• 距離和角度測量
• 精確校準系統
• LED 軟體亮度控制
• 測量結果記錄和匯出
• 重複性測試
• 精度驗證指南

使用步驟:
1. 點擊「開啟攝影機」
2. 調整適當倍率 (建議50x-100x)
3. 調整LED亮度獲得最佳照明
4. 進行校準 (建議使用1mm標準距離)
5. 選擇測量工具
6. 在影像上點擊進行測量

測量技巧:
• 校準後測量精度更高
• 選擇清晰的測量點
• 適當的照明很重要
• 可進行重複性測試驗證精度

AM3111 規格:
• 倍率範圍: 20x-200x
• 最佳測量倍率: 50x-100x
• 內建LED照明

開始您的精密測量！"""

            messagebox.showinfo("Dino-Lite AM3111", welcome_text)
        except Exception as e:
            print(f"Welcome message error: {str(e)}")

        print("Starting main loop...")
        root.mainloop()
        print("Main loop ended")

    except Exception as e:
        print(f"Main function error: {str(e)}")
        try:
            messagebox.showerror("Error", "Program startup failed")
        except:
            print("Cannot show error dialog")

if __name__ == "__main__":
    print("=== Dino-Lite AM3111 Measurement System ===")
    main()
    print("Program ended")