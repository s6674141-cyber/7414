import os
import pandas as pd
from datetime import datetime
import streamlit as st
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm

# -------------------------------------------------------------------
# 0. 跨平台中文字型自動設定 (解決 Windows / Mac 中文亂碼)
# -------------------------------------------------------------------
plt.rcParams['font.sans-serif'] = [
    'Microsoft JhengHei',  # Windows 微軟正黑體
    'PingFang TC',        # Mac 蘋方體
    'Arial Unicode MS', 
    'DejaVu Sans'
]
plt.rcParams['axes.unicode_minus'] = False

# -------------------------------------------------------------------
# 1. 頁面基本設定 (標題、頁面圖示、寬螢幕排版)
# -------------------------------------------------------------------
st.set_page_config(
    page_title="水電倉管與資產追蹤系統",
    page_icon="🛠️",
    layout="wide"
)

MATERIALS_FILE = "materials.csv"
TOOLS_FILE = "tools.csv"
LOGS_FILE = "logs.csv"

# -------------------------------------------------------------------
# 2. 資料庫初始化與讀寫邏輯 (已更新為最新工具清單)
# -------------------------------------------------------------------
def init_databases():
    """初始化 3 個 CSV 資料檔案"""
    if not os.path.exists(MATERIALS_FILE):
        df_mat = pd.DataFrame([
            {"材料編號": "M001", "材料名稱": "2.0單芯電線(紅)", "分類": "電線類", "目前庫存": 5, "安全庫存量": 10, "單位": "捲"},
            {"材料編號": "M002", "材料名稱": "6分PVC水管", "分類": "管路類", "目前庫存": 20, "安全庫存量": 8, "單位": "支"},
            {"材料編號": "M003", "材料名稱": "單切開關面板", "分類": "開關類", "目前庫存": 3, "安全庫存量": 5, "單位": "個"},
        ])
        df_mat.to_csv(MATERIALS_FILE, index=False, encoding="utf-8-sig")

    # 🔄 自動匯入你最新的工具清單資料
    if not os.path.exists(TOOLS_FILE):
        new_tools_data = [
            {"工具編號": "FAA0001", "工具名稱": "探照燈", "分類": "照明工具 (F)", "狀態": "在庫", "當前借用人": "無", "借出日期": "無"},
            {"工具編號": "FAA0002", "工具名稱": "工業用探照燈", "分類": "照明工具 (F)", "狀態": "在庫", "當前借用人": "無", "借出日期": "無"},
            {"工具編號": "FAA0003", "工具名稱": "LED投射燈", "分類": "照明工具 (F)", "狀態": "在庫", "當前借用人": "無", "借出日期": "無"},
            {"工具編號": "FAA0004", "工具名稱": "伸縮腳架", "分類": "照明工具 (F)", "狀態": "在庫", "當前借用人": "無", "借出日期": "無"},
            {"工具編號": "FAA0005", "工具名稱": "雙燈LED兼三腳架", "分類": "照明工具 (F)", "狀態": "在庫", "當前借用人": "無", "借出日期": "無"},
            {"工具編號": "GAA0001", "工具名稱": "驗電筆", "分類": "測量工具 (G)", "狀態": "在庫", "當前借用人": "無", "借出日期": "無"},
            {"工具編號": "GAA0002", "工具名稱": "高阻計", "分類": "測量工具 (G)", "狀態": "在庫", "當前借用人": "無", "借出日期": "無"},
            {"工具編號": "GAA0003", "工具名稱": "檢相計（相序表）", "分類": "測量工具 (G)", "狀態": "在庫", "當前借用人": "無", "借出日期": "無"},
            {"工具編號": "GAA0004", "工具名稱": "數位式照度計", "分類": "測量工具 (G)", "狀態": "在庫", "當前借用人": "無", "借出日期": "無"},
            {"工具編號": "GAA0005", "工具名稱": "雷射測距儀", "分類": "測量工具 (G)", "狀態": "在庫", "當前借用人": "無", "借出日期": "無"},
            {"工具編號": "GAA0006", "工具名稱": "音波測距儀", "分類": "測量工具 (G)", "狀態": "在庫", "當前借用人": "無", "借出日期": "無"},
            {"工具編號": "GAA0007", "工具名稱": "紅外線熱影像儀", "分類": "測量工具 (G)", "狀態": "在庫", "當前借用人": "無", "借出日期": "無"},
            {"工具編號": "GAA0008", "工具名稱": "牆體探測儀", "分類": "測量工具 (G)", "狀態": "在庫", "當前借用人": "無", "借出日期": "無"},
            {"工具編號": "GAA0009", "工具名稱": "管路尋線儀", "分類": "測量工具 (G)", "狀態": "在庫", "當前借用人": "無", "借出日期": "無"},
            {"工具編號": "GAA0010", "工具名稱": "金屬探測器", "分類": "測量工具 (G)", "狀態": "在庫", "當前借用人": "無", "借出日期": "無"},
            {"工具編號": "GAA0011", "工具名稱": "管道內視鏡", "分類": "測量工具 (G)", "狀態": "在庫", "當前借用人": "無", "借出日期": "無"},
            {"工具編號": "GAA0012", "工具名稱": "冷媒洩漏檢測儀", "分類": "測量工具 (G)", "狀態": "在庫", "當前借用人": "無", "借出日期": "無"},
            {"工具編號": "GAA0013", "工具名稱": "可燃氣體檢漏儀", "分類": "測量工具 (G)", "狀態": "在庫", "當前借用人": "無", "借出日期": "無"},
            {"工具編號": "GAA0014", "工具名稱": "水管測漏儀", "分類": "測量工具 (G)", "狀態": "在庫", "當前借用人": "無", "借出日期": "無"},
            {"工具編號": "GAA0015", "工具名稱": "聽漏儀", "分類": "測量工具 (G)", "狀態": "在庫", "當前借用人": "無", "借出日期": "無"},
            {"工具編號": "HAA0001", "工具名稱": "全身式安全帶", "分類": "穿戴工具 (H)", "狀態": "在庫", "當前借用人": "無", "借出日期": "無"},
            {"工具編號": "HAA0002", "工具名稱": "防墜器", "分類": "穿戴工具 (H)", "狀態": "在庫", "當前借用人": "無", "借出日期": "無"},
            {"工具編號": "HAA0003", "工具名稱": "雙大鉤安全繩", "分類": "穿戴工具 (H)", "狀態": "在庫", "當前借用人": "無", "借出日期": "無"},
            {"工具編號": "HAA0004", "工具名稱": "防電弧面罩", "分類": "穿戴工具 (H)", "狀態": "在庫", "當前借用人": "無", "借出日期": "無"},
            {"工具編號": "HAA0005", "工具名稱": "自動變光焊接面罩", "分類": "穿戴工具 (H)", "狀態": "在庫", "當前借用人": "無", "借出日期": "無"},
            {"工具編號": "HAA0006", "工具名稱": "防塵毒口罩", "分類": "穿戴工具 (H)", "狀態": "在庫", "當前借用人": "無", "借出日期": "無"},
            {"工具編號": "HAA0007", "工具名稱": "攜帶式氣體偵測器", "分類": "穿戴工具 (H)", "狀態": "在庫", "當前借用人": "無", "借出日期": "無"},
            {"工具編號": "HAA0008", "工具名稱": "送風式呼吸防護具", "分類": "穿戴工具 (H)", "狀態": "在庫", "當前借用人": "無", "借出日期": "無"},
            {"工具編號": "HAA0009", "工具名稱": "絕緣手臂套", "分類": "穿戴工具 (H)", "狀態": "在庫", "當前借用人": "無", "借出日期": "無"},
            {"工具編號": "HAA0010", "工具名稱": "工具吊繩", "分類": "穿戴工具 (H)", "狀態": "在庫", "當前借用人": "無", "借出日期": "無"},
        ]
        df_tools = pd.DataFrame(new_tools_data)
        df_tools.to_csv(TOOLS_FILE, index=False, encoding="utf-8-sig")

    if not os.path.exists(LOGS_FILE):
        df_logs = pd.DataFrame(columns=["時間", "類型", "項目名稱", "變動數量/借用人", "備註"])
        df_logs.to_csv(LOGS_FILE, index=False, encoding="utf-8-sig")

