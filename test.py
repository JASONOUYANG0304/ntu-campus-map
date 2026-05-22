import streamlit as st
import folium
import smtplib
import random
import os
import json
from datetime import datetime, timedelta, timezone
from streamlit_folium import st_folium
from shapely.geometry import Point, Polygon
from supabase import create_client
from dotenv import load_dotenv
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# ==========================================
# 環境變數載入
# ==========================================
load_dotenv()

try:
    SUPABASE_URL = st.secrets["SUPABASE_URL"]
    SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
    GMAIL_ADDRESS = st.secrets["GMAIL_ADDRESS"]
    GMAIL_APP_PASSWORD = st.secrets["GMAIL_APP_PASSWORD"]
except Exception:
    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_KEY = os.getenv("SUPABASE_KEY")
    GMAIL_ADDRESS = os.getenv("GMAIL_ADDRESS")
    GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")

# ==========================================
# 資料庫操作
# ==========================================
client = create_client(SUPABASE_URL, SUPABASE_KEY)
TZ_TW = timezone(timedelta(hours=8))

def get_all_locations():
    try:
        response = client.table("locations").select("*").execute()
        return response.data
    except Exception:
        st.error("⚠️ 資料庫連線失敗，請稍等 10 秒後重新整理！")
        return []

def add_location(name, lat, lng, category, intro, floor="無"):
    data = {
        "name": name,
        "lat": lat,
        "lng": lng,
        "category": category,
        "intro": intro,
        "floor": floor,
        "score": 0,
        "crowdedness": "[]",
        "comments": "[]"
    }
    response = client.table("locations").insert(data).execute()
    return response.data

# 新增：用來更新地點座標的函式
def update_location_coords(name, category, lat, lng):
    # 利用 name 和 category 作為條件，一次更新該地點所有樓層的座標
    client.table("locations").update(
        {"lat": lat, "lng": lng}
    ).eq("name", name).eq("category", category).execute()

def update_crowdedness(location_id, value):
    location = client.table("locations").select("crowdedness").eq("id", location_id).execute()
    raw = json.loads(location.data[0]["crowdedness"] or "[]")
    current = raw if isinstance(raw, list) else [raw]

    one_hour_ago = datetime.now(TZ_TW) - timedelta(hours=1)
    converted = []
    for item in current:
        if isinstance(item, dict):
            if datetime.fromisoformat(item["time"]) > one_hour_ago:
                converted.append(item)

    converted.append({
        "value": value,
        "time": datetime.now(TZ_TW).isoformat()
    })

    client.table("locations").update(
        {"crowdedness": json.dumps(converted)}
    ).eq("id", location_id).execute()

def get_recent_crowd(crowdedness_json):
    try:
        data = json.loads(crowdedness_json)
        if not isinstance(data, list) or len(data) == 0:
            return "待回報"
        one_hour_ago = datetime.now(TZ_TW) - timedelta(hours=1)
        recent = [
            item["value"] for item in data
            if isinstance(item, dict) and datetime.fromisoformat(item["time"]) > one_hour_ago
        ]
        return round(sum(recent) / len(recent), 1) if recent else "待回報"
    except:
        return "待回報"

def add_comment(location_id, comment_dict):
    location = client.table("locations").select("comments").eq("id", location_id).execute()
    current_comments = json.loads(location.data[0]["comments"])
    current_comments.append(comment_dict)
    client.table("locations").update(
        {"comments": json.dumps(current_comments, ensure_ascii=False)}
    ).eq("id", location_id).execute()

def vote_comment(location_id, comment_index, vote_type):
    location = client.table("locations").select("comments").eq("id", location_id).execute()
    current_comments = json.loads(location.data[0]["comments"])
    
    try:
        target = current_comments[comment_index]
        if not isinstance(target, dict):
            target = {"text": target, "time": "未知", "upvotes": 0, "downvotes": 0}
            
        if vote_type == "upvote":
            target["upvotes"] = target.get("upvotes", 0) + 1
        elif vote_type == "downvote":
            target["downvotes"] = target.get("downvotes", 0) + 1
            
        current_comments[comment_index] = target
        
        client.table("locations").update(
            {"comments": json.dumps(current_comments, ensure_ascii=False)}
        ).eq("id", location_id).execute()
    except Exception:
        pass

