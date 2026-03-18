import streamlit as st
import baostock as bs
import pandas as pd
import datetime
import re
import requests
import io
import numpy as np
from PIL import Image, ImageOps
import pytesseract

st.set_page_config(page_title="股票分拣终端", page_icon="📈", layout="wide")

st.title("📈 股票分拣终端 v14.2 (双核扫图版)")
st.markdown("⚡ **双核引擎:** 腾讯实盘 + BS历史 | ♾️ **完全自由:** 纯本地双排版扫描，彻底榨干图片代码！")

# ==========================================
# (!! 核心黑科技 !!) 本地无限制切片与显微增强引擎
# ==========================================
def local_unlimited_ocr(uploaded_file, show_debug=False):
    """纯 Python 图像处理 + 本地 Tesseract 双核识别"""
    img = Image.open(uploaded_file)
    if img.mode != 'RGB':
        img = img.convert('RGB')
        
    w, h = img.size
    max_h = 1500  
    all_text = ""
    
    slices = (h // max_h) + 1 if h % max_h != 0 else h // max_h
    if slices > 1:
        st.info(f"📏 长图已切割为 {slices} 个高清碎片，正在全速扫描...")
    
    for i in range(0, h, max_h):
        box = (0, i, w, min(i + max_h, h))
        chunk = img.crop(box)
        
        # --- 显微镜级图像手术 ---
        # 1. 无损放大 2.5 倍
        cw, ch = chunk.size
        chunk = chunk.resize((int(cw * 2.5), int(ch * 2.5)), Image.Resampling.LANCZOS)
        
        # 2. 转灰度
        chunk_gray = chunk.convert('L')
        
        # 3. 更聪明的暗黑模式判断 (只取中间区域判断，避开白色导航栏的干扰)
        center_box = (cw, int(ch * 0.5), int(cw * 1.5), int(ch * 1.5))
        try:
            center_crop = chunk_gray.crop(center_box)
            img_np = np.array(center_crop)
        except:
            img_np = np.array(chunk_gray)
            
        if np.mean(img_np) < 135: # 稍微提高阈值，让深色图更容易被反色
            chunk_gray = ImageOps.invert(chunk_gray)
            
        # 4. 温和拉伸对比度
        chunk_final = ImageOps.autocontrast(chunk_gray)
        
        # 5. X光透视仪：如果用户开启了调试，显示 AI 视角的图片
        if show_debug:
            st.image(chunk_final, caption=f"🔍 X光透视：切片 {i//max_h + 1} (AI 就是看这张图识别的)", use_container_width=True)
        
        # 6. 双核召唤 Tesseract
        try:
            # 引擎 A：对付散乱、密集的股票列表
            text_11 = pytesseract.image_to_string(chunk_final, config='--psm 11')
            # 引擎 B：对付规整的、数量少的短图表格
            text_6 = pytesseract.image_to_string(chunk_final, config='--psm 6')
            
            # 合并两个引擎的视力结果，并打上容错补丁
            combined_text = (text_11 + " " + text_6).replace('O', '0').replace('o', '0').replace('C', '0').replace('I', '1').replace('l', '1')
            all_text += combined_text + " "
        except Exception as e:
            st.warning(f"本地引擎扫描切片 {i//max_h + 1} 时遇到小问题: {e}")
            
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
with st.expander("📸 展开使用【纯本地无损扫图】 (已开启双核容错)", expanded=True):
    # 新增：视觉调试开关
    debug_mode = st.checkbox("🔍 开启【X光透视】 (排查图片识别失败原因必点)")
    uploaded_file = st.file_uploader("请上传股票截图 (支持百股长图 / 短图)", type=["jpg", "png", "jpeg"])
    
    auto_codes = ""
    if uploaded_file is not None:
        col1, col2 = st.columns([1, 1])
        with col1: 
            st.image(uploaded_file, caption="原始截图", use_container_width=True)
            
        with col2:
            with st.spinner("🤖 双核引擎启动，正在进行交叉比对扫描..."):
                try:
                    text = local_unlimited_ocr(uploaded_file, show_debug=debug_mode)
                    codes = re.findall(r'(60\d{4}|68\d{4}|00\d{4}|30\d{4})', text)
                    unique_codes = list(set(codes))
                    
                    if unique_codes:
                        unique_codes.sort()
                        st.success(f"🎉 扫描完毕！成功榨取 {len(unique_codes)} 只股票！")
                        auto_codes = ", ".join(unique_codes)
                        st.code(auto_codes)
                    else:
                        st.error("未能提取到代码。请务必勾选上方的【X光透视】，查看底图是否异常。")
                        
                    with st.expander("🛠️ 查看 AI 眼里的原始字符 (双核合并后)"):
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
                        f"最新高({t_date})": t_high, f"次新高({y_date})": y_high, f"前高({db_date})": db_high, "数据引擎": engine_tag
                    })
                else: error_logs.append(f"{tc_name}({symbol})")

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