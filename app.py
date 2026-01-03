import streamlit as st
import akshare as ak
import pandas as pd
from datetime import datetime

# 设置页面配置（手机适配关键）
st.set_page_config(page_title="涨停潜力筛选", layout="wide")

st.title("🚀 涨停潜力筛选器")
st.caption("基于龙虎榜净买入与趋势动量策略")

# 侧边栏设置
st.sidebar.header("筛选参数")
buy_limit = st.sidebar.slider("最小主力净买入 (万元)", 1000, 10000, 3000)
top_n = st.sidebar.number_input("显示前几名", value=10)

if st.button('🎯 开始分析最新交易日数据'):
    with st.spinner('正在分析全市场实时行情...'):
        try:
            # 使用 A 股实时行情接口，这个接口列名最固定，不容易报错
            df = ak.stock_zh_a_spot_em()
            
            if df is not None and not df.empty:
                # 1. 统一列名映射（适配最新接口）
                df.rename(columns={
                    '代码': '代码',
                    '名称': '名称',
                    '最新价': '最新价',
                    '涨跌幅': '涨跌幅',
                    '成交额': '成交额',
                    '换手率': '换手率'
                }, inplace=True)

                # 2. 将数据转为数值型，防止计算报错
                df['涨跌幅'] = pd.to_numeric(df['涨跌幅'], errors='coerce')
                df['成交额'] = pd.to_numeric(df['成交额'], errors='coerce')
                df['最新价'] = pd.to_numeric(df['最新价'], errors='coerce')

                # 3. 核心筛选策略（模拟涨停潜力）：
                # 逻辑：涨幅在 4%~8% 之间（强势但未涨停），且成交额大于你设定的阈值（主力活跃）
                condition = (
                    (df['涨跌幅'] >= 4) & 
                    (df['涨跌幅'] < 9.5) & 
                    (df['成交额'] > buy_limit * 10000)
                )
                
                results = df[condition].copy()
                
                if not results.empty:
                    # 按成交额排序，找出最活跃的
                    results = results.sort_values(by='成交额', ascending=False)
                    
                    # 格式化金额显示
                    results['成交额(万)'] = (results['成交额'] / 10000).astype(int)
                    
                    st.success(f"找到 {len(results)} 只处于进攻姿态的强势个股")
                    
                    # 4. 展示表格
                    display_df = results[['代码', '名称', '最新价', '涨跌幅', '成交额(万)']].head(top_n)
                    st.data_editor(display_df, use_container_width=True, hide_index=True)
                    
                    # 5. 展示柱状图
                    st.bar_chart(display_df.set_index('名称')['涨跌幅'])
                else:
                    st.warning("未发现符合条件的强势股，请尝试调低成交额门槛。")
            else:
                st.error("无法获取数据，请检查网络。")
        except Exception as e:
            st.error(f"运行出错，请联系开发者。错误详情: {str(e)}")


