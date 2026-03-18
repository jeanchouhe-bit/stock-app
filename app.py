import streamlit as st
import baostock as bs
import pandas as pd
import datetime
import re
import requests
import io
import numpy as np
from PIL import Image
from rapidocr_onnxruntime import RapidOCR

st.set_page_config(page_title="股票分拣终端", page_icon="📈", layout="wide")

st.title("📈 股票分拣终端 v12.0 (本地 AI·智能切片版)")
st.markdown("⚡ **双核引擎:** 腾讯实盘 + BS历史 | 🔪 **极客视觉:** RapidOCR 本地引擎 + 智能切片放大，吊打长图限制！")

# ==========================================
# 本地 AI 引擎常驻内存
# ==========================================
@st.cache_resource(show_spinner=False)
def load_ocr_engine():
    return RapidOCR()

ocr = load_ocr_engine()

# ==========================================
# (!! 核心黑科技 !!) 本地长图智能切片引擎
# ==========================================
def local_smart_slice_and_scan(uploaded_file):
    """把长截图切片，局部放大后喂给本地 RapidOCR"""
    img = Image.open(uploaded_file)
    if img.mode != 'RGB':
        img = img.convert('RGB')
        
    w, h = img.size
    # 设定本地 AI 的最佳阅读高度 (比如 2000 像素切一刀)
    max_h = 2000 
    all_text = ""
    
    # 算一下要切几刀
    slices = (h // max_h) + 1 if h % max_h != 0 else h // max_h
    if slices > 1:
        st.info(f"📏 检测到超长截图 (高度 {h}px)，正在切割为 {slices} 个高清碎片进行扫描...")
    
    # 开始切片循环
    for i in range(0, h, max_h):
        box = (0, i, w, min(i + max_h, h))
        chunk = img.crop(box)
        
        # 物理外挂：把切下来的局部图再无损放大 1.5 倍，确保蚂蚁字清晰
        cw, ch = chunk.size
        chunk_enlarged = chunk.resize((int(cw * 1.5), int(ch * 1.5)), Image.Resampling.LANCZOS)
        
        # 转换成 numpy 矩阵喂给 RapidOCR
        img_np = np.array(chunk_enlarged)
        result, _ = ocr(img_np)
        
        if result:
            for line in result:
                # 强行纠正 AI 常见的视觉误差
                raw_line = line[1].replace('O', '0').replace('o', '0').replace('C', '0').replace('I', '1').replace('l', '1')
                all_text += raw_line + " "
                
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
        blocks = res.text.split(';')
        for block in blocks:
            if '="' in block:
                code_part = block.split('="')[0].split('_')[-1][2:]
                fields = block.split('="')[1].split('~')
                if len(fields) > 33:
                    d_str = fields[30][:8]
                    result_dict[code_part] = {"name": fields[1], "price": float(fields[3]), "high": float(fields[33]), "date": f"{d_str[:4]}-{d_str[4:6]}-{d_str[6:]}"}
        return result_dict
    except: return {}

# ==========================================
# 交互界面：呼叫本地算力
# ==========================================
with st.expander("📸 展开使用【本地极客扫码】 (切片无损版)", expanded=True):
    uploaded_file = st.file_uploader("支持上传 100+ 密集股票超长截图", type=["jpg", "png", "jpeg"])
    
    auto_codes = ""
    if uploaded_file is not None:
        col1, col2 = st.columns([1, 1])
        with col1: st.image(uploaded_file, caption="原始长图截图", use_container_width=True)
            
        with col2:
            with st.spinner("🤖 正在调用本地切片引擎，全速火力解析中..."):
                try:
                    # 启用本地智能切片扫描
                    text = local_smart_slice_and_scan(uploaded_file)
                    
                    codes = re.findall(r'(60\d{4}|68\d{4}|00\d{4}|30\d{4})', text)
                    unique_codes = list(set(codes))
                    
                    if unique_codes:
                        unique_codes.sort()
                        st.success(f"🎉 物理压制成功！本地 AI 精准锁定 {len(unique_codes)} 只股票！")
                        auto_codes = ", ".join(unique_codes)
                        st.code(auto_codes)
                    else:
                        st.error("AI 在所有碎片中均未找到代码。")
                        
                    with st.expander("🛠️ 查看 AI 传回的原始识别结果"):
                        st.text(text)
                except Exception as e:
                    st.error(f"识别引擎报错: {e}")
st.markdown("---")

st.markdown("### ⌨️ 代码控制台")
user_input = st.text_input("待检测阵列 (逗号分隔):", value=auto_codes if auto_codes else "600519, 000001")

# ==========================================
# 主力运算引擎
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
                tc_high, tc_price, tc_date = tc_info.get("high", 0.0), tc_info.get("price", 0.0), tc_info.get("date", "")
                engine_tag = "🕰️ 复盘"
                
                if len(bs_data) > 0:
                    df = pd.DataFrame(bs_data, columns=['date', 'high', 'close'])
                    df['high'], df['close'] = df['high'].astype(float), df['close'].astype(float)
                    if tc_date and tc_high > 0 and tc_price > 0:
                        if tc_date == df.iloc[-1]['date']:
                            df.at[df.index[-1], 'high'], df.at[df.index[-1], 'close'], engine_tag = max(df.iloc[-1]['high'], tc_high),