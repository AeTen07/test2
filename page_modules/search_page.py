import streamlit as st
from components.search_form import render_search_form
from components.property_list import render_property_list

def render_search_page():
    """
    渲染搜尋頁面
    """
    st.title("🔍 搜尋頁面")
    
    # 渲染搜尋表單
    render_search_form()
    
    # 顯示搜尋結果和分頁
    render_property_list()
