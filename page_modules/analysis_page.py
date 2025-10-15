import math
import json
import requests
import streamlit as st
import time
from string import Template
from streamlit.components.v1 import html
from components.solo_analysis import tab1_module
import google.generativeai as genai
import pandas as pd

# ===========================
# 收藏與分析功能
# ===========================
def get_favorites_data():
    if 'favorites' not in st.session_state or not st.session_state.favorites:
        return pd.DataFrame()
    all_df = None
    if 'all_properties_df' in st.session_state and not st.session_state.all_properties_df.empty:
        all_df = st.session_state.all_properties_df
    elif 'filtered_df' in st.session_state and not st.session_state.filtered_df.empty:
        all_df = st.session_state.filtered_df
    if all_df is None or all_df.empty:
        return pd.DataFrame()
    fav_ids = st.session_state.favorites
    fav_df = all_df[all_df['編號'].astype(str).isin(map(str, fav_ids))].copy()
    return fav_df


def render_favorites_list(fav_df):
    st.subheader("⭐ 我的收藏清單")
    for idx, (_, row) in enumerate(fav_df.iterrows()):
        with st.container():
            col1, col2 = st.columns([8, 2])
            with col1:
                st.markdown(f"**#{idx+1} 🏠 {row['標題']}**")
                st.write(f"**地址：** {row['地址']} | **屋齡：** {row['屋齡']} | **類型：** {row['類型']}")
                st.write(f"**建坪：** {row['建坪']} | **格局：** {row['格局']} | **樓層：** {row['樓層']}")
                if '車位' in row and pd.notna(row['車位']):
                    st.write(f"**車位：** {row['車位']}")
            with col2:
                st.metric("總價", f"{row['總價(萬)']} 萬")
                if pd.notna(row['建坪']) and row['建坪'] > 0:
                    unit_price = (row['總價(萬)'] * 10000) / row['建坪']
                    st.caption(f"單價: ${unit_price:,.0f}/坪")
                property_id = row['編號']
                if st.button("❌ 移除", key=f"remove_fav_{property_id}"):
                    st.session_state.favorites.discard(property_id)
                    st.rerun()
                property_url = f"https://www.sinyi.com.tw/buy/house/{row['編號']}?breadcrumb=list"
                st.markdown(f'[🔗 物件連結]({property_url})')
            st.markdown("---")


# ===========================
# Google Places 設定
# ===========================
PLACE_TYPES = {
    "教育": ["圖書館", "幼兒園", "小學", "學校", "中學", "大學"],
    "健康與保健": ["牙醫", "醫師", "藥局", "醫院"],
    "購物": ["便利商店", "超市", "百貨公司"],
    "交通運輸": ["公車站", "地鐵站", "火車站"],
    "餐飲": ["餐廳"]
}

CATEGORY_COLORS = {
    "教育": "#1E90FF",
    "健康與保健": "#32CD32",
    "購物": "#FF8C00",
    "交通運輸": "#800080",
    "餐飲": "#FF0000",
    "關鍵字": "#000000"
}

# ===========================
# 工具函式
# ===========================
def haversine(lat1, lon1, lat2, lon2):
    R = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = math.sin(d_phi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(d_lambda/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))


def _get_server_key():
    server_key = st.session_state.get("GMAPS_SERVER_KEY") or st.session_state.get("GOOGLE_MAPS_KEY", "")
    if "GMAPS_SERVER_KEY" not in st.session_state and server_key:
        st.warning("⚠️地圖加載 需要時間 請耐心等待")
    return server_key


def _get_browser_key():
    return st.session_state.get("GMAPS_BROWSER_KEY") or st.session_state.get("GOOGLE_MAPS_KEY", "")


def geocode_address(address: str, api_key: str):
    url = "https://maps.googleapis.com/maps/api/geocode/json"
    params = {"address": address, "key": api_key, "language": "zh-TW"}
    try:
        r = requests.get(url, params=params, timeout=10).json()
    except Exception as e:
        st.error(f"地址解析失敗: {e}")
        return None, None
    status = r.get("status")
    if status == "OK" and r.get("results"):
        loc = r["results"][0]["geometry"]["location"]
        return loc["lat"], loc["lng"]
    st.warning(f"Geocoding error: {status}")
    return None, None


