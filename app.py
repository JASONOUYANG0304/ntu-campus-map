import streamlit as st
import folium
from streamlit_folium import st_folium
from shapely.geometry import Point, Polygon
from database import get_all_locations, add_location
from auth import send_verification_code

# ==========================================
# 1. 初始化設定與預設資料 (Session State)
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

# 從資料庫讀取地點
if 'locations' not in st.session_state:
    raw = get_all_locations()
    st.session_state.locations = {
        "充電": [], "情緒釋放": [], "戶外放鬆": [], "排練": [], "面試": []
    }
    for loc in raw:
        cat = loc.get("category", "充電")
        if cat in st.session_state.locations:
            st.session_state.locations[cat].append({
                "name": loc["name"],
                "lat": loc["lat"],
                "lon": loc["lng"],
                "crowd": loc.get("score", 1),
                "comments": [],
                "desc": loc.get("intro", ""),
                "image": None
            })


# ==========================================
# 2. 登入頁面模組
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
# 3. 主應用程式模組
# ==========================================
def main_app():
    # 頂部導航與登出
    col_title, col_logout = st.columns([4, 1])
    col_title.title("🗺️ 臺大校園地圖指南")
    if col_logout.button("登出"):
        st.session_state.logged_in = False
        st.session_state.user_role = None
        st.session_state.locations = None
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
        st.write("**點擊地圖任意處可獲取座標 (用於新增地點)**")
        m = folium.Map(location=[25.017, 121.539], zoom_start=16)

        folium.Polygon(
            locations=folium_bounds,
            color="blue",
            fill=True,
            fill_opacity=0.1,
            tooltip="台大校總區範圍"
        ).add_to(m)

        current_locs = st.session_state.locations[st.session_state.current_category]
        for loc in current_locs:
            color = "green" if loc['crowd'] <= 2 else "orange" if loc['crowd'] <= 4 else "red"
            folium.Marker(
                [loc['lat'], loc['lon']],
                popup=f"<b>{loc['name']}</b><br>擁擠度: {loc['crowd']}/5",
                tooltip=loc['name'],
                icon=folium.Icon(color=color, icon="info-sign")
            ).add_to(m)

        map_data = st_folium(m, width=500, height=450)

        clicked_lat, clicked_lon = None, None
        if map_data.get("last_clicked"):
            clicked_lat = map_data["last_clicked"]["lat"]
            clicked_lon = map_data["last_clicked"]["lng"]
            st.info(f"📍 獲取地圖座標: 緯度 {clicked_lat:.5f}, 經度 {clicked_lon:.5f}")

    with col_details:
        st.markdown("#### 🏢 地點互動")
        loc_names = [loc['name'] for loc in current_locs]
        selected_loc_name = st.selectbox("選擇地點以查看或互動：", loc_names)

        selected_loc = next(loc for loc in current_locs if loc['name'] == selected_loc_name)

        if selected_loc.get('image') is not None:
            st.image(selected_loc['image'], use_container_width=True)

        st.write(f"**介紹：** {selected_loc.get('desc', '無')}")
        st.write(f"**目前擁擠程度：** {selected_loc['crowd']} / 5")

        # 功能 1: 回報擁擠狀況
        st.write("回報擁擠狀況：")
        crowd_cols = st.columns(5)
        for i in range(1, 6):
            if crowd_cols[i - 1].button(str(i), key=f"crowd_{selected_loc_name}_{i}"):
                selected_loc['crowd'] = i
                st.success(f"已更新 {selected_loc_name} 擁擠度為 {i}！")
                st.rerun()

        # 功能 2: 上傳圖片
        with st.expander("📷 上傳或更新此地點的圖片"):
            update_img_file = st.file_uploader(
                "選擇圖片", type=["jpg", "png", "jpeg"],
                key=f"upload_img_{selected_loc_name}"
            )
            if st.button("送出圖片", key=f"btn_update_img_{selected_loc_name}", use_container_width=True):
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

        new_comment = st.text_input("新增評論...", key=f"comment_{selected_loc_name}")
        if st.button("送出評論", use_container_width=True):
            if new_comment:
                selected_loc['comments'].append(new_comment)
                st.rerun()

        st.divider()

        # 新增地點功能
        if st.session_state.user_role == "student":
            with st.expander("➕ 新增地點 (需先點選地圖獲取座標)"):
                new_name = st.text_input("地點名稱")
                new_desc = st.text_area("介紹")
                uploaded_file = st.file_uploader(
                    "上傳圖片 (選填)", type=["jpg", "png", "jpeg"], key="new_loc_img"
                )

                if st.button("新增此地點", type="primary", use_container_width=True):
                    if not new_name:
                        st.error("請輸入地點名稱！")
                    elif not clicked_lat or not clicked_lon:
                        st.error("請先在地圖上點擊你要新增的位置！")
                    else:
                        pt = Point(clicked_lon, clicked_lat)
                        if ntu_campus_poly.contains(pt):
                            img_bytes = uploaded_file.read() if uploaded_file else None

                            # 寫入資料庫
                            add_location(
                                name=new_name,
                                lat=clicked_lat,
                                lng=clicked_lon,
                                category=st.session_state.current_category,
                                intro=new_desc
                            )

                            # 更新 session_state
                            st.session_state.locations[st.session_state.current_category].append({
                                "name": new_name,
                                "lat": clicked_lat,
                                "lon": clicked_lon,
                                "crowd": 1,
                                "comments": [],
                                "desc": new_desc,
                                "image": img_bytes
                            })
                            st.success(f"成功新增地點：{new_name}！")
                            st.rerun()
                        else:
                            st.error("⚠️ 該座標不在臺大校總區範圍內，無法新增！")


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