def upload_image(location_id, image_bytes, file_name):
    timestamp = int(datetime.now(TZ_TW).timestamp())
    ext = os.path.splitext(file_name)[1] 
    safe_file_path = f"{location_id}/{timestamp}{ext}"
    
    try:
        client.storage.from_("location-images").upload(
            safe_file_path,
            image_bytes,
            {"content-type": f"image/{ext.replace('.', '')}", "x-upsert": "true"} 
        )
    except Exception as e:
        st.error(f"❌ Supabase 拒絕上傳，錯誤原因：{str(e)}")
        st.stop()
    
    url = client.storage.from_("location-images").get_public_url(safe_file_path)
    client.table("locations").update(
        {"image_url": url}
    ).eq("id", location_id).execute()
    
    return url

# ==========================================
# 驗證碼寄送
# ==========================================
def send_verification_code(target_email):
    code = str(random.randint(100000, 999999))
    st.session_state["verify_code"] = code
    st.session_state["verify_email"] = target_email
    st.session_state["verify_time"] = datetime.now(TZ_TW).isoformat()

    msg = MIMEMultipart()
    msg["From"] = f"臺大校園地圖 <{GMAIL_ADDRESS}>"
    msg["To"] = target_email
    msg["Subject"] = "臺大地圖 驗證碼"
    msg.attach(MIMEText(f"你的驗證碼是：{code}\n\n10分鐘內有效。", "plain"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
        server.sendmail(GMAIL_ADDRESS, target_email, msg.as_string())

# ==========================================
# 1. 初始化設定
# ==========================================
ntu_polygon_coords = [
    (121.537209, 25.011598), (121.533004, 25.016414), (121.533402, 25.016789),
    (121.534567, 25.022169), (121.536965, 25.022190), (121.539104, 25.021150),
    (121.543849, 25.020836), (121.546168, 25.019094)
]
ntu_campus_poly = Polygon(ntu_polygon_coords)
folium_bounds = [(lat, lon) for lon, lat in ntu_polygon_coords]

# 登入狀態與其他紀錄初始化
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'user_role' not in st.session_state:
    st.session_state.user_role = None
if 'current_category' not in st.session_state:
    st.session_state.current_category = "充電"
if 'waiting_verify' not in st.session_state:
    st.session_state.waiting_verify = False
if 'pending_lat' not in st.session_state:
    st.session_state.pending_lat = None
if 'pending_lon' not in st.session_state:
    st.session_state.pending_lon = None
if 'pending_name' not in st.session_state:
    st.session_state.pending_name = None
if 'pending_floor' not in st.session_state:
    st.session_state.pending_floor = "無"
if 'pending_desc' not in st.session_state:
    st.session_state.pending_desc = ""
if 'crowd_voted' not in st.session_state:
    st.session_state.crowd_voted = {}
if 'comment_voted' not in st.session_state:
    st.session_state.comment_voted = set()

# 從資料庫讀取地點
if 'locations' not in st.session_state:
    raw = get_all_locations()
    st.session_state.locations = {
        "充電": {}, "情緒釋放": {}, "戶外放鬆": {}, "排練": {}, "面試": {}
    }
    for loc in raw:
        cat = loc.get("category", "充電")
        name = loc["name"]
        if cat in st.session_state.locations:
            floor_entry = {
                "id": loc["id"],
                "floor": loc.get("floor") or "無",
                "lat": loc["lat"],
                "lon": loc["lng"],
                "crowd": get_recent_crowd(loc.get("crowdedness", "[]")),
                "comments": json.loads(loc.get("comments", "[]")),
                "desc": loc.get("intro", ""),
                "image": loc.get("image_url")
            }
            if name not in st.session_state.locations[cat]:
                st.session_state.locations[cat][name] = []
            st.session_state.locations[cat][name].append(floor_entry)

# ==========================================
# 2. 登入頁面
# ==========================================
def login_page():
    st.title("🎓 臺大校園地圖指南")
    st.write("尋找校園內的專屬角落：充電、放鬆、排練與面試空間。")

    st.markdown("### 登入")
    email = st.text_input("輸入臺大信箱 (ntu.edu.tw)")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("寄送驗證碼", use_container_width=True):
            if not email.endswith("@ntu.edu.tw"):
                st.error("請輸入有效的臺大信箱！")
            else:
                last_send = st.session_state.get("last_send_time")
                if last_send and datetime.now(TZ_TW) - datetime.fromisoformat(last_send) < timedelta(seconds=60):
                    remaining = 60 - int((datetime.now(TZ_TW) - datetime.fromisoformat(last_send)).total_seconds())
                    st.warning(f"請等待 {remaining} 秒後再重新寄送")
                else:
                    send_verification_code(email)
                    st.session_state["last_send_time"] = datetime.now(TZ_TW).isoformat()
                    st.session_state.waiting_verify = True
                    st.success("驗證碼已寄出，請檢查信箱")

        if st.session_state.waiting_verify:
            code_input = st.text_input("輸入驗證碼")
            if st.button("驗證"):
                verify_time = st.session_state.get("verify_time")
                if verify_time and datetime.now(TZ_TW) - datetime.fromisoformat(verify_time) > timedelta(minutes=10):
                    st.error("驗證碼已過期，請重新寄送")
                    st.session_state.waiting_verify = False
                elif code_input == st.session_state.get("verify_code"):
                    st.session_state.logged_in = True
                    st.session_state.user_role = "student"
                    st.session_state.waiting_verify = False
                    st.rerun()
                else:
                    st.error("驗證碼錯誤，請再試一次")

    with col2:
        if st.button("訪客模式進入", use_container_width=True):
            st.session_state.logged_in = True
            st.session_state.user_role = "guest"
            st.info("以訪客模式進入（無法新增或修改地點）")
            st.rerun()

# ==========================================
# 3. 主應用程式
# ==========================================
def main_app():
    col_title, col_refresh, col_logout = st.columns([3, 1, 1])
    col_title.title("🗺️ 臺大校園地圖指南")
    
    if col_refresh.button("🔄 更新地圖資料", use_container_width=True):
        if "locations" in st.session_state:
            del st.session_state["locations"]
        st.rerun()

    if col_logout.button("登出", use_container_width=True):
        st.session_state.logged_in = False
        st.session_state.user_role = None
        if "locations" in st.session_state:
            del st.session_state["locations"]
        st.rerun()

    if st.session_state.user_role == "student":
        st.success("✅ 學生身份已驗證：具備完整功能與新增/修改地點權限。")
    else:
        st.warning("👁️ 訪客模式：可瀏覽與評論，但無法新增或修改地點。")

    categories = ["充電", "情緒釋放", "戶外放鬆", "排練", "面試"]
    cols = st.columns(5)
    for idx, cat in enumerate(categories):
        if cols[idx].button(cat, use_container_width=True):
            st.session_state.current_category = cat

    st.markdown(f"### 目前選擇類別：**{st.session_state.current_category}**")
    st.divider()

    col_map, col_details = st.columns([3, 2])

    with col_map:
        st.write("點擊地圖任意處可獲取座標 (新增/修改地點時使用)")
        m = folium.Map(location=[25.017, 121.539], zoom_start=16)

        folium.Polygon(
            locations=folium_bounds,
            color="blue",
            fill=True,
            fill_opacity=0.1,
            tooltip="台大校總區範圍"
        ).add_to(m)

        current_data = st.session_state.locations[st.session_state.current_category]
        for loc_name, floors in current_data.items():
            first_floor = floors[0]
            
            valid_crowds = [f['crowd'] for f in floors if isinstance(f['crowd'], (int, float))]
            
            if valid_crowds:
                avg_crowd = sum(valid_crowds) / len(valid_crowds)
                color = "green" if avg_crowd <= 2 else "orange" if avg_crowd <= 4 else "red"
                crowd_text = f"{'🟢' if avg_crowd <= 2 else '🟡' if avg_crowd <= 4 else '🔴'} 平均擁擠度: {round(avg_crowd, 1)}/5"
            else:
                color = "gray"
                crowd_text = "⚪ 待回報/5"
                
            floor_info = "" if (len(floors) == 1 and floors[0]['floor'] == "無") else f'<span style="color: gray; font-size: 12px;">共 {len(floors)} 個樓層</span><br>'
            
            folium.Marker(
                [first_floor['lat'], first_floor['lon']],
                popup=folium.Popup(
                    f"""
                    <div style="font-family: sans-serif; min-width: 130px; padding: 4px;">
                        <b style="font-size: 14px;">{loc_name}</b><br>
                        {floor_info}
                        <hr style="margin: 4px 0;">
                        {crowd_text}
                    </div>
                    """,
                    max_width=200
                ),
                tooltip=loc_name,
                icon=folium.Icon(color=color, icon="info-sign")
            ).add_to(m)

        map_data = st_folium(m, height=450, use_container_width=True)

        clicked_lat, clicked_lon = None, None
        if map_data.get("last_clicked"):
            clicked_lat = map_data["last_clicked"]["lat"]
            clicked_lon = map_data["last_clicked"]["lng"]
            st.session_state.pending_lat = clicked_lat
            st.session_state.pending_lon = clicked_lon
            st.info(f"📍 獲取地圖座標: 緯度 {clicked_lat:.5f}, 經度 {clicked_lon:.5f}")

    with col_details:
        st.markdown("#### 🏢 地點互動")
        loc_list = list(current_data.keys())

        if loc_list:
            selected_loc_name = st.selectbox("選擇地點：", loc_list)
            floors_data = current_data[selected_loc_name]

            if len(floors_data) == 1 and floors_data[0]['floor'] == "無":
                selected_floor_idx = 0
            else:
                floor_names = [f"樓層：{f['floor']}" for f in floors_data]
                selected_floor_idx = st.selectbox(
                    "選擇樓層：",
                    range(len(floor_names)),
                    format_func=lambda x: floor_names[x]
                )
            selected_loc = floors_data[selected_floor_idx]

            # 即時從資料庫拉取最新擁擠度
            try:
                fresh_db = client.table("locations").select("crowdedness").eq("id", selected_loc['id']).execute()
                if fresh_db.data:
                    selected_loc['crowd'] = get_recent_crowd(fresh_db.data[0]["crowdedness"])
            except Exception:
                pass

            if selected_loc.get('image'):
                st.image(selected_loc['image'], use_container_width=True)

            st.write(f"**介紹：** {selected_loc.get('desc', '無')}")
            
            display_crowd = f"{selected_loc['crowd']} / 5" if selected_loc['crowd'] != "待回報" else "待回報 / 5"
            st.write(f"**平均擁擠程度（1為最不擁擠)：** {display_crowd}")

            st.write("回報擁擠狀況：")
            if st.session_state.user_role == "student":
                crowd_cols = st.columns(5)
                loc_key = f"{selected_loc['id']}"
                last_voted = st.session_state.crowd_voted.get(loc_key)
                cooldown_minutes = 3

                if last_voted and datetime.now(TZ_TW) - last_voted < timedelta(minutes=cooldown_minutes):
                    remaining = cooldown_minutes * 60 - int((datetime.now(TZ_TW) - last_voted).total_seconds())
                    st.caption(f"⏳ 你已回報過，請等待 {remaining} 秒後再回報")
                else:
                    for i in range(1, 6):
                        if crowd_cols[i - 1].button(str(i), key=f"crowd_{selected_loc_name}_{selected_loc['floor']}_{i}"):
                            update_crowdedness(selected_loc['id'], i)
                            updated = client.table("locations").select("crowdedness").eq("id", selected_loc['id']).execute()
                            selected_loc['crowd'] = get_recent_crowd(updated.data[0]["crowdedness"])
                            st.session_state.crowd_voted[loc_key] = datetime.now(TZ_TW)
                            
                            new_display = f"{selected_loc['crowd']} / 5" if selected_loc['crowd'] != "待回報" else "待回報 / 5"
                            st.success(f"已更新！目前平均擁擠度：{new_display}")
                            st.rerun()
            else:
                st.caption("請登入台大信箱才能回報擁擠度")

            with st.expander("📷 上傳或更新此地點的圖片"):
                update_img_file = st.file_uploader(
                    "選擇圖片", type=["jpg", "png", "jpeg"],
                    key=f"upload_img_{selected_loc_name}_{selected_loc['floor']}"
                )
                if st.button("送出圖片", key=f"btn_update_img_{selected_loc_name}_{selected_loc['floor']}", use_container_width=True):
                    if update_img_file:
                        image_bytes = update_img_file.read()
                        url = upload_image(selected_loc['id'], image_bytes, update_img_file.name)
                        selected_loc['image'] = url
                        st.success("圖片更新成功！")
                        st.rerun()
                    else:
                        st.warning("請先選擇要上傳的圖片檔案！")

            st.markdown("##### 💬 留言評論")
            for i, c in enumerate(selected_loc['comments']):
                if not isinstance(c, dict):
                    c = {"text": c, "time": "未知", "upvotes": 0, "downvotes": 0}
                    selected_loc['comments'][i] = c
                
                upvotes = c.get("upvotes", 0)
                downvotes = c.get("downvotes", 0)
                
                col_text, col_up, col_down = st.columns([5, 1.5, 1.5])
                with col_text:
                    st.write(f"- {c.get('text', '')}　*{c.get('time', '')}*")
                with col_up:
                    if st.button(f"👍 推 {upvotes}", key=f"up_{selected_loc['id']}_{i}"):
                        vote_key = f"{selected_loc['id']}_comment_{i}"
                        if vote_key not in st.session_state.comment_voted:
                            vote_comment(selected_loc['id'], i, "upvote")
                            c["upvotes"] = upvotes + 1
                            st.session_state.comment_voted.add(vote_key)
                            st.rerun()
                        else:
                            st.toast("⚠️ 你已經對這則評論投過票囉！")
                with col_down:
                    if st.button(f"👎 噓 {downvotes}", key=f"down_{selected_loc['id']}_{i}"):
                        vote_key = f"{selected_loc['id']}_comment_{i}"
                        if vote_key not in st.session_state.comment_voted:
                            vote_comment(selected_loc['id'], i, "downvote")
                            c["downvotes"] = downvotes + 1
                            st.session_state.comment_voted.add(vote_key)
                            st.rerun()
                        else:
                            st.toast("⚠️ 你已經對這則評論投過票囉！")

            new_comment = st.text_input("新增評論...", key=f"comment_{selected_loc_name}_{selected_loc['floor']}", max_chars=100)
            if st.button("送出評論", use_container_width=True):
                if new_comment.strip():
                    new_c = {
                        "text": new_comment,
                        "time": datetime.now(TZ_TW).strftime("%Y/%m/%d %H:%M"),
                        "upvotes": 0,
                        "downvotes": 0
                    }
                    selected_loc['comments'].append(new_c)
                    add_comment(selected_loc['id'], new_c)
                    st.rerun()

        st.divider()

        # 新增/修改地點功能 (僅限學生)
        if st.session_state.user_role == "student":
            
            # --- 新增地點面板 ---
            with st.expander("➕ 新增地點"):
                add_mode = st.radio("新增方式：", ["新地點", "現有地點的新樓層"], key="add_mode")

                if add_mode == "新地點":
                    new_name = st.text_input("地點名稱")
                    new_floor = st.selectbox("選擇樓層", ["無", "B2", "B1", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10"])
                    new_desc = st.text_area("介紹", max_chars=200)

                    st.session_state.pending_name = new_name
                    st.session_state.pending_floor = new_floor
                    st.session_state.pending_desc = new_desc

                    if st.session_state.pending_lat:
                        st.info(f"📍 目前座標：{st.session_state.pending_lat:.5f}, {st.session_state.pending_lon:.5f}")
                    else:
                        st.warning("請先在地圖上點擊要新增的位置")

                    if st.button("新增此地點", type="primary", use_container_width=True):
                        if not new_name.strip():
                            st.error("請輸入地點名稱！")
                        elif not st.session_state.pending_lat:
                            st.error("請先在地圖上點擊你要新增的位置！")
                        elif new_name in st.session_state.locations[st.session_state.current_category]:
                            st.error(f"「{new_name}」已存在！如果要新增樓層，請選擇「現有地點的新樓層」。")
                        else:
                            pt = Point(st.session_state.pending_lon, st.session_state.pending_lat)
                            if ntu_campus_poly.contains(pt):
                                result = add_location(
                                    name=st.session_state.pending_name,
                                    lat=st.session_state.pending_lat,
                                    lng=st.session_state.pending_lon,
                                    category=st.session_state.current_category,
                                    intro=st.session_state.pending_desc,
                                    floor=st.session_state.pending_floor
                                )
                                new_id = result[0]["id"]
                                p_name = st.session_state.pending_name
                                if p_name not in st.session_state.locations[st.session_state.current_category]:
                                    st.session_state.locations[st.session_state.current_category][p_name] = []
                                st.session_state.locations[st.session_state.current_category][p_name].append({
                                    "id": new_id,
                                    "floor": st.session_state.pending_floor,
                                    "lat": st.session_state.pending_lat,
                                    "lon": st.session_state.pending_lon,
                                    "crowd": "待回報",
                                    "comments": [],
                                    "desc": st.session_state.pending_desc,
                                    "image": None
                                })
                                st.toast(f"✅ 成功新增地點：{p_name}！", icon="✅")
                                st.session_state.pending_lat = None
                                st.session_state.pending_lon = None
                                import time
                                time.sleep(1)
                                st.rerun()
                            else:
                                st.error("⚠️該座標不在臺大校總區範圍內，無法新增！")

                else:
                    existing_names = list(st.session_state.locations[st.session_state.current_category].keys())
                    if not existing_names:
                        st.warning("目前此類別還沒有地點")
                    else:
                        selected_existing = st.selectbox("選擇要歸入的地點", existing_names)
                        existing_floor_names = [f['floor'] for f in st.session_state.locations[st.session_state.current_category][selected_existing]]
                        available_floors = [f for f in ["無", "B2", "B1", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10"] if f not in existing_floor_names]

                        if not available_floors:
                            st.warning("此地點所有樓層都已新增完畢！")
                        else:
                            new_floor = st.selectbox("選擇樓層", available_floors, key="new_floor_existing")
                            new_desc = st.text_area("介紹", key="new_desc_existing", max_chars=200)

                            st.session_state.pending_floor = new_floor
                            st.session_state.pending_desc = new_desc

                            if st.button("新增樓層", type="primary", use_container_width=True):
                                existing_floors = st.session_state.locations[st.session_state.current_category][selected_existing]
                                existing_lat = existing_floors[0]['lat']
                                existing_lon = existing_floors[0]['lon']

                                result = add_location(
                                    name=selected_existing,
                                    lat=existing_lat,
                                    lng=existing_lon,
                                    category=st.session_state.current_category,
                                    intro=st.session_state.pending_desc,
                                    floor=st.session_state.pending_floor
                                )
                                new_id = result[0]["id"]
                                if selected_existing not in st.session_state.locations[st.session_state.current_category]:
                                    st.session_state.locations[st.session_state.current_category][selected_existing] = []
                                st.session_state.locations[st.session_state.current_category][selected_existing].append(
                                    {
                                        "id": new_id,
                                        "floor": st.session_state.pending_floor,
                                        "lat": existing_lat,
                                        "lon": existing_lon,
                                        "crowd": "待回報",
                                        "comments": [],
                                        "desc": st.session_state.pending_desc,
                                        "image": None
                                    })
                                st.toast(f"✅ 已新增 {selected_existing} {new_floor} 樓！", icon="✅")
                                import time
                                time.sleep(1)
                                st.rerun()
            
            # --- 修改座標面板 ---
            with st.expander("📍 修改地點座標"):
                st.write("請先在左側地圖點擊新的位置，然後選擇要修改的地點。")
                existing_names = list(st.session_state.locations[st.session_state.current_category].keys())
                if not existing_names:
                    st.warning("目前此類別還沒有地點可修改")
                else:
                    loc_to_modify = st.selectbox("選擇要修改座標的地點", existing_names, key="modify_loc_select")
                    
                    if st.session_state.pending_lat:
                        st.info(f"📍 準備更新為新座標：{st.session_state.pending_lat:.5f}, {st.session_state.pending_lon:.5f}")
                        if st.button("確認修改座標", type="primary", use_container_width=True, key="btn_modify_coords"):
                            pt = Point(st.session_state.pending_lon, st.session_state.pending_lat)
                            if ntu_campus_poly.contains(pt):
                                # 呼叫更新資料庫的函式
                                update_location_coords(
                                    name=loc_to_modify, 
                                    category=st.session_state.current_category, 
                                    lat=st.session_state.pending_lat, 
                                    lng=st.session_state.pending_lon
                                )
                                # 同步更新本地暫存
                                for floor_data in st.session_state.locations[st.session_state.current_category][loc_to_modify]:
                                    floor_data["lat"] = st.session_state.pending_lat
                                    floor_data["lon"] = st.session_state.pending_lon
                                
                                st.toast(f"✅ {loc_to_modify} 座標修改成功！", icon="✅")
                                st.session_state.pending_lat = None
                                st.session_state.pending_lon = None
                                import time
                                time.sleep(1)
                                st.rerun()
                            else:
                                st.error("⚠️ 該座標不在臺大校總區範圍內，無法修改！")
                    else:
                        st.warning("請先在地圖上點擊要設定的新位置！")

# ==========================================
# 4. 程式執行入口
# ==========================================
if __name__ == "__main__":
    st.set_page_config(
        page_title="臺大校園地圖",
        layout="wide",
        initial_sidebar_state="collapsed"
    )

    if not st.session_state.logged_in:
        login_page()
    else:
        main_app()