# ===========================
# 改良版 Google Places + 進度條
# ===========================
def query_google_places_keyword(lat, lng, api_key, selected_categories, radius=500, extra_keyword=""):
    results, seen = [], set()
    total_tasks = sum(len(PLACE_TYPES[cat]) for cat in selected_categories) + (1 if extra_keyword else 0)
    progress = st.progress(0)
    progress_text = st.empty()
    completed = 0

    def update_progress(task_desc):
        nonlocal completed
        completed += 1
        progress.progress(min(completed / total_tasks, 1.0))
        progress_text.text(f"進度：{completed}/{total_tasks} - {task_desc}")

    def call(params, tag_cat, tag_kw):
        """自動處理重試與延遲（5 次重試，每次間隔 5 秒）"""
        for attempt in range(5):
            try:
                data = requests.get(
                    "https://maps.googleapis.com/maps/api/place/nearbysearch/json",
                    params=params, timeout=10
                ).json()
            except Exception as e:
                st.warning(f"❌ {tag_cat}-{tag_kw} 查詢失敗: {e}")
                return []
            st_code = data.get("status")
            if st_code == "OK":
                return data.get("results", [])
            elif st_code == "ZERO_RESULTS":
                st.info(f"🏠 該地區沒有 {tag_cat}-{tag_kw}")
                return []
            elif st_code == "OVER_QUERY_LIMIT":
                st.warning(f"⏳ API 過載（{tag_cat}-{tag_kw}），第 {attempt+1} 次重試中...")
                time.sleep(5)
                continue
            else:
                st.warning(f"🏠 {tag_cat}-{tag_kw} 查詢錯誤: {st_code}")
                return []
        return []

    # 迴圈查詢
    for cat in selected_categories:
        for kw in PLACE_TYPES[cat]:
            update_progress(f"查詢 {cat}-{kw}")
            params = {"location": f"{lat},{lng}", "radius": radius, "keyword": kw, "key": api_key, "language": "zh-TW"}
            for p in call(params, cat, kw):
                try:
                    pid = p.get("place_id", "")
                    if pid in seen:
                        continue
                    seen.add(pid)
                    loc = p["geometry"]["location"]
                    dist = int(haversine(lat, lng, loc["lat"], loc["lng"]))
                    if dist <= radius:
                        results.append((cat, kw, p.get("name","未命名"), loc["lat"], loc["lng"], dist, pid))
                except Exception:
                    continue
            time.sleep(0.3)

    # 額外關鍵字
    if extra_keyword:
        update_progress(f"額外關鍵字: {extra_keyword}")
        params = {"location": f"{lat},{lng}", "radius": radius, "keyword": extra_keyword, "key": api_key, "language": "zh-TW"}
        for p in call(params, "關鍵字", extra_keyword):
            try:
                pid = p.get("place_id", "")
                if pid in seen:
                    continue
                seen.add(pid)
                loc = p["geometry"]["location"]
                dist = int(haversine(lat, lng, loc["lat"], loc["lng"]))
                if dist <= radius:
                    results.append(("關鍵字", extra_keyword, p.get("name","未命名"), loc["lat"], loc["lng"], dist, pid))
            except Exception:
                continue
        time.sleep(0.3)

    progress.progress(1.0)
    progress_text.text("✅ 查詢完成！")
    results.sort(key=lambda x: x[5])
    return results


# ===========================
# 地圖渲染
# ===========================
def render_map(lat, lng, places, radius, title="房屋"):
    browser_key = _get_browser_key()
    data = []
    for cat, kw, name, p_lat, p_lng, dist, pid in places:
        data.append({
            "cat": cat, "kw": kw, "name": name, "lat": p_lat, "lng": p_lng,
            "dist": dist, "pid": pid, "color": CATEGORY_COLORS.get(cat, "#000000")
        })
    data_json = json.dumps(data, ensure_ascii=False)

    tpl = Template("""
<div id="map" style="height:400px;"></div>
<script>
function initMap() {
  var center = {lat: $LAT, lng: $LNG};
  var map = new google.maps.Map(document.getElementById('map'), {zoom: 16, center: center});
  new google.maps.Marker({position: center, map: map, title: "$TITLE"});
  var data = $DATA_JSON;
  data.forEach(function(p){
    var info = p.cat + "-" + p.kw + ": " + p.name + "<br>距離中心 " + p.dist + " 公尺";
    var marker = new google.maps.Marker({
      position: {lat: p.lat, lng: p.lng},
      map: map,
      icon: {
        path: google.maps.SymbolPath.CIRCLE,
        scale: 6,
        fillColor: p.color,
        fillOpacity: 1,
        strokeWeight: 1
      },
      title: p.cat + "-" + p.name
    });
    marker.addListener("click", function(){
      new google.maps.InfoWindow({content: info}).open(map, marker);
    });
  });
  new google.maps.Circle({
    strokeColor:"#FF0000", strokeOpacity:0.8, strokeWeight:2,
    fillColor:"#FF0000", fillOpacity:0.1, map: map, center: center, radius: $RADIUS
  });
}
</script>
<script src="https://maps.googleapis.com/maps/api/js?key=$BROWSER_KEY&callback=initMap" async defer></script>
""")
    map_html = tpl.substitute(
        LAT=lat, LNG=lng, TITLE=title, DATA_JSON=data_json,
        RADIUS=radius, BROWSER_KEY=browser_key
    )
    html(map_html, height=400)


