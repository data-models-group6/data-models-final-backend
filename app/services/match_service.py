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

def get_users_who_liked_me(current_user_id: str):
    """
    取得「右滑我」但「我還沒滑過他」的使用者列表。
    """
    db = get_db()

    # 1. 查詢「誰喜歡我」 (Incoming Likes)
    # 條件：to_user_id == 我, action == LIKE
    incoming_query = db.collection("swipes")\
        .where("to_user_id", "==", current_user_id)\
        .where("action", "==", "LIKE")
    
    incoming_docs = incoming_query.stream()
    
    # 建立一個暫存字典: { user_id: liked_at_time }
    incoming_likes_map = {}
    for doc in incoming_docs:
        data = doc.to_dict()
        sender_id = data.get("from_user_id")
        created_at = data.get("created_at")
        if sender_id:
            incoming_likes_map[sender_id] = created_at

    # 如果沒人喜歡我，直接回傳空陣列 (節省資料庫讀取)
    if not incoming_likes_map:
        return []

    # 2. 查詢「我滑過誰」 (My Actions)
    # 條件：from_user_id == 我 (不管是 LIKE 還是 PASS 都要過濾掉)
    # 因為如果我們已經 Match (我 LIKE 他)，不需顯示。
    # 如果我已經 PASS 他，也不需顯示。
    my_actions_query = db.collection("swipes")\
        .where("from_user_id", "==", current_user_id)
    
    my_actions_docs = my_actions_query.stream()
    
    # 收集所有我處理過的 user_id
    already_swiped_ids = set()
    for doc in my_actions_docs:
        data = doc.to_dict()
        target_id = data.get("to_user_id")
        if target_id:
            already_swiped_ids.add(target_id)

    # 3. 過濾邏輯 (Set Difference)
    # 想要的名單 = (喜歡我的人) - (我已經滑過的人)
    pending_users = []
    
    # 對每一個喜歡我的人，檢查我是否已經滑過他
    for user_id, liked_at in incoming_likes_map.items():
        if user_id not in already_swiped_ids:
            pending_users.append({
                "user_id": user_id,
                "liked_at": liked_at
            })

    # 4. 排序 (通常顯示最新的在前面)
    # 注意：如果 liked_at 是 None 或格式不對，需做例外處理，這裡假設資料完整
    pending_users.sort(key=lambda x: x["liked_at"], reverse=True)

    return pending_users