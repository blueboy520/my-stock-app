import streamlit as st
import akshare as ak
import pandas as pd
import requests
import json
import time

# --- 1. 页面配置 ---
st.set_page_config(page_title="手机实战版(新浪源)", page_icon="📲", layout="wide")

st.title("📲 A股首板挖掘 (新浪抗封锁版)")
st.caption("当前数据源：新浪财经 | 状态：云端可用")

# --- 2. 侧边栏：参数 (去掉了量比) ---
with st.sidebar:
    st.header("🎛️ 筛选参数")
    st.info("注：为绕过云端封锁，已切换至新浪源（暂不支持量比筛选）。")
    
    min_pct = st.slider('最小涨幅 (%)', 0.0, 9.0, 3.5)
    max_pct = st.slider('最大涨幅 (%)', 5.0, 9.9, 8.5)
    # vol_ratio 已移除，因为新浪不提供
    min_turnover = st.slider('换手率 (%)', 1.0, 20.0, (5.0, 12.0))
    mkt_cap_limit = st.slider('最大流通市值 (亿)', 20, 500, 100)
    
    st.divider()
    enable_push = st.checkbox("开启微信推送")
    wechat_webhook = st.text_input("Webhook 地址", type="password")

# --- 3. 核心工具 ---
def get_em_url(code):
    # 虽然数据用新浪，但看图还是跳转东方财富最方便
    market = "1" if str(code).startswith(('60', '68')) else "2"
    return f"https://quote.eastmoney.com/basic/full.html?stockcode={code}.{market}"

def send_wechat(url, content):
    if not url: return
    try:
        headers = {"Content-Type": "application/json"}
        data = {"msgtype": "markdown", "markdown": {"content": f"## 🚀 手机预警\n{content}"}}
        requests.post(url, headers=headers, data=json.dumps(data), timeout=2)
    except: pass

# --- 4. 主逻辑 ---
if st.button('🚀 启动云端扫描'):
    status = st.status("正在连接新浪财经...", expanded=True)
    
    try:
        # === 关键改动：使用新浪接口 (stock_zh_a_spot) ===
        status.write("📡 拉取新浪实时行情 (抗封锁)...")
        
        # 增加一次重试
        for i in range(2):
            try:
                df = ak.stock_zh_a_spot()
                break
            except:
                time.sleep(1)
        else:
            st.error("新浪接口响应超时，请刷新网页重试。")
            st.stop()
            
        # === 新浪数据清洗 ===
        # 新浪返回的列名全是英文，需要翻译
        # code=代码, name=名称, changepercent=涨跌幅, trade=最新价, volume=成交量, amount=成交额, turnoverratio=换手率, nmc=流通市值
        
        # 1. 重命名
        df = df.rename(columns={
            'code': '代码',
            'name': '名称',
            'changepercent': '涨跌幅',
            'trade': '最新价',
            'turnoverratio': '换手率',
            'amount': '成交额',
            'nmc': '流通市值',
            'open': '今开'
        })
        
        # 2. 转换数值 (新浪的单位很特殊，要注意！)
        numeric_cols = ['涨跌幅', '最新价', '换手率', '成交额', '流通市值', '今开']
        for c in numeric_cols:
            df[c] = pd.to_numeric(df[c], errors='coerce')
        
        df['代码'] = df['代码'].astype(str)
        df['名称'] = df['名称'].astype(str)
        
        # 3. 初步过滤
        # 新浪的流通市值单位是“万”，所以 100亿 = 1000000万
        # 我们这里简单处理：先剔除垃圾股
        mask_basic = (
            (~df['名称'].str.contains('ST|退')) & 
            (~df['代码'].str.startswith(('8', '4'))) &
            (df['成交额'] > 3000 * 10000) # 3000万
        )
        pool = df[mask_basic].copy()
        
        status.write(f"🔍 新浪源返回 {len(pool)} 只活跃股，正在筛选...")
        
        # === 核心策略 (无量比版) ===
        mask_pct = (pool['涨跌幅'] >= min_pct) & (pool['涨跌幅'] <= max_pct)
        mask_candle = pool['最新价'] > pool['今开'] # 真阳线
        mask_turn = (pool['换手率'] >= min_turnover[0]) & (pool['换手率'] <= min_turnover[1])
        # 流通市值单位换算：新浪是万元，所以 / 10000 = 亿元
        mask_cap = ((pool['流通市值'] / 10000) <= mkt_cap_limit)
        
        candidates = pool[mask_pct & mask_candle & mask_turn & mask_cap].copy()
        
        # === 结果展示 ===
        status.update(label="扫描完成！", state="complete", expanded=False)
        
        if not candidates.empty:
            # 按换手率排序
            res = candidates.sort_values(by='换手率', ascending=False).head(20)
            
            st.success(f"🎯 筛选出 {len(res)} 只目标 (新浪源)")
            
            # 计算显示用的市值 (亿)
            res['市值(亿)'] = (res['流通市值'] / 10000).round(1)
            # 计算显示用的成交额 (亿)
            res['成交额(亿)'] = (res['成交额'] / 100000000).round(2)
            
            # 生成跳转链接
            res['链接'] = res['代码'].apply(lambda x: get_em_url(x))
            
            st.dataframe(
                res[['代码', '名称', '涨跌幅', '换手率', '市值(亿)', '成交额(亿)', '链接']],
                column_config={
                    "链接": st.column_config.LinkColumn("K线", display_text="点击查看")
                },
                hide_index=True,
                use_container_width=True
            )
            
            if enable_push and wechat_webhook:
                msg = "\n".join([f"- {r['名称']}: 涨{r['涨跌幅']}% 换手{r['换手率']}%" for _, r in res.head(5).iterrows()])
                send_wechat(wechat_webhook, msg)
        else:
            st.warning("⚠️ 暂无符合条件的个股 (可能因去掉量比筛选导致结果差异，或当前行情太弱)。")
            
    except Exception as e:
        st.error(f"运行出错: {str(e)}")
