import streamlit as st
import pandas as pd
import plotly.express as px
import yfinance as yf
from fredapi import Fred
from google import genai  # 引入 Google GenAI SDK

# 頁面基本配置
st.set_page_config(page_title="總體經濟與金融即時儀表板", layout="wide")
st.title("🌐 全球總體經濟與金融指標即時儀表板")

# 側邊欄：輸入 API Key 與刷新控制
st.sidebar.header("⚙️ 設定與金鑰")

# 1. FRED API Key 設定
if "FRED_API_KEY" in st.secrets:
    fred_key = st.secrets["FRED_API_KEY"]
    st.sidebar.success("已自動讀取 FRED Secrets 金鑰！")
else:
    fred_key = st.sidebar.text_input("請輸入你的 FRED API Key:", type="password")

# 2. Gemini API Key 設定（優先讀取 Secrets，若無則讓使用者在側邊欄輸入）
if "GEMINI_API_KEY" in st.secrets:
    gemini_key = st.secrets["GEMINI_API_KEY"]
    st.sidebar.success("已自動讀取 Gemini Secrets 金鑰！")
else:
    gemini_key = st.sidebar.text_input("請輸入你的 Gemini API Key:", type="password", help="用於產出總經 AI 短評")

if st.sidebar.button("手動刷新數據"):
    st.cache_data.clear()

# 1. 抓取 FRED 數據 (設快取 1 小時)
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

# 2. 抓取 Market 數據 (設快取 10 分鐘)
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

# 頁面渲染邏輯
if fred_key:
    try:
        macro_df = get_fred_data(fred_key)
        market_df = get_market_data()

        # 第一區塊：核心 KPI 卡片
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

        # 第二區塊：互動式圖表
        st.write("---")
        st.subheader("📈 市場走勢與總體指標折線圖")
        
        tab1, tab2 = st.tabs(["金融市場走勢 (yfinance)", "總體經濟趨勢 (FRED)"])
        
        with tab1:
            market_choice = st.selectbox("選擇金融市場標的：", market_df.columns)
            fig1 = px.line(market_df, y=market_choice, title=f"{market_choice} 近一年走勢")
            st.plotly_chart(fig1, use_container_width=True)
            
        with tab2:
            macro_choice = st.selectbox("選擇總體經濟指標：", macro_df.columns)
            fig2 = px.line(macro_df, y=macro_choice, title=f"{macro_choice} 近一年走勢")
            st.plotly_chart(fig2, use_container_width=True)

        # 第三區塊：AI 總體經濟摘要按鈕與功能
        st.write("---")
        st.subheader("🤖 AI 智能總經短評")
        
        if st.button("產生 AI 總體經濟摘要"):
            if not gemini_key:
                st.warning("請先在左側側邊欄位輸入您的 Gemini API Key，或設定至 Secrets 中！")
            else:
                with st.spinner("正在呼叫 Gemini 2.5 模型分析最新經濟數據中..."):
                    try:
                        # 初始化 Google GenAI Client
                        client = genai.Client(api_key=gemini_key)
                        
                        # 準備傳遞給 AI 的即時數值上下文
                        prompt = f"""
                        你是一位專業的總體經濟學家。請依據以下最新抓取到的美國總經數據，撰寫一份大約 200 字以內的精煉總體經濟短評，分析當前的通膨、就業與利率形勢對市場可能帶來的影響：
                        - 最新 CPI 物價指數: {latest_cpi:.1f}
                        - 10年期美債殖利率: {latest_rate:.2f}%
                        - 美國失業率: {latest_unemp:.1f}%
                        - 聯邦基金利率: {latest_fed:.2f}%
                        """
                        
                        # 修改為 gemini-3.8-flash
response = client.models.generate_content(
    model='gemini-3.8-flash',
    contents=prompt,
)
                    
                        
                        # 顯示結果
                        st.success("分析完成！")
                        st.info(response.text)
                        
                    except Exception as ai_err:
                        st.error(f"AI 摘要生成失敗，請確認 Gemini API Key 是否正確。錯誤訊息: {ai_err}")

    except Exception as e:
        st.error(f"數據讀取失敗，請確認 FRED API Key 是否正確。錯誤訊息: {e}")
else:
    st.info("👈 請在左側輸入您的 FRED API Key 以開啟儀表板。")
