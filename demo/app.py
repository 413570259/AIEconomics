import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import yfinance as yf
import ta  # 用於計算技術指標 (RSI, MACD, MA)
import feedparser
import google.generativeai as genai
from urllib.parse import quote

# ==========================================
# 1. 頁面配置與側邊欄設定
# ==========================================
st.set_page_config(page_title="台美個股深度分析與 AI 輿情儀表板", layout="wide")
st.title("📈 台美個股技術面、基本面與 AI 市場輿情分析儀表板")

st.sidebar.header("⚙️ 設定與金鑰")

# 檢查 Gemini API Key
gemini_key = None
if "GEMINI_API_KEY" in st.secrets:
    gemini_key = st.secrets["GEMINI_API_KEY"]
    genai.configure(api_key=gemini_key)
    st.sidebar.success("已自動讀取 Gemini API Key！")
else:
    gemini_input = st.sidebar.text_input("請輸入 Gemini API Key (AI 分析用):", type="password")
    if gemini_input:
        gemini_key = gemini_input
        genai.configure(api_key=gemini_key)

if st.sidebar.button("手動刷新數據"):
    st.cache_data.clear()

# 使用者可在側邊欄自訂想分析的股票代號（例如台積電 2330.TW、美股 NVDA、AAPL）
default_ticker = st.sidebar.text_input("輸入要分析的股票代號 (Yahoo Finance 格式):", value="2330.TW")

# ==========================================
# 2. 數據抓取與技術指標計算函式
# ==========================================
@st.cache_data(ttl=600)
def get_stock_data(ticker_symbol):
    stock = yf.Ticker(ticker_symbol)
    df = stock.history(period="1y")
    
    # 使用 ta 套件計算技術指標
    df["SMA_20"] = ta.trend.sma_indicator(df["Close"], window=20)
    df["SMA_50"] = ta.trend.sma_indicator(df["Close"], window=50)
    df["RSI"] = ta.momentum.rsi(df["Close"], window=14)
    
    # 取得個股基本資訊 (若有)
    info = stock.info
    return df, info

@st.cache_data(ttl=1800)
def fetch_google_news(keyword):
    safe_keyword = quote(keyword)
    url = f"https://news.google.com/rss/search?q={safe_keyword}&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
    feed = feedparser.parse(url)
    return [{"title": entry.title, "link": entry.link} for entry in feed.entries[:8]]

