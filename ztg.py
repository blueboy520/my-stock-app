import streamlit as st
import akshare as ak
import pandas as pd
import requests
import json

# --- 1. 页面配置 ---
st.set_page_config(page_title="黑马擒拿专业版", page_icon="🐎", layout="wide")
st.title("🐎 翻倍黑马潜力研判系统 (安全加强版)")

# --- 2. 侧边栏：参数设置 ---
with st.sidebar:
    st.header("🔍 核心选股因子")
    buy_limit = st.slider('成交额门槛 (万元)', 500, 20000, 3000)
    min_pct = st.slider('最小涨幅 (%)', 0.0, 9.0, 4.0)
    max_market_cap = st.slider("最大流通市值 (亿)", 20, 200, 80)
    min_turnover = st.slider('最小换手率 (%)', 0.0, 30.0, 5.0)
    
    st.divider()
    st.header("🛡️ 安全过滤 (已默认开启)")
    st.info("已自动过滤：ST股、退市股、亏损股(PE<0)")
    
    st.divider()
    st.header("🤖 微信推送")
    wechat_webhook = st.text_input("Webhook 地址", type="password")
    enable_push = st.checkbox("扫描到黑马即推送")

# --- 3. 核心工具函数 ---
def get_em_url(code):
    code = str(code)
    market = "1" if code.startswith(('60', '68')) else "2"
    return f"https://quote.eastmoney.com/basic/full.html?stockcode={code}.{market}"

def send_wechat_msg(url, content):
    headers = {"Content-Type": "application/json"}
    data = {"msgtype": "markdown", "markdown": {"content": f"## 🐎 黑马启动预警\n{content}"}}
    try: requests.post(url, headers=headers, data=json.dumps(data))
    except: pass

# --- 4. 主程序逻辑 ---
if st.button('🚀 执行深度扫描：寻找翻倍种子'):
    with st.spinner('正在分析全市场 5000+ 个股财务与技术指标...'):
        try:
            # 获取实时行情
            df = ak.stock_zh_a_spot_em()
            
            # 数据类型转换
            numeric_cols = ['涨跌幅', '成交额', '换手率', '流通市值', '市盈率-动态', '量比', '最新价']
            for col in numeric_cols:
                df[col] = pd.to_numeric(df[col], errors='coerce')
            
            # 5. 核心过滤逻辑：【安全过滤】+【黑马模型】
            # 安全逻辑：剔除ST、剔除名称中带退字、剔除市盈率为负（亏损）
            safe_mask = (
                (~df['名称'].str.contains('ST')) & 
                (~df['名称'].str.contains('退')) & 
                (df['市盈率-动态'] > 0)
            )
            
            # 黑马启动逻辑：
            # - 处于起爆点（涨幅4%-9.5%）
            # - 小市值（容易翻倍）
            # - 高活跃（量比、换手率双高）
            black_horse_mask = (
                (df['涨跌幅'] >= min_pct) & 
                (df['涨跌幅'] < 9.6) &
                (df['流通市值'] / 100000000 <= max_market_cap) &
                (df['成交额'] >= buy_limit * 10000) &
                (df['换手率'] >= min_turnover) &
                (df['量比'] >= 1.5)
            )
            
            res = df[safe_mask & black_horse_mask].copy()
            
            if not res.empty:
                res = res.sort_values(by=['量比', '换手率'], ascending=False).head(15)
                res['市值(亿)'] = (res['流通市值'] / 100000000).round(1)
                res['链接'] = res['代码'].apply(lambda x: f'<a href="{get_em_url(x)}" target="_blank">🔗看图</a>')
                
                st.success(f"🎯 成功锁定 {len(res)} 只符合『低位启动+财务安全』的潜力黑马！")
                
                # 展示表格
                cols = ['代码', '名称', '最新价', '涨跌幅', '换手率', '市值(亿)', '量比', '链接']
                st.write(res[cols].to_html(escape=False, index=False), unsafe_allow_html=True)
                
                # 微信推送
                if enable_push and wechat_webhook:
                    items = [f"- **{r['名称']}** ({r['代码']}): 涨幅`{r['涨跌幅']}%`, 市值`{r['市值(亿)']}亿`, 换手`{r['换手率']}%`" for _, r in res.head(5).iterrows()]
                    send_wechat_msg(wechat_webhook, "\n".join(items))
            else:
                st.warning("⚠️ 暂未发现符合条件的种子选手，请适当放宽换手率或市值门槛。")
                
        except Exception as e:
            st.error(f"分析出错: {e}")

st.divider()
st.caption("提示：选股逻辑基于量化因子，实战请结合当日热点板块及K线形态判断。")