init_databases()

def add_log(action_type, item_name, detail, note=""):
    """自動記錄每一次異動流水帳"""
    df_logs = pd.read_csv(LOGS_FILE, encoding="utf-8-sig")
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    new_log = {"時間": now_str, "類型": action_type, "項目名稱": item_name, "變動數量/借用人": detail, "備註": note}
    df_logs = pd.concat([df_logs, pd.DataFrame([new_log])], ignore_index=True)
    df_logs.to_csv(LOGS_FILE, index=False, encoding="utf-8-sig")

# -------------------------------------------------------------------
# 3. 側邊欄控制與導覽目錄
# -------------------------------------------------------------------
st.sidebar.title("🛠️ 水電倉管系統")
st.sidebar.markdown("---")
page = st.sidebar.radio(
    "請選擇系統功能分頁：",
    ["📦 材料庫存管理", "🔨 工具資產追蹤", "📊 數據分析儀表板", "📜 歷史異動紀錄"]
)

# -------------------------------------------------------------------
# 分頁 1：材料庫存管理
# -------------------------------------------------------------------
if page == "📦 材料庫存管理":
    st.header("📦 材料耗材庫存管理模組")
    
    df_mat = pd.read_csv(MATERIALS_FILE, encoding="utf-8-sig")
    low_stock_df = df_mat[df_mat["目前庫存"] <= df_mat["安全庫存量"]]
    
    col1, col2, col3 = st.columns(3)
    col1.metric("材料總品項", f"{len(df_mat)} 項")
    col2.metric("庫存正常項目", f"{len(df_mat) - len(low_stock_df)} 項")
    col3.metric("⚠️ 庫存警報項目", f"{len(low_stock_df)} 項", delta_color="inverse")
    
    st.markdown("---")
    
    if not low_stock_df.empty:
        st.error("⚠️ **【安全庫存警報】以下材料庫存已低於警戒線，請及時補貨！**")
        st.dataframe(low_stock_df[["材料編號", "材料名稱", "分類", "目前庫存", "安全庫存量", "單位"]], use_container_width=True)

    st.subheader("📋 當前材料庫存總覽")
    st.dataframe(df_mat, use_container_width=True)
    
    st.markdown("---")
    
    st.subheader("🔄 庫存異動操作面板")
    tab1, tab2, tab3 = st.tabs(["📤 師傅領料登記", "📥 進貨入庫登記", "➕ 新增材料品項"])
    
    with tab1:
        with st.form("borrow_material_form"):
            selected_mat = st.selectbox("選擇領料項目", df_mat["材料編號"] + " - " + df_mat["材料名稱"])
            borrow_qty = st.number_input("領取數量", min_value=1, step=1)
            worker = st.text_input("領用師傅 / 工地名稱")
            submit_borrow = st.form_submit_button("確認領料出庫")
            
            if submit_borrow:
                mat_id = selected_mat.split(" - ")[0]
                idx = df_mat[df_mat["材料編號"] == mat_id].index[0]
                mat_name = df_mat.loc[idx, "材料名稱"]
                curr_qty = df_mat.loc[idx, "目前庫存"]
                unit = df_mat.loc[idx, "單位"]
                
                if borrow_qty > curr_qty:
                    st.error(f"❌ 庫存不足！目前剩餘庫存為 {curr_qty} {unit}")
                else:
                    df_mat.loc[idx, "目前庫存"] -= borrow_qty
                    df_mat.to_csv(MATERIALS_FILE, index=False, encoding="utf-8-sig")
                    add_log("領料出庫", mat_name, f"-{borrow_qty} {unit}", f"領用人/工程: {worker}")
                    st.success(f"✅ 成功領用 [{mat_name}] {borrow_qty} {unit}！")
                    st.rerun()

    with tab2:
        with st.form("add_stock_form"):
            selected_mat_in = st.selectbox("選擇進貨項目", df_mat["材料編號"] + " - " + df_mat["材料名稱"], key="in")
            in_qty = st.number_input("進貨數量", min_value=1, step=1, key="in_q")
            vendor = st.text_input("來源廠商 / 備註")
            submit_in = st.form_submit_button("確認進貨入庫")
            
            if submit_in:
                mat_id = selected_mat_in.split(" - ")[0]
                idx = df_mat[df_mat["材料編號"] == mat_id].index[0]
                mat_name = df_mat.loc[idx, "材料名稱"]
                unit = df_mat.loc[idx, "單位"]
                
                df_mat.loc[idx, "目前庫存"] += in_qty
                df_mat.to_csv(MATERIALS_FILE, index=False, encoding="utf-8-sig")
                add_log("進貨入庫", mat_name, f"+{in_qty} {unit}", f"進貨廠商: {vendor}")
                st.success(f"✅ 成功補貨 [{mat_name}] {in_qty} {unit}！")
                st.rerun()

    with tab3:
        with st.form("new_material_form"):
            new_name = st.text_input("材料名稱 (例如: 3/4 PVC彎頭)")
            new_cat = st.text_input("分類 (例如: 管路類)")
            init_qty = st.number_input("初始庫存數量", min_value=0, step=1)
            safe_qty = st.number_input("安全庫存警戒門檻", min_value=1, step=1)
            unit_str = st.text_input("計算單位 (例如: 個/支/捲)")
            submit_new = st.form_submit_button("確認新增建檔")
            
            if submit_new and new_name:
                new_id = f"M{len(df_mat) + 1:03d}"
                new_row = {"材料編號": new_id, "材料名稱": new_name, "分類": new_cat, "目前庫存": init_qty, "安全庫存量": safe_qty, "單位": unit_str}
                df_mat = pd.concat([df_mat, pd.DataFrame([new_row])], ignore_index=True)
                df_mat.to_csv(MATERIALS_FILE, index=False, encoding="utf-8-sig")
                add_log("新增品項", new_name, f"+{init_qty}{unit_str}", "新品建檔")
                st.success(f"✅ 成功新增品項：[{new_id}] {new_name}")
                st.rerun()

