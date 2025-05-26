import cv2
import numpy as np
import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time

class DistanceMeasurement:
    def __init__(self):
        self.cap = None
        self.running = False
        self.pixel_to_mm_ratio = 1.0  # 預設比例，需要校準
        self.measuring = False
        self.points = []
        self.current_frame = None
        self.processed_frame = None

        # 建立GUI
        self.setup_gui()

    def setup_gui(self):
        """設定GUI介面"""
        self.root = tk.Tk()
        self.root.title("視訊測距系統")
        self.root.geometry("400x500")

        # 相機選擇
        ttk.Label(self.root, text="選擇相機:").grid(row=0, column=0, padx=5, pady=5)
        self.camera_var = tk.StringVar(value="0")
        self.camera_combo = ttk.Combobox(self.root, textvariable=self.camera_var, width=10)
        self.camera_combo['values'] = ["0", "1", "2", "3"]
        self.camera_combo.grid(row=0, column=1, padx=5, pady=5)

        # 控制按鈕
        self.start_btn = ttk.Button(self.root, text="啟動相機", command=self.start_camera)
        self.start_btn.grid(row=1, column=0, padx=5, pady=5)

        self.stop_btn = ttk.Button(self.root, text="停止相機", command=self.stop_camera, state="disabled")
        self.stop_btn.grid(row=1, column=1, padx=5, pady=5)

        # 校準設定
        ttk.Label(self.root, text="校準 (已知距離mm):").grid(row=2, column=0, padx=5, pady=5)
        self.calibration_entry = ttk.Entry(self.root, width=10)
        self.calibration_entry.grid(row=2, column=1, padx=5, pady=5)
        self.calibration_entry.insert(0, "10.0")

        self.calibrate_btn = ttk.Button(self.root, text="開始校準", command=self.start_calibration)
        self.calibrate_btn.grid(row=3, column=0, columnspan=2, padx=5, pady=5)

        # 測量模式
        self.measure_mode_var = tk.StringVar(value="manual")
        ttk.Label(self.root, text="測量模式:").grid(row=4, column=0, padx=5, pady=5)
        ttk.Radiobutton(self.root, text="手動", variable=self.measure_mode_var, value="manual").grid(row=4, column=1)
        ttk.Radiobutton(self.root, text="自動", variable=self.measure_mode_var, value="auto").grid(row=5, column=1)

        # 測量按鈕
        self.measure_btn = ttk.Button(self.root, text="開始測量", command=self.start_measurement)
        self.measure_btn.grid(row=6, column=0, columnspan=2, padx=5, pady=5)

        # 邊緣檢測參數
        ttk.Label(self.root, text="邊緣檢測參數:").grid(row=7, column=0, columnspan=2, padx=5, pady=5)

        ttk.Label(self.root, text="Canny低閾值:").grid(row=8, column=0, padx=5, pady=2)
        self.canny_low = tk.Scale(self.root, from_=0, to=255, orient=tk.HORIZONTAL, length=200)
        self.canny_low.set(50)
        self.canny_low.grid(row=8, column=1, padx=5, pady=2)

        ttk.Label(self.root, text="Canny高閾值:").grid(row=9, column=0, padx=5, pady=2)
        self.canny_high = tk.Scale(self.root, from_=0, to=255, orient=tk.HORIZONTAL, length=200)
        self.canny_high.set(150)
        self.canny_high.grid(row=9, column=1, padx=5, pady=2)

        # 結果顯示
        ttk.Label(self.root, text="測量結果:").grid(row=10, column=0, padx=5, pady=5)
        self.result_label = ttk.Label(self.root, text="--", font=("Arial", 16, "bold"))
        self.result_label.grid(row=11, column=0, columnspan=2, padx=5, pady=5)

        # 狀態列
        self.status_label = ttk.Label(self.root, text="準備就緒", relief=tk.SUNKEN)
        self.status_label.grid(row=12, column=0, columnspan=2, sticky="ew", padx=5, pady=5)

    def start_camera(self):
        """啟動相機"""
        try:
            camera_index = int(self.camera_var.get())
            self.cap = cv2.VideoCapture(camera_index)

            if not self.cap.isOpened():
                messagebox.showerror("錯誤", "無法開啟相機")
                return

            self.running = True
            self.start_btn.config(state="disabled")
            self.stop_btn.config(state="normal")
            self.status_label.config(text="相機已啟動")

            # 開始視訊處理線程
            self.video_thread = threading.Thread(target=self.process_video)
            self.video_thread.start()

        except Exception as e:
            messagebox.showerror("錯誤", f"啟動相機失敗: {str(e)}")

    def stop_camera(self):
        """停止相機"""
        self.running = False
        if self.cap:
            self.cap.release()
        cv2.destroyAllWindows()

        self.start_btn.config(state="normal")
        self.stop_btn.config(state="disabled")
        self.status_label.config(text="相機已停止")

    def process_video(self):
        """處理視訊串流"""
        while self.running:
            ret, frame = self.cap.read()
            if not ret:
                continue

            self.current_frame = frame.copy()

            # 轉換為灰度圖
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

            # 高斯模糊
            blurred = cv2.GaussianBlur(gray, (5, 5), 0)

            # 邊緣檢測
            edges = cv2.Canny(blurred, self.canny_low.get(), self.canny_high.get())

            # 儲存處理後的圖像
            self.processed_frame = edges

            # 顯示原始影像
            display_frame = frame.copy()

            # 如果在測量模式，顯示測量資訊
            if self.measuring:
                if self.measure_mode_var.get() == "manual":
                    # 手動模式：顯示選擇的點
                    for i, point in enumerate(self.points):
                        cv2.circle(display_frame, point, 5, (0, 255, 0), -1)
                        cv2.putText(display_frame, f"P{i+1}", (point[0]+10, point[1]),
                                  cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)

                    # 如果有兩個點，畫線並顯示距離
                    if len(self.points) == 2:
                        cv2.line(display_frame, self.points[0], self.points[1], (0, 255, 0), 2)
                        distance = self.calculate_distance(self.points[0], self.points[1])
                        mid_point = ((self.points[0][0] + self.points[1][0]) // 2,
                                   (self.points[0][1] + self.points[1][1]) // 2)
                        cv2.putText(display_frame, f"{distance:.2f} mm", mid_point,
                                  cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

                elif self.measure_mode_var.get() == "auto":
                    # 自動模式：偵測並測量物體
                    self.auto_measure(display_frame, edges)

            # 顯示影像
            cv2.imshow("視訊測距系統", display_frame)

            # 顯示邊緣檢測結果
            cv2.imshow("邊緣檢測", edges)

            # 按ESC鍵退出
            if cv2.waitKey(1) & 0xFF == 27:
                self.stop_camera()
                break

    def mouse_callback(self, event, x, y, flags, param):
        """滑鼠事件回調函數"""
        if event == cv2.EVENT_LBUTTONDOWN and self.measuring:
            if self.measure_mode_var.get() == "manual":
                self.points.append((x, y))
                if len(self.points) > 2:
                    self.points = [(x, y)]

                if len(self.points) == 2:
                    distance = self.calculate_distance(self.points[0], self.points[1])
                    self.result_label.config(text=f"{distance:.2f} mm")
                    self.status_label.config(text=f"測量完成: {distance:.2f} mm")

    def calculate_distance(self, p1, p2):
        """計算兩點間的距離"""
        pixel_distance = np.sqrt((p1[0] - p2[0])**2 + (p1[1] - p2[1])**2)
        real_distance = pixel_distance * self.pixel_to_mm_ratio
        return real_distance

    def start_calibration(self):
        """開始校準"""
        if not self.running:
            messagebox.showwarning("警告", "請先啟動相機")
            return

        try:
            known_distance = float(self.calibration_entry.get())
            if known_distance <= 0:
                raise ValueError("距離必須大於0")

            self.measuring = True
            self.points = []
            self.calibration_distance = known_distance
            self.status_label.config(text="校準模式：請點擊兩個點")

            # 設定滑鼠回調
            cv2.setMouseCallback("視訊測距系統", self.calibration_callback)

        except ValueError as e:
            messagebox.showerror("錯誤", "請輸入有效的距離值")

    def calibration_callback(self, event, x, y, flags, param):
        """校準滑鼠回調"""
        if event == cv2.EVENT_LBUTTONDOWN:
            self.points.append((x, y))
            if len(self.points) == 2:
                pixel_distance = np.sqrt((self.points[0][0] - self.points[1][0])**2 +
                                       (self.points[0][1] - self.points[1][1])**2)
                self.pixel_to_mm_ratio = self.calibration_distance / pixel_distance
                self.status_label.config(text=f"校準完成：1像素 = {self.pixel_to_mm_ratio:.4f} mm")
                self.measuring = False
                self.points = []
                cv2.setMouseCallback("視訊測距系統", lambda *args: None)

    def start_measurement(self):
        """開始測量"""
        if not self.running:
            messagebox.showwarning("警告", "請先啟動相機")
            return

        self.measuring = True
        self.points = []
        self.status_label.config(text="測量模式已啟動")

        if self.measure_mode_var.get() == "manual":
            cv2.setMouseCallback("視訊測距系統", self.mouse_callback)
        else:
            cv2.setMouseCallback("視訊測距系統", lambda *args: None)

    def auto_measure(self, display_frame, edges):
        """自動測量模式"""
        # 尋找輪廓
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        # 過濾太小的輪廓
        min_area = 500
        valid_contours = [c for c in contours if cv2.contourArea(c) > min_area]

        if len(valid_contours) >= 2:
            # 找到兩個最大的輪廓
            valid_contours = sorted(valid_contours, key=cv2.contourArea, reverse=True)[:2]

            # 計算輪廓的中心點
            centers = []
            for contour in valid_contours:
                M = cv2.moments(contour)
                if M["m00"] != 0:
                    cx = int(M["m10"] / M["m00"])
                    cy = int(M["m01"] / M["m00"])
                    centers.append((cx, cy))

            if len(centers) == 2:
                # 畫出輪廓
                cv2.drawContours(display_frame, valid_contours, -1, (0, 255, 0), 2)

                # 畫出中心點
                for center in centers:
                    cv2.circle(display_frame, center, 5, (255, 0, 0), -1)

                # 畫出連接線
                cv2.line(display_frame, centers[0], centers[1], (255, 0, 0), 2)

                # 計算並顯示距離
                distance = self.calculate_distance(centers[0], centers[1])
                self.result_label.config(text=f"{distance:.2f} mm")

                # 在影像上顯示距離
                mid_point = ((centers[0][0] + centers[1][0]) // 2,
                           (centers[0][1] + centers[1][1]) // 2)
                cv2.putText(display_frame, f"{distance:.2f} mm", mid_point,
                          cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 0, 0), 2)

    def run(self):
        """執行主程式"""
        self.root.mainloop()
        self.stop_camera()

if __name__ == "__main__":
    app = DistanceMeasurement()
    app.run()