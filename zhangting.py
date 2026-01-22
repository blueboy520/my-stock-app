import streamlit as st
import akshare as ak
import pandas as pd
import numpy as np
import requests
import json
import time

# --- 页面配置 ---
st.set_page_config(page_title="2025实战打板系统(新浪源)", page_icon="🔥", layout="wide")

st.title("🔥 A股超短线·首板挖掘 (新浪救援版)")
st.caption("当前使用【新浪财经】数据源，以绕过东方财富的云端IP封锁")

# --- 侧边栏：战法参数 ---
with st.sidebar:
    st.header("🎛️ 核心参数")
    st.info("注：新浪源暂不支持'量比'筛选")
    
    st.subheader("1. 进攻参数")
    min_pct = st.slider('最小涨幅 (%)', 0.0, 9.0, 3.5)
    max_pct = st.slider('最大涨幅 (%)', 5.0, 9.9, 7.5)
    
    st.subheader("2. 防守参数")
    min_turnover = st.slider('换手率 (%)', 1.0, 20.0, (5.0, 12.0))
    mkt_cap_limit = st.slider('最大流通市值 (亿)', 20, 500, 100)
    
    st.divider()
    st.header("🤖 微信预警")
    wechat_webhook = st.text_input("Webhook 地址", type="password")
    enable_push = st.checkbox("发现目标立即推送")

# --- 工具函数 ---
def get_em_url(code):
    # 跳转依然用东财，看图更方便
    market = "1" if str(code).startswith(('60', '68')) else "2"
    return f"https://quote.eastmoney.com/basic/full.html?stockcode={code}.{market}"

def send_wechat(url, title, content):
    headers = {"Content-Type": "application/json"}
    data = {"msgtype": "markdown", "markdown": {"content": f"## {title}\n{content}"}}
    try: requests.post(url, headers=headers, data=json.dumps(data), timeout=2)
    except: pass

def get_sina_data_safe():
    """获取新浪全市场数据，抗封锁能力强"""
    max_retries = 3
    for i in range(max_retries):
        try:
            # 使用新浪接口：stock_zh_a_spot
            df = ak.stock_zh_a_spot()
            if df is not None and not df.empty:
                return df
        except Exception as e:
            time.sleep(1)
    return None

# --- 主逻辑 ---
if st.button('🚀 启动新浪源扫描'):
    status = st.status("正在切换至新浪线路...", expanded=True)
    
    try:
        # Step 1: 获取数据
        status.write("📡 正在连接新浪财经实时数据...")
        df = get_sina_data_safe()
        
        if df is None:
            st.error("新浪接口也暂时繁忙，请过几分钟再试，或建议在本地电脑运行。")
            st.stop()

        # Step 2: 数据清洗 (适配新浪列名)
        # 新浪返回列名：symbol, code, name, trade, pricechange, changepercent, buy, sell, settlement, open, high, low, volume, amount, ticktime, per, pb, mktcap, nmc, turnoverratio
        
        # 重命名为我们习惯的中文
        df = df.rename(columns={
            'code': '代码',
            'name': '名称',
            'trade': '最新价',
            'changepercent': '涨跌幅',
            'amount': '成交额',
            'nmc': '流通市值', # nmc是流通市值
            'turnoverratio': '换手率',
            'open': '今开'
        })

        # 转换数值
        numeric_cols = ['涨跌幅', '最新价', '成交额', '流通市值', '换手率', '今开']
        for c in numeric_cols:
            df[c] = pd.to_numeric(df[c], errors='coerce')
        
        # 新浪的流通市值单位是“万元”，需要统一逻辑
        # 我们的策略是用“亿”判断，所以 1亿 = 10000万
        # 下面计算时要注意单位换算
        
        df['代码'] = df['代码'].astype(str)
        df['名称'] = df['名称'].astype(str)
        
        # Step 3: 基础过滤
        mask_basic = (
            (~df['名称'].str.contains('ST|退')) & 
            (~df['代码'].str.startswith(('8', '4'))) &
            (df['成交额'] > 3000 * 10000) # 成交额 > 3000万
        )
        pool = df[mask_basic].copy()
        
        status.write(f"🔍 基础池剩余 {len(pool)} 只，执行筛选...")
        
        # Step 4: 核心选股逻辑
        mask_pct = (pool['涨跌幅'] >= min_pct) & (pool['涨跌幅'] <= max_pct)
        mask_candle = pool['最新价'] > pool['今开'] # 真阳线
        mask_turn = (pool['换手率'] >= min_turnover[0]) & (pool['换手率'] <= min_turnover[1])
        # 新浪流通市值单位是万，所以 x/10000 = 亿
        mask_cap = ((pool['流通市值'] / 10000) <= mkt_cap_limit)
        
        candidates = pool[mask_pct & mask_candle & mask_turn & mask_cap].copy()
        
        # Step 5: 结果展示 (新浪源不支持K线回测，因为请求太慢，直接出结果)
        status.update(label="扫描完成！", state="complete", expanded=False)
        
        if not candidates.empty:
            # 排序：按换手率活跃度
            res = candidates.sort_values(by='换手率', ascending=False).head(20)
            
            st.success(f"🎯 新浪源锁定 {len(res)} 只潜力股")
            
            res['市值(亿)'] = (res['流通市值'] / 10000).round(1)
            res['跳转'] = res['代码'].apply(lambda x: f'<a href="{get_em_url(x)}" target="_blank">🔗看K线</a>')
            
            # 这里的成交额单位也是元，转亿
            res['成交额(亿)'] = (res['成交额'] / 100000000).round(2)

            cols = ['代码', '名称', '涨跌幅', '最新价', '换手率', '成交额(亿)', '市值(亿)', '跳转']
            st.write(res[cols].to_html(escape=False, index=False), unsafe_allow_html=True)
            
            if enable_push and wechat_webhook:
                msg = "\n".join([f"- {r['名称']}: 涨{r['涨跌幅']}% 换手{r['换手率']}%" for _, r in res.head(5).iterrows()])
                send_wechat(wechat_webhook, "🔥 新浪源预警", msg)
        else:
            st.warning("⚠️ 未发现符合条件的个股。")

    except Exception as e:
        st.error(f"新浪源连接失败: {str(e)}")

