import os
import pandas as pd
import math
import streamlit as st

import os

def get_city_options(data_dir="./Data"):
    """
    獲取城市選項，只顯示對照表內有定義的檔案
    """
    if not os.path.exists(data_dir):
        return {}

    # 對照表：英文檔名 -> 中文名稱
    name_map = {
        "Taichung-city_buy_properties.csv": "台中市",
        "Taipei-city_buy_properties.csv": "台北市"
        

        # 可以繼續加其他城市
    }

    # 讀取資料夾中的檔案
    files = [f for f in os.listdir(data_dir) if f.endswith(".csv")]

    # 只挑出有對照表的檔案
    options = {name_map[f]: f for f in files if f in name_map}

    # 排序（照中文名稱）
    options = dict(sorted(options.items(), key=lambda x: x[0]))

    return options


def filter_properties(df, filters):
    """
    根據篩選條件過濾房產資料（支援模糊搜尋類型）
    """
    filtered_df = df.copy()
    
    try:
        # 🔑 房產類型篩選（模糊搜尋）
        if filters['housetype'] != "不限":
            if '類型' in filtered_df.columns:
                filtered_df = filtered_df[
                    filtered_df['類型'].astype(str).str.contains(filters['housetype'], case=False, na=False)
                ]
        
        # 預算篩選（總價萬元）
        if filters['budget_min'] > 0:
            filtered_df = filtered_df[filtered_df['總價(萬)'] >= filters['budget_min']]
        if filters['budget_max'] < 1000000:
            filtered_df = filtered_df[filtered_df['總價(萬)'] <= filters['budget_max']]
        
        # 屋齡篩選
        if filters['age_min'] > 0:
            filtered_df = filtered_df[filtered_df['屋齡'] >= filters['age_min']]
        if filters['age_max'] < 100:
            filtered_df = filtered_df[filtered_df['屋齡'] <= filters['age_max']]
        
        # 建坪篩選
        if filters['area_min'] > 0:
            filtered_df = filtered_df[filtered_df['建坪'] >= filters['area_min']]
        if filters['area_max'] < 1000:
            filtered_df = filtered_df[filtered_df['建坪'] <= filters['area_max']]
        
        # 車位篩選
        if filters['car_grip'] == "需要":
            if '車位' in filtered_df.columns:
                filtered_df = filtered_df[
                    (filtered_df['車位'].notna()) & 
                    (filtered_df['車位'] != "無") & 
                    (filtered_df['車位'] != 0)
                ]
        elif filters['car_grip'] == "不要":
            if '車位' in filtered_df.columns:
                filtered_df = filtered_df[
                    (filtered_df['車位'].isna()) | 
                    (filtered_df['車位'] == "無") | 
                    (filtered_df['車位'] == 0)
                ]
        
    except Exception as e:
        st.error(f"篩選過程中發生錯誤: {e}")
        return df
    
    return filtered_df

def display_pagination(df, items_per_page=10):
    """
    處理分頁邏輯並返回當前頁面的資料
    """
    # 初始化頁面狀態
    if 'current_search_page' not in st.session_state:
        st.session_state.current_search_page = 1
    
    total_items = len(df)
    total_pages = math.ceil(total_items / items_per_page) if total_items > 0 else 1
    
    # 確保頁面數在有效範圍內
    if st.session_state.current_search_page > total_pages:
        st.session_state.current_search_page = 1
    
    # 計算當前頁面的資料範圍
    start_idx = (st.session_state.current_search_page - 1) * items_per_page
    end_idx = min(start_idx + items_per_page, total_items)
    
    current_page_data = df.iloc[start_idx:end_idx]
    
    return current_page_data, st.session_state.current_search_page, total_pages, total_items



