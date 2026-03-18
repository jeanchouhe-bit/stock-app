import streamlit as st
import baostock as bs
import pandas as pd
import datetime
import re
import requests
import io
import numpy as np
from PIL import Image, ImageOps, ImageEnhance, ImageFilter
import pytesseract

st.set_page_config(page_title="股票分拣终端", page_icon="📈", layout="wide")

st.title("📈 股票分拣终端 v14.8 (凌迟切片版)")
st.markdown("⚡ **双核引擎:** 腾讯实盘 + BS历史 | 🔪 **凌迟算法:** 极小窗口高频切片，杜绝排版遗漏！")

# ==========================================
# (!! 核心黑科技 !!) 动态自适应与高频重叠切片
# ==========================================
def local_unlimited_ocr(uploaded_file, show_debug=False):
    img = Image.open(uploaded_file)
    if img.mode != 'RGB':
        img = img.convert('RGB')
        
    w, h = img.size
    
    # 听你的：大幅缩小切片高度，增加切片数量！
    max_h = 800  # 每张切片高度从 1500 暴降至 800
    step = 700   # 步长 700，确保有 100px 的重叠区，坚决不漏
    all_text = ""
    
    is_long_image = h > max_h
    slices = (h // step) + 1 if h % step != 0 else h // step
    
    if is_long_image:
        st.info(f"📏 启动【凌迟切片模式】，长图将被粉碎为 {slices} 个极小碎片进行地毯式扫描...")
    else:
        st.info("📏 启动【纳米锐化模式】，专注解除像素粘连...")
    
    for i in range(0, h, step):
        box = (0, i, w, min(i + max_h, h))
        chunk = img.crop(box)
        
        if chunk.size[1] < 50:
            continue
            
        # --- 智能分流图像手术 ---
        if is_long_image:
            # 💡 路线 A：长图专享 (完美复刻创纪录的 V14.4 暴力拉伸配方)
            chunk = chunk.filter(ImageFilter.MedianFilter(size=3))
            cw, ch = chunk.size
            chunk = chunk.resize((int(cw * 2.5), int(ch * 2.5)), Image.Resampling.LANCZOS)
            chunk_gray = chunk.convert('L')
            if np.mean(np.array(chunk_gray)) < 140: 
                chunk_gray = ImageOps.invert(chunk_gray)
                
            chunk_final = ImageOps.autocontrast(chunk_gray, cutoff=5)
            enhancer = ImageEnhance.Contrast(chunk_final)
            chunk_final = enhancer.enhance(2.5)
            
        else:
            # 💡 路线 B：短图专享 (V14.5 纳米锐化配方)
            cw, ch = chunk.size
            chunk = chunk.resize((int(cw * 2.5), int(ch * 2.5)), Image.Resampling.LANCZOS)
            chunk_gray = chunk.convert('L')
            if np.mean(np.array(chunk_gray)) < 140: 
                chunk_gray = ImageOps.invert(chunk_gray)
                
            chunk_final = ImageOps.autocontrast(chunk_gray, cutoff=1)
            sharp_enhancer = ImageEnhance.Sharpness(chunk_final)
            chunk_final = sharp_enhancer.enhance(2.0)
            contrast_enhancer = ImageEnhance.Contrast(chunk_final)
            chunk_final = contrast_enhancer.enhance(1.5)
            
        if show_debug:
            mode_name = "暴力降噪" if is_long_image else "纳米锐化"
            st.image(chunk_final, caption=f"🔍 显微透视：第 {i//step + 1}/{slices} 块 (算法: {mode_name})", use_container_width=True)
        
        try:
            text_6 = pytesseract.image_to_string(chunk_final, config='--psm 6')
            combined_text = text_6.replace('O', '0').replace('o', '0').replace('C', '0').replace('I', '1').replace('l', '1')
            all_text += combined_text + " "
        except Exception as e:
            st.warning(f"碎片扫描遇到异常: {e}")
            
    return all_text

# ==========================================
# 记忆缓存模块
# ==========================================
@st.cache_data(ttl=3600*12, show_spinner=False)
def get_baostock_history(symbol):
    bs.login()
    bs_code = "sh." + symbol if symbol.startswith('6') else "sz." + symbol
    today = datetime.date.today()
    bs_end = today.strftime('%Y-%m-%d')
    bs_start = (today - datetime.timedelta(days=45)).strftime('%Y-%m-%d')
    rs = bs.query_history_k_data_plus(bs_code, "date,high,close", start_date=bs_start, end_date=bs_end, frequency="d")
    data = []
    while (rs.error_code == '0') & rs.next(): data.append(rs.get_row_data())
    bs.logout()
    return data

def get_tencent_batch_realtime(symbol_list):
    tc_codes = ["sh" + s if s.startswith('6') else "sz" + s for s in symbol_list]
    query_str = ",".join(tc_codes)
    try:
        res = requests.get(f"http://qt.gtimg.cn/q={query_str}", timeout=3)
        result_dict = {}
        for block in res.text.split(';'):
            if '="' in block:
                code_part = block.split('="')[0].split('_')[-1][2:]
                fields = block.split('="')[1].split('~')
                if len(fields) > 33:
                    d_str = fields[30][:8]
                    result_dict[code_part] = {
                        "name": fields[1], "price": float(fields[3]), 
                        "high": float(fields[33]), "date": f"{d_str[:4]}-{d_str[4:6]}-{d_str[6:]}"
                    }
        return result_dict
    except: return {}

# ==========================================
# 交互界面：呼叫本地算力
# ==========================================
with st.expander("📸 展开使用【纯本地智能扫图】 (自动高频切片)", expanded=True):
    debug_mode = st.checkbox("🔍 开启【X光透视】 (调试排查专用)") 
    uploaded_file = st.file_uploader("请上传股票截图 (长短图均支持)", type=["jpg", "png", "jpeg"])
    
    auto_codes = ""
    if uploaded_file is not None:
        col1, col2 = st.columns([1, 1])
        with col1: 
            st.image(uploaded_file, caption="原始截图", use_container_width=True)
            
        with col2:
            with st.spinner("🧠 凌迟切片刀已启动，正在进行地毯式解析..."):
                try:
                    text = local_unlimited_ocr(uploaded_file, show_debug=debug_mode)
                    codes = re.findall(r'(60\d{4}|68\d{4}|00\d{4}|30\d{4})', text)
                    unique_codes = list(set(codes))
                    
                    if unique_codes:
                        unique_codes.sort()
                        st.success(f"🎉 破解完毕！地毯式搜查成功提取 {len(unique_codes)} 只股票！")
                        auto_codes = ", ".join(unique_codes)
                        st.code(auto_codes)
                    else:
                        st.error("未能提取到代码。请查看下方 X光透视。")
                        
                    with st.expander("🛠️ 查看 AI 眼里的原始字符"):
                        st.text(text if text.strip() else "【完全空白，请检查X光透视底图】")
                except Exception as e:
                    st.error(f"发生意外错误: {e}")
st.markdown("---")

st.markdown("### ⌨️ 代码控制台")
user_input = st.text_input("待检测阵列 (逗号分隔):", value=auto_codes if auto_codes else "600519, 000001")

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
                tc_high, tc_price, tc_date = tc_info.get("high", 0.0), tc_info.get("price", 0.0), tc_info.get("date", "")
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
                    if cp > up: boll_status = "🔥 突破上轨"
                    elif cp < low: boll_status = "🧊 跌破下轨"
                    elif abs(cp - up) / up <= 0.015: boll_status = "🎯 接近上轨"
                    elif abs(cp - mid) / mid <= 0.015: boll_status = "🎯 接近中轨"
                    elif abs(cp - low) / low <= 0.015: boll_status = "🎯 接近下轨"
                    else: boll_status = "〰️ 通道内"
                elif len(df) > 0: boll_status = "数据不足"

                if len(df) >= 3:
                    t_date, y_date, db_date = df.iloc[-1]['date'][5:], df.iloc[-2]['date'][5:], df.iloc[-3]['date'][5:]
                    t_high, y_high, db_high = df.iloc[-1]['high'], df.iloc[-2]['high'], df.iloc[-3]['high']   
                    pattern = "🔥 双日连破" if (t_high > y_high > db_high) else ("💡 今日突破" if (t_high > y_high <= db_high) else ("🧊 连续未破" if (t_high <= y_high <= db_high) else "📉 冲高回落"))
                    all_results.append({
                        "股票代码": symbol, "股票名称": tc_name, "形态判定": pattern, "📍 BOLL状态": boll_status,
                        f"最新高({t_date})": t_high, f"次新高({y_date})": y_high, f