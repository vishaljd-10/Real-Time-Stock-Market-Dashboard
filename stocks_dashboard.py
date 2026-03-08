import streamlit as st
import plotly.graph_objects as go
import pandas as pd 
import yfinance as yf
from datetime import datetime, timedelta
import ta 
from streamlit_autorefresh import st_autorefresh

# ==================================================
# 🔹 AUTO REFRESH (LIVE UPDATES EVERY 60 SECONDS)
# ==================================================
st_autorefresh(interval=60 * 1000, key="data_refresh")

# ==================================================
# 🔹 PAGE CONFIG
# ==================================================
sts.set_page_config(
    page_title="Real-Time Stock Dashboard",
    layout="wide"
)

st.title("📈 Professional Real-Time Stock Dashboard")

# ==================================================
# 🔹 HELPER FUNCTIONS
# ==================================================

def fetch_stock_data(ticker, period, interval):
    """Download stock data from Yahoo Finance"""
    try:
        if period == "1wk":
            end_date = datetime.now()
            start_date = end_date - timedelta(days=7)
            data = yf.download(
                ticker,
                start=start_date,
                end=end_date,
                interval=interval,
                progress=False
            )
        else:
            data = yf.download(
                ticker,
                period=period,
                interval=interval,
                progress=False
            )
        return data
    except Exception as e:
        st.error(f"Data download failed: {e}")
        return pd.DataFrame()


def process_data(data):
    """Clean and prepare dataframe — FULL FIX"""
    if data.empty:
        return data

    # ---- FIX MULTIINDEX COLUMNS (MOST IMPORTANT FIX) ----
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)

    # ---- TIMEZONE FIX ----
    if data.index.tzinfo is None:
        data.index = data.index.tz_localize("UTC")

    data.index = data.index.tz_convert("US/Eastern")

    # ---- MOVE DATETIME INTO COLUMN ----
    data.reset_index(inplace=True)

    # Rename properly
    if "Date" in data.columns:
        data.rename(columns={"Date": "Datetime"}, inplace=True)
    elif "Datetime" not in data.columns:
        data.rename(columns={data.columns[0]: "Datetime"}, inplace=True)

    # ---- CLEAN COLUMN NAMES ----
    data.columns = data.columns.str.strip()

    return data


def calculate_metrics(data):
    """Calculate key performance metrics safely"""
    if data.empty:
        return 0, 0, 0, 0, 0, 0

    last_close = float(data["Close"].iloc[-1])
    prev_close = float(data["Close"].iloc[0])

    change = last_close - prev_close
    pct_change = (change / prev_close) * 100 if prev_close != 0 else 0

    high = float(data["High"].max())
    low = float(data["Low"].min())
    volume = int(data["Volume"].sum())

    return last_close, change, pct_change, high, low, volume


def add_technical_indicators(data):
    """Add all technical indicators safely"""
    close = data["Close"].squeeze()

    # Trend Indicators
    data["SMA_20"] = ta.trend.sma_indicator(close, window=20)
    data["EMA_20"] = ta.trend.ema_indicator(close, window=20)

    # RSI
    data["RSI"] = ta.momentum.rsi(close, window=14)

    # MACD
    macd = ta.trend.MACD(close)
    data["MACD"] = macd.macd()
    data["MACD_Signal"] = macd.macd_signal()
    data["MACD_Hist"] = macd.macd_diff()

    # Bollinger Bands
    bb = ta.volatility.BollingerBands(close, window=20, window_dev=2)
    data["BB_Upper"] = bb.bollinger_hband()
    data["BB_Lower"] = bb.bollinger_lband()

    return data

# ==================================================
# 🔹 SIDEBAR INPUTS
# ==================================================
st.sidebar.header("📊 Chart Settings")

ticker = st.sidebar.text_input("Ticker", "AAPL").upper()

time_period = st.sidebar.selectbox(
    "Time Period",
    ["1d", "1wk", "1mo", "1y", "max"]
)

chart_type = st.sidebar.selectbox(
    "Chart Type",
    ["Candlestick", "Line"]
)

indicators = st.sidebar.multiselect(
    "Technical Indicators",
    ["SMA 20", "EMA 20", "RSI", "MACD", "Bollinger Bands"]
)

interval_mapping = {
    "1d": "1m",
    "1wk": "30m",
    "1mo": "1d",
    "1y": "1wk",
    "max": "1wk"
}

