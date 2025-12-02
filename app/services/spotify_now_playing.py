# app/services/spotify_now_playing.py
import requests

def fetch_now_playing(access_token: str):
    """
    呼叫 Spotify Currently Playing API，
    確保永遠不會因為 r.json() 而爆錯。
    回傳：
    - dict item：有在播放
    - None：沒有播放
    - "TOKEN_EXPIRED"：需要 refresh token
    """
    headers = {"Authorization": f"Bearer {access_token}"}
    url = "https://api.spotify.com/v1/me/player/currently-playing"

    r = requests.get(url, headers=headers)

    # Debug（必要）
    print("Spotify Status:", r.status_code)
    print("Spotify Raw:", r.text)

    # 204 -> No Content
    if r.status_code == 204:
        return None

    # 401 -> Token 過期
    if r.status_code == 401:
        return "TOKEN_EXPIRED"

    # 沒內容 → 避免 json decode 錯誤
    if not r.text:
        return None

    # Spotify 可能回 HTML（Render proxy / rate limit / blocking）
    if not r.headers.get("content-type", "").startswith("application/json"):
        return None

    # 其它情況才 parse JSON
    data = r.json()
    return data.get("item")