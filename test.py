import streamlit as st
import folium
import smtplib
import math
import random
import os
import json
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
except:
    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_KEY = os.getenv("SUPABASE_KEY")
    GMAIL_ADDRESS = os.getenv("GMAIL_ADDRESS")
    GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")

# ==========================================
# 資料庫操作
# ==========================================
client = create_client(SUPABASE_URL, SUPABASE_KEY)

def get_all_locations():
    # 讀取所有地點
    response = client.table("locations").select("*").execute()
    return response.data

def add_location(name, lat, lng, category, intro, floor="無"):
    # 新增一個地點
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

# def update_score(location_id, delta):
#     # 推 delta=+1，噓 delta=-1
#     location = client.table("locations").select("score").eq("id", location_id).execute()
#     current_score = location.data[0]["score"]
#     client.table("locations").update(
#         {"score": current_score + delta}
#     ).eq("id", location_id).execute()



def update_crowdedness(location_id, value):
    location = client.table("locations").select("crowdedness").eq("id", location_id).execute()
    raw = json.loads(location.data[0]["crowdedness"])
    current = raw if isinstance(raw, list) else [raw]
    current.append(value)
    client.table("locations").update(
        {"crowdedness": json.dumps(current)}
    ).eq("id", location_id).execute()

def add_comment(location_id, comment):
    # 新增評論
    location = client.table("locations").select("comments").eq("id", location_id).execute()
    current_comments = json.loads(location.data[0]["comments"])
    current_comments.append(comment)
    client.table("locations").update(
        {"comments": json.dumps(current_comments, ensure_ascii=False)}
    ).eq("id", location_id).execute()

# ==========================================
# 驗證碼寄送
# ==========================================
def send_verification_code(target_email):
    # 產生 6 位數驗證碼
    code = str(random.randint(100000, 999999))
    st.session_state["verify_code"] = code
    st.session_state["verify_email"] = target_email

    # 組合信件
    msg = MIMEMultipart()
    msg["From"] = f"臺大校園地圖 <{GMAIL_ADDRESS}>"
    msg["To"] = target_email
    msg["Subject"] = "臺大地圖 驗證碼"
    msg.attach(MIMEText(f"你的驗證碼是：{code}\n\n10分鐘內有效。", "plain"))

    # 寄信
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
        server.sendmail(GMAIL_ADDRESS, target_email, msg.as_string())

# ==========================================
# 1. 初始化設定
# ==========================================
# 臺大總區邊界
ntu_polygon_coords = [
    (121.537209, 25.011598), (121.533004, 25.016414), (121.533402, 25.016789),
    (121.534567, 25.022169), (121.536965, 25.022190), (121.539104, 25.021150),
    (121.543849, 25.020836), (121.546168, 25.019094)
]
ntu_campus_poly = Polygon(ntu_polygon_coords)
folium_bounds = [(lat, lon) for lon, lat in ntu_polygon_coords]

# 登入狀態初始化
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'user_role' not in st.session_state:
    st.session_state.user_role = None
if 'current_category' not in st.session_state:
    st.session_state.current_category = "充電"
if 'waiting_verify' not in st.session_state:
    st.session_state.waiting_verify = False

