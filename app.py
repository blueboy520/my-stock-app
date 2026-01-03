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
            # 使用最新且稳定的龙虎榜活跃股接口
            df = ak.stock_zh_a_spot_em()
            
            if df is not None and not df.empty:
                # --- 智能列名修复逻辑 ---
                # 找出实际返回的列名中，哪个是我们要的“代码”、“名称”和“净买额”
                col_map = {
                    "代码": ["代码", "股票代码", "secuCode"],
                    "名称": ["名称", "股票名称", "secuName"],
                    "净买额": ["净买额", "累计净买额", "净买入额", "net_buy_amt"],
                    "涨跌幅": ["涨跌幅", "累积涨跌幅", "chg_percent"]
                }
                
                # 动态重命名，防止 KeyError
                for target, suspects in col_map.items():
                    for s in suspects:
                        if s in df.columns:
                            df.rename(columns={s: target}, inplace=True)
                            break

                # 确保关键列存在后再处理
                if '净买额' in df.columns:
                    df['净买额'] = pd.to_numeric(df['净买额'], errors='coerce')
                    df['涨跌幅'] = pd.to_numeric(df['涨跌幅'], errors='coerce')
                    
                    # 3. 执行策略
                    condition = (df['净买额'] > buy_limit * 10000) & (df['涨跌幅'] > 0)
                    results = df[condition].copy()
                    
                    if not results.empty:
                        results['净买额(万)'] = (results['净买额'] / 10000).astype(int)
                        # 只显示存在的列
                        final_cols = [c for c in ['代码', '名称', '最新价', '涨跌幅', '净买额(万)'] if c in results.columns]
                        display_df = results[final_cols].head(top_n)
                        
                        st.success(f"找到 {len(results)} 只符合条件的股票")
                        st.data_editor(display_df, use_container_width=True, hide_index=True)
                        st.bar_chart(display_df.set_index('名称')['净买额(万)'])
                    else:
                        st.warning("当前参数下未筛选出符合条件的个股，请调低金额门槛。")
                else:
                    st.error(f"接口返回列名不符。当前列名为: {list(df.columns)}")
            else:
                st.error("无法获取数据，请检查网络或是否为非交易日。")
        except Exception as e:
            st.error(f"运行出错: {str(e)}")