# ===========================
# 分析主頁
# ===========================
def render_analysis_page():
    st.title("📊 分析頁面")
    if 'favorites' not in st.session_state:
        st.session_state.favorites = set()

    tab1, tab2, _ = st.tabs(["個別分析","房屋比較","市場趨勢分析"])

    with tab1:
        _ = get_favorites_data()
        tab1_module()

    with tab2:
        st.subheader("🏠 房屋比較（Google Places + Gemini 分析）")
        fav_df = get_favorites_data()
        if fav_df.empty:
            st.info("⭐ 尚未有收藏房產，無法比較")
            return

        options = fav_df['標題'] + " | " + fav_df['地址']
        c1, c2 = st.columns(2)
        with c1: choice_a = st.selectbox("選擇房屋 A", options, key="compare_a")
        with c2: choice_b = st.selectbox("選擇房屋 B", options, key="compare_b")

        server_key = _get_server_key()
        gemini_key = st.session_state.get("GEMINI_KEY", "")
        radius = 500
        keyword = st.text_input("額外關鍵字搜尋 (可選)", key="extra_keyword")

        st.subheader("選擇要比較的生活機能類別")
        selected_categories = []
        cols = st.columns(len(PLACE_TYPES))
        for i, cat in enumerate(PLACE_TYPES.keys()):
            with cols[i]:
                if st.checkbox(cat, value=True, key=f"comp_cat_{cat}"):
                    selected_categories.append(cat)

        if st.button("開始比較"):
            if not _get_browser_key():
                st.error("❌ 請在側邊欄填入 Google Maps **Browser Key**"); st.stop()
            if not server_key or not gemini_key:
                st.error("❌ 請在側邊欄填入 Server Key 與 Gemini Key"); st.stop()
            if choice_a == choice_b:
                st.warning("⚠️ 請選擇兩個不同房屋"); st.stop()

            house_a = fav_df[(fav_df['標題'] + " | " + fav_df['地址']) == choice_a].iloc[0]
            house_b = fav_df[(fav_df['標題'] + " | " + fav_df['地址']) == choice_b].iloc[0]
            lat_a, lng_a = geocode_address(house_a["地址"], server_key)
            lat_b, lng_b = geocode_address(house_b["地址"], server_key)
            if lat_a is None or lat_b is None:
                st.error("❌ 地址解析失敗，請檢查 Server Key 限制。")
                return

            with st.spinner("正在查詢房屋 A 周邊..."):
                places_a = query_google_places_keyword(lat_a, lng_a, server_key, selected_categories, radius, extra_keyword=keyword)
            time.sleep(1)
            with st.spinner("正在查詢房屋 B 周邊..."):
                places_b = query_google_places_keyword(lat_b, lng_b, server_key, selected_categories, radius, extra_keyword=keyword)

            col1, col2 = st.columns(2)
            with col1: render_map(lat_a, lng_a, places_a, radius, title="房屋 A")
            with col2: render_map(lat_b, lng_b, places_b, radius, title="房屋 B")

            genai.configure(api_key=gemini_key)
            model = genai.GenerativeModel("gemini-2.0-flash")
            prompt = f"""你是一位房地產分析專家，請比較以下兩間房屋的生活機能，
房屋 A：
{format_places(places_a)}
房屋 B：
{format_places(places_b)}
請列出優缺點與結論。"""
            resp = model.generate_content(prompt)
            st.subheader("📊 Gemini 分析結果")
            st.write(resp.text)


def format_places(places):
    return "\n".join([f"{cat}-{kw}: {name} ({dist} m)" for cat, kw, name, lat, lng, dist, pid in places])
