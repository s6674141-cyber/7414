import pandas as pd
from datetime import datetime
import streamlit as st
import matplotlib.pyplot as plt
import gspread
from google.oauth2.service_account import Credentials
import re
import plotly.express as px
import plotly.graph_objects as go
import google.generativeai as genai

# -------------------------------------------------------------------
# 0. 頁面基本設定 (預設展開側邊欄)
# -------------------------------------------------------------------
plt.rcParams['font.sans-serif'] = ['Microsoft JhengHei', 'PingFang TC', 'Arial Unicode MS', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

st.set_page_config(
    page_title="ProStock 雲端倉管與 AI BI 決策系統",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# -------------------------------------------------------------------
# 🎨 UI / CSS (v3.5 Full BI Edition 簡約質感深色風)
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

    .stButton>button {
        border-radius: 8px !important;
        font-weight: 600 !important;
        transition: all 0.2s ease-in-out !important;
        border: none !important;
    }
    .stButton>button[kind="primary"] {
        background: linear-gradient(135deg, #2563EB 0%, #1D4ED8 100%) !important;
        color: white !important;
        box-shadow: 0 2px 4px rgba(37, 99, 235, 0.2) !important;
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
# 2. Session State 身分管理與側邊欄
# -------------------------------------------------------------------
if "is_admin" not in st.session_state:
    st.session_state.is_admin = False

st.sidebar.markdown("### ⚡ ProStock 雲端倉管與 BI")
st.sidebar.caption("v4.5 Full BI + AI Assistant")
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
# 分頁 AI：🤖 AI 經營決策助理 (老闆專屬對話框)
# -------------------------------------------------------------------
if page == "🤖 AI 經營決策助理" and st.session_state.is_admin:
    st.title("🤖 老闆專屬 AI 經營決策助理")
    st.caption("基於全公司實體倉管、專案預算與流水帳數據的即時 AI 決策諮詢")
    st.markdown("---")
    
    # 檢查是否設定 GEMINI_API_KEY
    if "GEMINI_API_KEY" not in st.secrets:
        st.error("⚠️ 未在 `.streamlit/secrets.toml` 中找到 `GEMINI_API_KEY`，請完成設定以啟用 AI 助理。")
    else:
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
        
        # 初始化聊天歷史
        if "chat_messages" not in st.session_state:
            st.session_state.chat_messages = [
                {"role": "assistant", "content": "老闆您好！我是您的 AI 經營決策助理。您可以問我任何關於專案材料預算消化率、高價值耗材領用情況、工具設備維修 TCO 評估，或是 2025 全年金流趨勢的問題，我會為您做精準分析！"}
            ]
            
        # 展示歷史訊息
        for msg in st.session_state.chat_messages:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])
                
        # 使用者輸入框
        if prompt := st.chat_input("請輸入您想詢問的經營數據問題 (例如: 2025年哪一個工程案材料花最多錢？有超支嗎？)"):
            st.session_state.chat_messages.append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.markdown(prompt)
                
            # 準備向 AI 傳送 Prompt
            with st.chat_message("assistant"):
                with st.spinner("🤖 AI 正在讀取並分析公司資料庫中..."):
                    try:
                        # 1. 抓取最新數據快照
                        df_logs, _ = load_data("logs")
                        df_mat, _ = load_data("materials")
                        df_proj, _ = load_data("projects")
                        df_tools, _ = load_data("tools")
                        
                        # 摘要數據供 Prompt 使用
                        mat_summary = df_mat[["材料名稱", "目前庫存", "安全庫存量", "單價"]].to_string() if not df_mat.empty else "無"
                        proj_summary = df_proj.to_string() if not df_proj.empty else "無"
                        tools_summary = df_tools[["工具名稱", "品牌/廠牌", "型號", "新機購入單價", "狀態"]].to_string() if not df_tools.empty else "無"
                        logs_sample = df_logs.tail(100).to_string() if not df_logs.empty else "無"
                        
                        system_prompt = f"""
                        你是一位專精於水電工程與倉管財務的 AI 經營顧問，正在為公司老闆解答經營疑難雜症。
                        請根據以下提供的公司【實體最新資料庫快照】進行思考與回答。請保持專業、精準、口吻親切，並附帶具體的經營建議（例如：JIT採購、報廢新購、預算稽核）。

                        【1. 工程專案預算清單】:
                        {proj_summary}

                        【2. 庫存與單價摘要】:
                        {mat_summary}

                        【3. 工具設備資產摘要】:
                        {tools_summary}

                        【4. 歷史流水帳摘要 (最近100筆)】:
                        {logs_sample}

                        使用者問題: {prompt}
                        """
                        
                        model = genai.GenerativeModel('gemini-1.5-flash')
                        response = model.generate_content(system_prompt)
                        ai_reply = response.text
                        
                        st.markdown(ai_reply)
                        st.session_state.chat_messages.append({"role": "assistant", "content": ai_reply})
                    except Exception as e:
                        st.error(f"❌ AI 分析失敗，請確認 API Key 與連線狀態：{e}")

# -------------------------------------------------------------------
# 分頁 A：📦 材料領用與進貨 (一般員工)
# -------------------------------------------------------------------
elif page == "📦 材料領用與進貨":
    st.title("📦 材料領用與進貨登記")
    st.caption("現場即時庫存扣抵與進貨補給面板")
    st.markdown("---")
    
    df_mat, sheet_mat = load_data("materials")
    df_proj, _ = load_data("projects")
    
    proj_options = ["一般維修/未分類"]
    if not df_proj.empty and "工程案名稱" in df_proj.columns:
        proj_options = list(df_proj["工程案名稱"].dropna().unique())
    
    if not df_mat.empty:
        df_mat["目前庫存"] = pd.to_numeric(df_mat["目前庫存"], errors='coerce').fillna(0).astype(int)
        if "單價" not in df_mat.columns: df_mat["單價"] = 0
        df_mat["單價"] = pd.to_numeric(df_mat["單價"], errors='coerce').fillna(0)
        
        st.subheader("📋 即時材料庫存狀態")
        
        search_mat = st.text_input("🔍 快速搜尋材料 (輸入名稱、編號、規格或分類)：", placeholder="例如: 電線, M001, 2.0mm, 管路類...")
        filtered_mat = df_mat.copy()
        if search_mat:
            search_term = search_mat.strip().lower()
            filtered_mat = filtered_mat[
                filtered_mat["材料編號"].astype(str).str.lower().str.contains(search_term, na=False) |
                filtered_mat["材料名稱"].astype(str).str.lower().str.contains(search_term, na=False) |
                filtered_mat["規格/尺寸"].astype(str).str.lower().str.contains(search_term, na=False) |
                filtered_mat["分類"].astype(str).str.lower().str.contains(search_term, na=False)
            ]
        
        show_cols = ["材料編號", "材料名稱", "規格/尺寸", "分類", "目前庫存", "單位", "單價"]
        valid_cols = [c for c in show_cols if c in filtered_mat.columns]
        st.dataframe(filtered_mat[valid_cols], use_container_width=True)
        st.markdown("<br>", unsafe_allow_html=True)
        
        tab1, tab2 = st.tabs(["📤 師傅領料登記", "📥 進貨入庫登記"])
        
        with tab1:
            st.markdown("##### 領料出庫作業")
            with st.form("emp_borrow_form"):
                selected_mat = st.selectbox("選擇領料項目", df_mat["材料編號"].astype(str) + " - " + df_mat["材料名稱"])
                selected_proj = st.selectbox("選擇所屬工程專案", proj_options)
                borrow_qty = st.number_input("領取數量", min_value=1, step=1)
                worker = st.text_input("領用師傅姓名")
                submit_borrow = st.form_submit_button("確認領料出庫", type="primary")
                
                if submit_borrow:
                    mat_id = selected_mat.split(" - ")[0]
                    idx = df_mat[df_mat["材料編號"].astype(str) == mat_id].index[0]
                    mat_name = df_mat.loc[idx, "材料名稱"]
                    curr_qty = df_mat.loc[idx, "目前庫存"]
                    unit = df_mat.loc[idx, "單位"]
                    
                    if borrow_qty > curr_qty:
                        st.error(f"❌ 庫存不足！目前僅剩庫存：{curr_qty} {unit}")
                    else:
                        df_mat.loc[idx, "目前庫存"] -= borrow_qty
                        save_data(sheet_mat, df_mat)
                        note_text = f"{selected_proj} - 師傅:{worker}"
                        add_log_gsheet("領料出庫", mat_name, f"-{borrow_qty} {unit}", note_text)
                        st.success(f"✅ 成功領用 [{mat_name}] {borrow_qty} {unit}！專案：{selected_proj}")
                        st.rerun()

        with tab2:
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
        # 1. 整理單價數據
        if "單價" not in df_mat.columns: df_mat["單價"] = 0
        df_mat["單價"] = pd.to_numeric(df_mat["單價"], errors='coerce').fillna(0)
        df_mat["目前庫存"] = pd.to_numeric(df_mat["目前庫存"], errors='coerce').fillna(0)
        price_dict = dict(zip(df_mat["材料名稱"].astype(str), df_mat["單價"]))
        
        # 2. 解析領料與維修日誌
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

        # ---------------------------------------------------------------
        # 📊 頂部 KPI 卡片區
        # ---------------------------------------------------------------
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
        
        # ---------------------------------------------------------------
        # 【圖表 1】專案材料預算 vs 實際消耗金額
        # ---------------------------------------------------------------
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
            
            over_budget = merged_proj[merged_proj["消耗金額"] > merged_proj["材料總預算"]]
            warning_budget = merged_proj[(merged_proj["預算使用率 (%)"] >= 80) & (merged_proj["消耗金額"] <= merged_proj["材料總預算"])]
            
            if not over_budget.empty:
                for _, row in over_budget.iterrows():
                    st.error(f"🚨 **預算超支警報**：【{row['工程案名稱']}】材料已超出預算 **${row['消耗金額'] - row['材料總預算']:,.0f} 元** (使用率 {row['預算使用率 (%)']}%)！建議 PM 查核是否有材料偷挪用或漏報追加工程。")
            if not warning_budget.empty:
                for _, row in warning_budget.iterrows():
                    st.warning(f"⚠️ **預算高風險預警**：【{row['工程案名稱']}】預算已消化 **{row['預算使用率 (%)']}%**！請 PM 查核剩餘工期進度。")
            if over_budget.empty and warning_budget.empty:
                st.success("🎉 當前所有進行中工程專案之材料預算均控管良好！")
        else:
            st.info("💡 請先至【🏗️ 工程案預算管理】建檔工程案以啟用預算分析。")

        st.markdown("---")
        
        # ---------------------------------------------------------------
        # 【圖表 2A & 2B】動態領用 Top 5 vs 靜態庫存資產 Top 5
        # ---------------------------------------------------------------
        col_a, col_b = st.columns(2)
        
        with col_a:
            st.markdown("##### 💎 【圖表 2A】高價值材料 (A類資產) 消耗總金額排行榜")
            if not usage_logs.empty and usage_logs["消耗金額"].sum() > 0:
                mat_cost_df = usage_logs.groupby("項目名稱")["消耗金額"].sum().reset_index()
                mat_cost_df = mat_cost_df.sort_values(by="消耗金額", ascending=False).head(5)
                
                fig2a = px.bar(
                    mat_cost_df, x="消耗金額", y="項目名稱", orientation='h',
                    text=[f"${x:,.0f}" for x in mat_cost_df["消耗金額"]],
                    color="消耗金額", color_continuous_scale="Teal"
                )
                fig2a.update_traces(textposition='outside')
                fig2a.update_layout(yaxis={'categoryorder':'total ascending', 'title':''}, coloraxis_showscale=False, height=320, margin=dict(l=10, r=40, t=10, b=10))
                st.plotly_chart(fig2a, use_container_width=True)
                
                top_mat = mat_cost_df.iloc[0]["項目名稱"]
                top_val = mat_cost_df.iloc[0]["消耗金額"]
                st.info(f"💡 **ABC 採購建議**：【{top_mat}】為金流消耗最高之材料（已消耗 ${top_val:,.0f} 元）。建議採用 JIT 及時採購，避免囤積資金。")
            else:
                st.info("尚無領料出庫金流紀錄。")

        with col_b:
            st.markdown("##### 💰 【圖表 2B】庫存積壓資產金額排行榜 (Top 5)")
            stock_val_df = df_mat[df_mat["庫存總價值"] > 0].sort_values(by="庫存總價值", ascending=False).head(5)
            
            if not stock_val_df.empty:
                fig2b = px.bar(
                    stock_val_df, x="庫存總價值", y="材料名稱", orientation='h',
                    text=[f"${x:,.0f}" for x in stock_val_df["庫存總價值"]],
                    color="庫存總價值", color_continuous_scale="Purples"
                )
                fig2b.update_traces(textposition='outside')
                fig2b.update_layout(yaxis={'categoryorder':'total ascending', 'title':''}, coloraxis_showscale=False, height=320, margin=dict(l=10, r=40, t=10, b=10))
                st.plotly_chart(fig2b, use_container_width=True)
                
                top_stock_mat = stock_val_df.iloc[0]["材料名稱"]
                top_stock_val = stock_val_df.iloc[0]["庫存總價值"]
                st.warning(f"💡 **靜態資產建議**：【{top_stock_mat}】目前倉庫積壓金額達 **${top_stock_val:,.0f} 元**。請 PM 優先將此庫存調撥至近期專案使用，加速資產週轉。")
            else:
                st.info("目前倉庫內無高價值庫存材料。")

        st.markdown("---")
        
        # ---------------------------------------------------------------
        # 【圖表 3】高頻損壞 / 設備報修警報 (TCO 分析)
        # ---------------------------------------------------------------
        st.markdown("##### 🚨 【圖表 3】高頻損壞 / 設備報修警報 (TCO 總持有成本分析)")
        if not df_tools.empty:
            if "新機購入單價" not in df_tools.columns: df_tools["新機購入單價"] = 0
            df_tools["新機購入單價"] = pd.to_numeric(df_tools["新機購入單價"], errors='coerce').fillna(0)
            tool_price_dict = dict(zip(df_tools["工具名稱"].astype(str), df_tools["新機購入單價"]))
            
            if not repair_logs.empty:
                def parse_repair_cost(row):
                    detail = str(row["變動數量/借用人"])
                    note = str(row["備註"])
                    numbers = re.findall(r'\d+', detail)
                    if numbers: return int(numbers[0])
                    note_nums = re.findall(r'維修費:\s*\$?(\d+)', note)
                    if note_nums: return int(note_nums[0])
                    return 1500
                
                repair_logs["維修花費"] = repair_logs.apply(parse_repair_cost, axis=1)
                
                tco_df = repair_logs.groupby("項目名稱").agg(
                    送修次數=("類型", "count"),
                    累積維修費用=("維修花費", "sum")
                ).reset_index()
                
                tco_df["新機購入單價"] = tco_df["項目名稱"].map(tool_price_dict).fillna(0)
                tco_df["維修費佔比 (%)"] = (tco_df["累積維修費用"] / tco_df["新機購入單價"] * 100).round(1).fillna(0)
                tco_df = tco_df.sort_values(by="送修次數", ascending=False)
                
                fig3 = px.bar(
                    tco_df, x="送修次數", y="項目名稱", orientation='h',
                    text="送修次數", color="送修次數", color_continuous_scale="Reds"
                )
                fig3.update_traces(textposition='outside')
                fig3.update_layout(yaxis={'categoryorder':'total ascending', 'title':''}, coloraxis_showscale=False, height=320, margin=dict(l=10, r=30, t=10, b=10))
                st.plotly_chart(fig3, use_container_width=True)
                
                worst_tool = tco_df.iloc[0]["項目名稱"]
                worst_count = tco_df.iloc[0]["送修次數"]
                worst_cost = tco_df.iloc[0]["累積維修費用"]
                
                if worst_count >= 3:
                    st.error(f"💡 **修不如買建議**：【{worst_tool}】累積送修已達 **{worst_count} 次** (累積費用 ${worst_cost:,.0f} 元)，維修成本過高。建議直接辦理**資產報廢並購買新機**。")
                else:
                    st.warning(f"💡 **保養建議**：【{worst_tool}】送修頻率偏高，請安排原廠定期檢測。")
            else:
                st.success("🎉 目前設備狀況良好，無任何故障送修紀錄！")
        else:
            st.info("無工具資料。")

        st.markdown("---")
        
        # ---------------------------------------------------------------
        # 【圖表 4 & 5】每日領料金額動態趨勢 vs 工具外借超期滯留警報
        # ---------------------------------------------------------------
        col_c, col_d = st.columns(2)
        
        with col_c:
            st.markdown("##### 📈 【圖表 4】每日領料金額動態與資金消耗趨勢")
            if not usage_logs.empty and "時間" in usage_logs.columns:
                try:
                    usage_logs_copy = usage_logs.copy()
                    usage_logs_copy["時間_dt"] = pd.to_datetime(usage_logs_copy["時間"], errors='coerce')
                    usage_logs_valid = usage_logs_copy.dropna(subset=["時間_dt"])
                    
                    if not usage_logs_valid.empty:
                        usage_logs_valid["日期"] = usage_logs_valid["時間_dt"].dt.date
                        trend_df = usage_logs_valid.groupby("日期")["消耗金額"].sum().reset_index()
                        
                        fig4 = px.line(trend_df, x="日期", y="消耗金額", markers=True, line_shape="spline")
                        fig4.update_traces(line_color="#2563EB", line_width=3)
                        fig4.update_layout(height=280, margin=dict(l=10, r=20, t=10, b=10), xaxis_title="", yaxis_title="每日消耗金額 (元)")
                        st.plotly_chart(fig4, use_container_width=True)
                        st.caption("💡 **資金流洞察**：監控每日資金消耗峰值，可協助財務預先安排專案材料款項。")
                    else:
                        st.info("時間解析中 (請確認流水帳中包含標準時間格式)。")
                except Exception as e:
                    st.info(f"時間解析中 ({e})。")
            else:
                st.info("尚無時間序列數據。")

        with col_d:
            st.markdown("##### ⏳ 【圖表 5】外借工具超期滯留警報 (> 7 天未歸還)")
            if not df_tools.empty:
                borrowed_tools = df_tools[df_tools["狀態"] == "借出"].copy()
                if not borrowed_tools.empty and "借出日期" in borrowed_tools.columns:
                    today = pd.to_datetime("today").date()
                    borrowed_tools["借出天數"] = borrowed_tools["借出日期"].apply(
                        lambda x: (today - pd.to_datetime(x, errors='coerce').date()).days if str(x) != "無" and pd.notnull(x) else 0
                    )
                    overdue_tools = borrowed_tools[borrowed_tools["借出天數"] >= 7]
                    
                    if not overdue_tools.empty:
                        st.dataframe(
                            overdue_tools[["工具編號", "工具名稱", "當前借用人", "借出日期", "借出天數"]],
                            use_container_width=True
                        )
                        st.warning("💡 **調度建議**：以上工具外借已超過 7 天，請發送催還通知，避免機具閒置或重複購買。")
                    else:
                        st.success("🎉 當前所有外借工具均在正常 7 天借期內！")
                else:
                    st.info("目前沒有外借中的工具。")
            else:
                st.info("無工具資料。")

    else:
        st.info("💡 請確認材料表中包含【單價】資訊，即可展現完整 BI 圖表！")

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
            new_proj = {
                "工程案編號": p_id,
                "工程案名稱": p_name,
                "客戶名稱": p_client or "個人業主",
                "材料總預算": p_budget,
                "開工日期": p_date.strftime("%Y-%m-%d"),
                "狀態": "進行中"
            }
            df_proj = pd.concat([df_proj, pd.DataFrame([new_proj])], ignore_index=True)
            save_data(sheet_proj, df_proj)
            add_log_gsheet("建立專案", p_name, f"預算:${p_budget:,.0f}", f"客戶:{p_client}")
            st.success(f"🎉 成功建立工程專案 [{p_id}] {p_name}！")
            st.rerun()

# -------------------------------------------------------------------
# 分頁 E：📦 材料庫存總覽 (管理員全功能)
# -------------------------------------------------------------------
elif page == "📦 材料庫存總覽" and st.session_state.is_admin:
    st.title("📦 材料庫存全功能管理模組")
    st.caption("完整品項控制、單價設定與警戒監控")
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
            st.error("⚠️ **【安全庫存預警】以下材料低於設定警戒線，請妥善規劃採購補貨：**")
            st.dataframe(low_stock_df[["材料編號", "材料名稱", "分類", "目前庫存", "安全庫存量", "單位"]], use_container_width=True)

        col_ex1, _ = st.columns([1, 4])
        with col_ex1:
            csv_data = df_mat.to_csv(index=False).encode('utf-8-sig')
            st.download_button("📥 匯出材料總表 (CSV)", data=csv_data, file_name=f"材料庫存總表_{datetime.now().strftime('%Y%m%d')}.csv", mime="text/csv")

        st.subheader("📋 雲端即時材料資料庫")
        st.dataframe(df_mat, use_container_width=True)
        st.markdown("---")
        
        tab1, tab2, tab3, tab4 = st.tabs(["➕ 新增品項建檔", "✏️ 編輯材料/單價", "🗑️ 刪除下架", "📥 進貨庫存變更"])
        
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
                st.warning(f"⚠️ 確定下架刪除 [{d_name}] 嗎？")
                chk = st.checkbox(f"我確定要刪除 [{d_name}]")
                if st.button("🔥 確定刪除") and chk:
                    df_mat = df_mat.drop(d_idx).reset_index(drop=True)
                    save_data(sheet_mat, df_mat)
                    st.success("✅ 刪除成功！"); st.rerun()

        with tab4:
            with st.form("adm_in_form"):
                selected_mat_in = st.selectbox("選擇進貨項目", df_mat["材料編號"].astype(str) + " - " + df_mat["材料名稱"], key="adm_in")
                in_qty = st.number_input("進貨數量", min_value=1, step=1, key="adm_in_q")
                vendor = st.text_input("來源廠商 / 備註")
                submit_in = st.form_submit_button("確認進貨入庫")
                if submit_in:
                    mat_id = selected_mat_in.split(" - ")[0]
                    idx = df_mat[df_mat["材料編號"].astype(str) == mat_id].index[0]
                    mat_name, unit = df_mat.loc[idx, "材料名稱"], df_mat.loc[idx, "單位"]
                    df_mat.loc[idx, "目前庫存"] += in_qty
                    save_data(sheet_mat, df_mat)
                    add_log_gsheet("進貨入庫", mat_name, f"+{in_qty} {unit}", f"進貨廠商: {vendor}")
                    st.success(f"✅ 已成功入庫 [{mat_name}]"); st.rerun()

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
        st.markdown("---")
        tab_tn, tab_te, tab_td = st.tabs(["➕ 新增工具建檔", "✏️ 編輯工具/價格", "🗑️ 資產報銷"])
        
        with tab_tn:
            with st.form("adm_new_tool"):
                t_name = st.text_input("工具名稱")
                t_brand = st.text_input("品牌 / 廠牌")
                t_model = st.text_input("型號")
                t_cat = st.text_input("分類名稱")
                t_price = st.number_input("新機購入單價 (元)", min_value=0, step=500, value=8500)
                if st.form_submit_button("確認新增建檔") and t_name:
                    new_t_id = f"T{len(df_tools) + 1:03d}"
                    new_tool = {"工具編號": new_t_id, "工具名稱": t_name, "品牌/廠牌": t_brand or "無", "型號": t_model or "無", "分類": t_cat or "通用", "新機購入單價": t_price, "狀態": "在庫", "當前借用人": "無", "借出日期": "無"}
                    df_tools = pd.concat([df_tools, pd.DataFrame([new_tool])], ignore_index=True)
                    save_data(sheet_tools, df_tools)
                    st.success("✅ 建檔成功！"); st.rerun()

        with tab_te:
            selected_edit_t = st.selectbox("選擇要編輯的工具", df_tools["工具編號"].astype(str) + " - " + df_tools["工具名稱"], key="edit_t_sel")
            if selected_edit_t:
                et_id = selected_edit_t.split(" - ")[0]
                et_idx = df_tools[df_tools["工具編號"].astype(str) == et_id].index[0]
                with st.form("edit_tool_form"):
                    et_name = st.text_input("工具名稱", value=df_tools.loc[et_idx, "工具名稱"])
                    et_price = st.number_input("新機購入單價 (元)", value=int(df_tools.loc[et_idx, "新機購入單價"]) if "新機購入單價" in df_tools.columns else 0, min_value=0)
                    et_brand = st.text_input("品牌", value=df_tools.loc[et_idx, "品牌/廠牌"])
                    et_model = st.text_input("型號", value=df_tools.loc[et_idx, "型號"])
                    if st.form_submit_button("💾 儲存修改內容"):
                        df_tools.loc[et_idx, ["工具名稱", "新機購入單價", "品牌/廠牌", "型號"]] = [et_name, et_price, et_brand, et_model]
                        save_data(sheet_tools, df_tools)
                        st.success("✅ 工具資料更新成功！"); st.rerun()

        with tab_td:
            selected_del_t = st.selectbox("選擇報銷工具", df_tools["工具編號"].astype(str) + " - " + df_tools["工具名稱"])
            if selected_del_t:
                dt_id = selected_del_t.split(" - ")[0]
                dt_idx = df_tools[df_tools["工具編號"].astype(str) == dt_id].index[0]
                dt_name = df_tools.loc[dt_idx, "工具名稱"]
                if st.button(f"🔥 確定報銷刪除 [{dt_name}]"):
                    df_tools = df_tools.drop(dt_idx).reset_index(drop=True)
                    save_data(sheet_tools, df_tools)
                    st.success("✅ 資產報銷成功！"); st.rerun()

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
