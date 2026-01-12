import streamlit as st
import akshare as ak
import pandas as pd

# 设置网页标题和图标
st.set_page_config(page_title="量化选股专业版", page_icon="📈", layout="wide")

st.title("📈 涨停潜力研判系统 (专业版)")
st.caption("集成实时行情、资金流向与技术面筛选")

# --- 侧边栏：参数设置 ---
with st.sidebar:
    st.header("🔍 策略因子")
    buy_limit = st.slider('成交额门槛 (万元)', 500, 10000, 2000, step=500)
    min_pct = st.slider('最小涨幅 (%)', 0.0, 9.0, 4.0)
    max_pct = st.slider('最大涨幅 (%)', 5.0, 20.0, 9.5)
    min_turnover = st.slider('最小换手率 (%)', 0.0, 20.0, 3.0)
    top_n = st.number_input('显示前几名', value=15)
    
    st.divider()
    st.info("💡 建议：准涨停个股通常满足『放量+高换手+进攻性涨幅』。")

# --- 核心逻辑 ---
if st.button('🎯 执行深度全市场扫描'):
    with st.spinner('正在分析 5000+ 只个股...'):
        try:
            # 获取实时行情
            df = ak.stock_zh_a_spot_em()
            
            # 数据清洗与转换
            df['涨跌幅'] = pd.to_numeric(df['涨跌幅'], errors='coerce')
            df['成交额'] = pd.to_numeric(df['成交额'], errors='coerce')
            df['最新价'] = pd.to_numeric(df['最新价'], errors='coerce')
            df['换手率'] = pd.to_numeric(df['换手率'], errors='coerce')
            
            # 综合策略筛选
            condition = (
                (df['涨跌幅'] >= min_pct) & 
                (df['涨跌幅'] <= max_pct) & 
                (df['成交额'] >= buy_limit * 10000) &
                (df['换手率'] >= min_turnover)
            )
            
            res = df[condition].copy()
            
            if not res.empty:
                # 按成交额排序
                res = res.sort_values(by='成交额', ascending=False).head(top_n)
                
                # 1. 核心数值转换
                res['成交额(亿)'] = (res['成交额'] / 100000000).round(2)
                
                # 2. 生成跳转东方财富的链接 (关键新功能！)
                # 构造 URL: https://quote.eastmoney.com/unify/r/0.代码 (沪市 60) 或 1.代码 (深市 00/300)
                def make_clickable(code):
                    prefix = "0" if code.startswith('6') else "1"
                    url = f"https://quote.eastmoney.com/unify/r/{prefix}.{code}"
                    return f'<a href="{url}" target="_blank">{code}</a>'
                
                res['代码'] = res['代码'].apply(make_clickable)

                # 3. 布局显示
                st.success(f"⚡ 扫描完毕：筛选出 {len(res)} 只强势股")
                
                # 使用 HTML 渲染表格以支持点击链接
                cols_to_show = ['代码', '名称', '最新价', '涨跌幅', '换手率', '成交额(亿)']
                st.write(res[cols_to_show].to_html(escape=False, index=False), unsafe_allow_html=True)
                
                # 4. 可视化分析
                st.divider()
                c1, c2 = st.columns(2)
                with c1:
                    st.subheader("成交热度分布")
                    st.bar_chart(res.set_index('名称')['成交额(亿)'])
                with c2:
                    st.subheader("换手率对比")
                    st.line_chart(res.set_index('名称')['换手率'])
            else:
                st.warning("❌ 当前参数下未找到符合条件的股票，建议放宽筛选标准。")
                
        except Exception as e:
            st.error(f"系统运行波动，请稍后重试。详情: {e}")

# --- 底部提示 ---
st.divider()
st.caption("注：本系统仅供量化研究参考，不构成投资建议。股市有风险，入市需谨慎。")



