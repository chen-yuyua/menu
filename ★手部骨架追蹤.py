import cv2
import mediapipe as mp
import numpy as np
# 不需要schedule庫，所以不導入它
# 如果你確實需要schedule庫，請使用下面的import語句
# import schedule

# 初始化MediaPipe手部追蹤模型
mp_hands = mp.solutions.hands
mp_drawing = mp.solutions.drawing_utils
mp_drawing_styles = mp.solutions.drawing_styles

# 定義骨架連接關係 (手指關節間的連接)
HAND_CONNECTIONS = [
    (0, 1), (1, 2), (2, 3), (3, 4),  # 拇指
    (0, 5), (5, 6), (6, 7), (7, 8),  # 食指
    (0, 9), (9, 10), (10, 11), (11, 12),  # 中指
    (0, 13), (13, 14), (14, 15), (15, 16),  # 無名指
    (0, 17), (17, 18), (18, 19), (19, 20),  # 小指
    (5, 9), (9, 13), (13, 17),  # 掌心橫向連接
    (0, 5), (0, 17)  # 腕部到掌心
]

# 設置攝影機
cap = cv2.VideoCapture(0)  # 使用內建攝影機，如果有多個攝影機，可以改為1, 2等

# 設置手部追蹤模型
with mp_hands.Hands(
        max_num_hands=2,  # 最多檢測兩隻手
        min_detection_confidence=0.5,  # 最小檢測信心度
        min_tracking_confidence=0.5) as hands:

    while cap.isOpened():
        success, image = cap.read()
        if not success:
            print("無法讀取攝影機畫面")
            continue

        # 水平翻轉影像以正確顯示
        image = cv2.flip(image, 1)

        # 優化效能：將BGR轉換為RGB
        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        # 設置影像不可寫入，加速處理
        image_rgb.flags.writeable = False

        # 處理影像
        results = hands.process(image_rgb)

        # 繪製結果
        image.flags.writeable = True

        # 創建一個黑色背景，用於更清晰顯示手部骨架
        hand_skeleton = np.zeros_like(image)

        if results.multi_hand_landmarks:
            for hand_landmarks in results.multi_hand_landmarks:
                # 繪製MediaPipe預設的手部關節與連接
                mp_drawing.draw_landmarks(
                    image,
                    hand_landmarks,
                    mp_hands.HAND_CONNECTIONS,
                    mp_drawing_styles.get_default_hand_landmarks_style(),
                    mp_drawing_styles.get_default_hand_connections_style())

                # 在黑色背景上繪製骨架
                mp_drawing.draw_landmarks(
                    hand_skeleton,
                    hand_landmarks,
                    mp_hands.HAND_CONNECTIONS,
                    mp_drawing_styles.DrawingSpec(color=(0, 255, 0), thickness=2),
                    mp_drawing_styles.DrawingSpec(color=(255, 255, 255), thickness=2))

                # 添加關節點標籤（可選）
                for id, landmark in enumerate(hand_landmarks.landmark):
                    h, w, c = image.shape
                    cx, cy = int(landmark.x * w), int(landmark.y * h)
                    cv2.circle(image, (cx, cy), 5, (255, 0, 0), cv2.FILLED)
                    cv2.putText(image, str(id), (cx, cy), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)

        # 顯示結果
        cv2.imshow('原始影像 (含手部標記)', image)
        cv2.imshow('手部骨架', hand_skeleton)

        # 按 'q' 鍵退出
        if cv2.waitKey(5) & 0xFF == ord('q'):
            break

# 釋放資源
cap.release()
cv2.destroyAllWindows()