import streamlit as st
import baostock as bs
import datetime

# 设置网页标题和图标
st.set_page_config(page_title="股票突破检测仪", page_icon="📈")

st.title("📈 极简股票突破检测仪")
st.write("随时随地，一键检测今天最高价是否突破昨高！")

# 网页上的输入框
user_input = st.text_input("请输入股票代码 (多只用逗号隔开):", "600519, 000001")

# 网页上的大按钮
if st.button("🚀 开始光速检测"):
    
    # 清洗输入的代码
    stock_list = [code.strip() for code in user_input.replace("，", ",").split(",") if code.strip()]
    clean_stocks = []
    for code in stock_list:
        if "." not in code:
            if code.startswith("6"): code = "sh." + code
            elif code.startswith("0") or code.startswith("3"): code = "sz." + code
        clean_stocks.append(code)

    if not clean_stocks:
        st.warning("❌ 请输入有效的股票代码！")
    else:
        # 显示一个转圈圈的加载动画
        with st.spinner("正在连接数据源，疯狂计算中..."):
            bs.login()
            
            end_date = datetime.date.today().strftime('%Y-%m-%d')
            start_date = (datetime.date.today() - datetime.timedelta(days=10)).strftime('%Y-%m-%d')

            good_stocks = []
            bad_stocks = []

            for code in clean_stocks:
                # 查名字
                rs_name = bs.query_stock_basic(code=code)
                stock_name = code
                if rs_name.error_code == '0' and rs_name.next():
                    stock_name = rs_name.get_row_data()[1]

                # 查数据
                rs = bs.query_history_k_data_plus(
                    code, "date,high",
                    start_date=start_date, end_date=end_date, frequency="d"
                )
                
                data = []
                while (rs.error_code == '0') & rs.next():
                    data.append(rs.get_row_data())
                    
                if len(data) >= 2:
                    today_high = float(data[-1][1])
                    yesterday_high = float(data[-2][1])
                    
                    if today_high > yesterday_high:
                        good_stocks.append(f"**{stock_name} ({code})** | 今高: {today_high} > 昨高: {yesterday_high}")
                    else:
                        bad_stocks.append(f"**{stock_name} ({code})** | 今高: {today_high} <= 昨高: {yesterday_high}")
                else:
                    st.warning(f"⚠️ {stock_name} ({code}) 数据不足（可能近期停牌）")

            bs.logout()

        # 在网页上漂亮地显示结果
        st.subheader("🎯 检测结果汇报")
        
        if good_stocks:
            st.success("🔥 **强势突破（满足条件）：**")
            for s in good_stocks:
                st.write("✅ " + s)
        else:
            st.info("🔥 强势突破：无")

        if bad_stocks:
            st.error("🧊 **未能突破（不满足条件）：**")
            for s in bad_stocks:
                st.write("❌ " + s)
        else:
            st.info("🧊 未能突破：无")