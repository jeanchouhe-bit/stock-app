import streamlit as st
import baostock as bs
import pandas as pd
import datetime
import re
from PIL import Image, ImageOps
import numpy as np
from rapidocr_onnxruntime import RapidOCR
import requests
import io

st.set_page_config(page_title="股票分拣终端", page_icon="📈", layout="wide")

st.title("📈 股票分拣终端 v10.2 (显微镜增强版)")
st.markdown("⚡ **双核引擎:** 腾讯实盘 + BS历史 | 🔬 **显微视觉:** 无损放大重采样 + 深度学习，专治百股蚂蚁字！")

@st.cache_resource(show_spinner=False)
def load_ocr_engine():
    return RapidOCR()

ocr = load_ocr_engine()

@st.cache_data(ttl=3600*12, show_spinner=False)
def get_baostock_history(symbol):
    bs.login()
    bs_code = "sh." + symbol if symbol.startswith('6') else "sz." + symbol
    today = datetime.date.today()
    bs_end = today.strftime('%Y-%m-%d')
    bs_start = (today - datetime.timedelta(days=45)).strftime('%Y-%m-%d')
    
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
                        "price": float(fields[3]),
                        "high": float(fields[33]),
                        "date": f"{d_str[:4]}-{d_str[4:6]}-{d_str[6:]}"
                    }
        return result_dict
    except:
        return {}

# ==========================================
# 交互界面：显微镜级增强扫描
# ==========================================
with st.expander("📸 展开使用【显微视觉扫码】 (已加入无损放大抗锯齿)", expanded=True):
    uploaded_file = st.file_uploader("支持上传 100+ 密集股票截图", type=["jpg", "png", "jpeg"])
    
    auto_codes = ""
    if uploaded_file is not None:
        col1, col2 = st.columns([1, 1])
        
        with col1:
            st.image(uploaded_file, caption="原始截图 (可能存在像素粘连)", use_container_width=True)
            
        with col2:
            with st.spinner("🔬 正在对图像进行无损重采样放大与增强..."):
                try:
                    # 1. 打开图片
                    img = Image.open(uploaded_file)
                    
                    # 2. (!!核心修复!!) 显微镜无损放大 2.5 倍
                    # 使用 LANCZOS 算法，能最大程度把模糊的数字边缘补齐，防止 0 变成 C
                    w, h = img.size
                    img_large = img.resize((int(w * 2.5), int(h * 2.5)), Image.Resampling.LANCZOS)
                    
                    # 3. 强制灰度去色 + 自动对比度拉伸 (让灰色的数字变白/变黑，更清晰)
                    img_gray = img_large.convert('L')
                    img_enhanced = ImageOps.autocontrast(img_gray)
                    
                    # 4. 转回 RGB 格式喂给 RapidOCR
                    img_ready = img_enhanced.convert('RGB')
                    img_np = np.array(img_ready)
                    
                    # st.image(img_ready, caption="AI 视角的增强画面 (用于调试)", use_container_width=True)
                    
                    result, _ = ocr(img_np)
                    
                    text = ""
                    if result:
                        for line in result:
                            # 暴力替换掉 AI 容易认错的极其相似的字符 (容错补丁)
                            raw_line = line[1].replace('O', '0').replace('o', '0').replace('C', '0').replace('I', '1').replace('l', '1')
                            text += raw_line + " "
                    
                    # 暴力抓取 6 位数
                    codes = re.findall(r'(60\d{4}|68\d{4}|00\d{4}|30\d{4})', text)
                    unique_codes = list(set(codes))
                    
                    if unique_codes:
                        unique_codes.sort()
                        st.success(f"🎉 显微增强成功！从乱码中抢救回 {len(unique_codes)} 只股票！")
                        auto_codes = ", ".join(unique_codes)
                        st.code(auto_codes)
                    else:
                        st.error("仍然未找到代码，截图可能过度压缩。")
                        
                    with st.expander("🛠️ 查看增强后的 AI 识别原文"):
                        st.text(text)
                        
                except Exception as e:
                    st.error(f"AI 引擎崩溃: {e}")
st.markdown("---")

st.markdown("### ⌨️ 代码控制台")
user_input = st.text_input("待检测阵列 (逗号分隔):", value=auto_codes if auto_codes else "600519, 000001")

