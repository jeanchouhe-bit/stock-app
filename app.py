import streamlit as st
import baostock as bs
import datetime

# 设置网页标题和图标
st.set_page_config(page_title="股票形态分拣器", page_icon="📊")

st.title("📊 股票形态自动分拣器")
st.write("输入一堆股票代码，自动按近三日的「突破形态」分类整理！")

# 网页上的输入框
user_input = st.text_input("请输入股票代码 (多只用逗号隔开):", "600519, 000001, 002594")

# 网页上的大按钮
if st.button("🚀 开始自动分拣"):
    
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
        # 显示加载动画
        with st.spinner("正在连接数据源，疯狂扫描并分类中..."):
            bs.login()
            
            end_date = datetime.date.today().strftime('%Y-%m-%d')
            start_date = (datetime.date.today() - datetime.timedelta(days=15)).strftime('%Y-%m-%d')

            # 准备 4 个分类的“篮子”
            cat_2_break = []  # 两连破
            cat_1_break = []  # 仅今日突破
            cat_0_break = []  # 连续两日未突破
            cat_drop = []     # 今日回落 (昨破今未破)
            cat_error = []    # 异常数据

            for code in clean_stocks:
                rs_name = bs.query_stock_basic(code=code)
                stock_name = code
                if rs_name.error_code == '0' and rs_name.next():
                    stock_name = rs_name.get_row_data()[1]

                rs = bs.query_history_k_data_plus(
                    code, "date,high",
                    start_date=start_date, end_date=end_date, frequency="d"
                )
                
                data = []
                while (rs.error_code == '0') & rs.next():
                    data.append(rs.get_row_data())
                    
                # 确保至少有 3 天的数据
                if len(data) >= 3:
                    t_high = float(data[-1][1])    # 今天最高
                    y_high = float(data[-2][1])    # 昨天最高
                    db_high = float(data[-3][1])   # 前天最高
                    
                    info_str = f"**{stock_name} ({code})** | 今:{t_high} 昨:{y_high} 前:{db_high}"
                    
                    # === 核心逻辑：自动分装到 4 个篮子里 ===
                    if t_high > y_high and y_high > db_high:
                        cat_2_break.append(info_str)
                    elif t_high > y_high and y_high <= db_high:
                        cat_1_break.append(info_str)
                    elif t_high <= y_high and y_high <= db_high:
                        cat_0_break.append(info_str)
                    elif t_high <= y_high and y_high > db_high:
                        cat_drop.append(info_str) # 逻辑补全：昨天突破了，但今天萎了
                else:
                    cat_error.append(f"⚠️ {stock_name} ({code}) 数据不足 3 天")

            bs.logout()

        # ==========================================
        # 在网页上漂亮地显示分类报告
        # ==========================================
        st.subheader("🎯 自动分类复盘报告")
        
        # 篮子 1：两连破
        st.success("🔥 **【双日连破】 (今高 > 昨高 > 前高)** —— 绝对强势")
        if cat_2_break:
            for s in cat_2_break: st.write("✅ " + s)
        else:
            st.write("  (空)")

        # 篮子 2：今天刚突破
        st.info("💡 **【今日刚突破】 (今高 > 昨高，但昨高 <= 前高)** —— 拐点初现")
        if cat_1_break:
            for s in cat_1_break: st.write("↗️ " + s)
        else:
            st.write("  (空)")

        # 篮子 3：连续未突破
        st.error("🧊 **【连续两日未突破】 (今高 <= 昨高 <= 前高)** —— 弱势阴跌")
        if cat_0_break:
            for s in cat_0_break: st.write("❌ " + s)
        else:
            st.write("  (空)")

        # 篮子 4：冲高回落 (为了逻辑严密补全的第四种状态)
        st.warning("⚠️ **【今日冲高回落】 (今高 <= 昨高，但昨高 > 前高)** —— 上攻遇阻")
        if cat_drop:
            for s in cat_drop: st.write("📉 " + s)
        else:
            st.write("  (空)")

        # 异常数据展示
        if cat_error:
            st.markdown("---")
            for s in cat_error: st.write(s)