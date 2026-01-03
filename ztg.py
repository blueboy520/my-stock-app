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
import streamlit as st
import akshare as ak
import pandas as pd

# 侧边栏增加黑马筛选参数
with st.sidebar:
    st.header("型 翻倍黑马模型参数")
    max_market_cap = st.slider("最大流通市值 (亿)", 20, 200, 80)
    min_vol_ratio = st.slider("成交量放大倍数", 1.5, 5.0, 2.0)

# 主程序逻辑
if st.button('🚀 深度扫描翻倍潜力黑马'):
    with st.spinner('正在分析全市场 5000+ 股票的市值、动量与资金流...'):
        try:
            # 1. 获取实时行情与基本面
            df = ak.stock_zh_a_spot_em()
            
            # 2. 核心数值转换
            df['涨跌幅'] = pd.to_numeric(df['涨跌幅'], errors='coerce')
            df['成交额'] = pd.to_numeric(df['成交额'], errors='coerce')
            df['换手率'] = pd.to_numeric(df['换手率'], errors='coerce')
            df['流通市值'] = pd.to_numeric(df['流通市值'], errors='coerce') / 100000000 # 转为亿元
            df['量比'] = pd.to_numeric(df['量比'], errors='coerce')

            # 3. 翻倍黑马复合策略
            # 策略逻辑：
            # - 流通市值 < 80亿 (拉升阻力小)
            # - 涨幅 > 4% 且 < 9.5% (正在起爆)
            # - 量比 > 2 (成交量异常放大)
            # - 换手率 > 5% (主力高度活跃)
            condition = (
                (df['流通市值'] <= max_market_cap) & 
                (df['涨跌幅'] >= 4) & 
                (df['涨跌幅'] < 9.6) &
                (df['量比'] >= min_vol_ratio) &
                (df['换手率'] >= 5)
            )
            
            results = df[condition].copy()
            
            if not results.empty:
                # 排序：按量比（活跃度）和市值（拉升潜力）综合评估
                results = results.sort_values(by=['量比', '流通市值'], ascending=[False, True])
                
                st.success(f"🎯 筛选出 {len(results)} 只具备黑马潜质的个股")
                
                # 增加跳转功能
                results['跳转'] = results['代码'].apply(lambda x: f'<a href="{get_em_url(x)}" target="_blank">🔗看图</a>')
                
                display_cols = ['代码', '名称', '涨跌幅', '换手率', '流通市值', '量比', '跳转']
                st.write(results[display_cols].to_html(escape=False, index=False), unsafe_allow_html=True)
                
                # 推送微信
                if enable_push and wechat_webhook:
                    top_3 = results.head(3)
                    msg = "发现潜在翻倍黑马：\n" + "\n".join([f"- {r['名称']} (市值{int(r['流通市值'])}亿, 量比{r['量比']})" for _, r in top_3.iterrows()])
                    send_wechat_msg(wechat_webhook, msg)
            else:
                st.warning("当前筛选条件过于严苛，暂无黑马股。")
        except Exception as e:
            st.error(f"分析失败: {e}")
