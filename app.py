import streamlit as st
import baostock as bs
import pandas as pd
import datetime
import re
from PIL import Image
import pytesseract
import requests
import io

st.set_page_config(page_title="股票分拣终端", page_icon="📈", layout="wide")

st.title("📈 股票形态分拣终端 v9.0 (BOLL共振版)")
st.markdown("⚡ **双核引擎:** 腾讯实盘 + BS历史 | 🎯 **全新算法:** 新增 BOLL 布林带空间位置智能判定")

# ==========================================
# 记忆缓存模块 (获取更长的数据算 BOLL)
# ==========================================
@st.cache_data(ttl=3600*12, show_spinner=False)
def get_baostock_history(symbol):
    bs.login()
    bs_code = "sh." + symbol if symbol.startswith('6') else "sz." + symbol
    today = datetime.date.today()
    bs_end = today.strftime('%Y-%m-%d')
    # 往前推 45 天，确保绝对能拿到 20 个交易日的数据来算 BOLL
    bs_start = (today - datetime.timedelta(days=45)).strftime('%Y-%m-%d')
    
    # 获取日期、最高价(算突破)、收盘价(算BOLL)
    rs = bs.query_history_k_data_plus(bs_code, "date,high,close", start_date=bs_start, end_date=bs_end, frequency="d")
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
                        "price": float(fields[3]),  # 最新价 (算BOLL当前位置)
                        "high": float(fields[33]),  # 今日最高 (算突破)
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
user_input = st.text_input("待检测阵列 (逗号分隔):", value=auto_codes if auto_codes else "600519, 000001, 002594")

# ==========================================
# 主力运算引擎
# ==========================================
if st.button("🚀 启动极速分拣", use_container_width=True):
    
    raw_list = user_input.replace("，", ",").split(",")
    clean_stocks = list(set([re.search(r'\b(60\d{4}|68\d{4}|00\d{4}|30\d{4})\b', raw).group() for raw in raw_list if re.search(r'\b(60\d{4}|68\d{4}|00\d{4}|30\d{4})\b', raw)]))

    if not clean_stocks:
        st.warning("❌ 必须输入至少一只 6 位数 A 股代码。")
    else:
        with st.spinner("⚡ 正在执行毫秒级数据融合与 BOLL 计算..."):
            tc_realtime_data = get_tencent_batch_realtime(clean_stocks)
            
            all_results = []
            error_logs = []

            for symbol in clean_stocks:
                bs_data = get_baostock_history(symbol)
                tc_info = tc_realtime_data.get(symbol, {})
                tc_name = tc_info.get("name", symbol)
                tc_high = tc_info.get("high", 0.0)
                tc_price = tc_info.get("price", 0.0)
                tc_date = tc_info.get("date", "")
                engine_tag = "🕰️ 复盘"
                
                # --- 1. 构建 Pandas 终极分析表 ---
                if len(bs_data) > 0:
                    df = pd.DataFrame(bs_data, columns=['date', 'high', 'close'])
                    df['high'] = df['high'].astype(float)
                    df['close'] = df['close'].astype(float)
                    
                    if tc_date and tc_high > 0 and tc_price > 0:
                        if tc_date == df.iloc[-1]['date']:
                            df.at[df.index[-1], 'high'] = max(df.iloc[-1]['high'], tc_high)
                            df.at[df.index[-1], 'close'] = tc_price 
                            engine_tag = "⚡ 实盘"
                        elif tc_date > df.iloc[-1]['date']:
                            new_row = pd.DataFrame([{'date': tc_date, 'high': tc_high, 'close': tc_price}])
                            df = pd.concat([df, new_row], ignore_index=True)
                            engine_tag = "⚡ 实盘"
                else:
                    if tc_date and tc_high > 0 and tc_price > 0:
                        df = pd.DataFrame([{'date': tc_date, 'high': tc_high, 'close': tc_price}])
                    else:
                        df = pd.DataFrame(columns=['date', 'high', 'close'])

                # --- 2. 核心算法：BOLL 空间位置判定 ---
                boll_status = "-"
                if len(df) >= 20:
                    df['MA20'] = df['close'].rolling(window=20).mean()
                    # 采用传统看盘软件的标准：总体标准差 ddof=0
                    df['STD'] = df['close'].rolling(window=20).std(ddof=0)
                    df['UP'] = df['MA20'] + 2 * df['STD']
                    df['LOW'] = df['MA20'] - 2 * df['STD']
                    
                    latest = df.iloc[-1]
                    cp = latest['close']
                    up = latest['UP']
                    mid = latest['MA20']
                    low = latest['LOW']
                    
                    # 设定 1.5% 为“接近”的数学阈值
                    threshold = 0.015
                    if cp > up: 
                        boll_status = "🔥 突破上轨"
                    elif cp < low: 
                        boll_status = "🧊 跌破下轨"
                    elif abs(cp - up) / up <= threshold: 
                        boll_status = "🎯 接近上轨"
                    elif abs(cp - mid) / mid <= threshold: 
                        boll_status = "🎯 接近中轨"
                    elif abs(cp - low) / low <= threshold: 
                        boll_status = "🎯 接近下轨"
                    else: 
                        boll_status = "〰️ 通道内运行"
                elif len(df) > 0:
                    boll_status = "数据不足20天"

                # --- 3. 动能突破判定 ---
                if len(df) >= 3:
                    t_date = df.iloc[-1]['date'][5:]
                    y_date = df.iloc[-2]['date'][5:]
                    db_date = df.iloc[-3]['date'][5:]
                    t_high = df.iloc[-1]['high']    
                    y_high = df.iloc[-2]['high']    
                    db_high = df.iloc[-3]['high']   
                    
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
                        "📍 BOLL状态": boll_status,
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
            st.subheader("📊 自动化复盘看板 (包含 BOLL 分析)")
            
            df_all = pd.DataFrame(all_results)
            
            tab1, tab2, tab3, tab4 = st.tabs(["🔥 双日连破", "💡 今日突破", "🧊 连续未破", "📉 冲高回落"])
            
            with tab1:
                st.dataframe(df_all[df_all['形态判定'] == "🔥 双日连破"], use_container_width=True, hide_index=True)
            with tab2:
                st.dataframe(df_all[df_all['形态判定'] == "💡 今日突破"], use_container_width=True, hide_index=True)
            with tab3:
                st.dataframe(df_all[df_all['形态判定'] == "🧊 连续未破"], use_container_width=True, hide_index=True)
            with tab4:
                st.dataframe(df_all[df_all['形态判定'] == "📉 冲高回落"], use_container_width=True, hide_index=True)

            st.markdown("---")
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                df_all.to_excel(writer, index=False, sheet_name='形态与空间全景图')
            
            st.download_button(
                label="📥 一键下载 Excel 报表 (含 BOLL 计算结果)",
                data=buffer.getvalue(),
                file_name=f"量化复盘报告_{datetime.date.today()}.xlsx",
                mime="application/vnd.ms-excel",
                use_container_width=True
            )

        if error_logs:
            st.caption(f"⚠️ 忽略了 {len(error_logs)} 只数据不足的标的: {', '.join(error_logs)}")