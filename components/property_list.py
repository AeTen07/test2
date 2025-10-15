import streamlit as st
import pandas as pd
from utils import display_pagination

def render_property_list():
    """
    渲染房產列表和分頁功能
    """
    # 初始化收藏
    if 'favorites' not in st.session_state:
        st.session_state.favorites = set()
        
    if 'filtered_df' not in st.session_state or st.session_state.filtered_df.empty:
        return
    
    df = st.session_state.filtered_df
    search_params = st.session_state.search_params
    
    # 使用分頁功能
    current_page_data, current_page, total_pages, total_items = display_pagination(df, items_per_page=10)
    
    # 顯示結果統計和篩選條件
    st.subheader(f"🏠 {search_params['city']}房產列表")
    
    # 顯示當前頁面的資料
    for idx, (index, row) in enumerate(current_page_data.iterrows()):
        render_property_card(row, current_page, idx)
    
    # 渲染分頁控制按鈕
    render_pagination_controls(current_page, total_pages, total_items)

def render_property_card(row, current_page, idx):
    """
    渲染單個房產卡片
    """
    with st.container():
        # 計算全域索引
        global_idx = (current_page - 1) * 10 + idx + 1
        
        # 標題與指標
        col1, col2, col3, col4 = st.columns([7, 1, 1, 2])
        with col1:
            st.subheader(f"#{global_idx} 🏠 {row['標題']}")    
            st.write(f"**地址：** {row['地址']} | **屋齡：** {row['屋齡']} | **類型：** {row['類型']}")
            st.write(f"**建坪：** {row['建坪']} | **主+陽：** {row['主+陽']} | **格局：** {row['格局']} | **樓層：** {row['樓層']}")
            # 如果有車位資訊就顯示
            if '車位' in row and pd.notna(row['車位']):
                st.write(f"**車位：** {row['車位']}")
        with col4:
            st.metric("Price(NT$)", f"${int(row['總價(萬)'] * 10):,}K")
            # 計算單價（每坪）
            if pd.notna(row['建坪']) and row['建坪'] > 0:
                unit_price = (row['總價(萬)'] * 10000) / row['建坪']
                st.caption(f"單價: ${unit_price:,.0f}/坪")

        
        col1, col2, col3, col4, col5, col6, col7 = st.columns([1, 1, 1, 1, 1, 1, 1])
        with col1:
            property_id = row['編號']
            is_fav = property_id in st.session_state.favorites
            if st.button("✅ 已收藏" if is_fav else "⭐ 收藏", key=f"fav_{property_id}"):
                if is_fav:
                    st.session_state.favorites.remove(property_id)
                else:
                    st.session_state.favorites.add(property_id)
                st.rerun()  # 立即刷新畫面

        with col7:
            property_url = f"https://www.sinyi.com.tw/buy/house/{row['編號']}?breadcrumb=list"
            st.markdown(
                f'<a href="{property_url}" target="_blank">'
                f'<button style="padding:5px 10px;">Property Link</button></a>',
                unsafe_allow_html=True
            )

        st.markdown("---")

def render_pagination_controls(current_page, total_pages, total_items):
    """
    渲染分頁控制按鈕
    """
    if total_pages <= 1:
        return
        
    col1, col2, col3, col4, col5 = st.columns([1, 1, 2, 1, 1])
    
    with col1:
        if st.button("⏮️ 第一頁", disabled=(current_page == 1)):
            st.session_state.current_search_page = 1
            st.rerun()
    
    with col2:
        if st.button("⏪ 上一頁", disabled=(current_page == 1)):
            st.session_state.current_search_page = max(1, current_page - 1)
            st.rerun()
    
    with col3:
        # 頁面跳轉選擇器
        new_page = st.selectbox(
            "",
            range(1, total_pages + 1),
            index=current_page - 1,
            key="page_selector"
        )
        if new_page != current_page:
            st.session_state.current_search_page = new_page
            st.rerun()
    
    with col4:
        if st.button("下一頁 ⏩", disabled=(current_page == total_pages)):
            st.session_state.current_search_page = min(total_pages, current_page + 1)
            st.rerun()
    
    with col5:
        if st.button("最後一頁 ⏭️", disabled=(current_page == total_pages)):
            st.session_state.current_search_page = total_pages
            st.rerun()
    
    # 顯示頁面資訊
    st.info(f"📄 第 {current_page} 頁，共 {total_pages} 頁 | 顯示第 {(current_page-1)*10+1} - {min(current_page*10, total_items)} 筆資料")
