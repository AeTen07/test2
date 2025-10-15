import os
import re
import json
import pandas as pd
import streamlit as st
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

        st.subheader("🛠️特殊要求（可輸入文字，如：一房二廳一衛）")
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


def _extract_json_text(text: str):
    """嘗試從回傳文字抓出第一個 JSON 物件或陣列字串"""
    if not text:
        return None
    # 只抓最外層 {} 或 []
    # 注意這個簡單版本不支援完全任意深度嵌套，但通常 Gemini 回傳沒問題
    start = text.find('{')
    end = text.rfind('}')
    if start != -1 and end != -1 and end > start:
        return text[start:end+1]
    # 嘗試陣列形式
    start = text.find('[')
    end = text.rfind(']')
    if start != -1 and end != -1 and end > start:
        return text[start:end+1]
    return None



def _normalize_value(val):
    """把單一欄位的解析結果轉成整數或區間 dict"""
    if val is None:
        return None
    # 若已是數字型態
    if isinstance(val, (int, float)):
        return int(val)
    s = str(val).strip()
    if s == '':
        return None
    # 常見的 range 表示法 "1-3"
    m = re.match(r'^\s*(\d+)\s*[-~–]\s*(\d+)\s*$', s)
    if m:
        return {"min": int(m.group(1)), "max": int(m.group(2))}
    # "3以上" 或 ">=3" 或 "3+" -> min
    m = re.search(r'(\d+)\s*(以上|\+|>=)', s)
    if m:
        return {"min": int(m.group(1))}
    # "3以下" 或 "<=3" -> max
    m = re.search(r'(以下|<=)\s*(\d+)', s)
    if m:
        return {"max": int(m.group(2))}
    # 單一數字
    m = re.match(r'^\s*(\d+)\s*$', s)
    if m:
        return int(m.group(1))
    # 標籤式：低樓層 / 高樓層
    if '低' in s:
        return {"min": 1, "max": 5}
    if '高' in s:
        return {"min": 6}
    # 若是文字描述（ex: "2房"、"三房"），嘗試抽數字
    m = re.search(r'(\d+)', s)
    if m:
        return int(m.group(1))
    # 無法解析就回 None
    return None

