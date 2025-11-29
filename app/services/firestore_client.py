# app/services/firestore_client.py
import os
import base64
import json
from google.cloud import firestore
from google.oauth2 import service_account

_cached_client = None

def get_db():
    """
    Lazy-load Firestore client using service account credentials
    stored in the environment variable GOOGLE_CLOUD_CREDENTIALS.
    This will work on Render and any non-GCP environment.
    """

    global _cached_client

    # Already initialized → return cached client
    if _cached_client is not None:
        return _cached_client

    # 1. Load base64 string from environment
    raw = os.getenv("GOOGLE_CLOUD_CREDENTIALS")
    if not raw:
        raise Exception("GOOGLE_CLOUD_CREDENTIALS is missing in environment variables")

    # 2. Decode base64 → dict
    try:
        creds_json = json.loads(base64.b64decode(raw))
    except Exception as e:
        raise Exception(f"Failed to decode GOOGLE_CLOUD_CREDENTIALS: {e}")

    # 3. Build service account credentials
    try:
        creds = service_account.Credentials.from_service_account_info(creds_json)
    except Exception as e:
        raise Exception(f"Failed to create service account credentials: {e}")

    # 4. Create Firestore client
    try:
        _cached_client = firestore.Client(credentials=creds, project=creds.project_id)
    except Exception as e:
        raise Exception(f"Failed to create Firestore client: {e}")

    return _cached_client