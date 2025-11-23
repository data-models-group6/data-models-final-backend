# import sys, os
# sys.path.append(os.path.dirname(os.path.dirname(__file__)))

# import requests, json
# from app.config.spotify_auth import get_valid_oauth_token, get_client_credentials_token

# print("Spotify 大量歌曲爬蟲開始...")

# # Token
# oauth_token = get_valid_oauth_token()              # for search
# client_token = get_client_credentials_token()      # for audio features

# headers_oauth = {"Authorization": f"Bearer {oauth_token}"}
# headers_client = {"Authorization": f"Bearer {client_token}"}

# keywords = ["pop", "kpop", "jpop"]

# def pretty(obj):
#     print(json.dumps(obj, indent=2, ensure_ascii=False))

# def fetch_audio_feature(track_id):
#     url = f"https://api.spotify.com/v1/audio-features/{track_id}"
#     r = requests.get(url, headers=headers_client)
#     if r.status_code != 200:
#         print(f"[Audio Feature 失敗] {track_id}, status: {r.status_code}")
#         pretty(r.json())
#         return None
#     return r.json()

# for kw in keywords:
#     print(f"\n搜尋關鍵字：{kw}")

#     search = requests.get(
#         "https://api.spotify.com/v1/search",
#         headers=headers_oauth,
#         params={"q": kw, "type": "track", "limit": 5},
#     )

#     if search.status_code != 200:
#         print("搜尋失敗:", search.status_code)
#         pretty(search.json())
#         continue

#     tracks = search.json().get("tracks", {}).get("items", [])
#     if not tracks:
#         print("查無 tracks")
#         continue

#     print("\nTracks 資訊（已移除 available_markets）：")

#     final_tracks = []
#     for t in tracks:
#         info = {
#             "track_id": t["id"],
#             "track_name": t["name"],
#             "artist_id": t["artists"][0]["id"],
#             "artist_name": t["artists"][0]["name"],
#             "popularity": t.get("popularity"),
#             "album": t.get("album", {}).get("name"),
#         }
#         print("-" * 50)
#         pretty(info)
#         final_tracks.append(info)

#     print("\n開始抓取 Audio Features")

#     for t in final_tracks:
#         print(f"\n=== {t['track_name']} - {t['artist_name']} ({t['track_id']}) ===")
#         feat = fetch_audio_feature(t["track_id"])
#         if feat:
#             pretty(feat)