# pending 座標初始化
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
            crowdedness_raw = json.loads(loc.get("crowdedness", "[1]"))
            crowdedness_data = crowdedness_raw if isinstance(crowdedness_raw, list) else [crowdedness_raw]
            floor_entry = {
                "id": loc["id"],
                "floor": loc.get("floor") or "無",
                "lat": loc["lat"],
                "lon": loc["lng"],
                "crowd": round(sum(crowdedness_data) / len(crowdedness_data), 1) if crowdedness_data else 1,
                "comments": json.loads(loc.get("comments", "[]")),
                "desc": loc.get("intro", ""),
                "image": None
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
                send_verification_code(email)
                st.session_state.waiting_verify = True
                st.success("驗證碼已寄出，請檢查信箱")

        if st.session_state.waiting_verify:
            code_input = st.text_input("輸入驗證碼")
            if st.button("驗證"):
                if code_input == st.session_state.get("verify_code"):
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
            st.info("以訪客模式進入（無法新增地點）")
            st.rerun()

# ==========================================
# 3. 主應用程式
# ==========================================
def main_app():
    # 頂部導航與登出
    col_title, col_logout = st.columns([4, 1])
    col_title.title("🗺️ 臺大校園地圖指南")
    if col_logout.button("登出"):
        st.session_state.logged_in = False
        st.session_state.user_role = None
        del st.session_state["locations"]  # 改這行
        st.rerun()

    if st.session_state.user_role == "student":
        st.success("✅ 學生身份已驗證：具備完整功能與新增地點權限。")
    else:
        st.warning("👁️ 訪客模式：可瀏覽與評論，但無法新增地點。")

    # 五個類別按鈕
    categories = ["充電", "情緒釋放", "戶外放鬆", "排練", "面試"]
    cols = st.columns(5)
    for idx, cat in enumerate(categories):
        if cols[idx].button(cat, use_container_width=True):
            st.session_state.current_category = cat

    st.markdown(f"### 目前選擇類別：**{st.session_state.current_category}**")
    st.divider()

    # 畫面佈局
    col_map, col_details = st.columns([3, 2])

    with col_map:
        st.write("點擊地圖任意處可獲取座標 (新增地點時使用)")
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
            avg_crowd = sum(f['crowd'] for f in floors) / len(floors)
            color = "green" if avg_crowd <= 2 else "orange" if avg_crowd <= 4 else "red"
            folium.Marker(
                [first_floor['lat'], first_floor['lon']],
                popup=f"<b>{loc_name}</b><br>樓層數: {len(floors)}<br>平均擁擠度: {round(avg_crowd, 1)}/5",
                tooltip=loc_name,
                icon=folium.Icon(color=color, icon="info-sign")
            ).add_to(m)

        map_data = st_folium(m, width=500, height=450)

        clicked_lat, clicked_lon = None, None
        if map_data.get("last_clicked"):
            clicked_lat = map_data["last_clicked"]["lat"]
            clicked_lon = map_data["last_clicked"]["lng"]
            # 存進 session_state
            st.session_state.pending_lat = clicked_lat
            st.session_state.pending_lon = clicked_lon
            st.info(f"📍 獲取地圖座標: 緯度 {clicked_lat:.5f}, 經度 {clicked_lon:.5f}")

    with col_details:
        st.markdown("#### 🏢 地點互動")
        loc_list = list(current_data.keys())

        if loc_list:
            selected_loc_name = st.selectbox("選擇地點：", loc_list)
            floors_data = current_data[selected_loc_name]

            # 如果只有一個樓層且是「無」，不顯示樓層選單
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

            if selected_loc.get('image') is not None:
                st.image(selected_loc['image'], use_container_width=True)

            st.write(f"**介紹：** {selected_loc.get('desc', '無')}")
            st.write(f"**平均擁擠程度：** {selected_loc['crowd']} / 5")

            # 功能 1: 回報擁擠狀況
            st.write("回報擁擠狀況：")
            if st.session_state.user_role == "student":
                crowd_cols = st.columns(5)
                for i in range(1, 6):
                    if crowd_cols[i - 1].button(str(i), key=f"crowd_{selected_loc_name}_{selected_loc['floor']}_{i}"):
                        update_crowdedness(selected_loc['id'], i)
                        updated = client.table("locations").select("crowdedness").eq("id", selected_loc['id']).execute()
                        data = json.loads(updated.data[0]["crowdedness"])
                        selected_loc['crowd'] = round(sum(data) / len(data), 1) if data else 1
                        st.success(f"已更新！目前平均擁擠度：{selected_loc['crowd']} / 5")
                        st.rerun()
            else:
                st.caption("請登入台大信箱才能回報擁擠度")

            # 功能 2: 上傳圖片
            with st.expander("📷 上傳或更新此地點的圖片"):
                update_img_file = st.file_uploader(
                    "選擇圖片", type=["jpg", "png", "jpeg"],
                    key=f"upload_img_{selected_loc_name}_{selected_loc['floor']}"
                )
                if st.button("送出圖片", key=f"btn_update_img_{selected_loc_name}_{selected_loc['floor']}",
                             use_container_width=True):
                    if update_img_file:
                        selected_loc['image'] = update_img_file.read()
                        st.success("圖片更新成功！")
                        st.rerun()
                    else:
                        st.warning("請先選擇要上傳的圖片檔案！")

            # 功能 3: 留言評論
            st.markdown("##### 💬 留言評論")
            for c in selected_loc['comments']:
                st.write(f"- {c}")

            new_comment = st.text_input("新增評論...", key=f"comment_{selected_loc_name}_{selected_loc['floor']}")
            if st.button("送出評論", use_container_width=True):
                if new_comment:
                    selected_loc['comments'].append(new_comment)
                    add_comment(selected_loc['id'], new_comment)
                    st.rerun()

        st.divider()

        # 新增地點功能
        if st.session_state.user_role == "student":
            with st.expander("➕ 新增地點 (需先點選地圖獲取座標)"):

                # 先選擇新增類型
                add_mode = st.radio(
                    "新增方式：",
                    ["新地點", "現有地點的新樓層"],
                    key="add_mode"
                )

                if add_mode == "新地點":
                    new_name = st.text_input("地點名稱")
                    new_floor = st.selectbox(
                        "選擇樓層",
                        ["無", "B2", "B1", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10"]
                    )
                    new_desc = st.text_area("介紹")

                    st.session_state.pending_name = new_name
                    st.session_state.pending_floor = new_floor
                    st.session_state.pending_desc = new_desc

                    if st.session_state.pending_lat:
                        st.info(f"📍 目前座標：{st.session_state.pending_lat:.5f}, {st.session_state.pending_lon:.5f}")
                    else:
                        st.warning("請先在地圖上點擊要新增的位置")

                    if st.button("新增此地點", type="primary", use_container_width=True):
                        if not new_name:
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
                                    "crowd": 1,
                                    "comments": [],
                                    "desc": st.session_state.pending_desc,
                                    "image": None
                                })
                                st.toast(f"✅ 成功新增地點：{p_name}！", icon="✅")
                                st.rerun()
                            else:
                                st.error("⚠️ 該座標不在臺大校總區範圍內，無法新增！")

                else:
                    # 現有地點的新樓層
                    existing_names = list(st.session_state.locations[st.session_state.current_category].keys())
                    if not existing_names:
                        st.warning("目前此類別還沒有地點")
                    else:
                        selected_existing = st.selectbox("選擇要歸入的地點", existing_names)

                        # 過濾已存在的樓層
                        existing_floor_names = [f['floor'] for f in
                                                st.session_state.locations[st.session_state.current_category][
                                                    selected_existing]]
                        available_floors = [f for f in
                                            ["無", "B2", "B1", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10"] if
                                            f not in existing_floor_names]

                        if not available_floors:
                            st.warning("此地點所有樓層都已新增完畢！")
                        else:
                            new_floor = st.selectbox(
                                "選擇樓層",
                                available_floors,
                                key="new_floor_existing"
                            )
                            new_desc = st.text_area("介紹", key="new_desc_existing")

                            st.session_state.pending_floor = new_floor
                            st.session_state.pending_desc = new_desc

                            if st.button("新增樓層", type="primary", use_container_width=True):
                                existing_floors = st.session_state.locations[st.session_state.current_category][
                                    selected_existing]
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
                                if selected_existing not in st.session_state.locations[
                                    st.session_state.current_category]:
                                    st.session_state.locations[st.session_state.current_category][
                                        selected_existing] = []
                                st.session_state.locations[st.session_state.current_category][selected_existing].append(
                                    {
                                        "id": new_id,
                                        "floor": st.session_state.pending_floor,
                                        "lat": existing_lat,
                                        "lon": existing_lon,
                                        "crowd": 1,
                                        "comments": [],
                                        "desc": st.session_state.pending_desc,
                                        "image": None
                                    })
                                st.toast(f"✅ 已新增 {selected_existing} {new_floor} 樓！", icon="✅")
                                st.rerun()

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