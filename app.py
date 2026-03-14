import streamlit as st
import akshare as ak
import pandas as pd
import datetime
import re
from PIL import Image
import pytesseract

st.set_page_config(page_title="股票形态分拣器", page_icon="📊")

st.title("📊 股票形态分拣器 v5.2 (周末侦探版)")
st.write("直连东方财富，盘中秒级刷新！自带底层报错透视功能。")

# --- 缓存股票名字字典 ---
@st.cache_data(ttl=3600) 
def get_stock_dict():
    try:
        df_info = ak.stock_info_a_code_name()
        return dict(zip(df_info['code'], df_info['name']))
    except:
        return {}

stock_map = get_stock_dict()

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
# 实盘核心逻辑 (周末兼容 + 报错透视)
# ==========================================
user_input = st.text_input("或者手动输入代码 (多只用逗号隔开):", value=auto_codes if auto_codes else "600519, 000001")

if st.button("🚀 开始实盘检测"):
    
    raw_list = user_input.replace("，", ",").split(",")
    clean_stocks = []
    for raw in raw_list:
        match = re.search(r'\b(60\d{4}|68\d{4}|00\d{4}|30\d{4})\b', raw)
        if match:
            clean_stocks.append(match.group())

    if not clean_stocks:
        st.warning("❌ 请输入有效的股票代码！")
    else:
        with st.spinner("⚡ 正在直连实盘接口，拉取数据..."):
            
            end_date = datetime.date.today().strftime('%Y%m%d')
            start_date = (datetime.date.today() - datetime.timedelta(days=20)).strftime('%Y%m%d')

            cat_2_break = []  
            cat_1_break = []  
            cat_0_break = []  
            cat_drop = []     
            cat_error = []    

            for symbol in clean_stocks:
                stock_name = stock_map.get(symbol, symbol)

                try:
                    df = ak.stock_zh_a_hist(symbol=symbol, period="daily", start_date=start_date, end_date=end_date, adjust="qfq")
                    
                    if len(df) >= 3:
                        t_date = str(df.iloc[-1]['日期'])[5:]
                        y_date = str(df.iloc[-2]['日期'])[5:]
                        db_date = str(df.iloc[-3]['日期'])[5:]

                        t_high = float(df.iloc[-1]['最高'])    
                        y_high = float(df.iloc[-2]['最高'])    
                        db_high = float(df.iloc[-3]['最高'])   
                        
                        info_str = f"**{stock_name} ({symbol})** | {t_date}高:{t_high}  {y_date}高:{y_high}  {db_date}高:{db_high}"
                        
                        if t_high > y_high and y_high > db_high:
                            cat_2_break.append(info_str)
                        elif t_high > y_high and y_high <= db_high:
                            cat_1_break.append(info_str)
                        elif t_high <= y_high and y_high <= db_high:
                            cat_0_break.append(info_str)
                        elif t_high <= y_high and y_high > db_high:
                            cat_drop.append(info_str)
                    else:
                        cat_error.append(f"⚠️ {stock_name} ({symbol}) 数据不足 3 天")
                except Exception as e:
                    # ===== (!!核心透视!!) 抓取底层真实报错 =====
                    error_msg = str(e)[:150] # 截取一段报错信息防止撑爆屏幕
                    cat_error.append(f"⚠️ 崩溃！获取 {stock_name} ({symbol}) 失败。底层原因: {error_msg}")

        # ==========================================
        # 展示报告
        # ==========================================
        st.subheader("🎯 交易日分类报告")
        
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

        # 重点看这里：打印真实错误！
        if cat_error:
            st.markdown("---")
            st.error("🚨 下方是系统底层截获的真实错误原因，请发给助手诊断：")
            for s in cat_error: st.write(s)