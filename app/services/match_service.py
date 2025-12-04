from google.cloud import firestore
from app.services.firestore_client import get_db
from datetime import datetime
import pytz

def process_swipe_transaction(from_user_id: str, target_user_id: str, action: str):
    """
    處理滑動邏輯的進入點。
    設定好 Reference 後，啟動 Firestore Transaction。
    """
    db = get_db()
    
    # 1. 設定 Swipes 文件 ID：使用「主動方_被動方」確保唯一性
    # 這樣 A 滑 B 永遠只會有一筆紀錄，若重複滑動則會覆蓋或更新
    swipe_doc_id = f"{from_user_id}_{target_user_id}"
    swipe_ref = db.collection("swipes").document(swipe_doc_id)

    # 2. 設定反向查詢 ID：檢查「對方有沒有滑過我」
    reverse_swipe_doc_id = f"{target_user_id}_{from_user_id}"
    reverse_swipe_ref = db.collection("swipes").document(reverse_swipe_doc_id)

    # 3. 設定 Matches 文件 ID：使用「排序後的 ID 組合」
    # 確保 user1 和 user2 無論誰先滑誰，產生的 Match ID 都是同一個 (如 user1_user2)
    sorted_ids = sorted([from_user_id, target_user_id])
    match_doc_id = f"{sorted_ids[0]}_{sorted_ids[1]}"
    match_ref = db.collection("matches").document(match_doc_id)

    # 4. 啟動交易
    transaction = db.transaction()

    # 執行交易內的邏輯
    try:
        result = _execute_swipe_transaction(
            transaction, 
            swipe_ref, 
            reverse_swipe_ref, 
            match_ref, 
            from_user_id, 
            target_user_id, 
            action
        )
        return result
    except Exception as e:
        print(f"Transaction failed: {e}")
        raise e

@firestore.transactional
def _execute_swipe_transaction(transaction, swipe_ref, reverse_swipe_ref, match_ref, from_user_id, target_user_id, action):
    """
    在 Transaction 內部執行的邏輯。
    規則：必須先讀取 (get)，再寫入 (set/update)。
    """
    
    # --- STEP 1: 讀取 (Read) ---
    
    # 只有當我是 "LIKE" 時，才需要去檢查對方是否已經 LIKE 我
    reverse_doc_snapshot = None
    if action == "LIKE":
        reverse_doc_snapshot = reverse_swipe_ref.get(transaction=transaction)

    # --- STEP 2: 寫入 (Write) ---

    # 記錄我的滑動動作
    swipe_data = {
        "from_user_id": from_user_id,
        "to_user_id": target_user_id,
        "action": action,
        "created_at": datetime.now(pytz.utc)
    }
    # 使用 merge=True，如果未來有加欄位不會被洗掉
    transaction.set(swipe_ref, swipe_data, merge=True)

    # --- STEP 3: 判斷配對 (Match Logic) ---
    is_match = False
    
    # 配對成立條件：
    # 1. 我是 LIKE
    # 2. 對方資料存在 (reverse_doc_snapshot.exists)
    # 3. 對方也是 LIKE
    if action == "LIKE" and reverse_doc_snapshot and reverse_doc_snapshot.exists:
        reverse_data = reverse_doc_snapshot.to_dict()
        if reverse_data.get("action") == "LIKE":
            is_match = True
            
            # 寫入配對資料
            match_data = {
                "users": [from_user_id, target_user_id], # 方便之後用 array-contains 查詢
                "created_at": datetime.now(pytz.utc),
                "is_active": True,
                "last_message": "",
                "last_message_time": None
            }
            # 如果配對已存在，merge=True 會保留舊資料；若不存在則建立
            transaction.set(match_ref, match_data, merge=True)

    return {
        "status": "success",
        "is_match": is_match,
        "match_id": match_ref.id if is_match else None
    }