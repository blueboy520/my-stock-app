import streamlit as st
import akshare as ak
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
from datetime import datetime, timedelta

# --- 页面基础配置 ---
st.set_page_config(page_title="超级个股看板", layout="wide")

# --- 侧边栏：控制面板 ---
st.sidebar.header("🛠️ 参数设置")
symbol = st.sidebar.text_input("股票代码 (6位)", value="000001")
period = st.sidebar.selectbox("K线周期", ["daily", "weekly", "monthly"], index=0)

# 默认显示最近半年的数据
default_start = (datetime.now() - timedelta(days=180)).strftime("%Y%m%d")
default_end = datetime.now().strftime("%Y%m%d")

start_date = st.sidebar.text_input("开始日期 (YYYYMMDD)", value=default_start)
end_date = st.sidebar.text_input("结束日期 (YYYYMMDD)", value=default_end)

# --- 主逻辑 ---
st.title(f"🚀 个股深度复盘: {symbol}")

# 添加一个加载提示
with st.spinner('正在从 AkShare 拉取最新数据...'):
    try:
        # 1. 获取数据
        stock_df = ak.stock_zh_a_hist(symbol=symbol, period=period, start_date=start_date, end_date=end_date)
        
        if stock_df.empty:
            st.warning("⚠️ 没有获取到数据，请检查股票代码或日期范围。")
        else:
            # 2. 数据清洗
            stock_df.rename(columns={'日期': 'date', '开盘': 'open', '收盘': 'close', 
                                     '最高': 'high', '最低': 'low', '成交量': 'volume'}, inplace=True)
            stock_df['date'] = pd.to_datetime(stock_df['date'])
            
            # 3. 计算均线指标 (MA5, MA10, MA20)
            stock_df['MA5'] = stock_df['close'].rolling(window=5).mean()
            stock_df['MA10'] = stock_df['close'].rolling(window=10).mean()
            stock_df['MA20'] = stock_df['close'].rolling(window=20).mean()

            # --- 4. 绘图核心逻辑 (终极版) ---
            # 创建子图：第一行是K线(70%)，第二行是成交量(30%)
            fig = make_subplots(
                rows=2, cols=1, 
                shared_xaxes=True, 
                vertical_spacing=0.03, 
                row_heights=[0.7, 0.3],
                subplot_titles=(f"{symbol} 价格走势", "成交量")
            )

            # [主图] 绘制 K线 (中国红涨绿跌风格)
            fig.add_trace(go.Candlestick(
                x=stock_df['date'],
                open=stock_df['open'], high=stock_df['high'],
                low=stock_df['low'], close=stock_df['close'],
                name='K线',
                increasing_line_color='#ef5350', # 红涨
                decreasing_line_color='#26a69a'  # 绿跌
            ), row=1, col=1)

            # [主图] 绘制均线
            fig.add_trace(go.Scatter(x=stock_df['date'], y=stock_df['MA5'], line=dict(color='orange', width=1.5), name='MA5'), row=1, col=1)
            fig.add_trace(go.Scatter(x=stock_df['date'], y=stock_df['MA10'], line=dict(color='skyblue', width=1.5), name='MA10'), row=1, col=1)
            fig.add_trace(go.Scatter(x=stock_df['date'], y=stock_df['MA20'], line=dict(color='purple', width=1.5), name='MA20'), row=1, col=1)

            # [副图] 绘制成交量 (颜色随涨跌变化)
            vol_colors = ['#ef5350' if c >= o else '#26a69a' for c, o in zip(stock_df['close'], stock_df['open'])]
            fig.add_trace(go.Bar(
                x=stock_df['date'], 
                y=stock_df['volume'],
                marker_color=vol_colors,
                name='成交量'
            ), row=2, col=1)

            # [全局] 布局美化
            fig.update_layout(
                height=700,  # 更高的大屏体验
                xaxis_rangeslider_visible=False,
                hovermode='x unified', # 十字光标同时显示上下图数据
                margin=dict(l=10, r=10, t=30, b=10),
                paper_bgcolor='rgba(0,0,0,0)', # 背景透明，适配 Streamlit 深色模式
                plot_bgcolor='rgba(0,0,0,0)'
            )
            
            # [全局] 坐标轴优化
            fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor='rgba(128,128,128,0.2)')
            fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor='rgba(128,128,128,0.2)')

            # 渲染图表
            st.plotly_chart(fig, use_container_width=True)

            # 显示最近一天的数据摘要
            last_day = stock_df.iloc[-1]
            st.info(f"📅 **{last_day['date'].date()}** | 收盘: {last_day['close']} | 涨幅: {((last_day['close']-last_day['open'])/last_day['open']*100):.2f}%")

    except Exception as e:
        st.error(f"发生错误: {e}")
        st.write("提示：请确保股票代码输入正确（如：000001），并检查网络连接。")
