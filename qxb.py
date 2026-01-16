import streamlit as st
import akshare as ak
import pandas as pd
import numpy as np
import requests
import json
import time

# --- 页面配置 ---
st.set_page_config(page_title="2025实战打板系统", page_icon="⚡", layout="wide")

# --- 样式优化 ---
st.markdown("""
<style>
    .metric-card {background-color: #f0f2f6; padding: 15px; border-radius: 10px; border-left: 5px solid #ff4b4b;}
    .big-font {font-size: 20px !important; font-weight: bold;}
</style>
""", unsafe_allow_html=True)

st.title("⚡ A股超短线·首板挖掘系统")
st.caption("逻辑核心：大盘情绪共振 + 底部放量启动 + 主力资金抢筹")

# --- 侧边栏：战法参数 ---
with st.sidebar:
    st.header("🎛️ 核心参数设置")
    
    st.subheader("1. 进攻参数")
    min_pct = st.slider('最小涨幅 (起爆点)', 0.0, 9.0, 3.5, help="低于3%往往是跟风，高于8%很难追")
    max_pct = st.slider('最大涨幅 (安全区)', 5.0, 9.9, 7.5, help="避开已经秒板的票")
    vol_ratio = st.slider('最小量比 (爆量)', 1.0, 5.0, 1.8, help="量比>1.8说明主力开始干活了")
    
    st.subheader("2. 防守参数")
    min_turnover = st.slider('换手率 (%)', 1.0, 20.0, (5.0, 12.0), help="换手太低没人玩，太高是出货")
    mkt_cap_limit = st.slider('最大流通市值 (亿)', 20, 500, 100)
    
    st.divider()
    st.header("🤖 微信预警")
    wechat_webhook = st.text_input("Webhook 地址", type="password")
    enable_push = st.checkbox("发现目标立即推送")

# --- 工具函数 ---
def get_em_url(code):
    market = "1" if str(code).startswith(('60', '68')) else "2"
    return f"https://quote.eastmoney.com/basic/full.html?stockcode={code}.{market}"

def send_wechat(url, title, content):
    headers = {"Content-Type": "application/json"}
    data = {"msgtype": "markdown", "markdown": {"content": f"## {title}\n{content}"}}
    try: requests.post(url, headers=headers, data=json.dumps(data), timeout=2)
    except: pass

def get_market_sentiment():
    """获取上证指数涨跌幅，判断大盘情绪"""
    try:
        df_index = ak.stock_zh_index_spot()
        # 上证指数代码通常是 sh000001
        sh_index = df_index[df_index['代码'] == 'sh000001'].iloc[0]
        return float(sh_index['涨跌幅']), float(sh_index['成交额'])
    except:
        return 0.0, 0.0

# --- 主逻辑 ---
# 1. 大盘情绪看板
sh_pct, sh_vol = get_market_sentiment()
c1, c2, c3 = st.columns(3)
with c1:
    st.metric("上证指数", f"{sh_pct}%", delta=f"{sh_pct}%")
with c2:
    sentiment_text = "🔥 情绪火热 (大胆干)" if sh_pct > 0.5 else ("❄️ 情绪冰点 (空仓)" if sh_pct < -0.5 else "⚖️ 震荡市 (精选)")
    st.metric("市场环境", sentiment_text)
with c3:
    st.metric("两市成交", f"{int(sh_vol/100000000)}亿")

st.divider()

