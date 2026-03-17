import streamlit as st
import baostock as bs
import pandas as pd
import datetime
import re
from PIL import Image
import pytesseract
import requests
import io  # 新增：用于在内存中生成 Excel

st.set_page_config(page_title="股票分拣终端", page_icon="📈", layout="wide") # 开启宽屏模式

st.title("📈 股票形态分拣终端 v8.0 (旗舰版)")
st.markdown("⚡ **核心引擎:** 腾讯毫秒级实盘 + BS历史缓存 | 🎨 **全新特性:** 沉浸式表格看板 + 一键报表导出")

# ==========================================
# 记忆缓存模块
# ==========================================
@st.cache_data(ttl=3600*12, show_spinner=False)
def get_baostock_history(symbol):
    bs.login()
    bs_code = "sh." + symbol if symbol.startswith('6') else "sz." + symbol
    today = datetime.date.today()
    bs_end = today.strftime('%Y-%m-%d')
    bs_start = (today - datetime.timedelta(days=20)).strftime('%Y-%m-%d')
    
    rs = bs.query_history_k_data_plus(bs_code, "date,high", start_date=bs_start, end_date=bs_end, frequency="d")
    data = []
    while (rs.error_code == '0') & rs.next():
        data.append(rs.get_row_data())
    bs.logout()
    return data

def get_tencent_batch_realtime(symbol_list):
    tc_codes = ["sh" + s if s.startswith('6') else "sz" + s for s in symbol_list]
    query_str = ",".join(tc_codes)
    try:
        res = requests.get(f"http://qt.gtimg.cn/q={query_str}", timeout=3)
        result_dict = {}
        blocks = res.text.split(';')
        for block in blocks:
            if '="' in block:
                code_part = block.split('="')[0].split('_')[-1]
                clean_code = code_part[2:]
                content = block.split('="')[1]
                fields = content.split('~')
                if len(fields) > 33:
                    d_str = fields[30][:8]
                    result_dict[clean_code] = {
                        "name": fields[1],
                        "high": float(fields[33]),
                        "date": f"{d_str[:4]}-{d_str[4:6]}-{d_str[6:]}"
                    }
        return result_dict
    except:
        return {}

# ==========================================
# 交互界面
# ==========================================
with st.expander("📸 展开使用【截图识股】功能", expanded=False):
    uploaded_file = st.file_uploader("支持上传手机截屏自动提取代码", type=["jpg", "png", "jpeg"])
    auto_codes = ""
    if uploaded_file is not None:
        with st.spinner("AI 视觉引擎扫图中..."):
            try:
                image = Image.open(uploaded_file).convert('RGB')
                text = pytesseract.image_to_string(image, config='--psm 6')
                codes = re.findall(r'\b(60\d{4}|68\d{4}|00\d{4}|30\d{4})\b', text)
                unique_codes = list(set(codes))
                if unique_codes:
                    st.success(f"🎉 成功锁定 {len(unique_codes)} 只目标！")
                    auto_codes = ", ".join(unique_codes)
            except:
                st.error("识别失败，请确保截图清晰。")

st.markdown("### ⌨️ 代码控制台")
user_input = st.text_input("待检测阵列 (逗号分隔):", value=auto_codes if auto_codes else "600519, 000001, 002594, 601318")

