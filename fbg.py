import yfinance as yf
import pandas as pd

def screen_potential_doublers(ticker_list):
    selected_stocks = []
    
    for ticker in ticker_list:
        try:
            # 获取最近6个月的历史数据
            df = yf.download(ticker, period="6mo", interval="1d")
            if len(df) < 60: continue
            
            # 计算指标
            df['MA20'] = df['Close'].rolling(window=20).mean()
            df['MA50'] = df['Close'].rolling(window=50).mean()
            df['V_MA20'] = df['Volume'].rolling(window=20).mean()
            
            latest = df.iloc[-1]
            prev = df.iloc[-2]
            
            # 筛选条件：
            # 1. 刚突破：股价站上50日线，且50日线向上
            c1 = latest['Close'] > latest['MA50'] and latest['MA50'] > prev['MA50']
            
            # 2. 放量：今日成交量是20日平均成交量的2倍以上
            c2 = latest['Volume'] > (latest['V_MA20'] * 2)
            
            # 3. 价格波动：今日涨幅在3%-7%之间（避免追高）
            pct_change = (latest['Close'] - prev['Close']) / prev['Close']
            c3 = 0.03 < pct_change < 0.07
            
            if c1 and c2 and c3:
                selected_stocks.append({
                    'Ticker': ticker,
                    'Price': latest['Close'],
                    'Volume_Incr': latest['Volume'] / latest['V_MA20']
                })
        except Exception as e:
            print(f"Error processing {ticker}: {e}")
            
    return pd.DataFrame(selected_stocks)

# 示例调用
# tickers = ["AAPL", "TSLA", "NVDA", ...] # 替换为你关注的股票池
# result = screen_potential_doublers(tickers)
