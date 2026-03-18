import streamlit as st
import baostock as bs
import pandas as pd
import datetime
import re
from PIL import Image, ImageOps, ImageEnhance # 新增：引入图像增强调参模块
import pytesseract
import requests
import io

st.set_page_config(page_title="股票分拣终端", page_icon="📈", layout="wide")

st.title("📈 股票分拣终端 v9.2 (可视化调参版)")
st.markdown("⚡ **双核引擎:** 腾讯实盘 + BS历史 | 🎛️ **全新特性:** 引入可视化 OCR 调参台，破解一切复杂截图")

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
# 交互界面：可视化调参台
# ==========================================
with st.expander("📸 展开使用【可视化截图识股】 (专治各种密集/模糊截图)", expanded=True):
    uploaded_file = st.file_uploader("支持上传手机截屏", type=["jpg", "png", "jpeg"])
    
    auto_codes = ""
    if uploaded_file is not None:
        col1, col2 = st.columns([1, 1.2])
        
        # --- 左侧：调参控制台 ---
        with col1:
            st.markdown("#### 🎛️ 图像调参控制台")
            st.caption("请调节滑块，直到右侧的图片变成清晰的『白底黑字』或『黑底白字』")
            
            # 提供互动滑块
            contrast = st.slider("对比度 (拉大可以让字迹更浓)", 0.5, 4.0, 1.5, 0.1)
            brightness = st.slider("亮度 (太暗就提亮)", 0.5, 3.0, 1.0, 0.1)
            do_invert = st.checkbox("☯️ 颜色反转 (暗黑模式极度推荐勾选)", value=True)
            
            # AI 模式选择 (不同模式对排版的理解不同)
            psm_mode = st.radio("🤖 AI 阅读模式 (如果漏字可以切换试试)", 
                                options=["--psm 6 (默认: 均匀文本块)", "--psm 4 (假设为单列数据)", "--psm 11 (极度稀疏散乱文本)"],
                                index=0)

        # --- 右侧：实时预览与识别 ---
        with col2:
            st.markdown("#### 👁️ AI 实际看到的画面")
            
            # 动态图像处理逻辑
            img = Image.open(uploaded_file).convert('RGB')
            
            # 1. 调对比度
            enhancer_c = ImageEnhance.Contrast(img)
            img = enhancer_c.enhance(contrast)
            
            # 2. 调亮度
            enhancer_b = ImageEnhance.Brightness(img)
            img = enhancer_b.enhance(brightness)
            
            # 3. 转灰度 (去掉红绿颜色的干扰)
            img = img.convert('L')
            
            # 4. 反转颜色
            if do_invert:
                img = ImageOps.invert(img)
                
            # 实时显示处理后的图片！
            st.image(img, use_container_width=True)
            
            with st.spinner("AI 正在凝视右侧的图片并提取代码..."):
                try:
                    # 提取真正的 PSM 参数
                    actual_psm = psm_mode.split(" ")[0] + " " + psm_mode.split(" ")[1]
                    
                    text = pytesseract.image_to_string(img, config=actual_psm)
                    codes = re.findall(r'\b(60\d{4}|68\d{4}|00\d{4}|30\d{4})\b', text)
                    unique_codes = list(set(codes))
                    
                    if unique_codes:
                        unique_codes.sort()
                        st.success(f"🎉 成功锁定 {len(unique_codes)} 只股票！")
                        auto_codes = ", ".join(unique_codes)
                        st.code(auto_codes)
                    else:
                        st.error("没有找到代码。请尝试调节左侧的对比度或亮度滑块，或者切换 AI 阅读模式。")
                except Exception as e:
                    st.error(f"识别引擎错误: {e}")
st.markdown("---")

st.markdown("### ⌨️ 代码控制台")
user_input = st.text_input("待检测阵列 (逗号分隔):", value=auto_codes if auto_codes else "600519, 000001, 002594")

# ==========================================
# 主力运算引擎 (保持极速逻辑不变)
# ==========================================
if st.button("🚀 启动极速分拣", use_container_width=True):
    
    raw_list = user_input.replace("，", ",").split(",")
    valid_codes = [re.search(r'\b(60\d{4}|68\d{4}|00\d{4}|30\d{4})\b', raw).group() for raw in raw_list if re.search(r'\b(60\d{4}|68\d{4}|00\d{4}|30\d{4})\b', raw)]
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
                            df.at[df.index[-1], 'high'] = max(df.iloc[-1]['high'], tc_high)
                            df.at[df.index[-1], 'close'] = tc_price 
                            engine_tag = "⚡ 实盘"
                        elif tc_date > df.iloc[-1]['date']:
                            df = pd.concat([df, pd.DataFrame([{'date': tc_date, 'high': tc_high, 'close': tc_price}])], ignore_index=True)
                            engine_tag = "⚡ 实盘"
                else:
                    df = pd.DataFrame([{'date': tc_date, 'high': tc_high, 'close': tc_price}]) if (tc_date and tc_high > 0 and tc_price > 0) else pd.DataFrame(columns=['date', 'high', 'close'])

                boll_status = "-"
                if len(df) >= 20:
                    df['MA20'] = df['close'].rolling(window=20).mean()
                    df['STD'] = df['close'].rolling(window=20).std(ddof=0)
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