# ==========================================
# 主力运算引擎
# ==========================================
if st.button("🚀 启动极速分拣", use_container_width=True):
    
    raw_list = user_input.replace("，", ",").split(",")
    clean_stocks = list(set([re.search(r'\b(60\d{4}|68\d{4}|00\d{4}|30\d{4})\b', raw).group() for raw in raw_list if re.search(r'\b(60\d{4}|68\d{4}|00\d{4}|30\d{4})\b', raw)]))

    if not clean_stocks:
        st.warning("❌ 必须输入至少一只 6 位数 A 股代码。")
    else:
        with st.spinner("⚡ 正在执行毫秒级跨源数据融合..."):
            tc_realtime_data = get_tencent_batch_realtime(clean_stocks)
            
            # 使用字典列表来存储结构化数据，方便转成表格
            all_results = []
            error_logs = []

            for symbol in clean_stocks:
                bs_data = get_baostock_history(symbol)
                tc_info = tc_realtime_data.get(symbol, {})
                tc_name = tc_info.get("name", symbol)
                tc_high = tc_info.get("high", 0.0)
                tc_date = tc_info.get("date", "")
                engine_tag = "🕰️ 复盘"
                
                if tc_date and tc_high > 0:
                    if len(bs_data) > 0:
                        if tc_date == bs_data[-1][0]:
                            bs_data[-1][1] = str(max(float(bs_data[-1][1]), tc_high))
                            engine_tag = "⚡ 实盘"
                        elif tc_date > bs_data[-1][0]:
                            bs_data.append([tc_date, str(tc_high)])
                            engine_tag = "⚡ 实盘"
                    else:
                        bs_data.append([tc_date, str(tc_high)])

                if len(bs_data) >= 3:
                    t_date = str(bs_data[-1][0])[5:]
                    y_date = str(bs_data[-2][0])[5:]
                    db_date = str(bs_data[-3][0])[5:]
                    t_high = float(bs_data[-1][1])    
                    y_high = float(bs_data[-2][1])    
                    db_high = float(bs_data[-3][1])   
                    
                    # 形态判定
                    pattern = ""
                    if t_high > y_high and y_high > db_high:
                        pattern = "🔥 双日连破"
                    elif t_high > y_high and y_high <= db_high:
                        pattern = "💡 今日突破"
                    elif t_high <= y_high and y_high <= db_high:
                        pattern = "🧊 连续未破"
                    elif t_high <= y_high and y_high > db_high:
                        pattern = "📉 冲高回落"
                        
                    all_results.append({
                        "股票代码": symbol,
                        "股票名称": tc_name,
                        "形态判定": pattern,
                        f"最新高 ({t_date})": t_high,
                        f"次新高 ({y_date})": y_high,
                        f"前高 ({db_date})": db_high,
                        "数据引擎": engine_tag
                    })
                else:
                    error_logs.append(f"{tc_name}({symbol})")

        # ==========================================
        # 全新 UI：看板与导出功能
        # ==========================================
        if all_results:
            st.markdown("---")
            st.subheader("📊 自动化复盘看板")
            
            # 将数据转换为 Pandas DataFrame，这是高级分析的核心
            df_all = pd.DataFrame(all_results)
            
            # 创建 4 个漂亮的标签页 (Tabs)
            tab1, tab2, tab3, tab4 = st.tabs(["🔥 双日连破", "💡 今日突破", "🧊 连续未破", "📉 冲高回落"])
            
            # 分别在不同的标签页展示不同形态的表格
            with tab1:
                df_sub = df_all[df_all['形态判定'] == "🔥 双日连破"]
                st.dataframe(df_sub, use_container_width=True, hide_index=True)
            with tab2:
                df_sub = df_all[df_all['形态判定'] == "💡 今日突破"]
                st.dataframe(df_sub, use_container_width=True, hide_index=True)
            with tab3:
                df_sub = df_all[df_all['形态判定'] == "🧊 连续未破"]
                st.dataframe(df_sub, use_container_width=True, hide_index=True)
            with tab4:
                df_sub = df_all[df_all['形态判定'] == "📉 冲高回落"]
                st.dataframe(df_sub, use_container_width=True, hide_index=True)

            # ====== 神奇的内存级 Excel 导出功能 ======
            st.markdown("---")
            buffer = io.BytesIO() # 在内存里开辟一块空间
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                # 把所有结果保存到一个叫做“形态全景图”的 Sheet 里
                df_all.to_excel(writer, index=False, sheet_name='形态全景图')
            
            # 召唤下载按钮！
            st.download_button(
                label="📥 一键下载 Excel 报表",
                data=buffer.getvalue(),
                file_name=f"量化复盘报告_{datetime.date.today()}.xlsx",
                mime="application/vnd.ms-excel",
                use_container_width=True
            )

        # 错误提示静默放在最底部
        if error_logs:
            st.caption(f"⚠️ 忽略了 {len(error_logs)} 只数据不足的标的: {', '.join(error_logs)}")