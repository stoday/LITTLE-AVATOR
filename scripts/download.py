from urllib.parse import quote
import requests
from dotenv import load_dotenv
import os

load_dotenv()

site_host = "https://iiiorgtw-my.sharepoint.com"
# 伺服器相對路徑 (Server Relative URL)
server_relative_path = "/personal/yutsai_iii_org_tw/Documents/Microsoft Teams 聊天檔案/trtc_update_20260106 1.zip"

# URL 編碼路徑以避免空格與中文字元問題
encoded_path = quote(server_relative_path)
api_url = f"{site_host}/personal/yutsai_iii_org_tw/_api/web/GetFileByServerRelativeUrl('{encoded_path}')/$value"

# BEARER_TOKEN = "eyJ0eXAiOiJKV1QiLC..."  # 替換為有效的 Token
BEARER_TOKEN = os.environ.get("BEARER_TOKEN")

headers = {
    "Authorization": f"Bearer {BEARER_TOKEN}",
    "Accept": "application/json;odata=verbose",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    ),
}

response = requests.get(api_url, headers=headers, stream=True)

if response.status_code == 200:
    with open("trtc_update_20260106 1.zip", "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)
    print("下載完成！")
else:
    print(f"下載失敗 ({response.status_code})：{response.text}")