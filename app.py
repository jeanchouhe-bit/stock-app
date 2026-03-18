import streamlit as st
import baostock as bs
import pandas as pd
import datetime
import re
from PIL import Image, ImageOps, ImageFilter # 新增：引入图像处理高级工具
import pytesseract
import requests
import io

st.set_page_config(page_title="股票分拣终端", page_icon="📈", layout="wide")

st.title("📈 股票形态分拣终端 v9.1 (视觉增强版)")
st.markdown("⚡ **双核引擎:** 腾讯实盘 + BS历史 | 👁️ **视觉增强:** 引入专业级 OCR 预处理，大幅提升密集截图识别率")

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
# (!! 核心升级 !!) 专业级 OCR 图像预处理函数
# ==========================================
def preprocess_image_for_ocr(uploaded_file):
    """
    针对炒股软件暗黑模式、密集列表进行图像增强
    """
    image = Image.open(uploaded_file)
    
    # 1. 强制转灰度 (L 模式)
    img = image.convert('L')
    
    # 2. 图像放大 (将图片放大2倍，使用高质量重采样，让小字体变大且清晰)
    w, h = img.size
    img = img.resize((w * 2, h * 2), Image.Resampling.LANCZOS)
    
    # 3. 自动对比度增强
    img = ImageOps.autocontrast(img)
    
    # 4. (核心) 二值化与反色处理
    # 算一下图片的平均亮度，如果偏暗（暗黑模式），就进行反色处理
    # 目标：强行变成“白底黑字”，Tesseract 对此模式识别率最高
    import numpy as np
    img_np = np.array(img)
    avg_brightness = np.mean(img_np)
    
    if avg_brightness < 128: # 判定为暗黑模式
        # 反色：黑变白，白变黑
        img = ImageOps.invert(img)
        # 再次增强对比度，让黑白更分明
        # 定义一个阈值，低于140的直接变黑，高于140的直接变白
        img = img.point(lambda p: 0 if p < 140 else 255)
    else: # 判定为明亮模式
        # 直接进行强力二值化
        img = img.point(lambda p: 0 if p < 120 else 255)
        
    return img

# ==========================================
# 交互界面
# ==========================================
with st.expander("📸 展开使用【截图识股v2.1】 (已增强对100+密集列表的识别)", expanded=True):
    uploaded_file = st.file_uploader("支持上传手机截屏 (兼容暗黑模式/极小字体)", type=["jpg", "png", "jpeg"])
    
    auto_codes = ""
    if uploaded_file is not None:
        col1, col2 = st.columns([1, 1])
        
        with col1:
            st.image(uploaded_file, caption="原始截图", use_container_width=True)
            
        with col2:
            with st.spinner("🔮 AI 正在进行图像视觉增强并扫描代码..."):
                try:
                    # 调用增强处理函数
                    processed_img = preprocess_image_for_ocr(uploaded_file)
                    
                    # 可以在调试时显示处理后的图片
                    # st.image(processed_img, caption="AI 视角的图片 (白底黑字增强)", use_container_width=True)
                    
                    # (!! 模式升级 !!) 切换为 PSM 11：稀疏文本模式，专门用于识别散乱的、密集的列表数据
                    text = pytesseract.image_to_string(processed_img, config='--psm 11')
                    
                    # 正则抓取代码
                    codes = re.findall(r'\b(60\d{4}|68\d{4}|00\d{4}|30\d{4})\b', text)
                    unique_codes = list(set(codes))
                    
                    if unique_codes:
                        st.success(f"🎉 视觉增强成功！识别到 {len(unique_codes)} 只股票 (较旧版大幅提升)。")
                        # 按照代码数字排序，方便查看
                        unique_codes.sort()
                        auto_codes = ", ".join(unique_codes)
                        
                        # 显示识别到的代码片段，方便用户核对
                        with st.expander("查看识别到的纯文本代码"):
                            st.code(auto_codes)
                    else:
                        st.error("即使经过增强，也没能认出代码。请确保截图里有清晰的 6 位数字代码。")
                except Exception as e:
                    st.error(f"视觉引擎出现未知错误: {e}")
st.markdown("---")

st.markdown("### ⌨️ 代码控制台")
# 将识别到的代码塞入输入框
user_input = st.text_input("待检测阵列 (逗号分隔):", value=auto_codes if auto_codes else "600519, 000001, 002594")

# ==========================================
# 主力运算引擎
# ==========================================
if st.button("🚀 启动极速分拣", use_container_width=True):
    
    # 增加一层清洗，防止识别出奇怪的数字
    raw_list = user_input.replace("，", ",").split(",")
    valid_codes = []
    for raw in raw_list:
        match = re.search(r'\b(60\d{4}|68\d{4}|00\d{4}|30\d{4})\b', raw)
        if match:
            valid_codes.append(match.group())
    
    clean_stocks = list(set(valid_codes))

    if not clean_stocks:
        st.warning("❌ 必须输入至少一只 6 位数 A 股代码。")
    else:
        with st.spinner(f"⚡ 正在为 {len(clean_stocks)} 只股票执行动能与空间计算..."):
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

                # BOLL 计算
                boll_status = "-"
                if len(df) >= 20:
                    df['MA20'] = df['close'].rolling(window=20).mean()
                    df['STD'] = df['close'].rolling(window=20).std(ddof=0)
                    df['UP'] = df['MA20'] + 2 * df['STD']
                    df['LOW'] = df['MA20'] - 2 * df['STD']
                    
                    latest = df.iloc[-1]
                    cp = latest['close']
                    up = latest['UP']
                    mid = latest['MA20']
                    low = latest['LOW']
                    
                    threshold = 0.015
                    if cp > up: boll_status = "🔥 突破上轨"
                    elif cp < low: boll_status = "🧊 跌破下轨"
                    elif abs(cp - up) / up <= threshold: boll_status = "🎯 接近上轨"
                    elif abs(cp - mid) / mid <= threshold: boll_status = "🎯 接近中轨"
                    elif abs(cp - low) / low <= threshold: boll_status = "🎯 接近下轨"
                    else: boll_status = "〰️ 通道内"
                elif len(df) > 0:
                    boll_status = "数据不足"

                # 突破判定
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
                        f"最新高({t_date})": t_high,
                        f"次新高({y_date})": y_high,
                        f"前高({db_date})": db_high,
                        "数据引擎": engine_tag
                    })
                else:
                    error_logs.append(f"{tc_name}({symbol})")

        # ==========================================
        # 展示报告
        # ==========================================
        if all_results:
            st.markdown("---")
            st.subheader(f"📊 自动化复盘看板 (已处理 {len(all_results)} 只标的)")
            
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
                label="📥 一键下载完整复盘报表 (Excel)",
                data=buffer.getvalue(),
                file_name=f"量化复盘报告_{datetime.date.today()}.xlsx",
                mime="application/vnd.ms-excel",
                use_container_width=True
            )

        if error_logs:
            with st.expander(f"⚠️ 忽略了 {len(error_logs)} 只数据不足的标的"):
                st.write(", ".join(error_logs))