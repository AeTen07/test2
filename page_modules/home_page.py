import streamlit as st

def render_home_page():
    """
    渲染首頁內容
    """
    st.title("🏠AI購屋分析")
    st.write("👋歡迎來到房地產分析系統")
    st.write("以下是使用說明：")

    col1, col2 = st.columns(2)

    with col1:
        # 左上表單
        with st.form("search"):
            st.subheader("🔍 搜尋頁面")
            st.write("第一步：阿對對對 就是這樣 嗯嗯嗯 沒錯沒錯")
            search_bt = st.form_submit_button("開始")
            if search_bt:
                st.session_state.current_page = 'search'

        # 左下表單
        with st.form("form2"):
            st.subheader("表單 2")
            submit2 = st.form_submit_button("提交")
            if submit2:
                st.write("施工中...")

    with col2:
        # 右上表單
        with st.form("analysis"):
            st.subheader("📊 分析頁面")
            st.write("第二步：阿對對對 就是這樣 嗯嗯嗯 沒錯沒錯")
            analysis_bt = st.form_submit_button("開始")
            if analysis_bt:
                st.session_state.current_page = 'analysis'

        # 右下表單
        with st.form("form4"):
            st.subheader("表單 4")
            submit4 = st.form_submit_button("提交")
            if submit4:
                st.write("施工中...")