# -------------------------------------------------------------------
# 分頁 2：工具資產追蹤
# -------------------------------------------------------------------
elif page == "🔨 工具資產追蹤":
    st.header("🔨 固定資產與高價工具借還追蹤")
    
    df_tools = pd.read_csv(TOOLS_FILE, encoding="utf-8-sig")
    borrowed_df = df_tools[df_tools["狀態"] == "借出"]
    
    col1, col2 = st.columns(2)
    col1.metric("工具總數量", f"{len(df_tools)} 件")
    col2.metric("目前外借中工具", f"{len(borrowed_df)} 件")
    
    st.markdown("---")
    
    st.subheader("📋 所有工具清單與當前狀態")
    
    # 支援按類別篩選工具
    categories = ["全部類別"] + list(df_tools["分類"].unique())
    selected_cat = st.selectbox("🔍 依工具類別篩選", categories)
    
    if selected_cat != "全部類別":
        display_tools = df_tools[df_tools["分類"] == selected_cat]
    else:
        display_tools = df_tools
        
    st.dataframe(display_tools, use_container_width=True)
    
    st.markdown("---")
    
    col_b, col_r = st.columns(2)
    
    with col_b:
        st.subheader("📤 登記工具借出")
        in_stock_tools = df_tools[df_tools["狀態"] == "在庫"]
        if not in_stock_tools.empty:
            tool_to_borrow = st.selectbox("選擇要借出的工具", in_stock_tools["工具編號"] + " - " + in_stock_tools["工具名稱"])
            borrower_name = st.text_input("借用師傅姓名", key="b_name")
            if st.button("確認登記借出"):
                if borrower_name:
                    t_id = tool_to_borrow.split(" - ")[0]
                    idx = df_tools[df_tools["工具編號"] == t_id].index[0]
                    today_str = datetime.now().strftime("%Y-%m-%d")
                    
                    df_tools.loc[idx, "狀態"] = "借出"
                    df_tools.loc[idx, "當前借用人"] = borrower_name
                    df_tools.loc[idx, "借出日期"] = today_str
                    df_tools.to_csv(TOOLS_FILE, index=False, encoding="utf-8-sig")
                    
                    add_log("工具借出", df_tools.loc[idx, "工具名稱"], borrower_name, f"借出日期: {today_str}")
                    st.success(f"✅ [{df_tools.loc[idx, '工具名稱']}] 已順利借給【{borrower_name}】")
                    st.rerun()
                else:
                    st.warning("⚠️ 請輸入借用師傅姓名！")
        else:
            st.info("目前所有工具皆外借中，無在庫工具。")

    with col_r:
        st.subheader("📥 登記工具歸還")
        if not borrowed_df.empty:
            tool_to_return = st.selectbox("選擇要歸還的工具", borrowed_df["工具編號"] + " - " + borrowed_df["工具名稱"])
            if st.button("確認登記歸還"):
                t_id = tool_to_return.split(" - ")[0]
                idx = df_tools[df_tools["工具編號"] == t_id].index[0]
                b_name = df_tools.loc[idx, "當前借用人"]
                
                df_tools.loc[idx, "狀態"] = "在庫"
                df_tools.loc[idx, "當前借用人"] = "無"
                df_tools.loc[idx, "借出日期"] = "無"
                df_tools.to_csv(TOOLS_FILE, index=False, encoding="utf-8-sig")
                
                add_log("工具歸還", df_tools.loc[idx, "工具名稱"], b_name, "歸還入庫")
                st.success(f"✅ [{df_tools.loc[idx, '工具名稱']}] 已歸還入庫！")
                st.rerun()
        else:
            st.success("🎉 目前所有工具皆在庫，沒有外借中的工具！")

