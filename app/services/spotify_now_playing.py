# app/services/spotify_now_playing.py
import requests

def fetch_now_playing(access_token: str):
    """
    使用 access_token 呼叫 Spotify 'Currently Playing' API，
    回傳 data["item"]，如果沒有在播歌則回傳 None。
    """
    headers = {"Authorization": f"Bearer {access_token}"}
    url = "https://api.spotify.com/v1/me/player/currently-playing"

    r = requests.get(url, headers=headers)

    # 204 表示目前沒有播放任何東西
    if r.status_code == 204:
        return None

    data = r.json()
    item = data.get("item")
    return item