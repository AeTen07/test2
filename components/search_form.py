import streamlit as st
import os
import pandas as pd
import google.generativeai as genai
from utils import get_city_options, filter_properties

def render_search_form():
    """ 渲染搜尋表單並處理提交邏輯 """
    with st.form("property_requirements"):
        st.subheader("📍 房產篩選條件")
        housetype = ["不限", "大樓", "華廈", "公寓", "套房", "透天", "店面", "辦公", "別墅", "倉庫", "廠房", "土地", "單售車位", "其它"]
        options = get_city_options()

        col1, col2 = st.columns([1, 1])
        with col1:
            selected_label = st.selectbox("請選擇城市：", list(options.keys()))
            housetype_change = st.selectbox("請選擇房產類別：", housetype, key="housetype")
        with col2:
            budget_max = st.number_input("💰預算上限(萬)", min_value=0, max_value=1000000, value=1000000, step=100)
            budget_min = st.number_input("💰預算下限(萬)", min_value=0, max_value=1000000, value=0, step=100)

        if budget_min > budget_max and budget_max > 0:
            st.error("⚠️ 預算下限不能大於上限！")

        st.subheader("🎯房產要求細項")
        col1, col2, col3 = st.columns([1, 1, 1])
        with col1:
            age_max = st.number_input("屋齡上限", min_value=0, max_value=100, value=100, step=1)
            age_min = st.number_input("屋齡下限", min_value=0, max_value=100, value=0, step=1)
            if age_min > age_max:
                st.error("⚠️ 屋齡下限不能大於上限！")
        with col2:
            area_max = st.number_input("建坪上限", min_value=0, max_value=1000, value=1000, step=10)
            area_min = st.number_input("建坪下限", min_value=0, max_value=1000, value=0, step=10)
            if area_min > area_max:
                st.error("⚠️ 建坪下限不能大於上限！")
        with col3:
            car_grip = st.selectbox("🅿️車位選擇", ["不限", "需要", "不要"], key="car_grip")

        st.subheader("🛠️特殊要求（可輸入文字，如：一房二廳一衛以上，低樓層）")
        Special_Requests = st.text_area("特殊要求", placeholder="例：一房二廳一衛以上，低樓層")

        col1, col2, col3, col4, col5 = st.columns([1, 1, 1, 1, 1])
        with col3:
            submit = st.form_submit_button("搜尋", use_container_width=True)

        if submit:
            return handle_search_submit(
                selected_label, options, housetype_change,
                budget_min, budget_max, age_min, age_max, area_min, area_max, car_grip,
                Special_Requests
            )
    return None


def handle_search_submit(selected_label, options, housetype_change, budget_min, budget_max,
                         age_min, age_max, area_min, area_max, car_grip, Special_Requests):
    """ 處理搜尋表單提交 """
    valid_input = True
    if budget_min > budget_max and budget_max > 0:
        st.error("❌ 請修正預算範圍設定")
        valid_input = False
    if age_min > age_max:
        st.error("❌ 請修正屋齡範圍設定")
        valid_input = False
    if area_min > area_max:
        st.error("❌ 請修正建坪範圍設定")
        valid_input = False

    if not valid_input:
        return False

    st.session_state.current_search_page = 1
    selected_file = options[selected_label]
    file_path = os.path.join("./Data", selected_file)

    try:
        df = pd.read_csv(file_path)

        # 先處理基本篩選
        filters = {
            'housetype': housetype_change,
            'budget_min': budget_min,
            'budget_max': budget_max,
            'age_min': age_min,
            'age_max': age_max,
            'area_min': area_min,
            'area_max': area_max,
            'car_grip': car_grip
        }

        # 處理特殊要求 -> Gemini AI
        gemini_key = st.session_state.get("GEMINI_KEY", "")
        parsed_req = {}
        if Special_Requests.strip() and gemini_key:
            try:
                genai.configure(api_key=gemini_key)
                model = genai.GenerativeModel("gemini-2.0-flash")
                prompt = f"""
                將以下房產需求文字解析成結構化條件（JSON格式）：
                {Special_Requests}
                輸出欄位包含：房間數、廳數、衛數、樓層。
                範例：
                {{
                  "房間數": 2,
                  "廳數": 1,
                  "衛數": 1,
                  "樓層": {{"min": 1, "max": 5}}
                }}
                """
                response = model.generate_content(prompt)
                import json
                parsed_req = json.loads(response.text)
            except Exception as e:
                st.error(f"❌ Gemini 解析特殊要求失敗: {e}")

        # 合併到篩選條件
        if parsed_req.get("房間數"):
            filters["rooms"] = parsed_req["房間數"]
        if parsed_req.get("廳數"):
            filters["living_rooms"] = parsed_req["廳數"]
        if parsed_req.get("衛數"):
            filters["bathrooms"] = parsed_req["衛數"]
        if parsed_req.get("樓層"):
            filters["floor"] = parsed_req["樓層"]

        # 執行篩選
        filtered_df = filter_properties(df, filters)
        st.session_state.filtered_df = filtered_df
        st.session_state.search_params = {
            'city': selected_label,
            'housetype': housetype_change,
            'budget_range': f"{budget_min}-{budget_max}萬" if budget_max < 1000000 else f"{budget_min}萬以上",
            'age_range': f"{age_min}-{age_max}年" if age_max < 100 else f"{age_min}年以上",
            'area_range': f"{area_min}-{area_max}坪" if area_max < 1000 else f"{area_min}坪以上",
            'car_grip': car_grip,
            'original_count': len(df),
            'filtered_count': len(filtered_df)
        }

        if len(filtered_df) == 0:
            st.warning("😅 沒有找到符合條件的房產，請調整篩選條件後重新搜尋")
        else:
            st.success(f"✅ 從 {len(df)} 筆資料中篩選出 {len(filtered_df)} 筆符合條件的房產")
        return True

    except FileNotFoundError:
        st.error(f"❌ 找不到檔案: {file_path}")
    except Exception as e:
        st.error(f"❌ 讀取 CSV 發生錯誤: {e}")
    return False
