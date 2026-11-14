import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import yfinance as yf
import feedparser
import google.generativeai as genai
from urllib.parse import quote

# ==========================================
# 1. 頁面配置與側邊欄設定
# ==========================================
st.set_page_config(page_title="個股深度分析與 AI 預測儀表板", layout="wide")
st.title("📈 個股即時行情、技術分析與 AI 智慧輿論解讀儀表板")

st.sidebar.header("⚙️ 設定與金鑰")

# 1.1 檢查 Gemini API Key
gemini_key = None
if "GEMINI_API_KEY" in st.secrets:
    gemini_key = st.secrets["GEMINI_API_KEY"]
    genai.configure(api_key=gemini_key)
    st.sidebar.success("已自動讀取 Gemini API Key！")
else:
    gemini_input = st.sidebar.text_input("請輸入 Gemini API Key:", type="password")
    if gemini_input:
        gemini_key = gemini_input
        genai.configure(api_key=gemini_key)

# 1.2 輸入想分析的股票代號（台股加 .TW，美股直接打代號）
st.sidebar.write("---")
st.sidebar.header("🔍 標的選擇")
default_ticker = "2330.TW"
stock_ticker = st.sidebar.text_input("輸入股票代號 (例: 2330.TW, AAPL, NVDA):", value=default_ticker).strip().upper()

if st.sidebar.button("手動刷新數據"):
    st.cache_data.clear()

# ==========================================
# 2. 數據抓取函式 (yfinance 與 Google News RSS)
# ==========================================
@st.cache_data(ttl=600)
def get_stock_data(ticker_symbol):
    stock = yf.Ticker(ticker_symbol)
    df = stock.history(period="1y")
    info = stock.info
    return df, info

@st.cache_data(ttl=1800)
def fetch_google_news(keyword):
    safe_keyword = quote(keyword)
    url = f"https://news.google.com/rss/search?q={safe_keyword}&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
    feed = feedparser.parse(url)
    return [{"title": entry.title, "link": entry.link} for entry in feed.entries[:10]]

