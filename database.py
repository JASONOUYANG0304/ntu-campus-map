from supabase import create_client

from dotenv import load_dotenv
import os

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

client = create_client(SUPABASE_URL, SUPABASE_KEY)

def get_all_locations():
    # 讀取所有地點
    response = client.table("locations").select("*").execute()
    return response.data

def add_location(name, lat, lng, category, intro, comment=""):
    # 新增一個地點
    data = {
        "name": name,
        "lat": lat,
        "lng": lng,
        "category": category,
        "intro": intro,
        "score": 0,
        "crowdedness": "[]",
        "comments": "[]"
    }
    response = client.table("locations").insert(data).execute()
    return response.data

def update_score(location_id, delta):
    # 推 delta=+1，噓 delta=-1
    location = client.table("locations").select("score").eq("id", location_id).execute()
    current_score = location.data[0]["score"]
    client.table("locations").update({"score": current_score + delta}).eq("id", location_id).execute()
