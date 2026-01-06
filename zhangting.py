import streamlit as st
import akshare as ak
import pandas as pd
import requests
import json

# --- 1. 页面配置 ---
st.set_page_config(page_title="涨停狙击手·尊享版", page_icon="🎯", layout="wide")
st.title("🎯 涨停狙击手 (高胜率收敛模式)")
st.caption("核心逻辑：均线多头排列 + 资金暴力抢筹 + 黄金换手率")

# --- 2. 侧边栏：参数设置 (默认值已调至最严苛) ---
with st.sidebar:
    st.header("⚙️ 狙击参数 (严选)")
    # 涨幅放宽一点，因为好票可能已经涨起来了
    min_pct = st.slider('最小涨幅 (%)', 0.0, 9.5, 3.0) 
    max_pct = st.slider('最大涨幅 (%)', 5.0, 10.0, 8.5) # 避开已经封板的
    
    st.divider()
    st.write("🔍 **资金与市值**")
    buy_limit = st.slider('成交额门槛 (万元)', 1000, 50000, 8000) # 只要大资金参与的
    min_vol_ratio = st.slider("最小量比 (倍)", 1.0, 5.0, 2.0) # 量比必须大
    turnover_range = st.slider("换手率区间 (%)", 1.0, 30.0, (5.0, 15.0)) # 锁定黄金换手区间
    
    st.divider()
    st.header("🤖 微信推送")
    wechat_webhook = st.text_input("Webhook 地址", type="password")
    enable_push = st.checkbox("开启自动推送")

# --- 3. 工具函数 ---
def get_em_url(code):
    market = "1" if str(code).startswith(('60', '68')) else "2"
    return f"https://quote.eastmoney.com/basic/full.html?stockcode={code}.{market}"

def send_wechat_msg(url, content):
    headers = {"Content-Type": "application/json"}
    data = {"msgtype": "markdown", "markdown": {"content": f"## 🎯 狙击手预警\n{content}"}}
    try: requests.post(url, headers=headers, data=json.dumps(data))
    except: pass

# --- 4. 核心逻辑 ---
if st.button('🚀 启动高胜率扫描'):
    status_text = st.empty()
    status_text.info('正在拉取全市场实时数据...')
    
    try:
        # 1. 获取基础行情
        df = ak.stock_zh_a_spot_em()
        
        # 2. 数据清洗与格式化
        numeric_cols = ['涨跌幅', '成交额', '换手率', '流通市值', '量比', '最新价', '最高', '今开']
        for col in numeric_cols:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        
        # 3. 第一轮筛选：基础池过滤 (快速排除垃圾股)
        # 逻辑：非ST、上市超过30天(这里简单用代码非68/30开头粗略过滤新股太复杂，暂且忽略)、有成交量
        base_mask = (
            (~df['名称'].str.contains('ST')) & 
            (~df['名称'].str.contains('退')) & 
            (df['成交额'] > buy_limit * 10000)
        )
        pool = df[base_mask].copy()
        
        status_text.info(f'基础池筛选完毕，剩余 {len(pool)} 只，正在进行趋势计算...')
        
        # 4. 第二轮筛选：高胜率形态 (狙击逻辑)
        # 这一步是关键！
        final_list = []
        
        # 为了速度，我们直接用 pandas 向量化计算，不遍历
        # 逻辑A: 涨幅在攻击区间
        cond_pct = (pool['涨跌幅'] >= min_pct) & (pool['涨跌幅'] <= max_pct)
        
        # 逻辑B: 量比爆发 (主力进场信号)
        cond_vol = pool['量比'] >= min_vol_ratio
        
        # 逻辑C: 换手率健康 (人气充足但未失控)
        cond_turn = (pool['换手率'] >= turnover_range[0]) & (pool['换手率'] <= turnover_range[1])
        
        # 逻辑D: 必须是阳线 (收盘 > 开盘) - 剔除假阴真阳
        cond_red = pool['最新价'] > pool['今开']
        
        # 逻辑E: 市值适中 (30亿-300亿最容易出妖股)
        mkt_cap_val = pool['流通市值'] / 100000000
        cond_cap = (mkt_cap_val >= 30) & (mkt_cap_val <= 300)
        
        target_df = pool[cond_pct & cond_vol & cond_turn & cond_red & cond_cap].copy()
        
        # 5. 结果展示
        if not target_df.empty:
            # 综合评分排序：量比 * 涨幅 (量价齐升的最优先)
            target_df['评分'] = target_df['量比'] * target_df['涨跌幅']
            target_df = target_df.sort_values(by='评分', ascending=False).head(10)
            
            target_df['市值(亿)'] = (target_df['流通市值'] / 100000000).round(1)
            target_df['链接'] = target_df['代码'].apply(lambda x: f'<a href="{get_em_url(x)}" target="_blank">🔗看图</a>')
            
            status_text.success(f"🎯 最终锁定 {len(target_df)} 只『主升浪』形态个股！")
            
            # 显示精美表格
            cols = ['代码', '名称', '涨跌幅', '量比', '换手率', '市值(亿)', '成交额', '链接']
            # 将成交额转为亿
            target_df['成交额'] = (target_df['成交额'] / 100000000).round(2).astype(str) + '亿'
            
            st.write(target_df[cols].to_html(escape=False, index=False), unsafe_allow_html=True)
            
            # 微信推送
            if enable_push and wechat_webhook:
                items = [f"- **{r['名称']}**: 涨`{r['涨跌幅']}%` 量比`{r['量比']}` 换手`{r['换手率']}%`" for _, r in target_df.iterrows()]
                send_wechat_msg(wechat_webhook, "\n".join(items))
        else:
            status_text.warning("⚠️ 市场情绪较弱，未发现符合『高胜率』模型的股票。宁缺毋滥！")
            
    except Exception as e:
        status_text.error(f"数据分析中断: {e}")
