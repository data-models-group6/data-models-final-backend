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
    取得「右滑我」但「我還沒滑過他」的使用者列表，並包含詳細資料。
    """
    db = get_db()

    # 1. 查詢「誰喜歡我」
    # 使用 keyword arguments 以減少警告
    incoming_query = db.collection("swipes")\
        .where(field_path="to_user_id", op_string="==", value=current_user_id)\
        .where(field_path="action", op_string="==", value="LIKE")
    
    incoming_docs = incoming_query.stream()
    
    incoming_likes_map = {}
    for doc in incoming_docs:
        data = doc.to_dict()
        sender_id = data.get("from_user_id")
        created_at = data.get("created_at")
        if sender_id:
            incoming_likes_map[sender_id] = created_at

    if not incoming_likes_map:
        return []

    # 2. 查詢「我滑過誰」 (用來過濾)
    my_actions_query = db.collection("swipes")\
        .where(field_path="from_user_id", op_string="==", value=current_user_id)
    
    my_actions_docs = my_actions_query.stream()
    
    already_swiped_ids = set()
    for doc in my_actions_docs:
        data = doc.to_dict()
        target_id = data.get("to_user_id")
        if target_id:
            already_swiped_ids.add(target_id)

    # 3. 整合與抓取 User 資料
    pending_users = []
    
    for user_id, liked_at in incoming_likes_map.items():
        if user_id not in already_swiped_ids:
            
            user_ref = db.collection("users").document(user_id)
            user_doc = user_ref.get()
            
            # 預設值
            display_name = "Unknown User"
            avatarUrl = None
            
            if user_doc.exists:
                user_data = user_doc.to_dict()
                # 嘗試取得 display_name，若沒有則找 name，再沒有則預設值
                display_name = user_data.get("display_name", user_data.get("name", "Unknown User"))
                # 嘗試取得 avatarUrl，若沒有則找 photo_url
                avatarUrl = user_data.get("avatarUrl", user_data.get("photo_url", None))
            
            pending_users.append({
                "user_id": user_id,
                "liked_at": liked_at,
                "display_name": display_name,  # 修正：Key 改為 display_name
                "avatarUrl": avatarUrl         # 修正：Key 改為 avatarUrl
            })

    # 4. 排序
    pending_users.sort(key=lambda x: x["liked_at"], reverse=True)

    return pending_users

def get_users_i_liked(current_user_id: str):
    """
    取得「我右滑過」但「尚未配對成功」的使用者列表。
    """
    db = get_db()

    # 1. 查詢我喜歡的人 (My Likes)
    my_likes_query = db.collection("swipes")\
        .where(field_path="from_user_id", op_string="==", value=current_user_id)\
        .where(field_path="action", op_string="==", value="LIKE")
    
    my_likes_docs = my_likes_query.stream()
    
    # 建立字典: { target_user_id: swiped_at_time }
    my_likes_map = {}
    for doc in my_likes_docs:
        data = doc.to_dict()
        target_id = data.get("to_user_id")
        created_at = data.get("created_at")
        if target_id:
            my_likes_map[target_id] = created_at

    if not my_likes_map:
        return []

    # 2. 查詢已經配對的人 (Matched Users)
    # 我們只要查詢 matches 集合中包含 current_user_id 的文件
    matches_query = db.collection("matches")\
        .where(field_path="users", op_string="array_contains", value=current_user_id)
    
    matches_docs = matches_query.stream()
    
    matched_user_ids = set()
    for doc in matches_docs:
        data = doc.to_dict()
        users_list = data.get("users", [])
        # 找出配對中「另一個」人的 ID
        for uid in users_list:
            if uid != current_user_id:
                matched_user_ids.add(uid)

    # 3. 過濾並抓取 User 詳細資料
    sent_users = []
    
    for user_id, liked_at in my_likes_map.items():
        # 如果這個人不在配對名單中 -> 代表是單方面喜歡 (或對方按了 PASS)
        if user_id not in matched_user_ids:
            
            user_ref = db.collection("users").document(user_id)
            user_doc = user_ref.get()
            
            display_name = "Unknown User"
            avatarUrl = None
            
            if user_doc.exists:
                user_data = user_doc.to_dict()
                display_name = user_data.get("display_name", user_data.get("name", "Unknown User"))
                avatarUrl = user_data.get("avatarUrl", user_data.get("photo_url", None))
            
            sent_users.append({
                "user_id": user_id,
                "liked_at": liked_at,
                "display_name": display_name,
                "avatarUrl": avatarUrl
            })

    # 4. 排序 (最新的在前面)
    sent_users.sort(key=lambda x: x["liked_at"], reverse=True)

    return sent_users