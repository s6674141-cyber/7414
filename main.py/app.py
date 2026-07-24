import pandas as pd
from datetime import datetime
import streamlit as st
import matplotlib.pyplot as plt
import gspread
from google.oauth2.service_account import Credentials
import re
import plotly.express as px
import plotly.graph_objects as go
from groq import Groq

# -------------------------------------------------------------------
# 0. 頁面基本設定 (RWD 手機版優化)
# -------------------------------------------------------------------
plt.rcParams['font.sans-serif'] = ['Microsoft JhengHei', 'PingFang TC', 'Arial Unicode MS', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

st.set_page_config(
    page_title="ProStock 雲端倉管與 AI BI 決策系統",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="auto"
)

# -------------------------------------------------------------------
# 🎨 UI / RWD CSS (大卡片、防誤觸按鈕與固定底欄)
# -------------------------------------------------------------------
custom_css = """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

    html, body, [class*="css"] {
        font-family: 'Inter', 'Microsoft JhengHei', sans-serif;
    }

    .stApp {
        background-color: #F8F9FA;
    }

    [data-testid="stAppDeployButton"], 
    #MainMenu, 
    footer {
        visibility: hidden !important;
        display: none !important;
    }

    [data-testid="stHeader"] {
        background-color: transparent !important;
    }

    section[data-testid="stSidebar"] {
        background-color: #1E293B !important;
    }
    section[data-testid="stSidebar"] .stMarkdown p,
    section[data-testid="stSidebar"] label,
    section[data-testid="stSidebar"] span,
    section[data-testid="stSidebar"] div {
        color: #F8FAFC !important;
        font-weight: 500 !important;
    }
    section[data-testid="stSidebar"] .stCaption {
        color: #CBD5E1 !important;
    }
    section[data-testid="stSidebar"] h1, 
    section[data-testid="stSidebar"] h2, 
    section[data-testid="stSidebar"] h3 {
        color: #FFFFFF !important;
        font-weight: 700 !important;
    }

    /* 📱 現場防誤觸大按鈕 */
    .stButton>button {
        border-radius: 8px !important;
        font-weight: 600 !important;
        transition: all 0.2s ease-in-out !important;
        border: none !important;
        min-height: 44px !important;
    }
    .stButton>button[kind="primary"] {
        background: linear-gradient(135deg, #2563EB 0%, #1D4ED8 100%) !important;
        color: white !important;
        box-shadow: 0 2px 4px rgba(37, 99, 235, 0.2) !important;
    }

    /* 📦 RWD 大卡片樣式 */
    .material-card {
        background-color: #FFFFFF;
        border-radius: 12px;
        padding: 16px;
        margin-bottom: 10px;
        box-shadow: 0 2px 6px rgba(0,0,0,0.04);
        border: 1px solid #E2E8F0;
    }

    .badge {
        display: inline-block;
        background-color: #EFF6FF;
        color: #1D4ED8;
        font-size: 13px;
        font-weight: 600;
        padding: 2px 8px;
        border-radius: 6px;
        margin-right: 6px;
    }

    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        background-color: #E2E8F0;
        padding: 6px;
        border-radius: 10px;
    }
    .stTabs [aria-selected="true"] {
        background-color: #FFFFFF !important;
        color: #0F172A !important;
        font-weight: 600;
    }

    [data-testid="stDataFrame"] {
        border: 1px solid #E2E8F0;
        border-radius: 8px;
    }
    </style>
"""
st.markdown(custom_css, unsafe_allow_html=True)

# -------------------------------------------------------------------
# 1. Google Sheets 雲端資料庫連線邏輯
# -------------------------------------------------------------------
@st.cache_resource
def get_gsheet_client():
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    credentials_info = st.secrets["gcp_service_account"]
    creds = Credentials.from_service_account_info(credentials_info, scopes=scope)
    return gspread.authorize(creds)

def load_data(worksheet_name):
    try:
        client = get_gsheet_client()
        sheet = client.open("水電倉管資料庫").worksheet(worksheet_name)
        data = sheet.get_all_records()
        return pd.DataFrame(data), sheet
    except Exception as e:
        if worksheet_name == "projects":
            try:
                client = get_gsheet_client()
                spreadsheet = client.open("水電倉管資料庫")
                sheet = spreadsheet.add_worksheet(title="projects", rows="100", cols="10")
                headers = ["工程案編號", "工程案名稱", "客戶名稱", "材料總預算", "開工日期", "狀態"]
                sheet.append_row(headers)
                return pd.DataFrame(columns=headers), sheet
            except:
                return pd.DataFrame(), None
        return pd.DataFrame(), None

def save_data(sheet, df):
    sheet.clear()
    sheet.update([df.columns.values.tolist()] + df.astype(str).values.tolist())

def add_log_gsheet(action_type, item_name, detail, note=""):
    df_logs, sheet_logs = load_data("logs")
    if sheet_logs is not None:
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        new_log = {"時間": now_str, "類型": action_type, "項目名稱": item_name, "變動數量/借用人": detail, "備註": note}
        df_logs = pd.concat([df_logs, pd.DataFrame([new_log])], ignore_index=True)
        save_data(sheet_logs, df_logs)

def undo_last_log():
    df_logs, sheet_logs = load_data("logs")
    if df_logs.empty:
        return False, "目前沒有可撤銷的歷史紀錄！"
    
    last_log = df_logs.iloc[-1]
    action_type = str(last_log["類型"])
    item_name = str(last_log["項目名稱"])
    detail = str(last_log["變動數量/借用人"])
    
    if action_type in ["領料出庫", "進貨入庫"]:
        df_mat, sheet_mat = load_data("materials")
        if not df_mat.empty and item_name in df_mat["材料名稱"].astype(str).values:
            idx = df_mat[df_mat["材料名稱"].astype(str) == item_name].index[0]
            numbers = re.findall(r'\d+', detail)
            qty = int(numbers[0]) if numbers else 0
            if action_type == "領料出庫":
                df_mat.loc[idx, "目前庫存"] = pd.to_numeric(df_mat.loc[idx, "目前庫存"], errors='coerce') + qty
            else:
                df_mat.loc[idx, "目前庫存"] = max(0, pd.to_numeric(df_mat.loc[idx, "目前庫存"], errors='coerce') - qty)
            save_data(sheet_mat, df_mat)

    elif action_type == "新增品項":
        df_mat, sheet_mat = load_data("materials")
        if not df_mat.empty and item_name in df_mat["材料名稱"].astype(str).values:
            df_mat = df_mat[df_mat["材料名稱"].astype(str) != item_name].reset_index(drop=True)
            save_data(sheet_mat, df_mat)

    elif action_type in ["工具借出", "工具歸還", "工具送修", "維修完成"]:
        df_tools, sheet_tools = load_data("tools")
        if not df_tools.empty and item_name in df_tools["工具名稱"].astype(str).values:
            idx = df_tools[df_tools["工具名稱"].astype(str) == item_name].index[0]
            if action_type in ["工具借出", "維修完成"]:
                df_tools.loc[idx, "狀態"] = "在庫"
                df_tools.loc[idx, "當前借用人"] = "無"
                df_tools.loc[idx, "借出日期"] = "無"
            elif action_type == "工具歸還":
                df_tools.loc[idx, "狀態"] = "借出"
                df_tools.loc[idx, "當前借用人"] = detail
                df_tools.loc[idx, "借出日期"] = datetime.now().strftime("%Y-%m-%d")
            save_data(sheet_tools, df_tools)

    df_logs = df_logs.iloc[:-1].reset_index(drop=True)
    save_data(sheet_logs, df_logs)
    add_log_gsheet("撤銷操作", item_name, "反轉成功", f"已撤銷: {action_type} ({detail})")
    return True, f"✅ 已成功撤銷【{action_type} - {item_name}】！"

# -------------------------------------------------------------------
# 2. Session State 初始化 (身分 & 領料購物車)
# -------------------------------------------------------------------
if "is_admin" not in st.session_state:
    st.session_state.is_admin = False

if "cart" not in st.session_state:
    st.session_state.cart = {} # 購物車暫存: {mat_id: {"name":..., "qty":..., "unit":...}}

st.sidebar.markdown("### ⚡ ProStock 雲端倉管與 BI")
st.sidebar.caption("v5.0 RWD Mobile + Groq AI Assistant")
st.sidebar.markdown("---")

role = st.sidebar.radio("👤 使用者權限切換：", ["👷 現場作業員 (師傅)", "🔑 系統管理員"])

if role == "🔑 系統管理員":
    if not st.session_state.is_admin:
        pwd = st.sidebar.text_input("🔑 請輸入管理密碼", type="password")
        if pwd == "admin123":
            st.session_state.is_admin = True
            st.sidebar.success("🔓 解鎖成功")
            st.rerun()
        elif pwd != "":
            st.sidebar.error("❌ 密碼錯誤")
else:
    st.session_state.is_admin = False

st.sidebar.markdown("---")

if st.session_state.is_admin:
    st.sidebar.markdown("**核心模組選單**")
    menu_options = [
        "🤖 AI 經營決策助理",
        "📊 BI 經營決策儀表板",
        "🏗️ 工程案預算管理",
        "📦 材料庫存總覽", 
        "🔨 工具資產追蹤", 
        "📤 CSV 批次資料匯入", 
        "📜 雲端流水帳紀錄"
    ]
else:
    st.sidebar.markdown("**現場快速功能**")
    menu_options = [
        "📦 材料領用與進貨", 
        "🔨 工具借還與報修"
    ]

page = st.sidebar.radio("系統導覽：", menu_options, label_visibility="collapsed")

# -------------------------------------------------------------------
# 分頁 AI：🤖 AI 經營決策助理 (Groq LLaMA 3.1 極速版)
# -------------------------------------------------------------------
if page == "🤖 AI 經營決策助理" and st.session_state.is_admin:
    st.title("🤖 老闆專屬 AI 經營決策助理")
    st.caption("基於全公司實體倉管、專案預算與流水帳數據的即時 AI 決策諮詢 (Powered by Groq)")
    st.markdown("---")
    
    if "GROQ_API_KEY" not in st.secrets:
        st.error("⚠️ 未在 Secrets 中找到 `GROQ_API_KEY`，請完成設定以啟用 AI 助理。")
    else:
        api_key = st.secrets["GROQ_API_KEY"].strip()
        client = Groq(api_key=api_key)
        
        if "chat_messages" not in st.session_state:
            st.session_state.chat_messages = [
                {"role": "assistant", "content": "老闆您好！我是您的 AI 經營決策助理。您可以問我任何關於專案材料預算消化率、高價值耗材領用情況、工具設備維修 TCO 評估，或是 2025 全年金流趨勢的問題，我會為您做精準分析！"}
            ]
            
        for msg in st.session_state.chat_messages:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])
                
        if prompt := st.chat_input("請輸入您想詢問的經營數據問題 (例如: 高價值耗材領用情況)"):
            st.session_state.chat_messages.append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.markdown(prompt)
                
            with st.chat_message("assistant"):
                with st.spinner("🤖 AI 正在讀取並分析公司資料庫中..."):
                    try:
                        df_logs, _ = load_data("logs")
                        df_mat, _ = load_data("materials")
                        df_proj, _ = load_data("projects")
                        df_tools, _ = load_data("tools")
                        
                        mat_summary = df_mat[["材料名稱", "目前庫存", "安全庫存量", "單價"]].head(50).to_string() if not df_mat.empty else "無"
                        proj_summary = df_proj.to_string() if not df_proj.empty else "無"
                        tools_summary = df_tools[["工具名稱", "品牌/廠牌", "型號", "新機購入單價", "狀態"]].head(40).to_string() if not df_tools.empty else "無"
                        logs_sample = df_logs.tail(40).to_string() if not df_logs.empty else "無"
                        
                        system_prompt = f"""
                        你是一位專精於水電工程與倉管財務的 AI 經營顧問，正在為公司老闆解答經營疑難雜症。
                        請根據以下提供的公司【實體最新資料庫快照】進行思考與回答。請保持專業、精準、條理分明，並以繁體中文回答，附帶具體的經營建議。

                        【1. 工程專案預算清單】:
                        {proj_summary}

                        【2. 庫存與單價摘要】:
                        {mat_summary}

                        【3. 工具設備資產摘要】:
                        {tools_summary}

                        【4. 歷史流水帳摘要 (最近40筆)】:
                        {logs_sample}
                        """
                        
                        response = client.chat.completions.create(
                            model="llama-3.1-8b-instant",
                            messages=[
                                {"role": "system", "content": system_prompt},
                                {"role": "user", "content": prompt}
                            ],
                            temperature=0.3
                        )
                        
                        ai_reply = response.choices[0].message.content
                        st.markdown(ai_reply)
                        st.session_state.chat_messages.append({"role": "assistant", "content": ai_reply})
                    except Exception as e:
                        st.error(f"❌ AI 分析失敗：{e}")

