import streamlit as st
import akshare as ak
import pandas as pd
import numpy as np
import requests
import json
import time

# --- 1. 页面与基础配置 ---
st.set_page_config(page_title="量化回测优化版", page_icon="🧬", layout="wide")
st.title("🧬 量化选股系统 (趋势共振优化版)")
st.caption("逻辑升级：实时量价筛选 + 历史K线趋势确认 (MA20 + RSI)")

# --- 2. 侧边栏参数 ---
with st.sidebar:
    st.header("🔍 第一阶段：初筛 (广撒网)")
    buy_limit = st.slider('成交额门槛 (万元)', 1000, 30000, 5000)
    min_pct = st.slider('最小涨幅 (%)', 0.0, 9.5, 3.0)
    max_pct = st.slider('最大涨幅 (%)', 5.0, 10.0, 9.0)
    min_turnover = st.slider('最小换手率 (%)', 0.0, 20.0, 5.0)
    
    st.divider()
    st.header("🔬 第二阶段：精筛 (技术面)")
    check_ma20 = st.checkbox("必须站上20日均线 (趋势向上)", value=True)
    check_rsi = st.checkbox("RSI未超买 (拒绝高位接盘)", value=True)
    rsi_threshold = st.slider("RSI 安全上限", 60, 90, 80)
    
    st.divider()
    st.header("🤖 微信推送")
    wechat_webhook = st.text_input("Webhook 地址", type="password")
    enable_push = st.checkbox("开启推送")

# --- 3. 工具函数 ---
def get_em_url(code):
    market = "1" if str(code).startswith(('60', '68')) else "2"
    return f"https://quote.eastmoney.com/basic/full.html?stockcode={code}.{market}"

def send_wechat_msg(url, content):
    headers = {"Content-Type": "application/json"}
    data = {"msgtype": "markdown", "markdown": {"content": f"## 🧬 趋势共振预警\n{content}"}}
    try: requests.post(url, headers=headers, data=json.dumps(data), timeout=2)
    except: pass

def calculate_technical_indicators(df_hist):
    """计算 MA20 和 RSI"""
    if df_hist is None or len(df_hist) < 25:
        return None, None
    
    # 计算 MA20
    ma20 = df_hist['收盘'].rolling(window=20).mean().iloc[-1]
    
    # 计算 RSI (14日)
    close_delta = df_hist['收盘'].diff()
    up = close_delta.clip(lower=0)
    down = -1 * close_delta.clip(upper=0)
    ma_up = up.rolling(window=14).mean()
    ma_down = down.rolling(window=14).mean()
    rsi = 100 - (100 / (1 + ma_up / ma_down))
    current_rsi = rsi.iloc[-1]
    
    return ma20, current_rsi

# --- 4. 主程序 ---
if st.button('🚀 执行二段式深度扫描'):
    status = st.status("正在初始化系统...", expanded=True)
    
    try:
        # === 第一阶段：全市场快照筛选 ===
        status.write("🔍 Phase 1: 正在扫描全市场实时数据...")
        df = ak.stock_zh_a_spot_em()
        
        # 数据清洗
        numeric_cols = ['涨跌幅', '成交额', '换手率', '流通市值', '最新价', '代码']
        for col in numeric_cols:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        
        # 基础过滤：非ST、非退市、有成交量
        base_mask = (
            (~df['名称'].str.contains('ST')) & 
            (~df['名称'].str.contains('退')) & 
            (df['成交额'] > buy_limit * 10000)
        )
        pool = df[base_mask].copy()
        
        # 量价过滤
        cond_1 = (pool['涨跌幅'] >= min_pct) & (pool['涨跌幅'] <= max_pct)
        cond_2 = pool['换手率'] >= min_turnover
        
        candidates = pool[cond_1 & cond_2].copy()
        
        # 限制初选数量，防止第二阶段太慢 (取前30名最活跃的)
        candidates = candidates.sort_values(by='换手率', ascending=False).head(30)
        
        status.write(f"✅ Phase 1 完成：初选出 {len(candidates)} 只活跃股，进入深度技术分析...")
        
        # === 第二阶段：逐个获取历史K线计算指标 ===
        final_results = []
        progress_bar = status.progress(0)
        total_candidates = len(candidates)
        
        for i, (index, row) in enumerate(candidates.iterrows()):
            try:
                # 更新进度条
                progress_bar.progress((i + 1) / total_candidates)
                
                # 获取个股历史数据 (最近60天)
                hist_df = ak.stock_zh_a_hist(symbol=row['代码'], period="daily", start_date="20240101", adjust="qfq")
                
                # 计算指标
                ma20, rsi = calculate_technical_indicators(hist_df)
                
                # 判空保护
                if ma20 is None: continue
                
                current_price = row['最新价']
                
                # --- 核心优化逻辑 ---
                is_valid = True
                fail_reason = ""
                
                # 逻辑A: 趋势共振 (价格 > 20日线)
                if check_ma20 and current_price < ma20:
                    is_valid = False
                    fail_reason = "股价在均线下方"
                
                # 逻辑B: 拒绝超买 (RSI < 阈值)
                if check_rsi and rsi > rsi_threshold:
                    is_valid = False
                    fail_reason = f"RSI超买({int(rsi)})"
                
                if is_valid:
                    final_results.append({
                        '代码': row['代码'],
                        '名称': row['名称'],
                        '最新价': row['最新价'],
                        '涨跌幅': row['涨跌幅'],
                        '换手率': row['换手率'],
                        'MA20乖离': f"{((current_price - ma20)/ma20*100):.1f}%",
                        'RSI指标': round(rsi, 1),
                        '成交额(亿)': round(row['成交额']/100000000, 2)
                    })
                    
            except Exception as e:
                continue # 个别股票数据获取失败跳过
        
        status.update(label="扫描完成！", state="complete", expanded=False)
        
        # === 结果展示 ===
        if final_results:
            res_df = pd.DataFrame(final_results)
            st.success(f"🎯 最终精选出 {len(res_df)} 只『趋势共振』个股")
            
            # 生成链接
            res_df['看K线'] = res_df['代码'].apply(lambda x: f'<a href="{get_em_url(x)}" target="_blank">🔗跳转</a>')
            
            # 展示
            cols = ['代码', '名称', '涨跌幅', '换手率', 'MA20乖离', 'RSI指标', '看K线']
            st.write(res_df[cols].to_html(escape=False, index=False), unsafe_allow_html=True)
            
            # 可视化 RSI 分布
            st.caption("🔍 选中股票 RSI 分布 (RSI>50为强势区)")
            st.bar_chart(res_df.set_index('名称')['RSI指标'])
            
            # 微信推送
            if enable_push and wechat_webhook:
                items = [f"- **{r['名称']}**: 涨`{r['涨跌幅']}%` RSI:`{r['RSI指标']}`" for r in final_results[:5]]
                send_wechat_msg(wechat_webhook, "\n".join(items))
        else:
            st.warning("⚠️ 初选股票均未通过技术面（MA20/RSI）验证，建议观察市场情绪。")
            
    except Exception as e:
        st.error(f"运行中断: {str(e)}")
