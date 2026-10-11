import os
from flask import Flask, render_template, request, jsonify
import pandas as pd
import numpy as np
import requests

app = Flask(__name__, template_folder='.', static_folder='.')

def fetch_binance_data(symbol="BTCUSDT", interval="5m", limit=100):
    url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}"
    try:
        response = requests.get(url, timeout=5)
        data = response.json()
        if isinstance(data, list) and len(data) > 0:
            df = pd.DataFrame(data, columns=[
                'timestamp', 'open', 'high', 'low', 'close', 'volume',
                'close_time', 'quote_asset_volume', 'number_of_trades',
                'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'
            ])
            df['close'] = df['close'].astype(float)
            df['high'] = df['high'].astype(float)
            df['low'] = df['low'].astype(float)
            df['open'] = df['open'].astype(float)
            df['volume'] = df['volume'].astype(float)
            return df
    except Exception as e:
        print("Error fetching data:", e)
    return None

def calculate_indicators(df):
    close = df['close']
    high = df['high']
    low = df['low']
    volume = df['volume']

    # 1. RSI (14)
    delta = close.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    current_rsi = rsi.iloc[-1]

    # 2. EMA 9 & 21
    ema9 = close.ewm(span=9, adjust=False).mean().iloc[-1]
    ema21 = close.ewm(span=12, adjust=False).mean().iloc[-1]

    # 3. MACD
    exp1 = close.ewm(span=12, adjust=False).mean()
    exp2 = close.ewm(span=26, adjust=False).mean()
    macd = exp1 - exp2
    signal_line = macd.ewm(span=9, adjust=False).mean()
    current_macd = macd.iloc[-1]
    current_signal = signal_line.iloc[-1]

    # 4. Stochastic
    lowest_low = low.rolling(window=14).min()
    highest_high = high.rolling(window=14).max()
    k = 100 * ((close - lowest_low) / (highest_high - lowest_low))
    d = k.rolling(window=3).mean()
    current_k = k.iloc[-1]

    # 5. Bollinger Bands
    sma20 = close.rolling(window=20).mean().iloc[-1]
    std20 = close.rolling(window=20).std().iloc[-1]
    upper_band = sma20 + (2 * std20)
    lower_band = sma20 - (2 * std20)
    curr_price = close.iloc[-1]

    # 6. Price Action
    prev_close = close.iloc[-2]

    # 7. ADX Proxy / Trend
    price_change = curr_price - close.iloc[-5]

    # 8. Volume Trend
    avg_vol = volume.rolling(window=10).mean().iloc[-1]
    curr_vol = volume.iloc[-1]

    # Evaluating 8 Indicators
    signals = {}
    score = 0

    # RSI Check
    if current_rsi < 45:
        signals['RSI (14)'] = {'direction': 'BUY', 'desc': 'Oversold zone'}
        score += 1
    elif current_rsi > 55:
        signals['RSI (14)'] = {'direction': 'SELL', 'desc': 'Overbought zone'}
    else:
        signals['RSI (14)'] = {'direction': 'NEUTRAL', 'desc': 'Mid range'}

    # EMA Check
    if ema9 > ema21:
        signals['EMA 9 vs EMA 21'] = {'direction': 'BUY', 'desc': 'Bullish crossover'}
        score += 1
    else:
        signals['EMA 9 vs EMA 21'] = {'direction': 'SELL', 'desc': 'Bearish crossover'}

    # MACD Check
    if current_macd > current_signal:
        signals['MACD (12,26,9)'] = {'direction': 'BUY', 'desc': 'Bullish momentum'}
        score += 1
    else:
        signals['MACD (12,26,9)'] = {'direction': 'SELL', 'desc': 'Bearish momentum'}

    # Stochastic Check
    if current_k < 30:
        signals['Stochastic (14,3,3)'] = {'direction': 'BUY', 'desc': 'Oversold bounce'}
        score += 1
    elif current_k > 70:
        signals['Stochastic (14,3,3)'] = {'direction': 'SELL', 'desc': 'Overbought zone'}
    else:
        signals['Stochastic (14,3,3)'] = {'direction': 'NEUTRAL', 'desc': 'Neutral'}

    # Bollinger Bands Check
    if curr_price <= lower_band:
        signals['Bollinger (20,2)'] = {'direction': 'BUY', 'desc': 'Touch lower band'}
        score += 1
    elif curr_price >= upper_band:
        signals['Bollinger (20,2)'] = {'direction': 'SELL', 'desc': 'Touch upper band'}
    else:
        signals['Bollinger (20,2)'] = {'direction': 'NEUTRAL', 'desc': 'Inside bands'}

    # Price Action Check
    if curr_price > prev_close:
        signals['Price action'] = {'direction': 'BUY', 'desc': 'Higher close'}
        score += 1
    else:
        signals['Price action'] = {'direction': 'SELL', 'desc': 'Lower close'}

    # ADX Trend Check
    if price_change > 0:
        signals['ADX (14) · Trend strength'] = {'direction': 'BUY', 'desc': 'Strong upward'}
        score += 1
    else:
        signals['ADX (14) · Trend strength'] = {'direction': 'SELL', 'desc': 'Strong downward'}

    # Volume Trend Check
    if curr_vol > avg_vol:
        signals['Volume trend'] = {'direction': 'BUY', 'desc': 'High volume spike'}
        score += 1
    else:
        signals['Volume trend'] = {'direction': 'NEUTRAL', 'desc': 'Normal volume'}

    # Final Status determination
    if score >= 7:
        status = "STRONG CALL: BUY"
        color = "#10b981"
    elif score <= 2:
        status = "STRONG CALL: SELL"
        color = "#ef4444"
    else:
        status = "WAIT / MARKET NEUTRAL"
        color = "#f59e0b"

    return {
        "score": score,
        "total_indicators": 8,
        "status": status,
        "color": color,
        "latest_price": f"${curr_price:,.2f}",
        "signals": signals
    }

@app.route('/')
def index():
    base_dir = os.path.abspath(os.path.dirname(__file__))
    html_path = os.path.join(base_dir, 'index.html')
    if os.path.exists(html_path):
        with open(html_path, 'r', encoding='utf-8') as f:
            return f.read()
    return f"Index HTML not found in: {base_dir}", 404

@app.route('/api/analyze')
def analyze():
    pair = request.args.get('pair', 'BTCUSDT')
    df = fetch_binance_data(symbol=pair)
    if df is not None and not df.empty:
        result = calculate_indicators(df)
        return jsonify({"success": True, "data": result})
    return jsonify({"success": False, "error": "Unable to fetch market data"})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)