# -------------------------------------------------------------------
# 分頁 3：數據分析儀表板
# -------------------------------------------------------------------
elif page == "📊 數據分析儀表板":
    st.header("📊 後台數據分析與決策儀表板")
    
    df_logs = pd.read_csv(LOGS_FILE, encoding="utf-8-sig")
    
    if df_logs.empty:
        st.info("目前尚無足夠的歷史流水帳數據可供分析，請先執行幾筆領料或借還操作！")
    else:
        col_chart1, col_chart2 = st.columns(2)
        
        with col_chart1:
            st.subheader("🔥 熱門耗材領料排行榜")
            usage_logs = df_logs[df_logs["類型"] == "領料出庫"]
            if not usage_logs.empty:
                mat_counts = usage_logs["項目名稱"].value_counts()
                
                fig, ax = plt.subplots(figsize=(6, 4))
                ax.barh(mat_counts.index, mat_counts.values, color='#3498db', edgecolor='black')
                ax.set_xlabel("領用次數 (Times)")
                ax.invert_yaxis()
                plt.tight_layout()
                st.pyplot(fig)
            else:
                st.write("尚無領料數據。")
                
        with col_chart2:
            st.subheader("🔨 工具借用頻率佔比")
            tool_logs = df_logs[df_logs["類型"] == "工具借出"]
            if not tool_logs.empty:
                tool_counts = tool_logs["項目名稱"].value_counts()
                
                fig2, ax2 = plt.subplots(figsize=(6, 4))
                ax2.pie(tool_counts.values, labels=tool_counts.index, autopct='%1.1f%%', startangle=140, colors=['#e74c3c', '#f1c40f', '#2ecc71', '#9b59b6'])
                plt.tight_layout()
                st.pyplot(fig2)
            else:
                st.write("尚無工具借出數據。")

# -------------------------------------------------------------------
# 分頁 4：歷史異動紀錄
# -------------------------------------------------------------------
elif page == "📜 歷史異動紀錄":
    st.header("📜 系統完整流水帳歷程")
    df_logs = pd.read_csv(LOGS_FILE, encoding="utf-8-sig")
    st.dataframe(df_logs.sort_index(ascending=False), use_container_width=True)