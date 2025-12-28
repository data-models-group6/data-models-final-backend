from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from google.cloud import bigquery
from app.services.match_utils import get_ranking_region  

PROJECT_ID = "spotify-match-project"
router = APIRouter()
bq_client = bigquery.Client(project=PROJECT_ID)

class LocationRequest(BaseModel):
    lat: float
    lng: float

@router.post("/ranking/regional")
def get_regional_ranking(location: LocationRequest):
    try:
        # 1. 取得用戶經緯度
        user_lat = location.lat
        user_lng = location.lng

        # 2. 計算 Geohash (精度 5)
        region_geohash = get_ranking_region(user_lat, user_lng)
        print(f"查詢地區 Geohash: {region_geohash}")

        # 3. 準備 SQL 查詢 (改為查詢已分析好的 weekly_top_songs)
        query = """
            SELECT
                Artist AS artist,
                Track_Name AS track_name,
                total_plays,
                current_rank AS rank
            FROM
                `spotify-match-project.analysis.weekly_top_songs`
            WHERE
                region_geohash = @region_geohash
            ORDER BY
                current_rank ASC
            LIMIT 5;
        """

        # 4. 設定查詢參數
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("region_geohash", "STRING", region_geohash)
            ]
        )

        # 5. 執行查詢並獲取結果
        query_job = bq_client.query(query, job_config=job_config)
        results = query_job.result()  

        # 6. 整理結果
        ranking_data = []
        for row in results:
            ranking_data.append({
                "rank": row.rank,
                "artist": row.artist,
                "track_name": row.track_name,
                "total_plays": row.total_plays
            })

        # 7. 回傳結果
        if not ranking_data:
            return {
                "status": "success", 
                "region_code": region_geohash,
                "message": "此地區目前沒有足夠的收聽數據",
                "data": []
            }

        return {
            "status": "success",
            "region_code": region_geohash,
            "data": ranking_data
        }

    except Exception as e:
        print(f"BigQuery Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))