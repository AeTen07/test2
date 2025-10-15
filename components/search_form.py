import streamlit as st
import os
import pandas as pd
from utils import get_city_options, filter_properties

def render_search_form():
    """
    渲染搜尋表單並處理提交邏輯
    """
    with st.form("property_requirements"):
        st.subheader("📍 房產篩選條件")
        
        housetype = ["不限", "大樓", "華廈", "公寓", "套房", "透天", "店面", "辦公", "別墅", "倉庫", "廠房", "土地", "單售車位", "其它"]
        options = get_city_options()
        col1, col2 = st.columns([1, 1])
        with col1:
            # 下拉選單
            selected_label = st.selectbox("請選擇城市：", list(options.keys()))
            housetype_change = st.selectbox("請選擇房產類別：", housetype, key="housetype")
                     
            
        with col2:
            # 選擇預算上限
            budget_max = st.number_input(
                "💰預算上限(萬)",
                min_value=0,
                max_value=1000000,
                value=1000000,  # 預設值
                step=100      # 每次 + 或 - 的數值
            )
            
            # 選擇預算下限
            budget_min = st.number_input(
                "💰預算下限(萬)",
                min_value=0,
                max_value=1000000,
                value=0,  # 預設值
                step=100      # 每次 + 或 - 的數值
            )
            
            # 驗證預算範圍
            if budget_min > budget_max and budget_max > 0:
                st.error("⚠️ 預算下限不能大於上限！")

        st.subheader("🎯房產要求細項")
        col1, col2, col3 = st.columns([1, 1, 1])
        with col1:
            # 選擇屋齡範圍
            age_max = st.number_input(
                "屋齡上限",
                min_value=0,
                max_value=100,
                value=100,  # 預設值
                step=1      # 每次 + 或 - 的數值
            )
            age_min = st.number_input(
                "屋齡下限",
                min_value=0,
                max_value=100,
                value=0,  # 預設值
                step=1      # 每次 + 或 - 的數值
            )
            
            # 驗證屋齡範圍
            if age_min > age_max:
                st.error("⚠️ 屋齡下限不能大於上限！")
                
        with col2:
            # 選擇建坪上限
            area_max = st.number_input(
                "建坪上限",
                min_value=0,
                max_value=1000,
                value=1000,  # 預設值
                step=10      # 每次 + 或 - 的數值
            )
            area_min = st.number_input(
                "建坪下限",
                min_value=0,
                max_value=1000,
                value=0,  # 預設值
                step=10      # 每次 + 或 - 的數值
            )
            
            # 驗證建坪範圍
            if area_min > area_max:
                st.error("⚠️ 建坪下限不能大於上限！")
                
        with col3:
            car_grip = st.selectbox("🅿️車位選擇", ["不限", "需要","不要"], key="car_grip")
        
        st.subheader("🛠️特殊要求")
        Special_Requests = st.text_area("請輸入您的需求", placeholder="輸入文字...")
        # 提交按鈕
        col1, col2, col3, col4, col5 = st.columns([1, 1, 1, 1, 1])
        with col3:
            submit = st.form_submit_button("搜尋", use_container_width=True)
        
        # 只有按下按鈕才會執行
        if submit:
            return handle_search_submit(
                selected_label, options, housetype_change,
                budget_min, budget_max, age_min, age_max,
                area_min, area_max, car_grip
            )
    
    return None

def handle_search_submit(selected_label, options, housetype_change,
                        budget_min, budget_max, age_min, age_max,
                        area_min, area_max, car_grip):
    """
    處理搜尋表單提交
    """
    # 驗證輸入
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
    
    if valid_input:
        # 重置搜尋頁面到第一頁
        st.session_state.current_search_page = 1
        selected_file = options[selected_label]
        file_path = os.path.join("./Data", selected_file)
        
        try:
            # 讀取 CSV 檔案
            df = pd.read_csv(file_path)
            
            # 準備篩選條件
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
            
            # 執行篩選
            filtered_df = filter_properties(df, filters)
            
            # 儲存篩選後的資料到 session state
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
            
            # 顯示篩選結果統計
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
