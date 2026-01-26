import streamlit as st
import akshare as ak
import pandas as pd
import time
import random

st.set_page_config(page_title="手机演示版", page_icon="📱", layout="wide")
st.title("📱 A股量化 (网络防御版)")
st.caption("检测到云端IP封锁严重，已启用智能灾备模式")

with st.sidebar:
    st.header("筛选参数")
    min_pct = st.slider('最小涨幅 (%)', 0.0, 9.0, 3.5)
    
if st.button('🚀 启动扫描'):
    status = st.status("正在连接数据源...", expanded=True)
    df = None
    
    # 1. 尝试连接新浪
    try:
        df = ak.stock_zh_a_spot()
    except Exception:
        pass
        
    # 2. 如果失败，尝试生成演示数据
    if df is None:
        st.error("❌ 所有数据接口均被云端封锁 (IP限制)。")
        st.warning("👇 以下为【模拟演示数据】，仅供验证系统逻辑：")
        
        # 生成假数据让程序跑通
        data = {
            '代码': ['600000', '000001', '601318'],
            '名称': ['模拟数据A', '模拟数据B', '模拟数据C'],
            '涨跌幅': [4.5, 3.8, 5.2],
            '最新价': [10.5, 12.8, 45.2],
            '换手率': [5.5, 6.1, 4.2],
            '成交额': [50000000, 60000000, 80000000],
            '流通市值': [1000000, 2000000, 3000000] # 单位万
        }
        df = pd.DataFrame(data)
        time.sleep(1)
        
    # 简单展示
    st.dataframe(df)
    status.update(label="完成", state="complete")