# ==========================================
# 3. 頁面渲染邏輯
# ==========================================
if stock_ticker:
    try:
        df, info = get_stock_data(stock_ticker)
        
        if df.empty:
            st.error(f"找不到代號「{stock_ticker}」的資料，請確認輸入是否正確（台股請加上 .TW，例如 2330.TW）。")
        else:
            # 取得公司名稱與基本數值
            company_name = info.get("longName", stock_ticker)
            latest_close = df["Close"].iloc[-1]
            prev_close = df["Close"].iloc[-2]
            price_change = latest_close - prev_close
            pct_change = (price_change / prev_close) * 100
            
            market_cap = info.get("marketCap", 0)
            pe_ratio = info.get("trailingPE", "N/A")
            high_52w = info.get("fiftyTwoWeekHigh", "N/A")
            low_52w = info.get("fiftyTwoWeekLow", "N/A")

            # 第一區塊：個股核心 KPI 卡片
            st.subheader(f"📊 {company_name} ({stock_ticker}) 即時市場指標")
            col1, col2, col3, col4, col5 = st.columns(5)
            
            col1.metric("最新收盤價", f"{latest_close:.2f}", f"{price_change:+.2f} ({pct_change:+.2f}%)")
            col2.metric("本益比 (P/E)", f"{pe_ratio}" if pe_ratio != "N/A" else "N/A")
            col3.metric("52週最高", f"{high_52w}" if high_52w != "N/A" else "N/A")
            col4.metric("52週最低", f"{low_52w}" if low_52w != "N/A" else "N/A")
            col5.metric("市值", f"{market_cap / 1e9:.2f} 億" if market_cap else "N/A")

            st.write("---")

            # 第二區塊：三大功能分頁
            tab1, tab2, tab3 = st.tabs([
                "📉 個股技術分析 (K線與均線)", 
                "📋 公司基本面與財務概況", 
                "🎯 即時新聞與 AI 走勢預測"
            ])
            
            # 頁籤 1: 技術分析 (K線 + 成交量 + 均線)
            with tab1:
                st.subheader(f"{stock_ticker} 近一年走勢與技術指標")
                
                # 計算移動平均線 MA20 與 MA60
                df['MA20'] = df['Close'].rolling(window=20).mean()
                df['MA60'] = df['Close'].rolling(window=60).mean()

                # 使用 Plotly 繪製專業金融圖表
                fig = go.Figure()
                
                # Candlestick K線圖
                fig.add_trace(go.Candlestick(
                    x=df.index,
                    open=df['Open'], high=df['High'],
                    low=df['Low'], close=df['Close'],
                    name="K線"
                ))
                
                # 均線
                fig.add_trace(go.Scatter(x=df.index, y=df['MA20'], line=dict(color='orange', width=1.5), name="MA20"))
                fig.add_trace(go.Scatter(x=df.index, y=df['MA60'], line=dict(color='blue', width=1.5), name="MA60"))
                
                fig.update_layout(
                    title=f"{stock_ticker} 股價走勢與技術均線圖",
                    yaxis_title="價格",
                    xaxis_title="日期",
                    template="plotly_white",
                    height=550
                )
                st.plotly_chart(fig, use_container_width=True)
                
            # 頁籤 2: 基本面資訊
            with tab2:
                st.subheader(f"🏢 {company_name} 基本面摘要")
                
                col_info1, col_info2 = st.columns(2)
                with col_info1:
                    st.write(f"**產業類別 (Sector):** {info.get('sector', 'N/A')}")
                    st.write(f"**次產業 (Industry):** {info.get('industry', 'N/A')}")
                    st.write(f"**國家/地區 (Country):** {info.get('country', 'N/A')}")
                    st.write(f"**員工人數:** {info.get('fullTimeEmployees', 'N/A'):,}" if isinstance(info.get('fullTimeEmployees'), int) else "**員工人數:** N/A")
                
                with col_info2:
                    st.write(f"**每股盈餘 (EPS):** {info.get('trailingEps', 'N/A')}")
                    st.write(f"**股利殖利率 (Dividend Yield):** {info.get('dividendYield', 0) * 100:.2f}%" if info.get('dividendYield') else "**股利殖利率:** N/A")
                    st.write(f"**目標價中位數 (Target Mean Price):** {info.get('targetMeanPrice', 'N/A')}")

                st.write("---")
                st.markdown("### 📝 公司業務簡介")
                st.info(info.get('longBusinessSummary', '目前無詳細業務簡介資料。'))

            # 頁籤 3: 新聞與 AI 預測
            with tab3:
                st.subheader(f"🎯 「{stock_ticker}」即時新聞輿論與 AI 走勢評析")
                
                # 自動以公司名稱或代號作為新聞搜尋關鍵字
                search_keyword = st.text_input("🔍 調整新聞搜尋關鍵字:", value=company_name if company_name else stock_ticker)
                news_items = fetch_google_news(search_keyword)

                col_news, col_ai = st.columns([1, 1])

                with col_news:
                    st.markdown(f"### 📌 最新相關新聞 (Google News)")
                    if news_items:
                        for i, item in enumerate(news_items, 1):
                            st.markdown(f"**{i}.** [{item['title']}]({item['link']})")
                    else:
                        st.warning("查無相關新聞標題。")

                with col_ai:
                    st.markdown(f"### 🤖 Gemini AI 智慧走勢預測與多空解析")
                    if gemini_key:
                        if st.button(f"🚀 開始分析 {stock_ticker} 未來走勢", type="primary"):
                            if news_items:
                                with st.spinner(f"Gemini 正在剖析 {stock_ticker} 的最新新聞與市場情緒中..."):
                                    try:
                                        news_text = "\n".join([f"- {item['title']}" for item in news_items])
                                        prompt = f"""
                                        你是一位專業的股票證券分析師。使用者目前正在研究個股：「{stock_ticker} ({company_name})」。
                                        以下是近期透過 Google 搜尋到的最新 10 條相關新聞標題：
                                        {news_text}

                                        請根據上述新聞內容與你的金融專業知識，以繁體中文輸出結構化報告，包含以下項目：
                                        1. **綜合市場情緒評分**：(0 到 100 分，分數越高代表越偏多/樂觀)
                                        2. **短期走勢方向預判**：(看漲 / 看跌 / 盤整中立，並說明核心邏輯)
                                        3. **核心利多與利空因子**：(條列式分析新聞中所釋出的正面與負面訊號)
                                        4. **後續操作風險與觀察重點**：(提醒投資人應注意的總經或產業風險)
                                        """
                                        
                                        # 使用目前最穩定的輕量模型
                                        model = genai.GenerativeModel("gemini-2.0-flash")
                                        response = model.generate_content(prompt)
                                        st.markdown(response.text)
                                    except Exception as e:
                                        st.error(f"AI 分析時發生錯誤: {e}")
                            else:
                                st.warning("尚無新聞數據可供分析。")
                    else:
                        st.warning("👈 請在左側輸入 Gemini API Key 以啟用 AI 預測功能。")

    except Exception as e:
        st.error(f"無法讀取該股票資料，請檢查代號是否正確。錯誤訊息: {e}")
else:
    st.info("👈 請在左側輸入欲查詢的股票代號。")
