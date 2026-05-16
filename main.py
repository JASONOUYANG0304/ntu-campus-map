# import streamlit as st
# from auth import check_login, is_logged_in
#
# check_login()
#
# if is_logged_in():
#     st.write("登入成功，歡迎使用台大地圖！")

from database import add_location

locations = [
    {"name": "心輔", "category": "充電", "lat": 25.0195, "lng": 121.5410, "intro": "提供心理諮商與輔導資源。"},
    {"name": "社科圖二樓", "category": "充電", "lat": 25.0210, "lng": 121.5420, "intro": "安靜舒適的閱讀與充電空間。"},
    {"name": "學輔", "category": "充電", "lat": 25.0175, "lng": 121.5390, "intro": "學生學習輔導中心。"},
    {"name": "博雅345樓遮陽", "category": "充電", "lat": 25.0185, "lng": 121.5375, "intro": "採光佳，適合放空或短暫休息。"},
    {"name": "管一3樓", "category": "充電", "lat": 25.0135, "lng": 121.5370, "intro": "管院學生的秘密基地。"},
    {"name": "總圖一樓", "category": "充電", "lat": 25.0174, "lng": 121.5404, "intro": "總圖大廳旁，適合短暫停留。"},
    {"name": "醉月湖", "category": "情緒釋放", "lat": 25.0198, "lng": 121.5376, "intro": "看鴨子、吹風、整理思緒的好地方。"},
    {"name": "總圖後草", "category": "情緒釋放", "lat": 25.0185, "lng": 121.5415, "intro": "人煙稀少，適合一個人靜靜。"},
    {"name": "總圖左邊", "category": "情緒釋放", "lat": 25.0170, "lng": 121.5395, "intro": "樹蔭下，遠離人群的角落。"},
    {"name": "總圖前面", "category": "戶外放鬆", "lat": 25.0165, "lng": 121.5400, "intro": "大草皮，適合野餐或躺著看天空。"},
    {"name": "鹿鳴堂草皮", "category": "戶外放鬆", "lat": 25.0150, "lng": 121.5390, "intro": "買完食物可以直接坐下來放鬆。"},
    {"name": "二活", "category": "排練", "lat": 25.0138, "lng": 121.5365, "intro": "各大社團排練的首選。"},
    {"name": "人文大樓", "category": "排練", "lat": 25.0160, "lng": 121.5335, "intro": "有寬敞的半戶外空間。"},
    {"name": "綜合一樓", "category": "排練", "lat": 25.0180, "lng": 121.5370, "intro": "下雨天的最佳排練備案。"},
    {"name": "演練室", "category": "面試", "lat": 25.0175, "lng": 121.5400, "intro": "適合單人線上面試，安靜無干擾。"},
    {"name": "綜合討論室", "category": "面試", "lat": 25.0182, "lng": 121.5368, "intro": "預約制，空間獨立。"},
]

for loc in locations:
    add_location(
        name=loc["name"],
        lat=loc["lat"],
        lng=loc["lng"],
        category=loc["category"],
        intro=loc["intro"]
    )
    print(f"新增：{loc['name']}")