# ==========================================
# 3. 頁面渲染邏輯
# ==========================================
try:
    df, stock_info = get_stock_data(default_ticker)
    
    if df.empty:
        st.error(f"找不到代號「{default_ticker}」的資料，請確認代號是否正確（例如台股請加 .TW，如 2330.TW）。")
    else:
        # 第一區塊：核心個股即時 KPI 卡片
        st.subheader(f"📊 「{default_ticker.upper()}」即時市場表現")
        col1, col2, col3, col4 = st.columns(4)
        
        latest_close = df["Close"].iloc[-1]
        prev_close = df["Close"].iloc[-2]
        price_change = latest_close - prev_close
        price_pct = (price_change / prev_close) * 100
        
        col1.metric("最新收盤價", f"{latest_close:.2f}", f"{price_change:+.2f} ({price_pct:+.2f}%)")
        
        latest_rsi = df["RSI"].iloc[-1]
        col2.metric("RSI (14日強弱指標)", f"{latest_rsi:.1f}")
        
        # 從 yfinance info 抓取市值或本益比 (若無則顯示 N/A)
        market_cap = stock_info.get("marketCap", "N/A")
        if market_cap != "N/A":
            market_cap_str = f"{market_cap / 1e8:.1f} 億"
        else:
            market_cap_str = "N/A"
        col3.metric("總市值", market_cap_str)
        
        pe_ratio = stock_info.get("trailingPE", "N/A")
        col4.metric("本益比 (P/E)", f"{pe_ratio}")

        st.write("---")

        # 第二區塊：分頁儀表板（技術面、基本面、AI輿情）
        tab1, tab2, tab3 = st.tabs([
            "📈 股價走勢與技術指標 (MACD/RSI/MA)", 
            "🏢 個股基本資訊與財報概況", 
            "🎯 即時新聞輿論與 AI 走勢預測"
        ])
        
        # 頁籤 1: 技術分析圖表
        with tab1:
            st.subheader(f"{default_ticker} 近一年技術分析走勢圖")
            
            # 使用 Plotly 繪製多重指標圖
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=df.index, y=df["Close"], name="收盤價", line=dict(color="blue")))
            fig.add_trace(go.Scatter(x=df.index, y=df["SMA_20"], name="20日均線 (MA20)", line=dict(color="orange", dash="dash")))
            fig.add_trace(go.Scatter(x=df.index, y=df["SMA_50"], name="50日均線 (MA50)", line=dict(color="green", dash="dash")))
            
            fig.update_layout(title=f"{default_ticker} 價格與移動平均線", xaxis_title="日期", yaxis_title="價格", height=500)
            st.plotly_chart(fig, use_container_width=True)
            
        # 頁籤 2: 基本面資訊
        with tab2:
            st.subheader(f"{default_ticker} 公司基本面與市場指標")
            if stock_info:
                # 將 yfinance 的重要基本面資訊整理成表格顯示
                info_keys = {
                    "公司名稱 (Long Name)": stock_info.get("longName", "N/A"),
                    "產業別 (Sector)": stock_info.get("sector", "N/A"),
                    "國家/地區 (Country)": stock_info.get("country", "N/A"),
                    "52週最高價 (52Week High)": stock_info.get("fiftyTwoWeekHigh", "N/A"),
                    "52週最低價 (52Week Low)": stock_info.get("fiftyTwoWeekLow", "N/A"),
                    "每股盈餘 (EPS)": stock_info.get("trailingEps", "N/A"),
                    "預估殖利率 (Dividend Yield)": f"{stock_info.get('dividendYield', 0)*100:.2f}%" if stock_info.get('dividendYield') else "N/A"
                }
                info_df = pd.DataFrame(list(info_keys.items()), columns=["指標項目", "內容數據"])
                st.table(info_df)
            else:
                st.info("目前無法取得該標的之詳細基本面資訊。")

        # 頁籤 3: AI 輿情與走勢預測
        with tab3:
            st.subheader("🎯 個股即時新聞與 AI 未來走勢方向預測")
            
            search_query = st.text_input("輸入新聞搜尋關鍵字:", value=stock_info.get("longName", default_ticker))
            news_items = fetch_google_news(search_query)

            col_news, col_ai = st.columns([1, 1])

            with col_news:
                st.markdown(f"### 📌 最新相關新聞")
                if news_items:
                    for i, item in enumerate(news_items, 1):
                        st.markdown(f"**{i}.** [{item['title']}]({item['link']})")
                else:
                    st.warning("查無相關新聞標題。")

            with col_ai:
                st.markdown(f"### 🤖 Gemini AI 綜合評析與走勢預測")
                if gemini_key:
                    if st.button(f"🚀 開始分析 {default_ticker} 走勢", type="primary"):
                        if news_items:
                            with st.spinner("Gemini 正在分析市場輿論與技術面狀態中..."):
                                try:
                                    news_text = "\n".join([f"- {item['title']}" for item in news_items])
                                    prompt = f"""
                                    你是一位專業的證券分析師。使用者目前正關注個股：「{default_ticker}」（{stock_info.get('longName', '')}）。
                                    最新技術指標數據：
                                    - 最新收盤價: {latest_close:.2f}
                                    - 14日 RSI: {latest_rsi:.1f}
                                    - 本益比: {pe_ratio}
                                    
                                    以下是即時抓取到的最新相關新聞標題：
                                    {news_text}

                                    請以繁體中文輸出結構化報告：
                                    1. **綜合市場情緒分數** (0-100分)
                                    2. **短期走勢方向預判** (看漲 / 看跌 / 盤整中立，並說明核心理由)
                                    3. **基本面與訊息面多空評析**
                                    4. **投資風險與後續追蹤重點**
                                    """
                                    
                                    model = genai.GenerativeModel("gemini-3.8-flash")
                                    response = model.generate_content(prompt)
                                    st.markdown(response.text)
                                except Exception as e:
                                    st.error(f"AI 分析時發生錯誤: {e}")
                        else:
                            st.warning("尚無新聞數據可供分析。")
                else:
                    st.warning("👈 請在側邊欄輸入 Gemini API Key 以啟用 AI 分析。")

except Exception as e:
    st.error(f"資料讀取或處理發生錯誤，請檢查股票代號是否正確。錯誤訊息: {e}")
    except Exception as e:
        st.error(f"數據讀取失敗，請確認 FRED API Key 是否正確。錯誤訊息: {e}")
else:
    st.info("👈 請在左側輸入您的 FRED API Key 以開啟儀表板。")
