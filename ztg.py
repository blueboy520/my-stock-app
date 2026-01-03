import streamlit as st
import akshare as ak
import pandas as pd
import requests
import json

# 1. 页面基础配置
st.set_page_config(page_title="量化选股+微信预警版", page_icon="📲", layout="wide")

st.title("📲 量化选股 + 微信预警版")

# --- 侧边栏配置 ---
with st.sidebar:
    st.header("⚙️ 核心参数")
    buy_limit = st.slider('成交额门槛 (万元)', 500, 20000, 5000, step=500)
    min_pct = st.slider('最小涨幅 (%)', 0.0, 9.0, 5.0)
    min_turnover = st.slider('最小换手率 (%)', 0.0, 30.0, 8.0)
    
    st.divider()
    st.header("🤖 微信预警设置")
    wechat_webhook = st.text_input("填入企业微信 Webhook 地址", type="password")
    enable_push = st.checkbox("开启实时推送")

# --- 推送函数 ---
def send_wechat_msg(url, content):
    headers = {"Content-Type": "application/json"}
    data = {
        "msgtype": "markdown",
        "markdown": {
            "content": f"## 🚀 选股系统预警\n> **筛选时间**: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')}\n\n{content}"
        }
    }
    try:
        response = requests.post(url, headers=headers, data=json.dumps(data))
        return response.json()
    except Exception as e:
        return str(e)

# --- 跳转链接函数 ---
def get_em_url(code):
    code = str(code)
    market = "1" if code.startswith(('60', '68')) else "2"
    return f"https://quote.eastmoney.com/basic/full.html?stockcode={code}.{market}"

# --- 主程序逻辑 ---
if st.button('🚀 执行深度扫描并推送'):
    with st.spinner('正在分析实时成交数据并准备推送...'):
        try:
            df = ak.stock_zh_a_spot_em()
            for col in ['涨跌幅', '成交额', '换手率']:
                df[col] = pd.to_numeric(df[col], errors='coerce')
            
            # 策略过滤
            mask = (df['涨跌幅'] >= min_pct) & (df['成交额'] >= buy_limit * 10000) & (df['换手率'] >= min_turnover)
            res = df[mask].copy()
            
            if not res.empty:
                res = res.sort_values(by='成交额', ascending=False).head(10)
                res['成交额(亿)'] = (res['成交额'] / 100000000).round(2)
                res['跳转'] = res['代码'].apply(lambda x: f'<a href="{get_em_url(x)}" target="_blank">🔗看图</a>')
                
                # 页面显示
                st.success(f"✅ 筛选到 {len(res)} 只目标")
                st.write(res[['代码', '名称', '涨跌幅', '换手率', '成交额(亿)', '跳转']].to_html(escape=False, index=False), unsafe_allow_html=True)
                
                # 推送逻辑
                if enable_push and wechat_webhook:
                    msg_items = []
                    for _, row in res.iterrows():
                        msg_items.append(f"- **{row['名称']}** ({row['代码']}): 涨幅 `{row['涨跌幅']}%`, 换手 `{row['换手率']}%`")
                    
                    push_content = "\n".join(msg_items)
                    status = send_wechat_msg(wechat_webhook, push_content)
                    st.toast("微信消息已发送！")
            else:
                st.warning("❌ 未发现符合条件的强势股。")
        except Exception as e:
            st.error(f"出错: {e}")
