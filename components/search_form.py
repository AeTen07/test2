# search_form.py

import os
import streamlit as st
import pandas as pd
from utils import get_city_options, filter_properties, parse_layout, parse_floor

def render_search_form():
    """渲染搜尋表單並處理提交邏輯"""
    with st.form("property_requirements"):
        st.subheader("📍 房產篩選條件")
        housetype_options = ["不限", "大樓", "華廈", "公寓", "套房", "透天", "店面", "辦公", "別墅", "倉庫", "廠房", "土地", "單售車位", "其它"]
        city_options = get_city_options()

        col1, col2 = st.columns([1, 1])
        with col1:
            selected_city = st.selectbox("請選擇城市：", list(city_options.keys()))
            selected_housetype = st.selectbox("請選擇房產類別：", housetype_options)
        with col2:
            budget_min = st.number_input("💰預算下限(萬)", min_value=0, max_value=1000000, value=0, step=100)
            budget_max = st.number_input("💰預算上限(萬)", min_value=0, max_value=1000000, value=1000000, step=100)
            if budget_min > budget_max and budget_max > 0:
                st.error("⚠️ 預算下限不能大於上限！")

        st.subheader("🎯 房產要求細項")
        col1, col2, col3 = st.columns([1, 1, 1])
        with col1:
            age_min = st.number_input("屋齡下限", min_value=0, max_value=100, value=0, step=1)
            age_max = st.number_input("屋齡上限", min_value=0, max_value=100, value=100, step=1)
            if age_min > age_max:
                st.error("⚠️ 屋齡下限不能大於上限！")
        with col2:
            area_min = st.number_input("建坪下限", min_value=0, max_value=1000, value=0, step=10)
            area_max = st.number_input("建坪上限", min_value=0, max_value=1000, value=1000, step=10)
            if area_min > area_max:
                st.error("⚠️ 建坪下限不能大於上限！")
        with col3:
            car_grip = st.selectbox("🅿️ 車位選擇", ["不限", "需要", "不要"])

        st.subheader("🛠️ 特殊要求（可輸入文字，如：二房二廳一衛）")
        special_requests = st.text_area("特殊要求", placeholder="請輸入")

        submit = st.form_submit_button("搜尋")

        if submit:
            handle_search_submit(selected_city, city_options, selected_housetype,
                                 budget_min, budget_max, age_min, age_max,
                                 area_min, area_max, car_grip, special_requests)


def handle_search_submit(selected_city, city_options, housetype,
                         budget_min, budget_max, age_min, age_max,
                         area_min, area_max, car_grip, special_requests):
    """處理搜尋表單提交"""
    file_name = city_options[selected_city]
    file_path = os.path.join("./Data", file_name)

    try:
        df = pd.read_csv(file_path)

        # ===== 解析格局與樓層 =====
        layout_parsed = df['格局'].apply(parse_layout)
        df['rooms'] = layout_parsed.apply(lambda x: x['rooms'])
        df['living_rooms'] = layout_parsed.apply(lambda x: x['living_rooms'])
        df['bathrooms'] = layout_parsed.apply(lambda x: x['bathrooms'])
        df['floor'] = df['樓層'].apply(lambda x: parse_floor(x)['min'])
        df['floor_max'] = df['樓層'].apply(lambda x: parse_floor(x)['max'])

        # ===== 一般條件篩選 =====
        filters = {
            'housetype': housetype,
            'budget_min': budget_min,
            'budget_max': budget_max,
            'age_min': age_min,
            'age_max': age_max,
            'area_min': area_min,
            'area_max': area_max,
            'car_grip': car_grip
        }

        # ===== Gemini 特殊要求解析 (只補充 rooms, living_rooms, bathrooms, floor) =====
        parsed_req = {}  # 這裡可接 Gemini 回傳 JSON
        # 示例：假設 Gemini 回傳 {"房間數": 2, "廳數": 1, "衛數": 1, "樓層": {"min":1,"max":5}}
        # 你可在這裡加入 Gemini API 呼叫並解析
        keymap = {"房間數": "rooms", "廳數": "living_rooms", "衛數": "bathrooms", "樓層": "floor"}
        normalized_req = {}
        for k, v in parsed_req.items():
            if k in keymap:
                normalized_req[keymap[k]] = v

        # 合併特殊要求，只補充缺失欄位
        for k, v in normalized_req.items():
            if k not in filters or filters[k] in [None, "", {}]:
                filters[k] = v

        # ===== 執行篩選 =====
        filtered_df = filter_properties(df, filters)

        st.session_state.filtered_df = filtered_df
        st.session_state.search_params = {
            'city': selected_city,
            'housetype': housetype,
            'budget_range': f"{budget_min}-{budget_max}萬" if budget_max < 1e6 else f"{budget_min}萬以上",
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

    except FileNotFoundError:
        st.error(f"❌ 找不到檔案: {file_path}")
    except Exception as e:
        st.error(f"❌ 讀取 CSV 發生錯誤: {e}")
