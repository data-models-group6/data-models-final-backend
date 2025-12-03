# app/services/bigquery_client.py
import os
import base64
import json
from google.cloud import bigquery
from google.oauth2 import service_account
from app.config.settings import BQ_PROJECT, BQ_DATASET

_cached_client = None

def get_bq_client():
    global _cached_client
    if _cached_client is not None:
        return _cached_client

    raw = os.getenv("GOOGLE_CLOUD_CREDENTIALS")
    if not raw:
        raise Exception("GOOGLE_CLOUD_CREDENTIALS missing")

    try:
        creds_json = json.loads(base64.b64decode(raw))
        creds = service_account.Credentials.from_service_account_info(creds_json)
        _cached_client = bigquery.Client(credentials=creds, project=creds.project_id)
        return _cached_client
    except Exception as e:
        raise Exception(f"Failed to init BigQuery client: {e}")


def insert_rows_json(table_name: str, rows: list):
    if not rows:
        return

    client = get_bq_client()
    table_id = f"{BQ_PROJECT}.{BQ_DATASET}.{table_name}"

    errors = client.insert_rows_json(table_id, rows)
    if errors:
        raise Exception(f"BQ insert_rows_json error: {errors}")