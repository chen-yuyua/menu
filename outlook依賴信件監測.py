# 監測 Outlook 信箱特定資料夾並處理 Excel 附件的自動化程式
# 此程式會監測 "BIL_Business request" 資料夾中的新郵件，並讀取其中的 Excel 附件

import win32com.client
import os
import time
import pandas as pd
from datetime import datetime
import logging

# 設定日誌
logging.basicConfig(filename='outlook_monitor.log', level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

# 設定參數
OUTLOOK_FOLDER_NAME = "BIL_Business request"  # 要監測的資料夾名稱
OUTPUT_EXCEL_PATH = r"C:\Path\To\Your\Output.xlsx"  # 輸出的 Excel 檔案路徑
TEMP_FOLDER = r"C:\Temp\ExcelTemp"  # 臨時儲存附件的資料夾
CHECK_INTERVAL = 300  # 檢查郵件間隔時間（秒）

# 確保臨時資料夾存在
if not os.path.exists(TEMP_FOLDER):
    os.makedirs(TEMP_FOLDER)

def connect_to_outlook():
    """連接到 Outlook 應用程式"""
    try:
        outlook = win32com.client.Dispatch("Outlook.Application")
        namespace = outlook.GetNamespace("MAPI")
        return namespace
    except Exception as e:
        logging.error(f"無法連接到 Outlook: {str(e)}")
        return None

def get_target_folder(namespace):
    """取得目標信箱資料夾"""
    try:
        inbox = namespace.GetDefaultFolder(6)  # 6 表示收件匣
        folders = inbox.Folders

        # 找到 BIL_Business request 資料夾
        for folder in folders:
            if folder.Name == OUTLOOK_FOLDER_NAME:
                return folder

        logging.error(f"找不到資料夾: {OUTLOOK_FOLDER_NAME}")
        return None
    except Exception as e:
        logging.error(f"取得資料夾時發生錯誤: {str(e)}")
        return None

def process_excel_attachment(file_path):
    """處理 Excel 附件並提取所需資料"""
    try:
        # 讀取 Excel 文件 (嘗試自動偵測所有工作表)
        excel_file = pd.ExcelFile(file_path)
        sheet_names = excel_file.sheet_names

        # 記錄所有可用的工作表
        logging.info(f"Excel 檔案包含以下工作表: {', '.join(sheet_names)}")

        # 嘗試識別可能包含所需資料的工作表
        target_sheet = None

        # 如果知道確切的工作表名稱，可以直接使用
        if '目標工作表' in sheet_names:  # 請替換為實際的工作表名稱
            target_sheet = '目標工作表'
        # 否則查找第一個非空的工作表
        else:
            for sheet in sheet_names:
                df_temp = pd.read_excel(file_path, sheet_name=sheet)
                if not df_temp.empty:
                    target_sheet = sheet
                    logging.info(f"自動選擇工作表: {sheet}")
                    break

        if target_sheet is None:
            logging.error("找不到有效的工作表")
            return None

        # 讀取選定的工作表
        df = pd.read_excel(file_path, sheet_name=target_sheet)

        # 打印列名以便調試
        logging.info(f"Excel 檔案包含以下欄位: {', '.join(str(col) for col in df.columns)}")

        # 智能提取資料 - 根據實際情況自動調整
        # 1. 如果知道確切的欄位名稱
        try:
            # 嘗試直接使用欄位名稱 (你需要替換這些為實際的欄位名稱)
            target_columns = ['需求單號', '申請日期', '申請人', '需求內容', '優先級']
            available_columns = [col for col in target_columns if col in df.columns]

            if available_columns:
                required_data = df.loc[:, available_columns].copy()
                logging.info(f"成功提取特定欄位: {', '.join(available_columns)}")
            else:
                # 如果找不到預期的欄位，則獲取所有列
                logging.warning("找不到預期的欄位，將提取所有資料")
                required_data = df.copy()

            # 提取前10行資料（或少於10行如果表格較小）
            row_limit = min(10, len(required_data))
            required_data = required_data.iloc[:row_limit].copy()

            # 在 DataFrame 中新增相關資訊欄位用於之後的填充
            required_data['收件時間'] = ''
            required_data['寄件者'] = ''
            required_data['主旨'] = ''

            return required_data

        except Exception as inner_e:
            logging.warning(f"按欄位名稱提取資料失敗: {str(inner_e)}，將嘗試其他方法")

            # 2. 如果不確定欄位結構，提取表格中的一部分區域
            # 提取前15行，所有列的資料
            required_data = df.iloc[:15, :].copy()

            # 在 DataFrame 中新增相關資訊欄位
            required_data['收件時間'] = ''
            required_data['寄件者'] = ''
            required_data['主旨'] = ''

            return required_data

    except Exception as e:
        logging.error(f"處理 Excel 附件時發生錯誤: {str(e)}")
        return None

def save_to_output_excel(data, sender, receive_time, subject):
    """將資料保存到輸出 Excel 文件"""
    try:
        # 檢查輸出文件是否存在，如果不存在則創建
        if not os.path.exists(OUTPUT_EXCEL_PATH):
            # 創建一個空的 DataFrame 並設置列名
            # 需要根據具體提取的資料欄位來設定列名
            columns = ['收件時間', '寄件者', '主旨']

            # 如果 data 已經有欄位，加入這些欄位
            if data is not None and not data.empty:
                for col in data.columns:
                    if col not in columns:
                        columns.append(col)

            output_df = pd.DataFrame(columns=columns)

            # 創建輸出文件的目錄（如果不存在）
            output_dir = os.path.dirname(OUTPUT_EXCEL_PATH)
            if not os.path.exists(output_dir) and output_dir:
                os.makedirs(output_dir)

            output_df.to_excel(OUTPUT_EXCEL_PATH, index=False)
            logging.info(f"創建了新的輸出文件: {OUTPUT_EXCEL_PATH}")

        # 讀取現有的輸出文件
        output_df = pd.read_excel(OUTPUT_EXCEL_PATH)

        # 如果沒有資料要保存，則記錄並返回
        if data is None or data.empty:
            logging.warning("沒有資料需要保存，跳過")
            return

        # 為提取的資料添加郵件相關資訊
        # 使用 fillna 確保 DataFrame 的所有列都填充了值
        data['收件時間'] = receive_time
        data['寄件者'] = sender
        data['主旨'] = subject

        # 確保所有必要的列都存在於輸出 DataFrame 中
        for col in data.columns:
            if col not in output_df.columns:
                output_df[col] = None

        # 將新資料附加到輸出文件
        output_df = pd.concat([output_df, data], ignore_index=True)

        # 保存更新後的資料 - 嘗試不同的方法以確保可靠性
        try:
            # 嘗試直接保存
            output_df.to_excel(OUTPUT_EXCEL_PATH, index=False)
        except PermissionError:
            # 如果文件被鎖定，嘗試另存為臨時文件然後重命名
            temp_file = OUTPUT_EXCEL_PATH + ".temp"
            output_df.to_excel(temp_file, index=False)

            # 如果原文件存在，嘗試刪除它
            if os.path.exists(OUTPUT_EXCEL_PATH):
                try:
                    os.remove(OUTPUT_EXCEL_PATH)
                except:
                    logging.error("無法刪除原輸出文件，可能被其他程序鎖定")
                    return

            # 重命名臨時文件
            os.rename(temp_file, OUTPUT_EXCEL_PATH)

        logging.info(f"已成功將資料保存到 {OUTPUT_EXCEL_PATH}，新增了 {len(data)} 行資料")
    except Exception as e:
        logging.error(f"保存資料到輸出文件時發生錯誤: {str(e)}")

def check_and_process_new_emails(folder):
    """檢查並處理資料夾中的新郵件"""
    try:
        messages = folder.Items
        messages.Sort("[ReceivedTime]", True)  # 按接收時間降序排序

        processed_count = 0
        excel_found = False

        # 檢查是否有未讀郵件
        for message in messages:
            # 只處理最近30天內的郵件，避免處理太多舊郵件
            received_date = message.ReceivedTime
            now = datetime.now()
            days_old = (now - received_date.replace(tzinfo=None)).days

            if days_old > 30:
                continue  # 跳過超過30天的郵件

            if message.Unread:
                processed_count += 1
                logging.info(f"發現新郵件 ({processed_count}) - 主旨: {message.Subject}, 寄件者: {message.SenderName}")

                # 處理附件
                attachments = message.Attachments
                attachment_count = attachments.Count

                if attachment_count == 0:
                    logging.info(f"郵件 '{message.Subject}' 沒有附件，略過處理")
                    continue

                excel_found_in_message = False

                for i in range(1, attachment_count + 1):
                    attachment = attachments.Item(i)
                    file_name = attachment.FileName

                    # 檢查是否為 Excel 檔案
                    if file_name.lower().endswith(('.xlsx', '.xls', '.xlsm')):
                        excel_found = True
                        excel_found_in_message = True

                        # 生成唯一的檔名避免衝突
                        unique_filename = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{file_name}"
                        temp_file_path = os.path.join(TEMP_FOLDER, unique_filename)

                        try:
                            attachment.SaveAsFile(temp_file_path)
                            logging.info(f"已儲存附件: {file_name} 到 {temp_file_path}")

                            # 處理 Excel 附件
                            extracted_data = process_excel_attachment(temp_file_path)
                            if extracted_data is not None:
                                # 保存到輸出文件
                                save_to_output_excel(
                                    extracted_data,
                                    message.SenderName,
                                    message.ReceivedTime.strftime('%Y-%m-%d %H:%M:%S'),
                                    message.Subject
                                )
                                logging.info(f"成功處理附件 {file_name} 並保存資料")
                            else:
                                logging.warning(f"從附件 {file_name} 中無法提取資料")

                        except Exception as attach_e:
                            logging.error(f"處理附件 {file_name} 時發生錯誤: {str(attach_e)}")
                        finally:
                            # 處理完成後刪除臨時文件（無論成功或失敗）
                            if os.path.exists(temp_file_path):
                                try:
                                    os.remove(temp_file_path)
                                    logging.info(f"已刪除臨時檔案: {temp_file_path}")
                                except Exception as del_e:
                                    logging.error(f"刪除臨時檔案時發生錯誤: {str(del_e)}")

                if not excel_found_in_message:
                    logging.info(f"郵件 '{message.Subject}' 中沒有找到 Excel 檔案附件")

                # 設為已讀
                try:
                    message.Unread = False
                    message.Save()
                    logging.info(f"郵件 '{message.Subject}' 已標記為已讀")
                except Exception as mark_e:
                    logging.error(f"標記郵件為已讀時發生錯誤: {str(mark_e)}")

        # 記錄處理結果摘要
        if processed_count == 0:
            logging.info("沒有發現新郵件需要處理")
        else:
            logging.info(f"本次檢查共處理了 {processed_count} 封郵件")

        if not excel_found:
            logging.info("沒有找到任何 Excel 附件")

        return processed_count
    except Exception as e:
        logging.error(f"檢查新郵件時發生錯誤: {str(e)}")
        return 0

def create_config_file(config_path):
    """創建默認的配置文件"""
    config = {
        "outlook_folder": OUTLOOK_FOLDER_NAME,
        "output_excel": OUTPUT_EXCEL_PATH,
        "temp_folder": TEMP_FOLDER,
        "check_interval": CHECK_INTERVAL,
        "log_level": "INFO"
    }

    with open(config_path, 'w', encoding='utf-8') as f:
        f.write("# Outlook 監控程式配置文件\n")
        for key, value in config.items():
            f.write(f"{key} = {value}\n")

    logging.info(f"建立默認配置文件: {config_path}")
    return config

def load_config(config_path="config.ini"):
    """加載配置文件"""
    config = {
        "outlook_folder": OUTLOOK_FOLDER_NAME,
        "output_excel": OUTPUT_EXCEL_PATH,
        "temp_folder": TEMP_FOLDER,
        "check_interval": CHECK_INTERVAL,
        "log_level": "INFO"
    }

    # 如果配置文件不存在，創建默認配置
    if not os.path.exists(config_path):
        return create_config_file(config_path)

    # 讀取配置文件
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            for line in f:
                # 忽略注釋和空行
                if line.strip() and not line.strip().startswith('#'):
                    key, value = line.strip().split('=', 1)
                    key = key.strip()
                    value = value.strip()

                    # 針對特定配置項進行類型轉換
                    if key == "check_interval":
                        config[key] = int(value)
                    else:
                        config[key] = value

        logging.info(f"已加載配置文件: {config_path}")
    except Exception as e:
        logging.error(f"加載配置文件時發生錯誤: {str(e)}，將使用默認配置")

    return config

def setup_logging(log_level="INFO"):
    """設置日誌系統"""
    level_dict = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL
    }

    level = level_dict.get(log_level.upper(), logging.INFO)

    # 確保日誌目錄存在
    log_dir = "logs"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    # 設置日誌文件名（包含日期）
    log_file = os.path.join(log_dir, f"outlook_monitor_{datetime.now().strftime('%Y%m%d')}.log")

    logging.basicConfig(
        filename=log_file,
        level=level,
        format='%(asctime)s - %(levelname)s - %(message)s',
        encoding='utf-8'
    )

    # 同時輸出到控制台
    console = logging.StreamHandler()
    console.setLevel(level)
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    console.setFormatter(formatter)
    logging.getLogger().addHandler(console)

    logging.info(f"日誌系統已設置，等級: {log_level}，日誌文件: {log_file}")

