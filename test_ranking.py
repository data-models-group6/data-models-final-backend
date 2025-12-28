import requests
import json

# 伺服器網址
url = "http://127.0.0.1:3000/api/ranking/regional"

# 要傳送的經緯度資料 (JSON body)
payload = {
    "lat": 25.033,
    "lng": 121.565
}

# 發送 POST 請求
try:
    response = requests.post(url, json=payload)
    response.raise_for_status()  # 檢查是否有 HTTP 錯誤 (例如 404, 500)

    # 印出結果
    print("--- API 回傳結果 ---")
    print(json.dumps(response.json(), indent=4, ensure_ascii=False))

except requests.exceptions.HTTPError as err:
    print(f"HTTP 錯誤發生: {err}")
    print("Response Body:", response.text)
except requests.exceptions.RequestException as err:
    print(f"連線錯誤發生 (請確認 Uvicorn 服務是否啟動): {err}")