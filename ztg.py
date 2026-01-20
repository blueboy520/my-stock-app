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

st.title("⚡ A股超短线·首板挖掘系统 (网络增强版)")
st.caption("逻辑核心：大盘情绪共振 + 底部放量启动 + 主力资金抢筹")

# --- 侧边栏：战法参数 ---
with st.sidebar:
    st.header("🎛️ 核心参数设置")
    
    st.subheader("1. 进攻参数")
    min_pct = st.slider('最小涨幅 (起爆点)', 0.0, 9.0, 3.5)
    max_pct = st.slider('最大涨幅 (安全区)', 5.0, 9.9, 7.5)
    vol_ratio = st.slider('最小量比 (爆量)', 1.0, 5.0, 1.8)
    
    st.subheader("2. 防守参数")
    min_turnover = st.slider('换手率 (%)', 1.0, 20.0, (5.0, 12.0))
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
    """获取大盘情绪，带重试机制"""
    for i in range(3): # 最多尝试3次
        try:
            df_index = ak.stock_zh_index_spot()
            sh_index = df_index[df_index['代码'] == 'sh000001'].iloc[0]
            return float(sh_index['涨跌幅']), float(sh_index['成交额'])
        except:
            time.sleep(1) # 休息1秒再试
    return 0.0, 0.0

def get_realtime_data_safe():
    """获取全市场数据，带重试防御机制"""
    max_retries = 3
    for i in range(max_retries):
        try:
            df = ak.stock_zh_a_spot_em()
            if df is not None and not df.empty:
                return df
        except Exception as e:
            if i == max_retries - 1:
                raise e # 最后一次还是失败，再报错
            time.sleep(2) # 遇到报错，休息2秒再重试
    return None

# --- 主逻辑 ---
sh_pct, sh_vol = get_market_sentiment()
c1, c2, c3 = st.columns(3)
with c1: st.metric("上证指数", f"{sh_pct}%", delta=f"{sh_pct}%")
with c2: st.metric("市场环境", "🔥 情绪火热" if sh_pct > 0.5 else ("❄️ 情绪冰点" if sh_pct < -0.5 else "⚖️ 震荡市"))
with c3: st.metric("两市成交", f"{int(sh_vol/100000000)}亿")

st.divider()

if st.button('🚀 启动全市场雷达扫描'):
    status = st.status("正在建立加密连接...", expanded=True)
    
    try:
        # Step 1: 获取数据 (使用新的安全函数)
        status.write("📡 正在连接交易所实时数据 (已开启防断连)...")
        df = get_realtime_data_safe()
        
        if df is None:
            st.error("无法连接到数据源，请稍后重试。")
            st.stop()

        # Step 2: 数据清洗
        numeric_cols = ['涨跌幅', '最新价', '换手率', '成交额', '流通市值', '量比', '最高', '今开']
        for c in numeric_cols:
            df[c] = pd.to_numeric(df[c], errors='coerce')
        
        df['代码'] = df['代码'].astype(str)
        df['名称'] = df['名称'].astype(str)
        
        # Step 3: 基础过滤
        mask_basic = (
            (~df['名称'].str.contains('ST|退')) & 
            (~df['代码'].str.startswith(('8', '4'))) &
            (df['成交额'] > 3000 * 10000)
        )
        pool = df[mask_basic].copy()
        
        status.write(f"🔍 基础池剩余 {len(pool)} 只，正在执行量价策略...")
        
        # Step 4: 核心选股逻辑
        mask_pct = (pool['涨跌幅'] >= min_pct) & (pool['涨跌幅'] <= max_pct)
        mask_candle = pool['最新价'] > pool['今开'] # 真阳线
        mask_vol = pool['量比'] >= vol_ratio
        mask_turn = (pool['换手率'] >= min_turnover[0]) & (pool['换手率'] <= min_turnover[1])
        mask_cap = (pool['流通市值'] <= mkt_cap_limit * 100000000)
        
        candidates = pool[mask_pct & mask_candle & mask_vol & mask_turn & mask_cap].copy()
        
        # Step 5: 深度技术确认
        if not candidates.empty:
            status.write(f"🔬 初筛出 {len(candidates)} 只潜力股，正在进行 K 线确认...")
            # 限制数量，防止请求过多被封
            candidates = candidates.sort_values(by='量比', ascending=False).head(15)
            
            final_list = []
            progress = status.progress(0)
            total = len(candidates)
            
            for i, (idx, row) in enumerate(candidates.iterrows()):
                progress.progress((i+1)/total)
                try:
                    # 获取K线也增加重试
                    for k in range(3):
                        try:
                            hist = ak.stock_zh_a_hist(symbol=row['代码'], period="daily", adjust="qfq", start_date="20241201")
                            break
                        except:
                            time.sleep(1)
                    else:
                        continue # 如果3次都拿不到K线，跳过这只股

                    if len(hist) < 20: continue
                    
                    ma5 = hist['收盘'].rolling(5).mean().iloc[-1]
                    ma10 = hist['收盘'].rolling(10).mean().iloc[-1]
                    ma20 = hist['收盘'].rolling(20).mean().iloc[-1]
                    
                    if row['最新价'] > ma5 and ma5 > ma10 and ma10 > ma20:
                        final_list.append(row)
                except:
                    continue
            
            status.update(label="扫描完成！", state="complete", expanded=False)
            
            if final_list:
                res = pd.DataFrame(final_list)
                st.success(f"🎯 最终锁定 {len(res)} 只『均线多头+放量起爆』个股")
                
                res['市值(亿)'] = (res['流通市值'] / 100000000).round(1)
                res['跳转'] = res['代码'].apply(lambda x: f'<a href="{get_em_url(x)}" target="_blank">🔗看K线</a>')
                
                cols = ['代码', '名称', '涨跌幅', '最新价', '量比', '换手率', '市值(亿)', '跳转']
                st.write(res[cols].to_html(escape=False, index=False), unsafe_allow_html=True)
                
                if enable_push and wechat_webhook:
                    msg = "\n".join([f"- {r['名称']}: 涨{r['涨跌幅']}% 量比{r['量比']}" for r in final_list[:5]])
                    send_wechat(wechat_webhook, "⚡ 涨停潜力预警", msg)
            else:
                st.warning("⚠️ 技术形态确认后无符合条件的个股，建议空仓。")
        else:
            status.update(label="无符合条件个股", state="complete")
            st.warning("⚠️ 基础量价筛选无结果，请放宽条件。")

    except Exception as e:
        st.error(f"网络连接不稳定，请稍后重试。详情: {str(e)}")