# ==================================================
# 🔹 MAIN DASHBOARD LOGIC
# ==================================================
if st.sidebar.button("Update"):

    data = fetch_stock_data(ticker, time_period, interval_mapping[time_period])

    if data.empty:
        st.error("No data found. Check ticker symbol.")
        st.stop()

    data = process_data(data)
    data = add_technical_indicators(data)

    last_close, change, pct_change, high, low, volume = calculate_metrics(data)

    # ---------------- METRICS ROW ----------------
    st.metric(
        label=f"{ticker} Last Price",
        value=f"{last_close:.2f} USD",
        delta=f"{change:.2f} ({pct_change:.2f}%)"
    )

    col1, col2, col3 = st.columns(3)
    col1.metric("High", f"{high:.2f} USD")
    col2.metric("Low", f"{low:.2f} USD")
    col3.metric("Volume", f"{volume:,}")

    # ---------------- MAIN PRICE CHART ----------------
    fig = go.Figure()

    if chart_type == "Candlestick":
        fig.add_trace(
            go.Candlestick(
                x=data["Datetime"],
                open=data["Open"],
                high=data["High"],
                low=data["Low"],
                close=data["Close"],
                name="Price"
            )
        )
    else:
        fig.add_trace(
            go.Scatter(
                x=data["Datetime"],
                y=data["Close"],
                mode="lines",
                name="Close Price"
            )
        )

    # ---- Add Indicators ----
    if "SMA 20" in indicators:
        fig.add_trace(go.Scatter(x=data["Datetime"], y=data["SMA_20"], name="SMA 20"))

    if "EMA 20" in indicators:
        fig.add_trace(go.Scatter(x=data["Datetime"], y=data["EMA_20"], name="EMA 20"))

    if "Bollinger Bands" in indicators:
        fig.add_trace(go.Scatter(x=data["Datetime"], y=data["BB_Upper"], name="BB Upper", line=dict(dash="dot")))
        fig.add_trace(go.Scatter(x=data["Datetime"], y=data["BB_Lower"], name="BB Lower", line=dict(dash="dot")))

    fig.update_layout(
        title=f"{ticker} {time_period.upper()} Price Chart",
        xaxis_title="Time",
        yaxis_title="Price (USD)",
        height=600
    )

    st.plotly_chart(fig, use_container_width=True)

    # ---------------- VOLUME CHART ----------------
    st.subheader("📊 Volume Chart")

    vol_fig = go.Figure()
    vol_fig.add_trace(go.Bar(x=data["Datetime"], y=data["Volume"], name="Volume"))
    vol_fig.update_layout(height=300)

    st.plotly_chart(vol_fig, use_container_width=True)

    # ---------------- RSI CHART ----------------
    if "RSI" in indicators:
        st.subheader("📈 RSI Indicator")

        rsi_fig = go.Figure()
        rsi_fig.add_trace(go.Scatter(x=data["Datetime"], y=data["RSI"], name="RSI"))
        rsi_fig.add_hline(y=70, line_dash="dash")
        rsi_fig.add_hline(y=30, line_dash="dash")

        st.plotly_chart(rsi_fig, use_container_width=True)

    # ---------------- MACD CHART ----------------
    if "MACD" in indicators:
        st.subheader("📉 MACD Indicator")

        macd_fig = go.Figure()
        macd_fig.add_trace(go.Scatter(x=data["Datetime"], y=data["MACD"], name="MACD"))
        macd_fig.add_trace(go.Scatter(x=data["Datetime"], y=data["MACD_Signal"], name="Signal Line"))

        st.plotly_chart(macd_fig, use_container_width=True)

    # ---------------- DATA TABLES ----------------
    st.subheader("📄 Historical Data")
    st.dataframe(
        data[["Datetime", "Open", "High", "Low", "Close", "Volume"]]
    )

    st.subheader("📊 Technical Indicators")
    st.dataframe(
        data[["Datetime", "SMA_20", "EMA_20", "RSI", "MACD", "MACD_Signal"]]
    )

# ==================================================
# 🔹 REAL-TIME SIDEBAR PRICES
# ==================================================
st.sidebar.header("🔴 Live Market Prices")

watchlist = ["AAPL", "GOOGL", "AMZN", "MSFT", "TSLA"]

for symbol in watchlist:
    rt_data = fetch_stock_data(symbol, "1d", "1m")

    if not rt_data.empty:
        rt_data = process_data(rt_data)

        last = float(rt_data["Close"].iloc[-1])
        openp = float(rt_data["Open"].iloc[0])

        ch = last - openp
        pct = (ch / openp) * 100 if openp != 0 else 0

        st.sidebar.metric(
            symbol,
            f"{last:.2f} USD",
            f"{ch:.2f} ({pct:.2f}%)"
        )

st.sidebar.info(
    "Live data refreshes every 60 seconds automatically."
)