# ==========================================
# 主力运算引擎 (保持极速逻辑)
# ==========================================
if st.button("🚀 启动极速分拣", use_container_width=True):
    raw_list = user_input.replace("，", ",").split(",")
    valid_codes = [re.search(r'(60\d{4}|68\d{4}|00\d{4}|30\d{4})', raw).group() for raw in raw_list if re.search(r'(60\d{4}|68\d{4}|00\d{4}|30\d{4})', raw)]
    clean_stocks = list(set(valid_codes))

    if not clean_stocks:
        st.warning("❌ 必须输入至少一只 6 位数 A 股代码。")
    else:
        with st.spinner(f"⚡ 正在为 {len(clean_stocks)} 只股票执行动能与空间计算..."):
            tc_realtime_data = get_tencent_batch_realtime(clean_stocks)
            all_results, error_logs = [], []

            for symbol in clean_stocks:
                bs_data = get_baostock_history(symbol)
                tc_info = tc_realtime_data.get(symbol, {})
                tc_name = tc_info.get("name", symbol)
                tc_high = tc_info.get("high", 0.0)
                tc_price = tc_info.get("price", 0.0)
                tc_date = tc_info.get("date", "")
                engine_tag = "🕰️ 复盘"
                
                if len(bs_data) > 0:
                    df = pd.DataFrame(bs_data, columns=['date', 'high', 'close'])
                    df['high'], df['close'] = df['high'].astype(float), df['close'].astype(float)
                    if tc_date and tc_high > 0 and tc_price > 0:
                        if tc_date == df.iloc[-1]['date']:
                            df.at[df.index[-1], 'high'], df.at[df.index[-1], 'close'], engine_tag = max(df.iloc[-1]['high'], tc_high), tc_price, "⚡ 实盘"
                        elif tc_date > df.iloc[-1]['date']:
                            df, engine_tag = pd.concat([df, pd.DataFrame([{'date': tc_date, 'high': tc_high, 'close': tc_price}])], ignore_index=True), "⚡ 实盘"
                else:
                    df = pd.DataFrame([{'date': tc_date, 'high': tc_high, 'close': tc_price}]) if (tc_date and tc_high > 0 and tc_price > 0) else pd.DataFrame(columns=['date', 'high', 'close'])

                boll_status = "-"
                if len(df) >= 20:
                    df['MA20'], df['STD'] = df['close'].rolling(20).mean(), df['close'].rolling(20).std(ddof=0)
                    df['UP'], df['LOW'] = df['MA20'] + 2 * df['STD'], df['MA20'] - 2 * df['STD']
                    cp, up, mid, low = df.iloc[-1]['close'], df.iloc[-1]['UP'], df.iloc[-1]['MA20'], df.iloc[-1]['LOW']
                    threshold = 0.015
                    if cp > up: boll_status = "🔥 突破上轨"
                    elif cp < low: boll_status = "🧊 跌破下轨"
                    elif abs(cp - up) / up <= threshold: boll_status = "🎯 接近上轨"
                    elif abs(cp - mid) / mid <= threshold: boll_status = "🎯 接近中轨"
                    elif abs(cp - low) / low <= threshold: boll_status = "🎯 接近下轨"
                    else: boll_status = "〰️ 通道内"
                elif len(df) > 0: boll_status = "数据不足"

                if len(df) >= 3:
                    t_date, y_date, db_date = df.iloc[-1]['date'][5:], df.iloc[-2]['date'][5:], df.iloc[-3]['date'][5:]
                    t_high, y_high, db_high = df.iloc[-1]['high'], df.iloc[-2]['high'], df.iloc[-3]['high']   
                    pattern = "🔥 双日连破" if (t_high > y_high > db_high) else ("💡 今日突破" if (t_high > y_high <= db_high) else ("🧊 连续未破" if (t_high <= y_high <= db_high) else "📉 冲高回落"))
                    all_results.append({
                        "股票代码": symbol, "股票名称": tc_name, "形态判定": pattern, "📍 BOLL状态": boll_status,
                        f"最新高({t_date})": t_high, f"次新高({y_date})": y_high, f"前高({db_date})": db_high, "数据引擎": engine_tag
                    })
                else: error_logs.append(f"{tc_name}({symbol})")

        # ==========================================
        # 展示报告
        # ==========================================
        if all_results:
            st.markdown("---")
            st.subheader(f"📊 自动化复盘看板 (已处理 {len(all_results)} 只标的)")
            df_all = pd.DataFrame(all_results)
            tab1, tab2, tab3, tab4 = st.tabs(["🔥 双日连破", "💡 今日突破", "🧊 连续未破", "📉 冲高回落"])
            with tab1: st.dataframe(df_all[df_all['形态判定'] == "🔥 双日连破"], use_container_width=True, hide_index=True)
            with tab2: st.dataframe(df_all[df_all['形态判定'] == "💡 今日突破"], use_container_width=True, hide_index=True)
            with tab3: st.dataframe(df_all[df_all['形态判定'] == "🧊 连续未破"], use_container_width=True, hide_index=True)
            with tab4: st.dataframe(df_all[df_all['形态判定'] == "📉 冲高回落"], use_container_width=True, hide_index=True)

            st.markdown("---")
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer: df_all.to_excel(writer, index=False, sheet_name='形态与空间全景图')
            st.download_button(label="📥 一键下载完整复盘报表 (Excel)", data=buffer.getvalue(), file_name=f"量化复盘报告_{datetime.date.today()}.xlsx", mime="application/vnd.ms-excel", use_container_width=True)

        if error_logs: st.caption(f"⚠️ 忽略了 {len(error_logs)} 只数据不足的标的: {', '.join(error_logs)}")