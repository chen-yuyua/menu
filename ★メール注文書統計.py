import win32com.client
import pandas as pd
from datetime import datetime

# 設定搜尋條件
FOLDER_NAME = "受信トレイ"  # 指定的信件夾
SUBJECT_KEYWORD = "【注文書発行】"  # 件名包含的關鍵字
START_DATE = datetime(2025, 3, 1)  # 開始日期
END_DATE = datetime(2025, 3, 13)  # 結束日期
OUTPUT_PATH = r"C:\Users\chenyw\Downloads\注文書統計_2024年度.xlsx"  # 輸出的檔案路徑

# 初始化 Outlook
outlook = win32com.client.Dispatch("Outlook.Application")
namespace = outlook.GetNamespace("MAPI")

# 尋找指定的信件夾
folder = namespace.GetDefaultFolder(6)  # 6 = Inbox
if folder.Name != FOLDER_NAME:
    for subfolder in folder.Folders:
        if subfolder.Name == FOLDER_NAME:
            folder = subfolder
            break

# 遍歷信件，符合條件的信件記錄下來
messages = folder.Items
messages = messages.Restrict(f"[ReceivedTime] >= '{START_DATE.strftime('%m/%d/%Y')}' AND [ReceivedTime] <= '{END_DATE.strftime('%m/%d/%Y')}'")
messages.Sort("[ReceivedTime]", True)  # 根據接收時間排序，降序

data = []
seen_subjects = set()  # 用於存儲已處理的件名
for message in messages:
    try:
        # 確保是 MailItem 類型並且有必要的屬性
        if hasattr(message, "Subject") and hasattr(message, "ReceivedTime") and hasattr(message, "SenderName"):
            if SUBJECT_KEYWORD in message.Subject and message.Subject not in seen_subjects:
                seen_subjects.add(message.Subject)  # 將件名添加到已處理集合中
                data.append({
                    "件名": message.Subject,
                    "接收時間": message.ReceivedTime.strftime("%Y-%m-%d %H:%M:%S"),
                    "寄件者": message.SenderName
                })
    except Exception as e:
        print(f"Error processing message: {message}. Error: {e}")
        continue  # 跳過處理錯誤的信件

# 將結果輸出到 Excel
df = pd.DataFrame(data)
if not df.empty:
    df.to_excel(OUTPUT_PATH, index=False, sheet_name="注文書統計")  # 移除 encoding
    print(f"信件件名與寄件者已彙整至 {OUTPUT_PATH}")
else:
    print("未找到符合條件的信件。")
