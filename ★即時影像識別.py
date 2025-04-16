import cv2
import numpy as np
import time
import logging
import datetime
from ultralytics import YOLO

class ObjectDetectionSystem:
    def __init__(self, confidence_threshold=0.5):
        self.confidence_threshold = confidence_threshold

        # 加載YOLOv8模型
        self.model = YOLO("yolov8l.pt")  # 使用YOLOv8 nano版本，速度快

        # 初始化攝像頭
        self.cap = cv2.VideoCapture(0)

        # 定義人物類別ID (person = 0 in COCO dataset)
        self.person_class_id = 0

        # 顏色設置
        self.person_color = (0, 255, 0)  # 綠色表示人
        self.object_color = (255, 0, 0)  # 藍色表示其他物體

        # 配置日誌 - 更改保存位置到指定目錄
        logging.basicConfig(filename=r'V:\VS CODE\Python\detection_log.txt', level=logging.INFO)

        # 定義監控區域 - 形成一個矩形區域
        self.monitoring_area = [(100, 100), (500, 100), (500, 400), (100, 400)]

    def draw_person_icon(self, frame, width=50, height=80):
        """在畫面右上角繪製一個更大的人物圖標，尺寸為50px×80px"""
        # 設定圖標位置（右上角）
        frame_width = frame.shape[1]
        icon_x = frame_width - width - 20  # 距離右邊界20px
        icon_y = 20  # 距離上邊界20px

        # 繪製人物圖標 - 更詳細的人形
        # 頭部
        head_radius = width // 3
        head_center = (icon_x + width // 2, icon_y + head_radius)
        cv2.circle(frame, head_center, head_radius, (255, 255, 255), -1)

        # 身體 - 更粗的線條
        body_start = (icon_x + width // 2, icon_y + head_radius * 2)
        body_end = (icon_x + width // 2, icon_y + height - height // 3)
        cv2.line(frame, body_start, body_end, (255, 255, 255), 4)

        # 手臂 - 稍微彎曲的手臂
        shoulders_y = icon_y + head_radius * 2 + 5
        left_shoulder = (icon_x + width // 2 - 3, shoulders_y)
        right_shoulder = (icon_x + width // 2 + 3, shoulders_y)

        left_elbow = (icon_x + width // 4, shoulders_y + height // 5)
        right_elbow = (icon_x + width * 3 // 4, shoulders_y + height // 5)

        left_hand = (icon_x + width // 6, shoulders_y + height // 3)
        right_hand = (icon_x + width * 5 // 6, shoulders_y + height // 3)

        # 繪製手臂
        cv2.line(frame, left_shoulder, left_elbow, (255, 255, 255), 3)
        cv2.line(frame, left_elbow, left_hand, (255, 255, 255), 3)
        cv2.line(frame, right_shoulder, right_elbow, (255, 255, 255), 3)
        cv2.line(frame, right_elbow, right_hand, (255, 255, 255), 3)

        # 腿部 - 更長的腿
        hips_y = icon_y + height - height // 3
        left_hip = (icon_x + width // 2 - 3, hips_y)
        right_hip = (icon_x + width // 2 + 3, hips_y)

        left_knee = (icon_x + width // 3, hips_y + height // 4)
        right_knee = (icon_x + width * 2 // 3, hips_y + height // 4)

        left_foot = (icon_x + width // 4, icon_y + height)
        right_foot = (icon_x + width * 3 // 4, icon_y + height)

        # 繪製腿部
        cv2.line(frame, left_hip, left_knee, (255, 255, 255), 3)
        cv2.line(frame, left_knee, left_foot, (255, 255, 255), 3)
        cv2.line(frame, right_hip, right_knee, (255, 255, 255), 3)
        cv2.line(frame, right_knee, right_foot, (255, 255, 255), 3)

        return frame

    def is_in_area(self, box, area):
        """檢查物體是否在監控區域內"""
        # 獲取物體的中心點
        x1, y1, x2, y2 = box
        center_x = (x1 + x2) // 2
        center_y = (y1 + y2) // 2

        # 使用點在多邊形內的算法 (Point in Polygon)
        inside = False
        j = len(area) - 1
        for i in range(len(area)):
            if ((area[i][1] > center_y) != (area[j][1] > center_y)) and \
               (center_x < (area[j][0] - area[i][0]) * (center_y - area[i][1]) /
                (area[j][1] - area[i][1]) + area[i][0]):
                inside = not inside
            j = i

        return inside

    def detect_objects(self, frame):
        # 使用YOLOv8進行預測
        results = self.model(frame, conf=self.confidence_threshold)

        # 初始化計數器
        persons_count = 0
        objects_count = 0
        persons_in_area = 0

        # 獲取第一個結果（通常只有一個）
        result = results[0]

        # 複製原始畫面以繪製結果
        annotated_frame = frame.copy()

        # 繪製監控區域
        pts = np.array(self.monitoring_area, np.int32)
        pts = pts.reshape((-1, 1, 2))
        cv2.polylines(annotated_frame, [pts], True, (255, 255, 0), 2)

        # 處理每個檢測結果
        if result.boxes is not None:
            boxes = result.boxes

            for box in boxes:
                # 獲取邊界框
                x1, y1, x2, y2 = box.xyxy[0].cpu().numpy().astype(int)

                # 獲取類別ID和信心度
                class_id = int(box.cls[0].item())
                confidence = box.conf[0].item()

                # 檢查是否在監控區域內
                in_area = self.is_in_area([x1, y1, x2, y2], self.monitoring_area)

                # 判斷是人還是物體
                if class_id == self.person_class_id:
                    persons_count += 1
                    if in_area:
                        persons_in_area += 1
                        color = (0, 255, 255)  # 區域內的人用黃色標記
                    else:
                        color = self.person_color
                    label = f"Person: {confidence:.2f}"
                else:
                    objects_count += 1
                    color = self.object_color
                    class_name = result.names[class_id]
                    label = f"{class_name}: {confidence:.2f}"

                # 繪製邊界框
                cv2.rectangle(annotated_frame, (x1, y1), (x2, y2), color, 2)

                # 繪製標籤背景
                text_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 2)[0]
                cv2.rectangle(annotated_frame, (x1, y1 - 25), (x1 + text_size[0], y1), color, -1)

                # 繪製標籤文字 - 使用更美觀的字體和更好的大小
                cv2.putText(annotated_frame, label, (x1, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX,
                            0.6, (255, 255, 255), 2)

        # 記錄檢測結果到日誌
        log_message = f"{datetime.datetime.now()}: Detected {persons_count} persons ({persons_in_area} in monitored area) and {objects_count} objects"
        logging.info(log_message)

        # 顯示檢測結果 - 使用更美觀的信息顯示
        # 為信息文字添加背景
        info_text = f"Persons: {persons_count} (In Area: {persons_in_area}), Objects: {objects_count}"
        text_size = cv2.getTextSize(info_text, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2)[0]
        cv2.rectangle(annotated_frame, (5, 5), (15 + text_size[0], 40), (0, 0, 0), -1)
        # 添加美觀的文字
        cv2.putText(annotated_frame, info_text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

        # 如果檢測到人，在右上角添加人物圖標
        if persons_count > 0:
            annotated_frame = self.draw_person_icon(annotated_frame, width=50, height=80)

        return annotated_frame, persons_count, objects_count, persons_in_area

    def run(self):
        try:
            while True:
                ret, frame = self.cap.read()
                if not ret:
                    print("無法獲取畫面")
                    break

                # 旋轉畫面180度以解決顛倒問題
                frame = cv2.rotate(frame, cv2.ROTATE_180)

                # 檢測物體
                start_time = time.time()
                processed_frame, persons, objects, persons_in_area = self.detect_objects(frame)
                end_time = time.time()

                # 計算FPS
                fps = 1 / (end_time - start_time)
                # 為FPS信息添加背景以美化顯示
                fps_text = f"FPS: {fps:.2f}"
                fps_text_size = cv2.getTextSize(fps_text, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2)[0]
                cv2.rectangle(processed_frame, (5, 45), (15 + fps_text_size[0], 80), (0, 0, 0), -1)
                cv2.putText(processed_frame, fps_text, (10, 70), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)

                # 顯示結果
                cv2.imshow("Real-time Object Detection", processed_frame)

                # 按'q'鍵退出
                if cv2.waitKey(1) == ord('q'):
                    break

        finally:
            # 釋放資源
            self.cap.release()
            cv2.destroyAllWindows()


if __name__ == "__main__":
    detector = ObjectDetectionSystem(confidence_threshold=0.5)
    detector.run()
