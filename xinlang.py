import streamlit as st
import akshare as ak
import pandas as pd
import requests
import json
import time

# --- 1. 页面配置 ---
st.set_page_config(page_title="手机实战修复版", page_icon="📲", layout="wide")

st.title("📲 A股首板挖掘 (新浪修复版)")
st.caption("数据源：新浪财经 | 状态：自动适配列名")

# --- 2. 侧边栏：参数 ---
with st.sidebar:
    st.header("🎛️ 筛选参数")
    
    min_pct = st.slider('最小涨幅 (%)', 0.0, 9.0, 3.5)
    max_pct = st.slider('最大涨幅 (%)', 5.0, 9.9, 8.5)
    
    # 增加一个开关：如果换手率数据获取失败，允许关闭该条件
    filter_turnover = st.checkbox("启用换手率筛选", value=True)
    if filter_turnover:
        min_turnover = st.slider('换手率 (%)', 1.0, 20.0, (3.0, 12.0))
    
    mkt_cap_limit = st.slider('最大流通市值 (亿)', 20, 500, 100)
    
    st.divider()
    enable_push = st.checkbox("开启微信推送")
    wechat_webhook = st.text_input("Webhook 地址", type="password")

# --- 3. 核心工具 ---
def get_em_url(code):
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
        # === Step 1: 获取数据 ===
        status.write("📡 拉取新浪实时行情...")
        df = None
        # 重试机制
        for i in range(3):
            try:
                df = ak.stock_zh_a_spot()
                if df is not None and not df.empty:
                    break
            except:
                time.sleep(1)
        
        if df is None or df.empty:
            st.error("无法获取数据，请稍后重试。")
            st.stop()

        # === Step 2: 智能列名映射（解决 KeyError 的核心）===
        # 先把所有列名转成小写，防止 TurnoverRatio 和 turnoverratio 的区别
        df.columns = df.columns.str.lower()
        
        # 调试：如果有问题，页面会显示这一行，告诉我列名是啥
        # st.write("调试信息 - 原始列名:", df.columns.tolist())
        
        # 建立“中英互译字典”
        rename_map = {
            'code': '代码',
            'symbol': '代码', 
            'name': '名称',
            'changepercent': '涨跌幅',
            'trade': '最新价',
            'volume': '成交量',
            'amount': '成交额',
            'open': '今开',
            'high': '最高',
            'low': '最低',
            'turnoverratio': '换手率', # 这就是报错的原因，新浪给的是这个
            'nmc': '流通市值',
            'mktcap': '总市值'
        }
        
        # 执行翻译
        df = df.rename(columns=rename_map)
        
        # === Step 3: 缺失列补救 ===
        # 如果翻译完还是没有“换手率”，就自动填0，防止报错
        if '换手率' not in df.columns:
            st.warning("⚠️ 数据源未返回换手率，已自动跳过该筛选。")
            df['换手率'] = 0.0
            filter_turnover = False # 强制关闭筛选
        
        if '流通市值' not in df.columns:
             # 如果没有流通市值，试着用总市值顶替
            if '总市值' in df.columns:
                df['流通市值'] = df['总市值']
            else:
                df['流通市值'] = 0.0

        # === Step 4: 数值转换 ===
        numeric_cols = ['涨跌幅', '最新价', '换手率', '成交额', '流通市值', '今开']
        for c in numeric_cols:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors='coerce')
        
        # === Step 5: 筛选逻辑 ===
        df['代码'] = df['代码'].astype(str)
        df['名称'] = df['名称'].astype(str)
        
        # 基础过滤
        mask_basic = (
            (~df['名称'].str.contains('ST|退')) & 
            (~df['代码'].str.startswith(('8', '4'))) &
            (df['成交额'] > 3000 * 10000) 
        )
        pool = df[mask_basic].copy()
        
        status.write(f"🔍 数据源返回 {len(pool)} 只活跃股，正在计算...")
        
        # 核心筛选
        mask_pct = (pool['涨跌幅'] >= min_pct) & (pool['涨跌幅'] <= max_pct)
        mask_candle = pool['最新价'] > pool['今开'] # 真阳线
        
        # 市值筛选 (新浪单位通常是万元，这里除以10000换算成亿)
        mask_cap = ((pool['流通市值'] / 10000) <= mkt_cap_limit)
        
        final_mask = mask_pct & mask_candle & mask_cap
        
        if filter_turnover:
            mask_turn = (pool['换手率'] >= min_turnover[0]) & (pool['换手率'] <= min_turnover[1])
            final_mask = final_mask & mask_turn
            
        candidates = pool[final_mask].copy()
        
        # === Step 6: 结果展示 ===
        status.update(label="扫描完成！", state="complete", expanded=False)
        
        if not candidates.empty:
            # 排序
            sort_col = '换手率' if filter_turnover else '涨跌幅'
            res = candidates.sort_values(by=sort_col, ascending=False).head(20)
            
            st.success(f"🎯 筛选出 {len(res)} 只目标")
            
            # 格式化显示
            res['市值(亿)'] = (res['流通市值'] / 10000).round(1)
            res['成交额(亿)'] = (res['成交额'] / 100000000).round(2)
            res['链接'] = res['代码'].apply(lambda x: get_em_url(x))
            
            # 动态决定显示的列
            show_cols = ['代码', '名称', '涨跌幅', '最新价', '成交额(亿)', '市值(亿)', '链接']
            if filter_turnover:
                show_cols.insert(4, '换手率')
                
            st.dataframe(
                res[show_cols],
                column_config={
                    "链接": st.column_config.LinkColumn("K线", display_text="查看")
                },
                hide_index=True,
                use_container_width=True
            )
            
            if enable_push and wechat_webhook:
                msg = "\n".join([f"- {r['名称']}: 涨{r['涨跌幅']}%" for _, r in res.head(5).iterrows()])
                send_wechat(wechat_webhook, msg)
        else:
            st.warning("⚠️ 暂无符合条件的个股。")
            
    except Exception as e:
        st.error(f"运行出错详情: {str(e)}")
        # 如果还是出错，这行代码会救命：它会把新浪到底返回了什么列名打印出来
        if 'df' in locals() and df is not None:
             st.write("❌ 调试信息-当前列名:", df.columns.tolist())
