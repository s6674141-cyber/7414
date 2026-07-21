import pandas as pd
from datetime import datetime
import streamlit as st
import matplotlib.pyplot as plt
import gspread
from google.oauth2.service_account import Credentials
import re

# -------------------------------------------------------------------
# 0. 跨平台中文字型自動設定
# -------------------------------------------------------------------
plt.rcParams['font.sans-serif'] = [
    'Microsoft JhengHei',  # Windows 微軟正黑體
    'PingFang TC',        # Mac 蘋方體
    'Arial Unicode MS', 
    'DejaVu Sans'
]
plt.rcParams['axes.unicode_minus'] = False

# -------------------------------------------------------------------
# 1. 頁面基本設定
# -------------------------------------------------------------------
st.set_page_config(
    page_title="水電倉管與資產追蹤系統 (Google Cloud 版)",
    page_icon="🛠️",
    layout="wide"
)

# -------------------------------------------------------------------
# 2. Google Sheets 雲端資料庫連線邏輯
# -------------------------------------------------------------------
@st.cache_resource
def get_gsheet_client():
    """使用 Streamlit Secrets 金鑰連線 Google Sheets API"""
    scope = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    credentials_info = st.secrets["gcp_service_account"]
    creds = Credentials.from_service_account_info(credentials_info, scopes=scope)
    client = gspread.authorize(creds)
    return client

def load_data(worksheet_name):
    """讀取 Google Sheets 指定分頁"""
    try:
        client = get_gsheet_client()
        sheet = client.open("水電倉管資料庫").worksheet(worksheet_name)
        data = sheet.get_all_records()
        return pd.DataFrame(data), sheet
    except Exception as e:
        st.error(f"❌ 無法連線至 Google Sheets 分頁 [{worksheet_name}]，請檢查名稱或共用權限！錯誤資訊：{e}")
        return pd.DataFrame(), None

def save_data(sheet, df):
    """將 DataFrame 覆寫回 Google Sheets 指定分頁"""
    sheet.clear()
    sheet.update([df.columns.values.tolist()] + df.astype(str).values.tolist())

def add_log_gsheet(action_type, item_name, detail, note=""):
    """寫入歷史流水帳至 Google Sheets 的 logs 分頁"""
    df_logs, sheet_logs = load_data("logs")
    if sheet_logs is not None:
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        new_log = {"時間": now_str, "類型": action_type, "項目名稱": item_name, "變動數量/借用人": detail, "備註": note}
        df_logs = pd.concat([df_logs, pd.DataFrame([new_log])], ignore_index=True)
        save_data(sheet_logs, df_logs)