def main():
    """主程序"""
    # 加載配置
    config = load_config()

    # 設置日誌
    setup_logging(config.get("log_level", "INFO"))

    # 更新全局變數
    global OUTLOOK_FOLDER_NAME, OUTPUT_EXCEL_PATH, TEMP_FOLDER, CHECK_INTERVAL
    OUTLOOK_FOLDER_NAME = config.get("outlook_folder", OUTLOOK_FOLDER_NAME)
    OUTPUT_EXCEL_PATH = config.get("output_excel", OUTPUT_EXCEL_PATH)
    TEMP_FOLDER = config.get("temp_folder", TEMP_FOLDER)
    CHECK_INTERVAL = int(config.get("check_interval", CHECK_INTERVAL))

    logging.info("=" * 50)
    logging.info("啟動 Outlook 資料夾監控程序")
    logging.info(f"監控資料夾: {OUTLOOK_FOLDER_NAME}")
    logging.info(f"輸出檔案: {OUTPUT_EXCEL_PATH}")
    logging.info(f"臨時資料夾: {TEMP_FOLDER}")
    logging.info(f"檢查間隔: {CHECK_INTERVAL} 秒")
    logging.info("=" * 50)

    # 確保臨時資料夾存在
    if not os.path.exists(TEMP_FOLDER):
        os.makedirs(TEMP_FOLDER)
        logging.info(f"創建臨時資料夾: {TEMP_FOLDER}")

    # 連接到 Outlook
    namespace = connect_to_outlook()
    if namespace is None:
        logging.critical("無法連接 Outlook，程序結束")
        return

    # 獲取目標資料夾
    target_folder = get_target_folder(namespace)
    if target_folder is None:
        logging.critical(f"無法找到目標資料夾: {OUTLOOK_FOLDER_NAME}，程序結束")
        return

    logging.info(f"成功連接到資料夾: {OUTLOOK_FOLDER_NAME}")

    # 持續監控新郵件
    error_count = 0
    try:
        run_count = 0
        while True:
            run_count += 1
            logging.info(f"第 {run_count} 次檢查開始...")

            try:
                emails_processed = check_and_process_new_emails(target_folder)

                # 如果成功處理了郵件，重置錯誤計數
                if emails_processed > 0:
                    error_count = 0
            except Exception as run_e:
                error_count += 1
                logging.error(f"檢查郵件時發生錯誤 (嘗試 {error_count}): {str(run_e)}")

                # 如果連續錯誤超過5次，嘗試重新連接
                if error_count >= 5:
                    logging.warning("連續發生多次錯誤，嘗試重新連接 Outlook...")
                    try:
                        namespace = connect_to_outlook()
                        if namespace is not None:
                            target_folder = get_target_folder(namespace)
                            if target_folder is not None:
                                logging.info("成功重新連接 Outlook")
                                error_count = 0
                            else:
                                logging.critical("重新連接後無法找到目標資料夾")
                        else:
                            logging.critical("無法重新連接 Outlook")
                    except Exception as reconnect_e:
                        logging.critical(f"重新連接時發生錯誤: {str(reconnect_e)}")

            logging.info(f"第 {run_count} 次檢查完成，休眠 {CHECK_INTERVAL} 秒後再次檢查")
            time.sleep(CHECK_INTERVAL)

    except KeyboardInterrupt:
        logging.info("程序手動停止")
    except Exception as e:
        logging.critical(f"程序執行關鍵錯誤: {str(e)}")
    finally:
        logging.info("程序結束")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"程序啟動失敗: {str(e)}")
        logging.critical(f"程序啟動失敗: {str(e)}")

        # 等待用戶按鍵後退出
        input("按任意鍵結束程序...")