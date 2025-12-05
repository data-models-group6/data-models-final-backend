import os
import json
import base64
import tempfile

def setup_google_credentials():
    encoded = os.getenv("GOOGLE_CLOUD_CREDENTIALS")

    if not encoded:
        print("⚠ No GOOGLE_CLOUD_CREDENTIALS found, Pub/Sub may fail.")
        return

    try:
        decoded = json.loads(base64.b64decode(encoded))

        # 寫成暫存 credentials.json
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".json")
        tmp.write(json.dumps(decoded).encode())
        tmp.close()

        # 給 GCP SDK 使用
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = tmp.name
        print("✔ GOOGLE_APPLICATION_CREDENTIALS set.")
    except Exception as e:
        print("❌ Failed to load GCP credentials:", e)