def undo_last_log():
    """撤銷 / 復原最後一筆操作歷史 (精準還原分類、數量與安全存量)"""
    df_logs, sheet_logs = load_data("logs")
    if df_logs.empty:
        return False, "目前沒有可撤銷的歷史紀錄！"
    
    last_log = df_logs.iloc[-1]
    action_type = str(last_log["類型"])
    item_name = str(last_log["項目名稱"])
    detail = str(last_log["變動數量/借用人"])
    note = str(last_log["備註"])
    
    # 1. 撤銷「領料出庫」或「進貨入庫」
    if action_type in ["領料出庫", "進貨入庫"]:
        df_mat, sheet_mat = load_data("materials")
        if not df_mat.empty and item_name in df_mat["材料名稱"].astype(str).values:
            idx = df_mat[df_mat["材料名稱"].astype(str) == item_name].index[0]
            # 抽出純數字
            numbers = re.findall(r'\d+', detail)
            qty = int(numbers[0]) if numbers else 0
            
            if action_type == "領料出庫":
                df_mat.loc[idx, "目前庫存"] = int(df_mat.loc[idx, "目前庫存"]) + qty
            else:
                df_mat.loc[idx, "目前庫存"] = max(0, int(df_mat.loc[idx, "目前庫存"]) - qty)
                
            save_data(sheet_mat, df_mat)

    # 2. 撤銷「新增品項」(自動刪除剛剛誤建的材料)
    elif action_type == "新增品項":
        df_mat, sheet_mat = load_data("materials")
        if not df_mat.empty and item_name in df_mat["材料名稱"].astype(str).values:
            df_mat = df_mat[df_mat["材料名稱"].astype(str) != item_name].reset_index(drop=True)
            save_data(sheet_mat, df_mat)

    # 3. 撤銷「刪除品項」(精準還原分類、數量、安全存量、單位)
    elif action_type == "刪除品項":
        df_mat, sheet_mat = load_data("materials")
        if item_name not in df_mat["材料名稱"].astype(str).values:
            new_id = f"M{len(df_mat) + 1:03d}"
            
            # 從 note 解析備份資訊: "分類:電線類 | 庫存:100 | 安全量:10 | 單位:捲"
            cat = "未分類"
            qty = 0
            safe_qty = 5
            unit = "個"
            
            if "分類:" in note:
                try:
                    parts = note.split(" | ")
                    for p in parts:
                        if p.startswith("分類:"): cat = p.replace("分類:", "")
                        elif p.startswith("庫存:"): qty = int(p.replace("庫存:", ""))
                        elif p.startswith("安全量:"): safe_qty = int(p.replace("安全量:", ""))
                        elif p.startswith("單位:"): unit = p.replace("單位:", "")
                except:
                    pass
            
            new_row = {
                "材料編號": new_id, 
                "材料名稱": item_name, 
                "分類": cat, 
                "目前庫存": qty, 
                "安全庫存量": safe_qty, 
                "單位": unit
            }
            df_mat = pd.concat([df_mat, pd.DataFrame([new_row])], ignore_index=True)
            save_data(sheet_mat, df_mat)

    # 4. 撤銷「工具借出」、「工具歸還」、「工具送修」或「維修完成」
    elif action_type in ["工具借出", "工具歸還", "工具送修", "維修完成"]:
        df_tools, sheet_tools = load_data("tools")
        if not df_tools.empty and item_name in df_tools["工具名稱"].astype(str).values:
            idx = df_tools[df_tools["工具名稱"].astype(str) == item_name].index[0]
            
            if action_type == "工具借出":
                df_tools.loc[idx, "狀態"] = "在庫"
                df_tools.loc[idx, "當前借用人"] = "無"
                df_tools.loc[idx, "借出日期"] = "無"
            elif action_type == "工具歸還":
                df_tools.loc[idx, "狀態"] = "借出"
                df_tools.loc[idx, "當前借用人"] = detail
                df_tools.loc[idx, "借出日期"] = datetime.now().strftime("%Y-%m-%d")
            elif action_type in ["工具送修", "維修完成"]:
                df_tools.loc[idx, "狀態"] = "在庫"
                df_tools.loc[idx, "當前借用人"] = "無"
                df_tools.loc[idx, "借出日期"] = "無"
                
            save_data(sheet_tools, df_tools)

    # 5. 撤銷「工具報銷刪除」(自動精準還原工具)
    elif action_type == "工具報銷刪除":
        df_tools, sheet_tools = load_data("tools")
        if item_name not in df_tools["工具名稱"].astype(str).values:
            new_id = f"T{len(df_tools) + 1:03d}"
            cat = "未分類"
            if "分類:" in note:
                cat = note.replace("分類:", "").strip()
                
            new_row = {
                "工具編號": new_id,
                "工具名稱": item_name,
                "分類": cat,
                "狀態": "在庫",
                "當前借用人": "無",
                "借出日期": "無"
            }
            df_tools = pd.concat([df_tools, pd.DataFrame([new_row])], ignore_index=True)
            save_data(sheet_tools, df_tools)

    # 刪除最後一筆 Log 並儲存
    df_logs = df_logs.iloc[:-1].reset_index(drop=True)
    save_data(sheet_logs, df_logs)
    add_log_gsheet("撤銷操作", item_name, "反轉成功", f"已撤銷: {action_type} ({detail})")
    return True, f"✅ 已成功撤銷【{action_type} - {item_name}】並還原資料庫！"

# -------------------------------------------------------------------
# 3. 側邊欄控制與導覽目錄
# -------------------------------------------------------------------
st.sidebar.title("🛠️ 水電倉管系統 (雲端同步版)")
st.sidebar.markdown("---")
page = st.sidebar.radio(
    "請選擇系統功能分頁：",
    ["📦 材料庫存管理", "🔨 工具資產追蹤", "📊 數據分析儀表板", "📜 歷史異動紀錄", "⚙️ 管理員安全後台"]
)