# -------------------------------------------------------------------
# 分頁 A：📦 材料領用與進貨 (全新 RWD 手機版大卡片 + 加減盤)
# -------------------------------------------------------------------
elif page == "📦 材料領用與進貨":
    st.title("📱 現場極簡領料與進貨")
    st.caption("大卡片抗誤觸介面 ‧ 支援手機快速領料")
    st.markdown("---")
    
    df_mat, sheet_mat = load_data("materials")
    df_proj, _ = load_data("projects")
    
    proj_options = ["一般維修/未分類"]
    if not df_proj.empty and "工程案名稱" in df_proj.columns:
        proj_options = list(df_proj["工程案名稱"].dropna().unique())

    tab_borrow, tab_in = st.tabs(["📤 師傅快速領料 (大卡片)", "📥 廠商進貨登記"])

    # 📤 頁籤 1：RWD 大卡片領料
    with tab_borrow:
        if not df_mat.empty:
            df_mat["目前庫存"] = pd.to_numeric(df_mat["目前庫存"], errors='coerce').fillna(0).astype(int)
            
            # 1️⃣ 選擇專案與搜尋列
            proj_col, search_col = st.columns([1, 2])
            with proj_col:
                selected_proj = st.selectbox("👷 當前施工專案", proj_options)
            with search_col:
                search_mat = st.text_input("🔍 搜尋品名/規格/分類...", placeholder="例如: 電線, 6分, PVC...")

            # 2️⃣ 分類橫向快捷切換
            cat_list = ["全部"] + list(df_mat["分類"].dropna().unique()) if "分類" in df_mat.columns else ["全部"]
            selected_cat = st.radio("分類篩選", cat_list, horizontal=True, label_visibility="collapsed")

            filtered_mat = df_mat.copy()
            if selected_cat != "全部":
                filtered_mat = filtered_mat[filtered_mat["分類"] == selected_cat]
            if search_mat:
                s_term = search_mat.strip().lower()
                filtered_mat = filtered_mat[
                    filtered_mat["材料名稱"].astype(str).str.lower().str.contains(s_term) |
                    filtered_mat["規格/尺寸"].astype(str).str.lower().str.contains(s_term)
                ]

            st.markdown("---")

            # 3️⃣ 以「大卡片 (Cards)」渲染每個料件
            if filtered_mat.empty:
                st.info("🔍 沒有符合條件的材料")
            else:
                for idx, row in filtered_mat.iterrows():
                    m_id = str(row["材料編號"])
                    m_name = str(row["材料名稱"])
                    m_spec = str(row.get("規格/尺寸", "標準"))
                    m_cat = str(row.get("分類", "未分類"))
                    m_stock = int(row["目前庫存"])
                    m_unit = str(row.get("單位", "個"))
                    
                    # 卡片本體
                    st.markdown(f"""
                    <div class="material-card">
                        <div style="font-size: 18px; font-weight: 700; color: #0F172A;">📦 {m_name}</div>
                        <div style="margin-top: 6px;">
                            <span class="badge">#{m_spec}</span>
                            <span class="badge">#{m_cat}</span>
                        </div>
                        <div style="margin-top: 8px; font-size: 14px; color: #475569;">
                            剩餘庫存：<strong style="font-size: 16px; color: {'#059669' if m_stock > 5 else '#DC2626'};">{m_stock} {m_unit}</strong>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    # 漸進式揭露 & 加減按鈕 (列排版)
                    col_info, col_sub, col_add = st.columns([2, 1, 1])
                    
                    with col_info:
                        with st.expander("ℹ️ 詳細資訊"):
                            st.caption(f"🆔 編號：{m_id}")
                            st.caption(f"💰 單價：${row.get('單價', 0)}")

                    current_qty = st.session_state.cart.get(m_id, {}).get("qty", 0)

                    with col_sub:
                        if st.button("➖", key=f"sub_{m_id}", use_container_width=True):
                            if current_qty > 0:
                                st.session_state.cart[m_id]["qty"] -= 1
                                if st.session_state.cart[m_id]["qty"] == 0:
                                    del st.session_state.cart[m_id]
                                st.rerun()

                    with col_add:
                        if st.button(f"➕ ({current_qty})", key=f"add_{m_id}", type="primary", use_container_width=True):
                            if current_qty < m_stock:
                                if m_id not in st.session_state.cart:
                                    st.session_state.cart[m_id] = {"name": m_name, "qty": 1, "unit": m_unit, "stock_idx": idx}
                                else:
                                    st.session_state.cart[m_id]["qty"] += 1
                                st.rerun()
                            else:
                                st.toast(f"⚠️ 已達庫存上限 ({m_stock} {m_unit})")

            # 4️⃣ 🛒 領料結帳車明細 (Bottom Sheet 體驗)
            total_cart_items = sum([item["qty"] for item in st.session_state.cart.values()])
            if total_cart_items > 0:
                st.markdown("---")
                st.markdown("##### 🛒 領料清單核對 (Bottom Cart)")
                
                with st.expander(f"📋 已選擇 {total_cart_items} 項料件 (點擊展開結帳)", expanded=True):
                    for c_id, c_data in list(st.session_state.cart.items()):
                        st.write(f"• **{c_data['name']}** × {c_data['qty']} {c_data['unit']}")
                    
                    worker_name = st.text_input("👷 請輸入領用師傅姓名", placeholder="例如: 王大明")
                    
                    if st.button("🚀 確認領出 (一鍵扣抵庫存)", type="primary", use_container_width=True):
                        if worker_name:
                            # 執行批量扣抵庫存
                            for c_id, c_data in st.session_state.cart.items():
                                idx = c_data["stock_idx"]
                                take_qty = c_data["qty"]
                                df_mat.loc[idx, "目前庫存"] -= take_qty
                                note_text = f"{selected_proj} - 師傅:{worker_name}"
                                add_log_gsheet("領料出庫", c_data["name"], f"-{take_qty} {c_data['unit']}", note_text)
                            
                            save_data(sheet_mat, df_mat)
                            st.session_state.cart = {} # 清空購物車
                            st.success(f"✅ 成功領出料件！專案：{selected_proj}")
                            st.rerun()
                        else:
                            st.warning("⚠️ 請填寫師傅姓名以完成登記。")

    # 📥 頁籤 2：進貨登記
    with tab_in:
        st.markdown("##### 廠商補貨入庫作業")
        with st.form("emp_in_form"):
            selected_mat_in = st.selectbox("選擇進貨項目", df_mat["材料編號"].astype(str) + " - " + df_mat["材料名稱"], key="emp_in")
            in_qty = st.number_input("進貨數量", min_value=1, step=1, key="emp_in_q")
            vendor = st.text_input("進貨廠商 / 備註資訊")
            submit_in = st.form_submit_button("確認進貨入庫", type="primary")
            
            if submit_in:
                mat_id = selected_mat_in.split(" - ")[0]
                idx = df_mat[df_mat["材料編號"].astype(str) == mat_id].index[0]
                mat_name = df_mat.loc[idx, "材料名稱"]
                unit = df_mat.loc[idx, "單位"]
                
                df_mat.loc[idx, "目前庫存"] += in_qty
                save_data(sheet_mat, df_mat)
                add_log_gsheet("進貨入庫", mat_name, f"+{in_qty} {unit}", f"進貨廠商: {vendor}")
                st.success(f"✅ 成功入庫 [{mat_name}] {in_qty} {unit}！")
                st.rerun()

# -------------------------------------------------------------------
# 分頁 B：🔨 工具借還與報修 (一般員工)
# -------------------------------------------------------------------
elif page == "🔨 工具借還與報修":
    st.title("🔨 工具資產借還與維修登記")
    st.caption("高價值機具與公用工具狀態追蹤")
    st.markdown("---")
    
    df_tools, sheet_tools = load_data("tools")
    
    if not df_tools.empty:
        st.subheader("📋 設備當前借還與在庫動態")
        search_tool = st.text_input("🔍 快速搜尋工具：", placeholder="例如: KNIPEX, BAA0002, 壓著鉗...")
        
        filtered_tools = df_tools.copy()
        if search_tool:
            search_term = search_tool.strip().lower()
            filtered_tools = filtered_tools[
                filtered_tools["工具編號"].astype(str).str.lower().str.contains(search_term, na=False) |
                filtered_tools["工具名稱"].astype(str).str.lower().str.contains(search_term, na=False) |
                filtered_tools["品牌/廠牌"].astype(str).str.lower().str.contains(search_term, na=False) |
                filtered_tools["型號"].astype(str).str.lower().str.contains(search_term, na=False)
            ]
        
        st.dataframe(filtered_tools, use_container_width=True)
        st.markdown("<br>", unsafe_allow_html=True)
        
        tab_tb, tab_tr, tab_maint = st.tabs(["📤 工具借出登記", "📥 工具歸還登記", "🔧 故障報修 / 維修完工"])
        
        borrowed_df = df_tools[df_tools["狀態"] == "借出"]
        repairing_df = df_tools[df_tools["狀態"] == "維修中"]
        in_stock_tools = df_tools[df_tools["狀態"] == "在庫"]
        
        with tab_tb:
            if not in_stock_tools.empty:
                tool_to_borrow = st.selectbox("選擇在庫工具", in_stock_tools["工具編號"].astype(str) + " - " + in_stock_tools["工具名稱"])
                borrower_name = st.text_input("借用師傅姓名", key="emp_b_name")
                if st.button("確認借出設備", type="primary"):
                    if borrower_name:
                        t_id = tool_to_borrow.split(" - ")[0]
                        idx = df_tools[df_tools["工具編號"].astype(str) == t_id].index[0]
                        today_str = datetime.now().strftime("%Y-%m-%d")
                        
                        df_tools.loc[idx, "狀態"] = "借出"
                        df_tools.loc[idx, "當前借用人"] = borrower_name
                        df_tools.loc[idx, "借出日期"] = today_str
                        
                        save_data(sheet_tools, df_tools)
                        add_log_gsheet("工具借出", df_tools.loc[idx, "工具名稱"], borrower_name, f"借出日期: {today_str}")
                        st.success(f"✅ [{df_tools.loc[idx, '工具名稱']}] 已登記借予【{borrower_name}】")
                        st.rerun()
                    else:
                        st.warning("⚠️ 請填寫借用人姓名。")
            else:
                st.info("目前無可借出之在庫工具。")

        with tab_tr:
            if not borrowed_df.empty:
                tool_to_return = st.selectbox("選擇歸還工具", borrowed_df["工具編號"].astype(str) + " - " + borrowed_df["工具名稱"])
                if st.button("確認歸還入庫", type="primary"):
                    t_id = tool_to_return.split(" - ")[0]
                    idx = df_tools[df_tools["工具編號"].astype(str) == t_id].index[0]
                    b_name = df_tools.loc[idx, "當前借用人"]
                    
                    df_tools.loc[idx, "狀態"] = "在庫"
                    df_tools.loc[idx, "當前借用人"] = "無"
                    df_tools.loc[idx, "借出日期"] = "無"
                    
                    save_data(sheet_tools, df_tools)
                    add_log_gsheet("工具歸還", df_tools.loc[idx, "工具名稱"], b_name, "歸還入庫")
                    st.success(f"✅ [{df_tools.loc[idx, '工具名稱']}] 已完成歸還！")
                    st.rerun()
            else:
                st.success("🎉 當前無外借中工具。")

        with tab_maint:
            col_m1, col_m2 = st.columns(2)
            with col_m1:
                st.markdown("##### 🛠️ 設備送修登記")
                can_repair_tools = df_tools[df_tools["狀態"].isin(["在庫", "借出"])]
                if not can_repair_tools.empty:
                    tool_to_repair = st.selectbox("選擇送修工具", can_repair_tools["工具編號"].astype(str) + " - " + can_repair_tools["工具名稱"], key="emp_rep")
                    repair_reason = st.text_input("故障原因 / 保養描述")
                    repair_cost = st.number_input("預估/實付維修費用 (元)", min_value=0, step=100, value=1500)
                    repair_vendor = st.text_input("維修廠商 (選填)")
                    
                    if st.button("確認登記送修"):
                        if repair_reason:
                            t_id = tool_to_repair.split(" - ")[0]
                            idx = df_tools[df_tools["工具編號"].astype(str) == t_id].index[0]
                            t_name = df_tools.loc[idx, "工具名稱"]
                            
                            df_tools.loc[idx, "狀態"] = "維修中"
                            df_tools.loc[idx, "當前借用人"] = f"維修中 ({repair_vendor})" if repair_vendor else "維修中"
                            df_tools.loc[idx, "借出日期"] = datetime.now().strftime("%Y-%m-%d")
                            
                            save_data(sheet_tools, df_tools)
                            add_log_gsheet("工具送修", t_name, f"-${repair_cost}", f"原因: {repair_reason} | 廠商: {repair_vendor} | 維修費:${repair_cost}")
                            st.success(f"✅ [{t_name}] 已轉為維修狀態，費用 ${repair_cost} 已記帳！")
                            st.rerun()
                        else:
                            st.warning("⚠️ 請輸入故障原因")
            
            with col_m2:
                st.markdown("##### ✅ 維修完工返回庫存")
                if not repairing_df.empty:
                    tool_repaired = st.selectbox("選擇完工工具", repairing_df["工具編號"].astype(str) + " - " + repairing_df["工具名稱"], key="emp_repaired")
                    repair_note = st.text_input("完工備註 (選填)")
                    
                    if st.button("確認完工入庫"):
                        t_id = tool_repaired.split(" - ")[0]
                        idx = df_tools[df_tools["工具編號"].astype(str) == t_id].index[0]
                        t_name = df_tools.loc[idx, "工具名稱"]
                        
                        df_tools.loc[idx, "狀態"] = "在庫"
                        df_tools.loc[idx, "當前借用人"] = "無"
                        df_tools.loc[idx, "借出日期"] = "無"
                        
                        save_data(sheet_tools, df_tools)
                        add_log_gsheet("維修完成", t_name, "修復完工入庫", f"備註: {repair_note}")
                        st.success(f"✅ [{t_name}] 重新恢復在庫狀態！")
                        st.rerun()

# -------------------------------------------------------------------
# 分頁 C：📊 BI 經營決策儀表板 (完整 7 大圖表)
# -------------------------------------------------------------------
elif page == "📊 BI 經營決策儀表板" and st.session_state.is_admin:
    st.title("📊 BI 商業智慧經營決策中心")
    st.caption("結合專案預算、材料金流、庫存資產、設備 TCO 與調度效率之高階經營控制台")
    st.markdown("---")
    
    df_logs, _ = load_data("logs")
    df_mat, _ = load_data("materials")
    df_proj, _ = load_data("projects")
    df_tools, _ = load_data("tools")
    
    if not df_mat.empty:
        if "單價" not in df_mat.columns: df_mat["單價"] = 0
        df_mat["單價"] = pd.to_numeric(df_mat["單價"], errors='coerce').fillna(0)
        df_mat["目前庫存"] = pd.to_numeric(df_mat["目前庫存"], errors='coerce').fillna(0)
        price_dict = dict(zip(df_mat["材料名稱"].astype(str), df_mat["單價"]))
        
        usage_logs = df_logs[df_logs["類型"] == "領料出庫"].copy() if not df_logs.empty else pd.DataFrame()
        repair_logs = df_logs[df_logs["類型"] == "工具送修"].copy() if not df_logs.empty else pd.DataFrame()
        
        def calculate_log_cost(row):
            item_name = str(row["項目名稱"])
            detail = str(row["變動數量/借用人"])
            numbers = re.findall(r'\d+', detail)
            qty = int(numbers[0]) if numbers else 0
            unit_price = price_dict.get(item_name, 0)
            return qty, qty * unit_price

        def extract_proj_name(note):
            note_str = str(note)
            if "-" in note_str:
                return note_str.split("-")[0].replace("領用人/工程:", "").strip()
            return "未分類工程"

        if not usage_logs.empty:
            res = usage_logs.apply(calculate_log_cost, axis=1)
            usage_logs["數量"] = [r[0] for r in res]
            usage_logs["消耗金額"] = [r[1] for r in res]
            usage_logs["工程案名稱"] = usage_logs["備註"].apply(extract_proj_name)
        else:
            usage_logs["數量"] = 0
            usage_logs["消耗金額"] = 0
            usage_logs["工程案名稱"] = "無"

        total_budget = pd.to_numeric(df_proj["材料總預算"], errors='coerce').sum() if not df_proj.empty else 0
        total_spent = usage_logs["消耗金額"].sum() if not usage_logs.empty else 0
        df_mat["庫存總價值"] = df_mat["目前庫存"] * df_mat["單價"]
        total_inventory_value = df_mat["庫存總價值"].sum()
        
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("🏗️ 全案材料總預算", f"${total_budget:,.0f} 元")
        c2.metric("💸 全案實際材料消耗", f"${total_spent:,.0f} 元")
        c3.metric("📊 整體預算消化率", f"{(total_spent/total_budget*100 if total_budget>0 else 0):.1f}%")
        c4.metric("📦 倉庫現有資產價值", f"${total_inventory_value:,.0f} 元")
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        st.markdown("##### 📈 【圖表 1】專案材料預算 vs 實際消耗金額 (Budget vs. Actual Cost)")
        if not df_proj.empty:
            df_proj["材料總預算"] = pd.to_numeric(df_proj["材料總預算"], errors='coerce').fillna(0)
            cost_summary = usage_logs.groupby("工程案名稱")["消耗金額"].sum().reset_index() if not usage_logs.empty else pd.DataFrame(columns=["工程案名稱", "消耗金額"])
            
            merged_proj = pd.merge(df_proj, cost_summary, on="工程案名稱", how="left")
            merged_proj["消耗金額"] = merged_proj["消耗金額"].fillna(0)
            merged_proj["預算使用率 (%)"] = (merged_proj["消耗金額"] / merged_proj["材料總預算"] * 100).round(1).fillna(0)
            
            fig1 = go.Figure()
            fig1.add_trace(go.Bar(
                y=merged_proj["工程案名稱"], x=merged_proj["材料總預算"],
                name="材料總預算 (元)", orientation='h', marker_color='#93C5FD',
                text=[f"${x:,.0f}" for x in merged_proj["材料總預算"]], textposition='outside'
            ))
            fig1.add_trace(go.Bar(
                y=merged_proj["工程案名稱"], x=merged_proj["消耗金額"],
                name="實際消耗金額 (元)", orientation='h', marker_color='#1D4ED8',
                text=[f"${x:,.0f}" for x in merged_proj["消耗金額"]], textposition='outside'
            ))
            fig1.update_layout(
                barmode='group', height=320, margin=dict(l=10, r=40, t=10, b=10),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)'
            )
            st.plotly_chart(fig1, use_container_width=True)

        st.markdown("---")
        
        col_a, col_b = st.columns(2)
        with col_a:
            st.markdown("##### 💎 【圖表 2A】高價值材料消耗總金額排行榜")
            if not usage_logs.empty and usage_logs["消耗金額"].sum() > 0:
                mat_cost_df = usage_logs.groupby("項目名稱")["消耗金額"].sum().reset_index().sort_values(by="消耗金額", ascending=False).head(5)
                fig2a = px.bar(mat_cost_df, x="消耗金額", y="項目名稱", orientation='h', text=[f"${x:,.0f}" for x in mat_cost_df["消耗金額"]], color="消耗金額", color_continuous_scale="Teal")
                fig2a.update_traces(textposition='outside')
                fig2a.update_layout(yaxis={'categoryorder':'total ascending', 'title':''}, coloraxis_showscale=False, height=320, margin=dict(l=10, r=40, t=10, b=10))
                st.plotly_chart(fig2a, use_container_width=True)

        with col_b:
            st.markdown("##### 💰 【圖表 2B】庫存積壓資產金額排行榜 (Top 5)")
            stock_val_df = df_mat[df_mat["庫存總價值"] > 0].sort_values(by="庫存總價值", ascending=False).head(5)
            if not stock_val_df.empty:
                fig2b = px.bar(stock_val_df, x="庫存總價值", y="材料名稱", orientation='h', text=[f"${x:,.0f}" for x in stock_val_df["庫存總價值"]], color="庫存總價值", color_continuous_scale="Purples")
                fig2b.update_traces(textposition='outside')
                fig2b.update_layout(yaxis={'categoryorder':'total ascending', 'title':''}, coloraxis_showscale=False, height=320, margin=dict(l=10, r=40, t=10, b=10))
                st.plotly_chart(fig2b, use_container_width=True)

# -------------------------------------------------------------------
# 分頁 D：🏗️ 工程案預算管理 (管理員專屬)
# -------------------------------------------------------------------
elif page == "🏗️ 工程案預算管理" and st.session_state.is_admin:
    st.title("🏗️ 工程專案預算管理中心")
    st.caption("建立工地專案基本資料、客戶對象與材料預算上限")
    st.markdown("---")
    
    df_proj, sheet_proj = load_data("projects")
    if not df_proj.empty:
        st.subheader("📋 當前進行中專案清單")
        st.dataframe(df_proj, use_container_width=True)
        st.markdown("---")
    
    st.subheader("➕ 建立新工程專案")
    with st.form("add_project_form"):
        p_col1, p_col2 = st.columns(2)
        with p_col1:
            p_name = st.text_input("工程案名稱 (例如: A棟15F浴室改修)")
            p_client = st.text_input("客戶 / 報價對象 (例如: 遠雄建設)")
        with p_col2:
            p_budget = st.number_input("材料總預算 (元)", min_value=1000, step=10000, value=200000)
            p_date = st.date_input("開工日期")
            
        submit_p = st.form_submit_button("🚀 確認建立工程專案", type="primary")
        if submit_p and p_name:
            p_id = f"P{len(df_proj) + 1:03d}"
            new_proj = {"工程案編號": p_id, "工程案名稱": p_name, "客戶名稱": p_client or "個人業主", "材料總預算": p_budget, "開工日期": p_date.strftime("%Y-%m-%d"), "狀態": "進行中"}
            df_proj = pd.concat([df_proj, pd.DataFrame([new_proj])], ignore_index=True)
            save_data(sheet_proj, df_proj)
            add_log_gsheet("建立專案", p_name, f"預算:${p_budget:,.0f}", f"客戶:{p_client}")
            st.success(f"🎉 成功建立工程專案 [{p_id}] {p_name}！")
            st.rerun()

# -------------------------------------------------------------------
# 分頁 E：📦 材料庫存總覽 (管理員全功能大表格)
# -------------------------------------------------------------------
elif page == "📦 材料庫存總覽" and st.session_state.is_admin:
    st.title("📦 材料庫存全功能管理模組")
    st.caption("完整品項控制、單價設定與警戒監控 (管理員表格檢視模式)")
    st.markdown("---")
    
    df_mat, sheet_mat = load_data("materials")
    if not df_mat.empty:
        df_mat["目前庫存"] = pd.to_numeric(df_mat["目前庫存"], errors='coerce').fillna(0).astype(int)
        df_mat["安全庫存量"] = pd.to_numeric(df_mat["安全庫存量"], errors='coerce').fillna(0).astype(int)
        if "單價" not in df_mat.columns: df_mat["單價"] = 0
        df_mat["單價"] = pd.to_numeric(df_mat["單價"], errors='coerce').fillna(0)
        
        low_stock_df = df_mat[df_mat["目前庫存"] <= df_mat["安全庫存量"]]
        
        m_col1, m_col2, m_col3 = st.columns(3)
        m_col1.metric("材料總品項數", f"{len(df_mat)} 項")
        m_col2.metric("庫存正常項目", f"{len(df_mat) - len(low_stock_df)} 項")
        m_col3.metric("⚠️ 低庫存警戒項目", f"{len(low_stock_df)} 項", delta_color="inverse")
        
        st.markdown("<br>", unsafe_allow_html=True)
        if not low_stock_df.empty:
            st.error("⚠️ **【安全庫存預警】以下材料低於設定警戒線：**")
            st.dataframe(low_stock_df[["材料編號", "材料名稱", "分類", "目前庫存", "安全庫存量", "單位"]], use_container_width=True)

        st.subheader("📋 雲端即時材料資料庫")
        st.dataframe(df_mat, use_container_width=True)
        st.markdown("---")
        
        tab1, tab2, tab3 = st.tabs(["➕ 新增品項建檔", "✏️ 編輯材料/單價", "🗑️ 刪除下架"])
        
        with tab1:
            with st.form("adm_new_form"):
                new_name = st.text_input("材料名稱")
                new_spec = st.text_input("規格/尺寸")
                new_cat = st.text_input("分類名稱")
                new_price = st.number_input("材料單價 (元)", min_value=0, step=10, value=100)
                init_qty = st.number_input("初始庫存數量", min_value=0, step=1)
                safe_qty = st.number_input("安全庫存警戒門檻", min_value=1, step=1)
                unit_str = st.text_input("單位")
                if st.form_submit_button("確認建檔") and new_name:
                    new_id = f"M{len(df_mat) + 1:03d}"
                    new_row = {"材料編號": new_id, "材料名稱": new_name, "規格/尺寸": new_spec or "無", "分類": new_cat, "目前庫存": init_qty, "安全庫存量": safe_qty, "單位": unit_str, "單價": new_price}
                    df_mat = pd.concat([df_mat, pd.DataFrame([new_row])], ignore_index=True)
                    save_data(sheet_mat, df_mat)
                    add_log_gsheet("新增品項", new_name, f"+{init_qty}{unit_str}", f"規格:{new_spec} | 單價:${new_price}")
                    st.success("✅ 建檔成功！"); st.rerun()

        with tab2:
            selected_edit = st.selectbox("選擇修改項目", df_mat["材料編號"].astype(str) + " - " + df_mat["材料名稱"], key="adm_edit_sel")
            if selected_edit:
                e_id = selected_edit.split(" - ")[0]
                m_idx = df_mat[df_mat["材料編號"].astype(str) == e_id].index[0]
                with st.form("adm_edit_form"):
                    e_name = st.text_input("材料名稱", value=df_mat.loc[m_idx, "材料名稱"])
                    e_price = st.number_input("材料單價 (元)", value=int(df_mat.loc[m_idx, "單價"]) if "單價" in df_mat.columns else 0, min_value=0)
                    e_cat = st.text_input("分類名稱", value=df_mat.loc[m_idx, "分類"])
                    e_unit = st.text_input("單位", value=df_mat.loc[m_idx, "單位"])
                    e_qty = st.number_input("目前庫存", value=int(df_mat.loc[m_idx, "目前庫存"]), min_value=0)
                    e_safe = st.number_input("安全庫存", value=int(df_mat.loc[m_idx, "安全庫存量"]), min_value=1)
                    if st.form_submit_button("💾 儲存修改內容"):
                        df_mat.loc[m_idx, ["材料名稱", "單價", "分類", "單位", "目前庫存", "安全庫存量"]] = [e_name, e_price, e_cat, e_unit, e_qty, e_safe]
                        save_data(sheet_mat, df_mat)
                        st.success("✅ 修改儲存成功！"); st.rerun()

        with tab3:
            selected_del = st.selectbox("選擇要刪除的材料", df_mat["材料編號"].astype(str) + " - " + df_mat["材料名稱"], key="adm_del_sel")
            if selected_del:
                d_id = selected_del.split(" - ")[0]
                d_idx = df_mat[df_mat["材料編號"].astype(str) == d_id].index[0]
                d_name = df_mat.loc[d_idx, "材料名稱"]
                if st.button(f"🔥 確定刪除 [{d_name}]"):
                    df_mat = df_mat.drop(d_idx).reset_index(drop=True)
                    save_data(sheet_mat, df_mat)
                    st.success("✅ 刪除成功！"); st.rerun()

# -------------------------------------------------------------------
# 分頁 F：🔨 工具資產追蹤 (管理員全功能)
# -------------------------------------------------------------------
elif page == "🔨 工具資產追蹤" and st.session_state.is_admin:
    st.title("🔨 工具與固定資產管理")
    st.caption("資產檔案建檔、新機身價與報銷控制")
    st.markdown("---")
    
    df_tools, sheet_tools = load_data("tools")
    if not df_tools.empty:
        st.dataframe(df_tools, use_container_width=True)

# -------------------------------------------------------------------
# 分頁 G：📤 CSV 批次資料匯入 (管理員專屬)
# -------------------------------------------------------------------
elif page == "📤 CSV 批次資料匯入" and st.session_state.is_admin:
    st.title("📤 批次資料匯入中心")
    st.caption("快速將外部 CSV 清單同步導入雲端資料庫")
    st.markdown("---")
    
    target_type = st.radio("📌 第一步：選擇資料目標類型", ["📦 材料耗材", "🔨 工具資產", "📜 歷史紀錄", "🏗️ 工程案預算"], horizontal=True)
    uploaded_file = st.file_uploader("📂 第二步：上傳 CSV 檔案", type=["csv"])
    
    if uploaded_file is not None:
        try:
            import_df = pd.read_csv(uploaded_file, encoding='utf-8-sig')
            st.dataframe(import_df.head(10), use_container_width=True)
            import_mode = st.radio("🔄 第三步：匯入模式設定", ["追加至現有資料庫底部", "完全覆蓋現有資料庫 (謹慎選用)"])
            
            if st.button("🚀 確認執行批次匯入", type="primary"):
                if "材料" in target_type:
                    df_mat, sheet_mat = load_data("materials")
                    if "規格/尺寸" not in import_df.columns: import_df["規格/尺寸"] = "無"
                    if "單價" not in import_df.columns: import_df["單價"] = 0
                    final_df = import_df if "完全覆蓋" in import_mode else pd.concat([df_mat, import_df], ignore_index=True)
                    save_data(sheet_mat, final_df)
                    st.success("🎉 材料資料匯入成功！")
                elif "工具" in target_type:
                    df_tools, sheet_tools = load_data("tools")
                    if "新機購入單價" not in import_df.columns: import_df["新機購入單價"] = 0
                    final_df = import_df if "完全覆蓋" in import_mode else pd.concat([df_tools, import_df], ignore_index=True)
                    save_data(sheet_tools, final_df)
                    st.success("🎉 工具資料匯入成功！")
                elif "工程案" in target_type:
                    df_proj, sheet_proj = load_data("projects")
                    final_df = import_df if "完全覆蓋" in import_mode else pd.concat([df_proj, import_df], ignore_index=True)
                    save_data(sheet_proj, final_df)
                    st.success("🎉 工程案預算資料匯入成功！")
                else:
                    df_logs, sheet_logs = load_data("logs")
                    final_df = import_df if "完全覆蓋" in import_mode else pd.concat([df_logs, import_df], ignore_index=True)
                    save_data(sheet_logs, final_df)
                    st.success("🎉 歷史紀錄匯入成功！")
        except Exception as e:
            st.error(f"❌ 讀取失敗：{e}")

# -------------------------------------------------------------------
# 分頁 H：📜 雲端流水帳紀錄 (管理員專屬)
# -------------------------------------------------------------------
elif page == "📜 雲端流水帳紀錄" and st.session_state.is_admin:
    st.title("📜 全系統歷史異動稽核日誌")
    st.caption("即時記錄每一筆領用、進貨、借還與維修操作")
    st.markdown("---")
    
    df_logs, _ = load_data("logs")
    if not df_logs.empty:
        last_log = df_logs.iloc[-1]
        st.info(f"📌 最新動態：【{last_log['時間']}】 - 【{last_log['類型']}】 - {last_log['項目名稱']}")
        if st.button("↩️ 一鍵反轉/撤銷最後這筆操作", type="primary"):
            success, msg = undo_last_log()
            if success: st.success(msg); st.rerun()
            else: st.error(msg)
        st.markdown("<br>", unsafe_allow_html=True)
        st.dataframe(df_logs.sort_index(ascending=False), use_container_width=True)
