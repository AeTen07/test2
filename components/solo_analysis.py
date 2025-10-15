import streamlit as st
import pandas as pd
import google.generativeai as genai
import hnswlib
from sentence_transformers import SentenceTransformer
import os
import numpy as np

# 在檔案開頭,name_map 下方加入反向對照表
name_map = {
    "Taichung-city_buy_properties.csv": "台中市",
    "Taipei-city_buy_properties.csv": "台北市"
}

# 建立反向對照表:中文 -> 英文檔名
reverse_name_map = {v: k for k, v in name_map.items()}

def get_favorites_data():
    """取得收藏房產的資料"""
    if 'favorites' not in st.session_state or not st.session_state.favorites:
        return pd.DataFrame()
    
    all_df = None
    if 'all_properties_df' in st.session_state and not st.session_state.all_properties_df.empty:
        all_df = st.session_state.all_properties_df
    elif 'filtered_df' in st.session_state and not st.session_state.filtered_df.empty:
        all_df = st.session_state.filtered_df
    
    if all_df is None or all_df.empty:
        return pd.DataFrame()
    
    fav_ids = st.session_state.favorites
    fav_df = all_df[all_df['編號'].isin(fav_ids)].copy()
    return fav_df

def tab1_module():
    fav_df = get_favorites_data()
    if fav_df.empty:
            st.header("個別分析")
            st.info("⭐ 尚未有收藏房產，無法比較")
    else:
        options = fav_df['標題']
        col1, col2 = st.columns([2, 1])
        with col1:
            st.header("個別分析")
        with col2:
            choice = st.selectbox("選擇房屋", options, key="analysis_solo")
        # 篩選出選中的房子
        selected_row = fav_df[fav_df['標題'] == choice].iloc[0]

        # 顯示卡片，標題直排，詳細資訊橫排
        st.markdown(f"""
        <div style="
            border:2px solid #4CAF50;
            border-radius:10px;
            padding:10px;
            background-color:#1f1f1f;
            text-align:center;
            color:white;
        ">
            <div style="font-size:40px; font-weight:bold;">{selected_row.get('標題','未提供')}</div>
            <div style="font-size:20px;">📍 {selected_row.get('地址','未提供')}</div>
        </div>
        """, unsafe_allow_html=True)

        st.write("\n")
        # 取得總價，並處理格式
        raw_price = selected_row.get('總價(萬)')
        if raw_price is None or raw_price == '' or raw_price == '未提供':
            formatted_price = '未提供'
        else:
            try:
                # 轉成數字後加上萬單位後的0，並加逗號
                formatted_price = f"{int(raw_price)*10000:,}"  # 乘 10000，把萬轉成元，並加逗號
            except:
                formatted_price = raw_price

        # 先處理建坪文字
        area = selected_row.get('建坪', '未提供')
        area_text = f"{area} 坪" if area != '未提供' else area
        
        # 先處理坪數文字
        Actual_space = selected_row.get('主+陽', '未提供')
        Actual_space_text = f"{Actual_space} 坪" if Actual_space != '未提供' else Actual_space

        #建坪單價/實際單價
        total_price = int(raw_price) * 10000
        area_Price_per = f"{int(total_price)/area:,.0f}"
        Actual_space_Price_per = f"{int(total_price)/Actual_space:,.0f}"
        
        col1, col2 = st.columns([1, 1])
        with col1:
            st.markdown(f"""
            <div style="
                border:2px solid #4CAF50;
                border-radius:10px;
                padding:10px;
                background-color:#1f1f1f;
                text-align:left;
                font-size:20px;
                color:white;
            ">
                <div> 類型：{selected_row.get('類型','未提供')}</div>
                <div> 建坪：{area_text}</div>
                <div> 實際坪數：{Actual_space_text}</div>
                <div> 格局：{selected_row.get('格局','未提供')}</div>
                <div> 樓層：{selected_row.get('樓層','未提供')}</div>
                <div> 屋齡：{selected_row.get('屋齡','未提供')}</div>
                <div> 車位：{selected_row.get('車位','未提供')}</div>
            </div>
            """, unsafe_allow_html=True)
            st.write("\n")
            analyze_clicked = st.button("開始分析", use_container_width=True, key="solo_analysis_button")
        with col2:
            st.markdown(f"""
            <div style="
                border:2px solid #4CAF50;
                border-radius:10px;
                padding:10px;
                background-color:#1f1f1f;
                text-align:center;
                font-size:30px;
                color:white;
                min-height:247px;
                display:flex;
                flex-direction:column;  /* 垂直排列 */
                justify-content:center;
            ">
                <div>💰 總價：{formatted_price} 元</div>
                <div style="font-size:14px; color:#cccccc; margin-top:5px;">
                    建坪單價：{area_Price_per} 元/坪
                </div>
                <div style="font-size:14px; color:#cccccc; margin-top:5px;">
                    實際單價：{Actual_space_Price_per} 元/坪
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            st.write("\n")
            chart_clicked = st.button("可視化圖表分析", use_container_width=True, key="chart_analysis_button")
            
        gemini_key = st.session_state.get("GEMINI_KEY","")

        if analyze_clicked:
            if not gemini_key:
                st.error("❌ 右側 gemini API Key 有誤")
                st.stop()
            try:
                genai.configure(api_key=gemini_key)
                model = genai.GenerativeModel("gemini-2.0-flash")

                address = selected_row.get('地址')
                city = address[:3]
                
                # 轉換成英文檔名
                english_filename = reverse_name_map.get(city)
                file_path = os.path.join("./Data", english_filename)
                
                # 讀取 CSV 檔案
                df = pd.read_csv(file_path)
                house_title = str(selected_row.get('標題','')).strip()
                # 根據標題篩選房型
                selected_row = df[df['標題'] == house_title].iloc[0]

                embed_model = SentenceTransformer('all-MiniLM-L6-v2')
                with st.spinner("正在將資料進行向量化處理..."):
                    def row_to_text(row):
                        """將每列資料轉為文字描述"""
                        return (
                            f"地址:{row['地址']}, 建坪:{row['建坪']}, 主+陽:{row['主+陽']}, "
                            f"總價:{row['總價(萬)']}萬, 屋齡:{row['屋齡']}, 類型:{row['類型']}, "
                            f"格局:{row['格局']}, 樓層:{row['樓層']}, 車位:{row['車位']}"
                        )
                    texts = df.apply(row_to_text, axis=1).tolist()
                    embeddings = embed_model.encode(texts, show_progress_bar=True)
                    embeddings = np.array(embeddings).astype('float32')
    
                    dimension = embeddings.shape[1]
                    num_elements = len(embeddings)
                    
                    # 初始化索引
                    index = hnswlib.Index(space='l2', dim=dimension)
                    
                    # 建立索引（ef_construction 越大越精確但越慢）
                    index.init_index(max_elements=num_elements, ef_construction=200, M=16)
    
                    index.add_items(embeddings, np.arange(num_elements))
                    
                    # 設定查詢參數（ef 越大越精確）
                    index.set_ef(50)
    
                    # 找到選中房屋的索引
                    selected_idx = df[df['標題'] == house_title].index[0]
                    selected_text = row_to_text(selected_row)
                    query_vec = embeddings[selected_idx:selected_idx+1]
                    
                    # 查詢相似房屋（包含自己，所以查 11 筆）
                    top_k = 11
                    labels, distances = index.knn_query(query_vec, k=top_k)
    
                    # 取得相似房屋資料（過濾掉自己）
                    relevant_data = []
                    for i, (idx, dist) in enumerate(zip(labels[0], distances[0])):
                        if idx != selected_idx:
                            house_data = df.iloc[idx].to_dict()
                            relevant_data.append(house_data)
                    
                    # 準備文字輸入
                    selected_text_display = f"{selected_row['標題']} - {selected_text}"
                    relevant_text = "\n".join([f"{r['標題']} - {row_to_text(r)}" for r in relevant_data])
                    
                    # 組合提示詞
                    prompt = f"""
                    你是一位台灣不動產市場專家，具有多年房屋估價與市場分析經驗。
                    請根據以下房屋資料生成中文市場分析：
                    
                    目標房型：
                    {selected_text_display}
                    
                    相似房屋資料：
                    {relevant_text}
                    
                    請分析價格合理性、坪數與屋齡，提供購買建議，避免編造不存在的數字。
                    """
                
                with st.spinner("Gemini 正在分析中..."):
                    response = model.generate_content(prompt)
        
                st.success("✅ 分析完成")
                st.markdown("### 🧠 **Gemini 市場分析結果**")
                
                # 顯示 Gemini 分析結果
                st.markdown(response.text)
                
                with st.expander("相似房型資料"):
                    if relevant_data:
                        # 將 list of dict 轉成 DataFrame
                        similar_df = pd.DataFrame(relevant_data)
                        
                        # 可以選擇只顯示特定欄位，或重新命名欄位
                        display_cols = ['標題', '地址', '建坪', '主+陽', '總價(萬)', '屋齡', '類型', '格局', '樓層', '車位']
                        similar_df = similar_df[display_cols]
                        
                        # 顯示 DataFrame
                        st.dataframe(similar_df)
                    else:
                        st.write("沒有找到相似房型")

            except Exception as e:
                st.error(f"❌ 分析過程發生錯誤：{e}")
        if chart_clicked:
            st.write("施工中...")




            
