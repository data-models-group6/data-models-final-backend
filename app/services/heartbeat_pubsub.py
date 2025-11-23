# app/services/heartbeat_pubsub.py
import os
import json
from google.cloud import pubsub_v1

TOPIC_ID = "heartbeat-topic"

_publisher = None
_topic_path = None


def get_publisher():
    """
    惰性初始化 Pub/Sub Publisher，避免 import 時就連線。
    在 Cloud Functions 上會用 GCP_PROJECT / GOOGLE_CLOUD_PROJECT，
    本地端沒有就 fallback 固定 project_id。
    """
    global _publisher, _topic_path

    if _publisher is None:
        project_id = (
            os.getenv("GCP_PROJECT")
            or os.getenv("GOOGLE_CLOUD_PROJECT")
            or "spotify-match-project"
        )
        _publisher = pubsub_v1.PublisherClient()
        _topic_path = _publisher.topic_path(project_id, TOPIC_ID)

    return _publisher, _topic_path


def publish_heartbeat(data: dict):
    """
    將 heartbeat JSON 丟到 Pub/Sub topic。
    """
    message = json.dumps(data).encode("utf-8")

    publisher, topic_path = get_publisher()
    future = publisher.publish(topic_path, message)
    future.result()  # 確保送出成功（之後要壓效能可以拿掉）

    return True