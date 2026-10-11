import os
from flask import Flask, render_template, request, jsonify
import pandas as pd
import numpy as np
import requests
from datetime import datetime

app = Flask(__name__, template_folder='.', static_folder='.')

def clean_symbol(pair_str):
    if not pair_str:
        return "BTCUSDT"
    # Remove all spaces, slashes, dashes to get clean string like SOLUSDT
    cleaned = str(pair_str).replace(" ", "").replace("/", "").replace("-", "").upper()
    return cleaned

def fetch_binance_data(symbol="BTCUSDT", interval="5m", limit=100):
    clean_sym = clean_symbol(symbol)
    url = f"https://api.binance.com/api/v3/klines?symbol={clean_sym}&interval={interval}&limit={limit}"
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
    ema21 = close.ewm(span=21, adjust=False).mean().iloc[-1]

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
    current_k = k.iloc[-1]

    # 5. Bollinger Bands
    sma20 = close.rolling(window=20).mean().iloc[-1]
    std20 = close.rolling(window=20).std().iloc[-1]
    upper_band = sma20 + (2 * std20)
    lower_band = sma20 - (2 * std20)
    curr_price = close.iloc[-1]

    # 6. Price Action
    prev_close = close.iloc[-2]

    # 7. ADX / Trend
    price_change = curr_price - close.iloc[-5]

    # 8. Volume
    avg_vol = volume.rolling(window=10).mean().iloc[-1]
    curr_vol = volume.iloc[-1]

    signals = {}
    score = 0

    # RSI
    if current_rsi < 45:
        signals['rsi'] = 'BUY'
        score += 1
    elif current_rsi > 55:
        signals['rsi'] = 'SELL'
    else:
        signals['rsi'] = 'NEUTRAL'

    # EMA
    if ema9 > ema21:
        signals['ema'] = 'BUY'
        score += 1
    else:
        signals['ema'] = 'SELL'

    # MACD
    if current_macd > current_signal:
        signals['macd'] = 'BUY'
        score += 1
    else:
        signals['macd'] = 'SELL'

    # Stochastic
    if current_k < 35:
        signals['stoch'] = 'BUY'
        score += 1
    elif current_k > 65:
        signals['stoch'] = 'SELL'
    else:
        signals['stoch'] = 'NEUTRAL'

    # Bollinger
    if curr_price <= lower_band:
        signals['bb'] = 'BUY'
        score += 1
    elif curr_price >= upper_band:
        signals['bb'] = 'SELL'
    else:
        signals['bb'] = 'NEUTRAL'

    # Price Action
    if curr_price > prev_close:
        signals['pa'] = 'BUY'
        score += 1
    else:
        signals['pa'] = 'SELL'

    # ADX Trend
    if price_change > 0:
        signals['adx'] = 'BUY'
        score += 1
    else:
        signals['adx'] = 'SELL'

    # Volume
    if curr_vol > avg_vol:
        signals['vol'] = 'BUY'
        score += 1
    else:
        signals['vol'] = 'NEUTRAL'

    if score >= 7:
        status = "BUY"
        color = "#10b981"
    elif score <= 2:
        status = "SELL"
        color = "#ef4444"
    else:
        status = "WAIT"
        color = "#f59e0b"

    now = datetime.utcnow().strftime("%I:%M %p UTC")

    return {
        "score": score,
        "total_indicators": 8,
        "status": status,
        "color": color,
        "latest_price": f"${curr_price:,.2f}",
        "trade_time": now,
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
    clean_pair = clean_symbol(pair)
    df = fetch_binance_data(symbol=clean_pair)
    if df is not None and not df.empty:
        result = calculate_indicators(df)
        return jsonify({"success": True, "data": result})
    return jsonify({"success": False, "error": "Unable to fetch market data"})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)