if st.button('🚀 启动全市场雷达扫描'):
    if sh_pct < -1.0:
        st.error("⚠️ 警告：当前大盘跌幅超过 1%，覆巢之下无完卵，建议今日空仓休息！")
    
    status = st.status("正在进行全市场清洗...", expanded=True)
    
    try:
        # Step 1: 获取实时数据
        status.write("📡 正在连接交易所实时数据...")
        df = ak.stock_zh_a_spot_em()
        
        # Step 2: 基础清洗
        cols = ['代码', '名称', '涨跌幅', '最新价', '换手率', '成交额', '流通市值', '量比', '最高', '今开']
        for c in cols: df[c] = pd.to_numeric(df[c], errors='coerce')
        
        # 剔除ST、退市、科创/北交(可选，这里暂保留科创，剔除北交因流动性差异)
        # 剔除北交所 (8/4开头)
        pool = df[
            (~df['名称'].str.contains('ST|退')) & 
            (~df['代码'].str.startswith(('8', '4'))) &
            (df['成交额'] > 3000 * 10000) # 成交额大于3000万，流动性基础
        ].copy()
        
        status.write(f"🔍 基础池剩余 {len(pool)} 只，正在执行量价策略...")
        
        # Step 3: 核心选股逻辑 (针对近期行情的优化)
        # 逻辑A: 涨幅卡位 (3% - 7.5%) -> 捕捉主升浪中段
        mask_pct = (pool['涨跌幅'] >= min_pct) & (pool['涨跌幅'] <= max_pct)
        
        # 逻辑B: 必须是实体阳线 (最新价 > 开盘价) -> 剔除墓碑线/假阳线
        mask_candle = pool['最新价'] > pool['今开']
        
        # 逻辑C: 量能爆发 (量比 > 阈值)
        mask_vol = pool['量比'] >= vol_ratio
        
        # 逻辑D: 换手率区间 (主力控盘)
        mask_turn = (pool['换手率'] >= min_turnover[0]) & (pool['换手率'] <= min_turnover[1])
        
        # 逻辑E: 市值适中 (游资最爱 20-100亿)
        mask_cap = (pool['流通市值'] <= mkt_cap_limit * 100000000)
        
        candidates = pool[mask_pct & mask_candle & mask_vol & mask_turn & mask_cap].copy()
        
        # Step 4: 深度技术确认 (只取前 20 名进行K线分析，提高速度)
        status.write(f"🔬 初筛出 {len(candidates)} 只潜力股，正在进行 K 线形态确认...")
        
        final_list = []
        # 按量比排序，优先看资金最猛的
        candidates = candidates.sort_values(by='量比', ascending=False).head(20)
        
        progress = status.progress(0)
        total = len(candidates)
        
        for i, (idx, row) in enumerate(candidates.iterrows()):
            progress.progress((i+1)/total)
            try:
                # 获取均线数据 (判断是不是多头排列)
                # 使用 ak.stock_zh_a_hist 获取日线，只需要最近30天
                hist = ak.stock_zh_a_hist(symbol=row['代码'], period="daily", adjust="qfq", start_date="20241201")
                if len(hist) < 20: continue
                
                ma5 = hist['收盘'].rolling(5).mean().iloc[-1]
                ma10 = hist['收盘'].rolling(10).mean().iloc[-1]
                ma20 = hist['收盘'].rolling(20).mean().iloc[-1]
                curr = row['最新价']
                
                # 核心策略：均线多头 (5日 > 10日 > 20日) 且 股价在5日线上方
                # 这种票在近期震荡市里最抗跌，一旦大盘反弹，最先涨停
                if curr > ma5 and ma5 > ma10 and ma10 > ma20:
                    final_list.append(row)
            except:
                continue
                
        status.update(label="扫描完成！", state="complete", expanded=False)
        
        # Step 5: 结果展示
        if final_list:
            res = pd.DataFrame(final_list)
            st.success(f"🎯 最终锁定 {len(res)} 只『均线多头+放量起爆』个股")
            
            # 格式化
            res['市值'] = (res['流通市值'] / 100000000).round(1)
            res['跳转'] = res['代码'].apply(lambda x: f'<a href="{get_em_url(x)}" target="_blank">🔗看K线</a>')
            
            # 展示表格
            cols = ['代码', '名称', '涨跌幅', '最新价', '换手率', '量比', '市值', '跳转']
            st.write(res[cols].to_html(escape=False, index=False), unsafe_allow_html=True)
            
            # 微信推送
            if enable_push and wechat_webhook:
                msg = "\n".join([f"- {r['名称']}: 涨{r['涨跌幅']}% 量比{r['量比']}" for r in final_list[:5]])
                send_wechat(wechat_webhook, "⚡ 涨停潜力股预警", msg)
        else:
            st.warning("⚠️ 市场情绪较弱，未发现完美符合『多头排列+放量』的个股，建议空仓。")

    except Exception as e:
        st.error(f"系统运行出错: {e}")
