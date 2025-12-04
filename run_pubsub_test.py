# run_pubsub_test.py
import sys
import os

# 確保可以正確地匯入 heartbeat_pubsub
# 假設 heartbeat_pubsub.py 位於 app/services/
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), 'app/services')))

from app.services.heartbeat_pubsub import publish_heartbeat

# 模擬前端傳入的歌曲資料
TEST_DATA = {
    "user_id": "vscode_local_test_009",
    "track_id": "T101",
    "track_name": "Test from VSCode Backend",
    "artist_id": "A101",
    "popularity": 91,
    "timestamp": 1764323199,
    "lat": 35.6895,  # 東京
    "lng": 139.6917,
    "genre": "J-Pop",
    "device_type": "Laptop"
}

print("--- Start Pub/Sub Test from VS Code ---")
success = publish_heartbeat(TEST_DATA)

if success:
    print(f"Message published successfully! User: {TEST_DATA['user_id']}")
    print("請回到 Cloud Shell 檢查 Cloud Functions 日誌。")
else:
    print("Message publish FAILED. Check local terminal output for errors.")