import streamlit as st
import baostock as bs
import pandas as pd
import datetime
import re
from PIL import Image
import pytesseract
import requests  # 新增的网络请求库

st.set_page_config(page_title="股票形态分拣器", page_icon="📊")

st.title("📊 股票形态分拣器 v6.0 (腾讯直连版)")
st.write("彻底无视云端IP封锁！采用【腾讯实时滴答 + BS历史底座】缝合技术，极致稳定！")

# ==========================================
# 图片上传与识别模块
# ==========================================
st.markdown("---")
st.subheader("📸 偷懒神器：截图识股")
uploaded_file = st.file_uploader("请上传含有股票代码的截图 (支持 jpg/png)", type=["jpg", "png", "jpeg"])

auto_codes = ""
if uploaded_file is not None:
    with st.spinner("正在呼叫 AI 扫描图片中的代码..."):
        try:
            image = Image.open(uploaded_file)
            if image.mode != 'RGB':
                image = image.convert('RGB')
            text = pytesseract.image_to_string(image, config='--psm 6')
            
            codes = re.findall(r'\b(60\d{4}|68\d{4}|00\d{4}|30\d{4})\b', text)
            unique_codes = list(set(codes))
            
            if unique_codes:
                st.success(f"🎉 识别成功！从图中抓取到 {len(unique_codes)} 只股票。")
                auto_codes = ", ".join(unique_codes)
            else:
                st.error("图片里没有找到清晰的 A股代码，请重试。")
        except Exception as e:
            st.error(f"图片识别出错: {e}")
st.markdown("---")

# ==========================================
# 核心逻辑：腾讯实盘 + Baostock 历史完美缝合
# ==========================================
user_input = st.text_input("或者手动输入代码 (多只用逗号隔开):", value=auto_codes if auto_codes else "600519, 000001")

if st.button("🚀 开始极速实盘检测"):
    
    raw_list = user_input.replace("，", ",").split(",")
    clean_stocks = []
    for raw in raw_list:
        match = re.search(r'\b(60\d{4}|68\d{4}|00\d{4}|30\d{4})\b', raw)
        if match:
            clean_stocks.append(match.group())

    if not clean_stocks:
        st.warning("❌ 请输入有效的股票代码！")
    else:
        with st.spinner("⚡ 正在混合双打：腾讯获取此时此刻 + BS获取历史底座..."):
            
            today = datetime.date.today()
            bs_end = today.strftime('%Y-%m-%d')
            bs_start = (today - datetime.timedelta(days=20)).strftime('%Y-%m-%d')

            cat_2_break = []  
            cat_1_break = []  
            cat_0_break = []  
            cat_drop = []     
            cat_error = []    

            bs.login()

            for symbol in clean_stocks:
                # 组装代码
                bs_code = "sh." + symbol if symbol.startswith('6') else "sz." + symbol
                tc_code = bs_code.replace('.', '') # 腾讯格式: sh600519
                
                # -----------------------------------
                # 1. 腾讯接口抓取最新实盘 (名字 + 今日最高价)
                # -----------------------------------
                tc_name = symbol
                tc_high = 0.0
                tc_date = ""
                engine_tag = "🕰️复盘" # 默认标签
                
                try:
                    # 直连腾讯财经，永不封锁！
                    res = requests.get(f"http://qt.gtimg.cn/q={tc_code}", timeout=3)
                    content = res.text.split('="')[1].split('";')[0]
                    fields = content.split('~')
                    
                    if len(fields) > 33:
                        tc_name = fields[1]            # 第1位是名字
                        tc_high = float(fields[33])    # 第33位是今日最高价
                        d_str = fields[30][:8]         # 第30位是时间戳 20260317...
                        tc_date = f"{d_str[:4]}-{d_str[4:6]}-{d_str[6:]}"
                except:
                    pass # 哪怕腾讯挂了，静默跳过，靠BS兜底
                
                # -----------------------------------
                # 2. Baostock 抓取历史数据
                # -----------------------------------
                rs = bs.query_history_k_data_plus(
                    bs_code, "date,high", start_date=bs_start, end_date=bs_end, frequency="d"
                )
                data = []
                while (rs.error_code == '0') & rs.next():
                    data.append(rs.get_row_data())
                    
                # -----------------------------------
                # 3. 终极缝合魔术：把今天的数据拼接到昨天后面
                # -----------------------------------
                if tc_date and tc_high > 0:
                    if len(data) > 0:
                        if tc_date == data[-1][0]:
                            # 盘后情况：BS已经有了今天的数据，那就取两者的最大值
                            data[-1][1] = str(max(float(data[-1][1]), tc_high))
                        elif tc_date > data[-1][0]:
                            # 盘中情况：BS只有昨天的数据，完美！把腾讯的“今天”追加进去
                            data.append([tc_date, str(tc_high)])
                            engine_tag = "⚡腾讯实盘"
                    else:
                        data.append([tc_date, str(tc_high)])

                # -----------------------------------
                # 4. 统一分拣逻辑
                # -----------------------------------
                if len(data) >= 3:
                    t_date = str(data[-1][0])[5:]
                    y_date = str(data[-2][0])[5:]
                    db_date = str(data[-3][0])[5:]
                    t_high = float(data[-1][1])    
                    y_high = float(data[-2][1])    
                    db_high = float(data[-3][1])   
                    
                    info_str = f"**{tc_name} ({symbol})** [{engine_tag}] | {t_date}高:{t_high}  {y_date}高:{y_high}  {db_date}高:{db_high}"
                    
                    if t_high > y_high and y_high > db_high:
                        cat_2_break.append(info_str)
                    elif t_high > y_high and y_high <= db_high:
                        cat_1_break.append(info_str)
                    elif t_high <= y_high and y_high <= db_high:
                        cat_0_break.append(info_str)
                    elif t_high <= y_high and y_high > db_high:
                        cat_drop.append(info_str)
                else:
                    cat_error.append(f"⚠️ {tc_name} ({symbol}) 数据不足 3 天 (新股或停牌)")

            bs.logout()

        # ==========================================
        # 展示报告
        # ==========================================
        st.subheader("🎯 智能分拣报告")
        
        st.success("🔥 **【双日连破】 (最新高 > 次新高 > 前高)**")
        if cat_2_break:
            for s in cat_2_break: st.write("✅ " + s)
        else:
            st.write("  (空)")

        st.info("💡 **【最新日突破】 (最新高 > 次新高，次新高 <= 前高)**")
        if cat_1_break:
            for s in cat_1_break: st.write("↗️ " + s)
        else:
            st.write("  (空)")

        st.error("🧊 **【连续两日未突破】 (最新高 <= 次新高 <= 前高)**")
        if cat_0_break:
            for s in cat_0_break: st.write("❌ " + s)
        else:
            st.write("  (空)")

        st.warning("⚠️ **【最新日冲高回落】 (最新高 <= 次新高，次新高 > 前高)**")
        if cat_drop:
            for s in cat_drop: st.write("📉 " + s)
        else:
            st.write("  (空)")

        if cat_error:
            st.markdown("---")
            for s in cat_error: st.write(s)