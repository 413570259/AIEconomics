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
user_input = st.sidebar.text_input("輸入公司名稱或代號 (例: 全景軟體, 8272, 台積電, 2330, AAPL):", value="全景軟體").strip()

def resolve_ticker(query):
    tw_mapping = {
        "全景軟體": "8272.TWO", "8272": "8272.TWO",
        "台積電": "2330.TW", "聯發科": "2454.TW", "鴻海": "2317.TW", 
        "長榮": "2603.TW", "聯電": "2303.TW", "大立光": "3008.TW",
        "台達電": "2308.TW", "國泰金": "2882.TW", "富邦金": "2881.TW",
        "中華電": "2412.TW", "緯創": "3231.TW", "廣達": "2382.TW"
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
# 2. 數據抓取與智慧統整函式
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

# 利用 Gemini 將任意公司的介紹或財報資訊自動統整為「產業概況、產品組合、營運展望」
@st.cache_data(ttl=86400)
def generate_structured_summary(company_name, raw_summary):
    try:
        model = genai.GenerativeModel("gemini-2.0-flash")
        prompt = f"""
        你是一位專業的證券與產業分析師。請針對公司「{company_name}」，根據以下參考資訊，以繁體中文撰寫一份精簡、結構化的公司簡介。
        必須嚴格包含以下三個段落（使用 Markdown 條列或小標題）：
        1. **產業概況**：說明公司所處產業地位、核心技術與營運據點。
        2. **產品組合**：說明其主要產品線與服務應用。
        3. **營運展望**：說明未來發展策略、市場拓展或ESG/永續方向。

        參考資料：
        {raw_summary}
        """
        response = model.generate_content(prompt)
        if response and response.text:
            return response.text.strip()
    except Exception:
        pass
    
    return f"{company_name} 是一家具備市場競爭力的優質企業，專注於相關核心技術研發與市場服務，並持續推動產品創新與業務拓展。"

# 中文化對照表
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

industry_zh_map = {
    "Semiconductors": "半導體業",
    "Software - Infrastructure": "軟體基礎設施業",
    "Software - Application": "應用軟體業",
    "Security & Protection": "資訊安全與防護業",
    "Consumer Electronics": "消費性電子產品業",
    "Internet Content & Information": "網路內容與資訊服務業"
}

name_zh_map = {
    "8272.TWO": "全景軟體股份有限公司 (8272)",
    "2330.TW": "台灣積體電路製造股份有限公司 (台積電)",
    "2317.TW": "鴻海精密工業股份有限公司 (鴻海)",
    "2454.TW": "聯發科技股份有限公司 (聯發科)",
    "AAPL": "蘋果公司 (Apple Inc.)",
    "NVDA": "輝達公司 (NVIDIA Corporation)"
}

# 全景軟體（8272）專屬精準結構化內容（對應你提供的報告內容）
pan_view_custom_summary = """
**產業概況：**
全景軟體成立於1998年，總部位於新竹科學園區，隸屬於緯創集團，為國內專業資訊安全軟體領導廠商。專注於「網路安全」與「人事物的識別認證」領域，深耕 PKI 與密碼學技術，所有解決方案均為自主研發。已取得 ISO 27001、FIDO、OATH 及資安院 ZTA 三階段驗證等專業認證，並於2024年10月23日轉上櫃掛牌（股票代號8272）。

**產品組合：**
* **安全認證與零信任架構（ZTA）：** 提供 CGTrust、IDExpert、MOTP、CGFIDO、MICS 與 ServiSign，完備身分鑑別與信任推斷需求。
* **科技金融資安與 PKI：** 提供金融/政府憑證、CA/RA 管理系統、SS簽章加密、CodeSign 與 HSM 硬體加密器（市佔率高）。
* **數位轉型應用與 AI 辨識：** 結合 AI-OCR 與影像處理，提供 FastSIGN 快速簽、手寫簽名、智慧證件辨識與 DIMS 文件管理系統。
* **IoT 物聯網安全：** 提供 KMS、CLM、Matter 裝置安全整合方案及智慧電網資安模組。

**營運展望：**
* 聚焦地端與 SaaS 雙軌模式（如 IDExpert Cloud），降低客戶建置成本並累積經常性收入。
* 取得「後量子多重簽章」發明專利，深化軟體供應鏈安全與 PQC 領域。
* 與日本 Cybertrust Japan 合作參展 CEATEC，積極拓展國際物聯網憑證與自動部署市場。
* 以電子簽署推動無紙化減碳落實 ESG，並持續深化企業與政府數位信任網。
"""

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
            
            if twii_latest > 0:
                twii_str = f"{twii_latest:,.2f}"
                twii_delta = f"{twii_change:+.2f} ({twii_pct:+.2f}%)"
            else:
                twii_str = "無資料"
                twii_delta = "無資料"
            col_idx.metric("台股加權指數", twii_str, twii_delta)

            col1.metric("收盤價", f"{latest_close:.2f}", f"{price_change:+.2f} ({pct_change:+.2f}%)")
            col2.metric("本益比", f"{pe_ratio:.2f}" if pe_ratio is not None else "無資料")
            col3.metric("52週最高", f"{high_52w:.2f}" if high_52w is not None else "無資料")
            col4.metric("52週最低", f"{low_52w:.2f}" if low_52w is not None else "無資料")
            col5.metric("市值", f"{market_cap / 1e8:,.2f} 億" if market_cap else "無資料")

            st.write("---")

            # 第二區塊：三大功能分頁
            tab1, tab2, tab3 = st.tabs([
                "📉 個股技術分析 (K線與均線)", 
                "📋 公司基本面與精簡統整摘要", 
                "🎯 即時新聞與 AI 走勢預測"
            ])
            
            # 頁籤 1: 技術分析
            with tab1:
                st.subheader(f"{company_name} ({stock_ticker}) 近一年技術走勢與均線")
                
                df['MA5'] = df['Close'].rolling(window=5).mean()
                df['MA20'] = df['Close'].rolling(window=20).mean()
                df['MA60'] = df['Close'].rolling(window=60).mean()
                df['MA120'] = df['Close'].rolling(window=120).mean()
                df['MA240'] = df['Close'].rolling(window=240).mean()

                fig = go.Figure()
                fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name="K線"))
                fig.add_trace(go.Scatter(x=df.index, y=df['MA5'], line=dict(color='#ff7f0e', width=1), name="週線 (MA5)"))
                fig.add_trace(go.Scatter(x=df.index, y=df['MA20'], line=dict(color='#2ca02c', width=1.2), name="月線 (MA20)"))
                fig.add_trace(go.Scatter(x=df.index, y=df['MA60'], line=dict(color='#d62728', width=1.5), name="季線 (MA60)"))
                fig.add_trace(go.Scatter(x=df.index, y=df['MA120'], line=dict(color='#9467bd', width=1.5), name="半年線 (MA120)"))
                fig.add_trace(go.Scatter(x=df.index, y=df['MA240'], line=dict(color='#8c564b', width=2), name="年線 (MA240)"))
                
                fig.update_layout(title=f"{stock_ticker} 股價走勢與多週期均線圖", yaxis_title="價格 (Price)", xaxis_title="日期 (Date)", template="plotly_white", height=580)
                st.plotly_chart(fig, use_container_width=True)
                
            # 頁籤 2: 基本面與結構化統整摘要
            with tab2:
                st.subheader(f"🏢 {company_name} 財務與基本面摘要")
                
                raw_sector = info.get('sector', None)
                sector = sector_zh_map.get(raw_sector, raw_sector) if raw_sector else "無資料"
                
                raw_industry = info.get('industry', None)
                industry = industry_zh_map.get(raw_industry, raw_industry) if raw_industry else "無資料"

                country = "台灣" if info.get('country') == "Taiwan" else info.get('country', "無資料")
                employees = info.get('fullTimeEmployees', None)
                eps = info.get('trailingEps', None)
                dividend_yield = info.get('dividendYield', None)
                target_mean = info.get('targetMeanPrice', None)

                col_info1, col_info2 = st.columns(2)
                with col_info1:
                    st.write(f"**產業類別:** {sector}")
                    st.write(f"**次產業:** {industry}")
                    st.write(f"**國家/地區:** {country}")
                    st.write(f"**員工人數:** {f'{employees:,} 人' if employees else '無資料'}")
                
                with col_info2:
                    st.write(f"**每股盈餘 (EPS):** {f'{eps:.2f}元' if eps is not None else '無資料'}")
                    st.write(f"**股利殖利率:** {f'{dividend_yield * 100:.2f}%' if dividend_yield else '無資料'}")
                    st.write(f"**分析師目標均價:** {f'{target_mean:.2f}' if target_mean is not None else '無資料'}")

                st.write("---")
                st.markdown("### 📝 公司業務概況與營運展望統整")
                
                # 若查詢全景軟體（8272），直接呈現專屬精準內容；其他公司則由 AI 自動統整
                if "8272" in stock_ticker or "全景軟體" in user_input:
                    st.info(pan_view_custom_summary)
                else:
                    raw_summary = info.get('longBusinessSummary', None)
                    if raw_summary:
                        with st.spinner("Gemini 正在統整該公司的產業概況、產品與展望..."):
                            structured_text = generate_structured_summary(company_name, raw_summary)
                        st.info(structured_text)
                    else:
                        st.warning("目前無詳細業務簡介資料（無資料）。")

            # 頁籤 3: 新聞與 AI 預測
            with tab3:
                st.subheader(f"🎯 「{company_name}」即時新聞輿論與 AI 走勢評析")
                
                search_keyword = st.text_input("🔍 調整新聞搜尋關鍵字:", value="全景軟體" if "8272" in stock_ticker else company_name)
                news_items = fetch_google_news(search_keyword)

                col_news, col_ai = st.columns([1, 1])

                with col_news:
                    st.markdown(f"### 📌 最新相關新聞 (Google News)")
                    if news_items:
                        for i, item in enumerate(news_items, 1):
                            st.markdown(f"**{i}.** [{item['title']}]({item['link']})")
                    else:
                        st.warning("查無相關新聞標題（無資料）。")

                with col_ai:
                    st.markdown(f"### 🤖 Gemini AI 智慧走勢預測與多空解析")
                    if gemini_key:
                        if st.button(f"🚀 開始分析未來走勢", type="primary"):
                            if news_items:
                                with st.spinner(f"Gemini 正在剖析最新新聞與市場情緒中..."):
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
                                        
                                        model = genai.GenerativeModel("gemini-2.0-flash")
                                        response = model.generate_content(prompt)
                                        st.markdown(response.text)
                                    except Exception as e:
                                        st.error(f"AI 分析時發生錯誤: {e}")
                            else:
                                st.warning("尚無新聞數據可供分析。")
                    else:
                        st.warning("👈 請在側邊欄輸入 Gemini API Key 以啟用 AI 預測功能。")

    except Exception as e:
        st.error(f"無法讀取該股票資料，請檢查代號或名稱是否正確。錯誤訊息: {e}")
else:
    st.info("👈 請在左側輸入欲查詢的股票代號或公司名稱。")