# -------------------------------------------------------------------
# 分頁 1：材料庫存管理
# -------------------------------------------------------------------
if page == "📦 材料庫存管理":
    st.header("📦 材料耗材庫存管理模組 (Google Sheets 雲端連線)")
    
    df_mat, sheet_mat = load_data("materials")
    
    if not df_mat.empty:
        df_mat["目前庫存"] = pd.to_numeric(df_mat["目前庫存"], errors='coerce').fillna(0).astype(int)
        df_mat["安全庫存量"] = pd.to_numeric(df_mat["安全庫存量"], errors='coerce').fillna(0).astype(int)
        
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
        
        st.subheader("🔄 庫存異動與資料編輯面板")
        tab1, tab2, tab3, tab4, tab5 = st.tabs(["📤 師傅領料登記", "📥 進貨入庫登記", "➕ 新增材料品項", "✏️ 修改/編輯材料資料", "🗑️ 刪除材料品項"])
        
        with tab1:
            with st.form("borrow_material_form"):
                selected_mat = st.selectbox("選擇領料項目", df_mat["材料編號"].astype(str) + " - " + df_mat["材料名稱"])
                borrow_qty = st.number_input("領取數量", min_value=1, step=1)
                worker = st.text_input("領用師傅 / 工地名稱")
                submit_borrow = st.form_submit_button("確認領料出庫")
                
                if submit_borrow:
                    mat_id = selected_mat.split(" - ")[0]
                    idx = df_mat[df_mat["材料編號"].astype(str) == mat_id].index[0]
                    mat_name = df_mat.loc[idx, "材料名稱"]
                    curr_qty = df_mat.loc[idx, "目前庫存"]
                    unit = df_mat.loc[idx, "單位"]
                    
                    if borrow_qty > curr_qty:
                        st.error(f"❌ 庫存不足！目前剩餘庫存為 {curr_qty} {unit}")
                    else:
                        df_mat.loc[idx, "目前庫存"] -= borrow_qty
                        save_data(sheet_mat, df_mat)
                        add_log_gsheet("領料出庫", mat_name, f"-{borrow_qty} {unit}", f"領用人/工程: {worker}")
                        st.success(f"✅ 成功領用 [{mat_name}] {borrow_qty} {unit}！已同步存入 Google Sheets！")
                        st.rerun()

        with tab2:
            with st.form("add_stock_form"):
                selected_mat_in = st.selectbox("選擇進貨項目", df_mat["材料編號"].astype(str) + " - " + df_mat["材料名稱"], key="in")
                in_qty = st.number_input("進貨數量", min_value=1, step=1, key="in_q")
                vendor = st.text_input("來源廠商 / 備註")
                submit_in = st.form_submit_button("確認進貨入庫")
                
                if submit_in:
                    mat_id = selected_mat_in.split(" - ")[0]
                    idx = df_mat[df_mat["材料編號"].astype(str) == mat_id].index[0]
                    mat_name = df_mat.loc[idx, "材料名稱"]
                    unit = df_mat.loc[idx, "單位"]
                    
                    df_mat.loc[idx, "目前庫存"] += in_qty
                    save_data(sheet_mat, df_mat)
                    add_log_gsheet("進貨入庫", mat_name, f"+{in_qty} {unit}", f"進貨廠商: {vendor}")
                    st.success(f"✅ 成功補貨 [{mat_name}] {in_qty} {unit}！已同步存入 Google Sheets！")
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
                    save_data(sheet_mat, df_mat)
                    add_log_gsheet("新增品項", new_name, f"+{init_qty}{unit_str}", f"分類:{new_cat} | 庫存:{init_qty} | 安全量:{safe_qty} | 單位:{unit_str}")
                    st.success(f"✅ 成功新增品項：[{new_id}] {new_name}！")
                    st.rerun()

        with tab4:
            st.subheader("✏️ 修改既有材料名稱、分類或安全庫存")
            selected_edit_mat = st.selectbox("選擇要修改的材料", df_mat["材料編號"].astype(str) + " - " + df_mat["材料名稱"], key="edit_mat_sel")
            
            if selected_edit_mat:
                edit_m_id = selected_edit_mat.split(" - ")[0]
                m_idx = df_mat[df_mat["材料編號"].astype(str) == edit_m_id].index[0]
                
                with st.form("edit_material_form"):
                    col_e1, col_e2 = st.columns(2)
                    with col_e1:
                        edit_name = st.text_input("材料名稱", value=df_mat.loc[m_idx, "材料名稱"])
                        edit_cat = st.text_input("分類名稱", value=df_mat.loc[m_idx, "分類"])
                        edit_unit = st.text_input("計算單位", value=df_mat.loc[m_idx, "單位"])
                    with col_e2:
                        edit_qty = st.number_input("目前庫存數量", value=int(df_mat.loc[m_idx, "目前庫存"]), min_value=0, step=1)
                        edit_safe_qty = st.number_input("安全庫存門檻", value=int(df_mat.loc[m_idx, "安全庫存量"]), min_value=1, step=1)
                        
                    submit_edit_mat = st.form_submit_button("💾 儲存修改內容")
                    
                    if submit_edit_mat:
                        old_name = df_mat.loc[m_idx, "材料名稱"]
                        df_mat.loc[m_idx, "材料名稱"] = edit_name
                        df_mat.loc[m_idx, "分類"] = edit_cat
                        df_mat.loc[m_idx, "單位"] = edit_unit
                        df_mat.loc[m_idx, "目前庫存"] = edit_qty
                        df_mat.loc[m_idx, "安全庫存量"] = edit_safe_qty
                        
                        save_data(sheet_mat, df_mat)
                        add_log_gsheet("資料修改", edit_name, "更正資料", f"原名: {old_name}")
                        st.success(f"✅ 成功更新材料 [{edit_m_id}] 資料！")
                        st.rerun()

        with tab5:
            st.subheader("🗑️ 刪除/下架材料品項")
            selected_del_mat = st.selectbox("選擇要刪除的材料", df_mat["材料編號"].astype(str) + " - " + df_mat["材料名稱"], key="del_mat_sel")
            
            if selected_del_mat:
                del_m_id = selected_del_mat.split(" - ")[0]
                m_del_idx = df_mat[df_mat["材料編號"].astype(str) == del_m_id].index[0]
                del_m_name = df_mat.loc[m_del_idx, "材料名稱"]
                del_cat = df_mat.loc[m_del_idx, "分類"]
                del_qty = df_mat.loc[m_del_idx, "目前庫存"]
                del_safe = df_mat.loc[m_del_idx, "安全庫存量"]
                del_unit = df_mat.loc[m_del_idx, "單位"]
                
                st.warning(f"⚠️ **確定要刪除材料 [{del_m_id}] {del_m_name} 嗎？此操作將無法復原！**")
                confirm_del_m = st.checkbox(f"我確定要刪除 [{del_m_name}]", key="chk_del_m")
                
                if st.button("🔥 確定執行刪除材料"):
                    if confirm_del_m:
                        df_mat = df_mat.drop(m_del_idx).reset_index(drop=True)
                        save_data(sheet_mat, df_mat)
                        # 將刪除前的數據打包備份在 Note 裡面！
                        backup_note = f"分類:{del_cat} | 庫存:{del_qty} | 安全量:{del_safe} | 單位:{del_unit}"
                        add_log_gsheet("刪除品項", del_m_name, "材料刪除", backup_note)
                        st.success(f"✅ 成功刪除材料：[{del_m_name}]！")
                        st.rerun()
                    else:
                        st.error("❌ 請先勾選上方「我確定要刪除...」核取方塊！")

