import streamlit as st
import pandas as pd
import plotly.express as px
import yfinance as yf
from fredapi import Fred
import feedparser
import google.generativeai as genai
from urllib.parse import quote  # 解決 URL 空白字元轉碼問題

# ==========================================
# 1. 頁面配置與側邊欄金鑰設定
# ==========================================
st.set_page_config(page_title="個股新聞輿論與 AI 走勢預測儀表板", layout="wide")
st.title("📈 個股即時新聞舆論、基本面與 AI 未來走勢預測儀表板")

st.sidebar.header("⚙️ 設定與金鑰")

# 1.1 檢查 FRED API Key
if "FRED_API_KEY" in st.secrets:
    fred_key = st.secrets["FRED_API_KEY"]
    st.sidebar.success("已自動讀取 FRED API Key！")
else:
    fred_key = st.sidebar.text_input("請輸入 FRED API Key:", type="password")

# 1.2 檢查 Gemini API Key (個股與情緒分析用)
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

# ==========================================
# 2. 數據抓取函式 (FRED, yfinance, Google News RSS)
# ==========================================
@st.cache_data(ttl=3600)
def get_fred_data(api_key):
    fred = Fred(api_key=api_key)
    data = {
        "CPI 物價指數": fred.get_series("CPIAUCSL"),
        "10年期美債殖利率": fred.get_series("DGS10"),
        "美國失業率": fred.get_series("UNRATE"),
        "聯邦基金利率": fred.get_series("FEDFUNDS")
    }
    df = pd.DataFrame(data).ffill().tail(365)
    return df

@st.cache_data(ttl=600)
def get_market_data():
    tickers = {
        "S&P 500": "^GSPC",
        "台灣加權指數": "^TWII",
        "布蘭特原油": "BZ=F",
        "美元/台幣匯率": "TWD=X"
    }
    df = yf.download(list(tickers.values()), period="1y")["Close"]
    df.rename(columns={v: k for k, v in tickers.items()}, inplace=True)
    return df

@st.cache_data(ttl=1800)
def fetch_google_news(keyword):
    # 利用 Google News RSS 搜尋任意使用者輸入的個股或主題，確保能廣泛抓取最新相關新聞
    safe_keyword = quote(keyword)
    url = f"https://news.google.com/rss/search?q={safe_keyword}&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
    feed = feedparser.parse(url)
    return [{"title": entry.title, "link": entry.link} for entry in feed.entries[:10]]

# ==========================================
# 3. 頁面渲染邏輯
# ==========================================
if fred_key:
    try:
        macro_df = get_fred_data(fred_key)
        market_df = get_market_data()

        # 第一區塊：核心總經 KPI 卡片
        st.subheader("📊 關鍵總體經濟指標 (FRED)")
        col1, col2, col3, col4 = st.columns(4)
        
        latest_cpi = macro_df["CPI 物價指數"].dropna().iloc[-1]
        col1.metric("CPI 物價指數", f"{latest_cpi:.1f}")
        
        latest_rate = macro_df["10年期美債殖利率"].dropna().iloc[-1]
        rate_prev = macro_df["10年期美債殖利率"].dropna().iloc[-2]
        col2.metric("10年美債殖利率", f"{latest_rate:.2f}%", f"{latest_rate - rate_prev:+.2f}%")
        
        latest_unemp = macro_df["美國失業率"].dropna().iloc[-1]
        col3.metric("美國失業率", f"{latest_unemp:.1f}%")
        
        latest_fed = macro_df["聯邦基金利率"].dropna().iloc[-1]
        col4.metric("聯邦基金利率", f"{latest_fed:.2f}%")

        st.write("---")

        # 第二區塊：分頁儀表板
        tab1, tab2, tab3 = st.tabs([
            "📈 金融市場走勢 (yfinance)", 
            "🏛️ 總體經濟趨勢 (FRED)", 
            "🎯 個股新聞輿論與 AI 走勢預測"
        ])
        
        # 頁籤 1: 金融市場
        with tab1:
            market_choice = st.selectbox("選擇金融市場標的：", market_df.columns)
            fig1 = px.line(market_df, y=market_choice, title=f"{market_choice} 近一年走勢")
            st.plotly_chart(fig1, use_container_width=True)
            
        # 頁籤 2: 總體經濟
        with tab2:
            macro_choice = st.selectbox("選擇總體經濟指標：", macro_df.columns)
            fig2 = px.line(macro_df, y=macro_choice, title=f"{macro_choice} 近一年走勢")
            st.plotly_chart(fig2, use_container_width=True)

        # 頁籤 3: 個股新聞輿論與 AI 走勢預測
        with tab3:
            st.subheader("🎯 個股即時新聞與 AI 未來漲跌方向預測分析")
            
            # 使用者可以自由輸入想分析的股票名稱或代號
            stock_keyword = st.text_input("🔍 輸入您關心的個股或關鍵字 (例如: 台積電、2330、Apple、NVDA):", value="台積電")
            
            news_items = fetch_google_news(stock_keyword)

            col_news, col_ai = st.columns([1, 1])

            with col_news:
                st.markdown(f"### 📌 「{stock_keyword}」最新即時新聞 (Google 搜尋來源)")
                if news_items:
                    for i, item in enumerate(news_items, 1):
                        st.markdown(f"**{i}.** [{item['title']}]({item['link']})")
                else:
                    st.warning("查無相關新聞標題，請嘗試更換個股名稱或關鍵字。")

            with col_ai:
                st.markdown(f"### 🤖 Gemini AI 個股綜合評析與走勢預測")
                if gemini_key:
                    if st.button(f"🚀 開始分析 {stock_keyword} 未來走勢", type="primary"):
                        if news_items:
                            with st.spinner(f"Gemini 正在分析 {stock_keyword} 的新聞輿論與市場前景中..."):
                                try:
                                    news_text = "\n".join([f"- {item['title']}" for item in news_items])
                                    prompt = f"""
                                    你是一位專業的股票分析師與總體經濟學家。使用者目前正在關注個股/標的：「{stock_keyword}」。
                                    以下是從網路上即時抓取到的最新相關新聞標題：
                                    {news_text}

                                    請依據上述新聞內容與你的專業知識，以繁體中文輸出結構化報告，包含以下項目：
                                    1. **綜合市場情緒分數**：(0 到 100 分，分數越高代表越偏多/樂觀)
                                    2. **短期走勢方向預判**：(看漲 / 看跌 / 盤整中立，並附帶核心理由)
                                    3. **關鍵利多與利空因素**：(條列式整理新聞中透露出的正面與負面訊號)
                                    4. **投資風險與觀察重點**：(提醒投資人後續該追蹤哪些指標或事件)
                                    """
                                    
                                    # 使用 gemini-2.5-flash 或 gemini-3.8-flash (視你的 API 權限而定，此處採用穩定模型)
                                    model = genai.GenerativeModel("gemini-2.5-flash")
                                    response = model.generate_content(prompt)
                                    st.markdown(response.text)
                                except Exception as e:
                                    st.error(f"AI 分析時發生錯誤: {e}")
                        else:
                            st.warning("尚無新聞數據可供分析。")
                else:
                    st.warning("👈 請在側邊欄輸入 Gemini API Key（或設定在 Secrets 中）以啟用 AI 分析功能。")

    except Exception as e:
        st.error(f"數據讀取失敗，請確認 FRED API Key 是否正確。錯誤訊息: {e}")
else:
    st.info("👈 請在左側輸入您的 FRED API Key 以開啟儀表板。")