def _normalize_parsed_req(parsed: dict):
    """把 Gemini 回傳的欄位（可能是中文或英文）轉成我們要的 keys"""
    if not parsed or not isinstance(parsed, dict):
        return {}

    out = {}
    # 支援中/英欄位名
    keymap = {
        "房間數": "rooms", "rooms": "rooms", "房間": "rooms", "臥室": "rooms",
        "廳數": "living_rooms", "廳": "living_rooms", "living_rooms": "living_rooms",
        "衛數": "bathrooms", "衛": "bathrooms", "bathrooms": "bathrooms",
        #"樓層": "floor", "floor": "floor"
    }

    for k, v in parsed.items():
        if not k:
            continue
        k_strip = k.strip()
        target = keymap.get(k_strip)
        if not target:
            # 嘗試英文小寫
            target = keymap.get(k_strip.lower())
        if not target:
            continue
        normalized = _normalize_value(v)
        if normalized is not None:
            out[target] = normalized

    return out

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

        # ===== 解析格局欄位 =====
        import re
        def parse_layout(layout_str):
            if not isinstance(layout_str, str):
                return {"房間數": None, "廳數": None, "衛數": None}
            m = re.match(r'(\d+)房(\d+)廳(\d+)衛', layout_str)
            if m:
                return {"房間數": int(m.group(1)),
                        "廳數": int(m.group(2)),
                        "衛數": int(m.group(3))}
            else:
                nums = re.findall(r'(\d+)', layout_str)
                return {
                    "房間數": int(nums[0]) if len(nums) > 0 else None,
                    "廳數": int(nums[1]) if len(nums) > 1 else None,
                    "衛數": int(nums[2]) if len(nums) > 2 else None
                }

        parsed_layout = df['格局'].apply(parse_layout)
        df['房間數'] = parsed_layout.apply(lambda x: x['房間數'])
        df['廳數'] = parsed_layout.apply(lambda x: x['廳數'])
        df['衛數'] = parsed_layout.apply(lambda x: x['衛數'])

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

        # ===== Gemini 特殊要求解析 =====
        parsed_req = {}
        gemini_key = st.session_state.get("GEMINI_KEY", "")
        if Special_Requests.strip() and gemini_key:
            try:
                import google.generativeai as genai
                genai.configure(api_key=gemini_key)
                model = genai.GenerativeModel("gemini-2.0-flash")
                prompt = f"""
                請將下列房產需求解析為**純 JSON**（不要任何說明文字，只回傳 JSON）：
                \"\"\"{Special_Requests}\"\"\"
                JSON 欄位請包含（若無則省略）：房間數、廳數、衛數、樓層。
                範例輸出：
                {{
                  "房間數": 2,
                  "廳數": 1,
                  "衛數": 1,
                  "樓層": {{"min": 1, "max": 5}}
                }}
                注意：請使用英文冒號和逗號，並確保回傳能被機器解析（valid JSON）。
                """
                response = model.generate_content(prompt)
                resp_text = (response.text or "").strip()
                with st.expander("🔎 Gemini 回傳（debug）", expanded=False):
                    st.code(resp_text)

                # 嘗試解析 JSON
                import json
                def extract_json(text):
                    start = text.find('{')
                    end = text.rfind('}')
                    if start != -1 and end != -1:
                        return text[start:end+1]
                    return None

                parsed_obj = None
                try:
                    parsed_obj = json.loads(resp_text)
                except Exception:
                    json_text = extract_json(resp_text)
                    if json_text:
                        try:
                            parsed_obj = json.loads(json_text.replace('：', ':').replace('，', ','))
                        except Exception:
                            parsed_obj = None

                # 標準化 key
                def normalize_parsed(parsed):
                    keymap = {
                        "房間數": "rooms", "rooms": "rooms", "房間": "rooms", "臥室": "rooms",
                        "廳數": "living_rooms", "廳": "living_rooms", "living_rooms": "living_rooms",
                        "衛數": "bathrooms", "衛": "bathrooms", "bathrooms": "bathrooms",
                        "樓層": "floor", "floor": "floor"
                    }
                    out = {}
                    if not parsed or not isinstance(parsed, dict):
                        return out
                    for k, v in parsed.items():
                        target = keymap.get(k.strip()) or keymap.get(str(k).strip().lower())
                        if not target:
                            continue
                        # 解析值
                        def norm_val(val):
                            if val is None:
                                return None
                            if isinstance(val, (int, float)):
                                return int(val)
                            s = str(val).strip()
                            import re
                            m = re.match(r'(\d+)[-~–](\d+)', s)
                            if m:
                                return {"min": int(m.group(1)), "max": int(m.group(2))}
                            m = re.search(r'(\d+)\s*(以上|\+|>=)', s)
                            if m:
                                return {"min": int(m.group(1))}
                            m = re.search(r'(以下|<=)\s*(\d+)', s)
                            if m:
                                return {"max": int(m.group(2))}
                            m = re.match(r'(\d+)', s)
                            if m:
                                return int(m.group(1))
                            if '低' in s:
                                return {"min": 1, "max": 5}
                            if '高' in s:
                                return {"min": 6}
                            return None
                        normed = norm_val(v)
                        if normed is not None:
                            out[target] = normed
                    return out

                parsed_req = normalize_parsed(parsed_obj)

            except Exception as e:
                st.error(f"❌ Gemini 解析特殊要求失敗: {e}")
                parsed_req = {}

        # 合併 Gemini 篩選條件
        filters.update(parsed_req)

        # ===== 執行篩選 =====
        from utils import filter_properties
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