# -------------------------------------------------------------------
# 分頁 2：工具資產追蹤 (含維修/保養流程)
# -------------------------------------------------------------------
elif page == "🔨 工具資產追蹤":
    st.header("🔨 固定資產與高價工具借還與維修追蹤")
    
    df_tools, sheet_tools = load_data("tools")
    
    if not df_tools.empty:
        borrowed_df = df_tools[df_tools["狀態"] == "借出"]
        repairing_df = df_tools[df_tools["狀態"] == "維修中"]
        
        col1, col2, col3 = st.columns(3)
        col1.metric("工具總數量", f"{len(df_tools)} 件")
        col2.metric("目前外借中工具", f"{len(borrowed_df)} 件")
        col3.metric("🔧 維修/待保養中", f"{len(repairing_df)} 件", delta_color="inverse")
        
        st.markdown("---")
        
        st.subheader("📋 所有工具清單與當前狀態")
        
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            categories = ["全部類別"] + list(df_tools["分類"].unique())
            selected_cat = st.selectbox("🔍 依工具類別篩選", categories)
        with col_f2:
            status_opts = ["全部狀態", "在庫", "借出", "維修中"]
            selected_status = st.selectbox("🔍 依使用狀態篩選", status_opts)
            
        display_tools = df_tools.copy()
        if selected_cat != "全部類別":
            display_tools = display_tools[display_tools["分類"] == selected_cat]
        if selected_status != "全部狀態":
            display_tools = display_tools[display_tools["狀態"] == selected_status]
            
        st.dataframe(display_tools, use_container_width=True)
        
        st.markdown("---")
        
        tab_tb, tab_tr, tab_maint, tab_te, tab_td = st.tabs(["📤 登記工具借出", "📥 登記工具歸還", "🔧 損壞報修 / 維修完成", "✏️ 修改/編輯工具", "🗑️ 報銷刪除工具"])
        
        with tab_tb:
            in_stock_tools = df_tools[df_tools["狀態"] == "在庫"]
            if not in_stock_tools.empty:
                tool_to_borrow = st.selectbox("選擇要借出的工具", in_stock_tools["工具編號"].astype(str) + " - " + in_stock_tools["工具名稱"])
                borrower_name = st.text_input("借用師傅姓名", key="b_name")
                if st.button("確認登記借出"):
                    if borrower_name:
                        t_id = tool_to_borrow.split(" - ")[0]
                        idx = df_tools[df_tools["工具編號"].astype(str) == t_id].index[0]
                        today_str = datetime.now().strftime("%Y-%m-%d")
                        
                        df_tools.loc[idx, "狀態"] = "借出"
                        df_tools.loc[idx, "當前借用人"] = borrower_name
                        df_tools.loc[idx, "借出日期"] = today_str
                        
                        save_data(sheet_tools, df_tools)
                        add_log_gsheet("工具借出", df_tools.loc[idx, "工具名稱"], borrower_name, f"借出日期: {today_str}")
                        st.success(f"✅ [{df_tools.loc[idx, '工具名稱']}] 已順利借給【{borrower_name}】！")
                        st.rerun()
                    else:
                        st.warning("⚠️ 請輸入借用師傅姓名！")
            else:
                st.info("目前無在庫可借出工具（全部外借中或維修中）。")

        with tab_tr:
            if not borrowed_df.empty:
                tool_to_return = st.selectbox("選擇要歸還的工具", borrowed_df["工具編號"].astype(str) + " - " + borrowed_df["工具名稱"])
                if st.button("確認登記歸還"):
                    t_id = tool_to_return.split(" - ")[0]
                    idx = df_tools[df_tools["工具編號"].astype(str) == t_id].index[0]
                    b_name = df_tools.loc[idx, "當前借用人"]
                    
                    df_tools.loc[idx, "狀態"] = "在庫"
                    df_tools.loc[idx, "當前借用人"] = "無"
                    df_tools.loc[idx, "借出日期"] = "無"
                    
                    save_data(sheet_tools, df_tools)
                    add_log_gsheet("工具歸還", df_tools.loc[idx, "工具名稱"], b_name, "歸還入庫")
                    st.success(f"✅ [{df_tools.loc[idx, '工具名稱']}] 已歸還入庫！")
                    st.rerun()
            else:
                st.success("🎉 目前沒有外借中的工具！")

        with tab_maint:
            col_m1, col_m2 = st.columns(2)
            
            with col_m1:
                st.subheader("🛠️ 登記工具送修 / 待保養")
                can_repair_tools = df_tools[df_tools["狀態"].isin(["在庫", "借出"])]
                if not can_repair_tools.empty:
                    tool_to_repair = st.selectbox("選擇要送修的工具", can_repair_tools["工具編號"].astype(str) + " - " + can_repair_tools["工具名稱"], key="sel_rep")
                    repair_reason = st.text_input("故障原因 / 保養項目 (例: 電池壞掉 / 電線接觸不良)")
                    repair_vendor = st.text_input("維修廠商 / 送修備註 (選填)")
                    
                    if st.button("🔧 確認登記送修"):
                        if repair_reason:
                            t_id = tool_to_repair.split(" - ")[0]
                            idx = df_tools[df_tools["工具編號"].astype(str) == t_id].index[0]
                            t_name = df_tools.loc[idx, "工具名稱"]
                            
                            df_tools.loc[idx, "狀態"] = "維修中"
                            df_tools.loc[idx, "當前借用人"] = f"維修中 ({repair_vendor})" if repair_vendor else "維修中"
                            df_tools.loc[idx, "借出日期"] = datetime.now().strftime("%Y-%m-%d")
                            
                            save_data(sheet_tools, df_tools)
                            add_log_gsheet("工具送修", t_name, "轉維修中", f"原因: {repair_reason} | 廠商: {repair_vendor}")
                            st.success(f"✅ [{t_name}] 已登記為【維修中】狀態！")
                            st.rerun()
                        else:
                            st.warning("⚠️ 請輸入故障原因或保養項目！")
                else:
                    st.info("目前沒有可送修的工具。")
                    
            with col_m2:
                st.subheader("✅ 登記維修完成入庫")
                if not repairing_df.empty:
                    tool_repaired = st.selectbox("選擇已修好的工具", repairing_df["工具編號"].astype(str) + " - " + repairing_df["工具名稱"], key="sel_repaired")
                    repair_note = st.text_input("維修花費金額 / 修復備註 (選填)")
                    
                    if st.button("🎉 確認修復完工入庫"):
                        t_id = tool_repaired.split(" - ")[0]
                        idx = df_tools[df_tools["工具編號"].astype(str) == t_id].index[0]
                        t_name = df_tools.loc[idx, "工具名稱"]
                        
                        df_tools.loc[idx, "狀態"] = "在庫"
                        df_tools.loc[idx, "當前借用人"] = "無"
                        df_tools.loc[idx, "借出日期"] = "無"
                        
                        save_data(sheet_tools, df_tools)
                        add_log_gsheet("維修完成", t_name, "修復完工入庫", f"備註: {repair_note}")
                        st.success(f"✅ [{t_name}] 已維修完成，重新恢復為【在庫】狀態！")
                        st.rerun()
                else:
                    st.success("🎉 目前沒有正在維修中的工具！")

        with tab_te:
            st.subheader("✏️ 修改工具編號、名稱或所屬類別")
            selected_edit_tool = st.selectbox("選擇要修改的工具", df_tools["工具編號"].astype(str) + " - " + df_tools["工具名稱"], key="edit_tool_sel")
            
            if selected_edit_tool:
                edit_t_id = selected_edit_tool.split(" - ")[0]
                t_idx = df_tools[df_tools["工具編號"].astype(str) == edit_t_id].index[0]
                
                with st.form("edit_tool_form"):
                    col_te1, col_te2 = st.columns(2)
                    with col_te1:
                        edit_tool_id = st.text_input("工具編號", value=df_tools.loc[t_idx, "工具編號"])
                        edit_tool_name = st.text_input("工具名稱", value=df_tools.loc[t_idx, "工具名稱"])
                    with col_te2:
                        edit_tool_cat = st.text_input("分類名稱 (例如: 照明工具 (F))", value=df_tools.loc[t_idx, "分類"])
                        
                    submit_edit_tool = st.form_submit_button("💾 儲存修改內容")
                    
                    if submit_edit_tool:
                        old_t_name = df_tools.loc[t_idx, "工具名稱"]
                        df_tools.loc[t_idx, "工具編號"] = edit_tool_id
                        df_tools.loc[t_idx, "工具名稱"] = edit_tool_name
                        df_tools.loc[t_idx, "分類"] = edit_tool_cat
                        
                        save_data(sheet_tools, df_tools)
                        add_log_gsheet("工具資料修改", edit_tool_name, "更正資料", f"原名: {old_t_name}")
                        st.success(f"✅ 成功更新工具 [{edit_tool_id}] 資料！")
                        st.rerun()

        with tab_td:
            st.subheader("🗑️ 報銷/刪除工具資產")
            selected_del_tool = st.selectbox("選擇要報銷刪除的工具", df_tools["工具編號"].astype(str) + " - " + df_tools["工具名稱"], key="del_tool_sel")
            
            if selected_del_tool:
                del_t_id = selected_del_tool.split(" - ")[0]
                t_del_idx = df_tools[df_tools["工具編號"].astype(str) == del_t_id].index[0]
                del_t_name = df_tools.loc[t_del_idx, "工具名稱"]
                del_t_cat = df_tools.loc[t_del_idx, "分類"]
                
                st.warning(f"⚠️ **確定要刪除/報銷工具 [{del_t_id}] {del_t_name} 嗎？此操作將無法復原！**")
                confirm_del_t = st.checkbox(f"我確定要報銷刪除 [{del_t_name}]", key="chk_del_t")
                
                if st.button("🔥 確定執行報銷刪除"):
                    if confirm_del_t:
                        df_tools = df_tools.drop(t_del_idx).reset_index(drop=True)
                        save_data(sheet_tools, df_tools)
                        add_log_gsheet("工具報銷刪除", del_t_name, "工具刪除", f"分類:{del_t_cat}")
                        st.success(f"✅ 成功刪除/報銷工具：[{del_t_name}]！")
                        st.rerun()
                    else:
                        st.error("❌ 請先勾選上方「我確定要報銷刪除...」核取方塊！")

