import streamlit as st
from sidebar import render_sidebar
from page_modules.home_page import render_home_page
from page_modules.search_page import render_search_page
from page_modules.analysis_page import render_analysis_page

def main():
#主應用程式入口

    st.set_page_config(layout="wide")
    
    # 初始化頁面狀態
    if 'current_page' not in st.session_state:
        st.session_state.current_page = 'home'
    # 渲染側邊欄
    render_sidebar()
    
    # 頁面路由
    if st.session_state.current_page == 'home':
        render_home_page()
    elif st.session_state.current_page == 'search':
        render_search_page()
    elif st.session_state.current_page == 'analysis':

     render_analysis_page()
    elif st.session_state.current_page == 'compare':
        render_compare_page()

if __name__ == "__main__":
    main()
