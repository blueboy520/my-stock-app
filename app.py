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
    with st.spinner('正在调取交易所数据...'):
        try:
            # 1. 获取数据
            # 自动获取最新交易日数据
            df = ak.stock_lhb_detail_daily_em() 
            
            if df is not None and not df.empty:
                # 2. 数据处理
                df['净买额'] = pd.to_numeric(df['净买额'], errors='coerce')
                df['涨跌幅'] = pd.to_numeric(df['涨跌幅'], errors='coerce')
                
                # 3. 执行策略
                condition = (df['净买额'] > buy_limit * 10000) & (df['涨跌幅'] > 0)
                results = df[condition].copy()
                
                if not results.empty:
                    results['净买额(万)'] = (results['净买额'] / 10000).astype(int)
                    display_df = results[['代码', '名称', '最新价', '涨跌幅', '净买额(万)', '上榜原因']].head(top_n)
                    
                    # 4. 手机端可视化展示
                    st.success(f"找到 {len(results)} 只符合条件的股票")
                    
                    # 使用 Data Editor 方便在手机上左右滑动查看
                    st.data_editor(
                        display_df,
                        column_config={
                            "涨跌幅": st.column_config.Number_column(format="%.2f%%"),
                            "净买额(万)": st.column_config.Progress_column(min_value=0, max_value=10000)
                        },
                        hide_index=True,
                        use_container_width=True
                    )
                    
                    # 简单的柱状图
                    st.bar_chart(display_df.set_index('名称')['净买额(万)'])
                else:
                    st.warning("当前参数下未筛选出股票，请调低金额门槛。")
            else:
                st.error("无法获取数据，请检查是否为非交易日。")
        except Exception as e:
            st.error(f"运行出错: {e}")

st.info("提示：在手机浏览器中点击'添加到主屏幕'，即可像App一样使用。")
# my-stock-app
