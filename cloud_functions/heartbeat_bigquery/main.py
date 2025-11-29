import base64
import json
import os
from google.cloud import bigquery

client = bigquery.Client()
TABLE_ID = "spotify-match-project.user_event.listening_history"

def heartbeat_to_bigquery(event, context):
    print("BigQuery Function triggered")

    if "data" not in event:
        print("Missing data")
        return

    try:
        message_bytes = base64.urlsafe_b64decode(event["data"])        
        data = json.loads(message_bytes.decode("utf-8"))
    except Exception as e:
        print("Decode error:", e)
        return

    row = {
        "user_id": data.get("user_id"),
        "track_id": data.get("track_id"),
        "track_name": data.get("track_name"),
        "artist_id": data.get("artist_id"),
        "artist_name": data.get("artist_name"),
        "popularity": data.get("popularity"),
        "timestamp": data.get("timestamp"),     # TIMESTAMP column
        "lat": data.get("lat"),
        "lng": data.get("lng"),
        "genre": data.get("genre"),
        "device_type": data.get("device_type"),
    }

    errors = client.insert_rows_json(TABLE_ID, [row])

    if errors:
        print("BigQuery Insert Error:", errors)
    else:
        print("Inserted to BigQuery:", row)
