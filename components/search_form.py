# search_form.py

import os
import re
import pandas as pd
import streamlit as st
from utils import get_city_options, filter_properties, parse_layout, parse_floor, normalize_special_value

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

        st.subheader("🛠️特殊要求（可輸入文字，如：二房二廳一衛）")
        Special_Requests = st.text_area("特殊要求", placeholder="請輸入")

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
    """處理搜尋表單提交（CSV 解析 + Gemini 特殊要求 + 篩選）"""
    # 驗證基本輸入
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
        # ===== 讀 CSV =====
        df = pd.read_csv(file_path)

        # ===== 解析格局與樓層 =====
        parsed_layout = df['格局'].apply(parse_layout)
        df['rooms'] = parsed_layout.apply(lambda x: x['rooms'])
        df['living_rooms'] = parsed_layout.apply(lambda x: x['living_rooms'])
        df['bathrooms'] = parsed_layout.apply(lambda x: x['bathrooms'])
        df['floor'] = df['樓層'].apply(lambda x: parse_floor(x)['min'])
        df['floor_max'] = df['樓層'].apply(lambda x: parse_floor(x)['max'])

        # ===== 一般篩選條件 =====
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

        # ===== Gemini 特殊要求解析（只補充格局/樓層）=====
        parsed_req = {}
        gemini_key = st.session_state.get("GEMINI_KEY", "")
        if Special_Requests.strip() and gemini_key:
            try:
                import google.generativeai as genai
                genai.configure(api_key=gemini_key)
                model = genai.GenerativeModel("gemini-2.0-flash")
                prompt = f"""
                請將下列房產需求解析為**純 JSON**：
                \"\"\"{Special_Requests}\"\"\"
                JSON 欄位請包含：房間數、廳數、衛數、樓層
                """
                response = model.generate_content(prompt)
                resp_text = (response.text or "").strip()
                with st.expander("🔎 Gemini 回傳（debug）", expanded=False):
                    st.code(resp_text)

                import json
                try:
                    parsed_obj = json.loads(resp_text)
                except Exception:
                    # 嘗試抽第一個 {} 的 JSON
                    start = resp_text.find('{')
                    end = resp_text.rfind('}')
                    parsed_obj = json.loads(resp_text[start:end+1].replace('：', ':').replace('，', ','))

                # 標準化 key
                keymap = {
                    "房間數": "rooms", "rooms": "rooms",
                    "廳數": "living_rooms", "廳": "living_rooms",
                    "衛數": "bathrooms", "衛": "bathrooms",
                    "樓層": "floor", "floor": "floor"
                }
                for k, v in parsed_obj.items():
                    target = keymap.get(k.strip()) or keymap.get(str(k).strip().lower())
                    if target:
                        normed = normalize_special_value(v)
                        if normed is not None:
                            parsed_req[target] = normed

            except Exception as e:
                st.error(f"❌ Gemini 解析特殊要求失敗: {e}")
                parsed_req = {}

        # 只將 Gemini 結果合併格局與樓層
        for k, v in parsed_req.items():
            filters[k] = v

        # ===== 執行篩選 =====
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