# -------------------------------------------------------------------
# 分頁 3：數據分析儀表板
# -------------------------------------------------------------------
elif page == "📊 數據分析儀表板":
    st.header("📊 後台數據分析與決策儀表板")
    
    df_logs, _ = load_data("logs")
    
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
            st.subheader("🔨 工具借用與維修頻率佔比")
            tool_logs = df_logs[df_logs["類型"].isin(["工具借出", "工具送修"])]
            if not tool_logs.empty:
                tool_counts = tool_logs["項目名稱"].value_counts()
                
                fig2, ax2 = plt.subplots(figsize=(6, 4))
                ax2.pie(tool_counts.values, labels=tool_counts.index, autopct='%1.1f%%', startangle=140, colors=['#e74c3c', '#f1c40f', '#2ecc71', '#9b59b6'])
                plt.tight_layout()
                st.pyplot(fig2)
            else:
                st.write("尚無工具借出或送修數據。")

# -------------------------------------------------------------------
# 分頁 4：歷史異動紀錄
# -------------------------------------------------------------------
elif page == "📜 歷史異動紀錄":
    st.header("📜 系統完整流水帳歷程 (Google Sheets 即時同步)")
    
    df_logs, _ = load_data("logs")
    
    if not df_logs.empty:
        st.subheader("↩️ 操作反轉與復原區域")
        last_log = df_logs.iloc[-1]
        st.info(f"📌 **最近一次操作紀錄：** 【{last_log['時間']}】 - 【{last_log['類型']}】 - {last_log['項目名稱']} ({last_log['變動數量/借用人']})")
        
        col_u1, col_u2 = st.columns([1, 4])
        with col_u1:
            if st.button("↩️ 一鍵撤銷最後這筆操作", type="primary"):
                success, msg = undo_last_log()
                if success:
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)
        
        st.markdown("---")
        st.subheader("📋 完整歷史流水帳明細")
        st.dataframe(df_logs.sort_index(ascending=False), use_container_width=True)

# -------------------------------------------------------------------
# 分頁 5：⚙️ 管理員安全後台
# -------------------------------------------------------------------
elif page == "⚙️ 管理員安全後台":
    st.header("⚙️ 倉管系統管理員專屬後台")
    st.caption("🔒 本區域為管理員權限，一般師傅與使用者請勿操作。")
    st.markdown("---")
    
    pwd = st.text_input("🔑 請輸入管理員通行密碼", type="password")
    
    if pwd == "admin123":
        st.success("🔓 管理員驗證成功！")
        st.info("💡 目前資料庫已直連您的個人 Google Sheets「水電倉管資料庫」，所有異動皆即時存入 Google 雲端！")
    elif pwd != "":
        st.error("❌ 密碼錯誤，無法開啟管理員權限！")
