import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import yfinance as yf
import feedparser
import google.generativeai as genai
from urllib.parse import quote

# ==========================================
# 1. 頁面配置與側邊欄設定
# ==========================================
st.set_page_config(page_title="個股深度分析與 AI 預測儀表板", layout="wide")
st.title("📈 台美股即時行情、技術均線與 AI 智慧輿論解讀儀表板")

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

# 1.2 智慧股票搜尋輸入框
st.sidebar.write("---")
st.sidebar.header("🔍 標的選擇")
user_input = st.sidebar.text_input("輸入公司名稱或代號 (例: 台積電, 2330, AAPL, NVDA):", value="台積電").strip()

def resolve_ticker(query):
    tw_mapping = {
        "台積電": "2330.TW", "聯發科": "2454.TW", "鴻海": "2317.TW", 
        "長榮": "2603.TW", "聯電": "2303.TW", "大立光": "3008.TW",
        "台達電": "2308.TW", "國泰金": "2882.TW", "富邦金": "2881.TW",
        "中華電": "2412.TW", "緯創": "3231.TW", "廣達": "2382.TW",
        "長榮航": "2618.TW", "中鋼": "2002.TW", "台塑": "1301.TW"
    }
    if query in tw_mapping:
        return tw_mapping[query]
    if query.isdigit() and len(query) == 4:
        return query + ".TW"
    return query.upper()

stock_ticker = resolve_ticker(user_input)

if st.sidebar.button("手動刷新數據"):
    st.cache_data.clear()

# ==========================================
# 2. 數據抓取與翻譯輔助函式
# ==========================================
@st.cache_data(ttl=600)
def get_stock_data(ticker_symbol):
    stock = yf.Ticker(ticker_symbol)
    df = stock.history(period="1y")
    info = stock.info
    return df, info

@st.cache_data(ttl=600)
def get_market_index():
    twii = yf.Ticker("^TWII")
    df = twii.history(period="5d")
    if not df.empty:
        latest = df['Close'].iloc[-1]
        prev = df['Close'].iloc[-2]
        change = latest - prev
        pct = (change / prev) * 100
        return latest, change, pct
    return 0.0, 0.0, 0.0

@st.cache_data(ttl=1800)
def fetch_google_news(keyword):
    safe_keyword = quote(keyword)
    url = f"https://news.google.com/rss/search?q={safe_keyword}&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
    feed = feedparser.parse(url)
    return [{"title": entry.title, "link": entry.link} for entry in feed.entries[:10]]

# 利用 Gemini 將英文業務簡介翻譯成流暢的繁體中文
def translate_summary_to_zh(english_summary):
    if not gemini_key or not english_summary:
        return english_summary
    try:
        model = genai.GenerativeModel("gemini-2.0-flash")
        prompt = f"請將以下的公司業務簡介翻譯成專業且流暢的繁體中文，不需要額外加上多餘的開場白：\n\n{english_summary}"
        response = model.generate_content(prompt)
        return response.text
    except:
        return english_summary

# 產業類別中文化對照
sector_zh_map = {
    "Technology": "資訊科技業",
    "Financial Services": "金融服務業",
    "Healthcare": "醫療保健業",
    "Consumer Cyclical": "非必需消費品業",
    "Consumer Defensive": "必需消費品業",
    "Communication Services": "通訊服務業",
    "Industrials": "工業",
    "Basic Materials": "基礎材料業",
    "Energy": "能源業",
    "Utilities": "公用事業",
    "Real Estate": "房地產業"
}

name_zh_map = {
    "2330.TW": "台灣積體電路製造股份有限公司 (台積電)",
    "2317.TW": "鴻海精密工業股份有限公司 (鴻海)",
    "2454.TW": "聯發科技股份有限公司 (聯發科)",
    "2303.TW": "聯華電子股份有限公司 (聯電)"
}

# ==========================================
# 3. 頁面渲染邏輯
# ==========================================
if stock_ticker:
    try:
        df, info = get_stock_data(stock_ticker)
        twii_latest, twii_change, twii_pct = get_market_index()
        
        if df.empty:
            st.error(f"找不到代號「{stock_ticker}」的資料，請確認輸入是否正確。")
        else:
            if stock_ticker in name_zh_map:
                company_name = name_zh_map[stock_ticker]
            else:
                company_name = info.get("longName", stock_ticker)

            latest_close = df["Close"].iloc[-1]
            prev_close = df["Close"].iloc[-2]
            price_change = latest_close - prev_close
            pct_change = (price_change / prev_close) * 100
            
            market_cap = info.get("marketCap", None)
            pe_ratio = info.get("trailingPE", None)
            high_52w = info.get("fiftyTwoWeekHigh", None)
            low_52w = info.get("fiftyTwoWeekLow", None)

            # 第一區塊：頂部大盤與個股核心 KPI 卡片
            st.subheader("📊 市場大盤與個股即時指標")
            col_idx, col1, col2, col3, col4, col5 = st.columns(6)
            
            col_idx.metric("台灣加權指數", f"{twii_latest:,.2f}" if twii_latest else "無資料", f"{twii_change:+.2f} ({twii_pct:+.2f}%)" if twii_latest else "無資料")
            col1.metric("收盤價", f"{latest_close:.2f}", f"{price_change:+.2f} ({pct_change:+.2f}%)")
            col2.metric("本益比", f"{pe_ratio:.2f}" if pe_ratio is not None else "
