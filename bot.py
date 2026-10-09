import os
import requests
import pandas as pd
import ta
from flask import Flask, jsonify, request, render_template_string
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# Fetch Market Data from Binance API
def get_binance_klines(symbol="BTCUSDT", interval="1m", limit=100):
    clean_symbol = symbol.replace("/", "").replace("-", "")
    url = f"https://api.binance.com/api/v3/klines?symbol={clean_symbol}&interval={interval}&limit={limit}"
    res = requests.get(url, timeout=5)
    data = res.json()
    
    df = pd.DataFrame(data, columns=[
        'timestamp', 'open', 'high', 'low', 'close', 'volume',
        'close_time', 'qav', 'num_trades', 'taker_base_vol', 'taker_quote_vol', 'ignore'
    ])
    df['close'] = df['close'].astype(float)
    df['high'] = df['high'].astype(float)
    df['low'] = df['low'].astype(float)
    df['volume'] = df['volume'].astype(float)
    return df

# Calculate 8 Indicator Engine Signals
def analyze_indicators(df):
    close = df['close']
    high = df['high']
    low = df['low']
    volume = df['volume']
    
    signals = {}
    
    # 1. RSI (14)
    rsi = ta.momentum.rsi(close, window=14).iloc[-1]
    if rsi < 35:
        signals['RSI (14)'] = {'direction': 'BUY', 'desc': f'Oversold ({rsi:.1f})'}
    elif rsi > 65:
        signals['RSI (14)'] = {'direction': 'SELL', 'desc': f'Overbought ({rsi:.1f})'}
    else:
        signals['RSI (14)'] = {'direction': 'NEUTRAL', 'desc': f'Neutral ({rsi:.1f})'}

    # 2. EMA 9 vs EMA 21
    ema9 = ta.trend.ema_indicator(close, window=9).iloc[-1]
    ema21 = ta.trend.ema_indicator(close, window=21).iloc[-1]
    if ema9 > ema21:
        signals['EMA 9 vs EMA 21'] = {'direction': 'BUY', 'desc': 'Bullish Cross'}
    else:
        signals['EMA 9 vs EMA 21'] = {'direction': 'SELL', 'desc': 'Bearish Cross'}

    # 3. MACD (12,26,9)
    macd = ta.trend.macd_diff(close).iloc[-1]
    if macd > 0:
        signals['MACD (12,26,9)'] = {'direction': 'BUY', 'desc': 'Positive Histogram'}
    else:
        signals['MACD (12,26,9)'] = {'direction': 'SELL', 'desc': 'Negative Histogram'}

    # 4. Stochastic (14,3,3)
    stoch_k = ta.momentum.stoch(high, low, close, window=14).iloc[-1]
    if stoch_k < 20:
        signals['Stochastic (14,3,3)'] = {'direction': 'BUY', 'desc': f'Oversold ({stoch_k:.1f})'}
    elif stoch_k > 80:
        signals['Stochastic (14,3,3)'] = {'direction': 'SELL', 'desc': f'Overbought ({stoch_k:.1f})'}
    else:
        signals['Stochastic (14,3,3)'] = {'direction': 'NEUTRAL', 'desc': f'Neutral ({stoch_k:.1f})'}

    # 5. Bollinger Bands (20,2)
    bb_upper = ta.volatility.bollinger_hband(close, window=20).iloc[-1]
    bb_lower = ta.volatility.bollinger_lband(close, window=20).iloc[-1]
    current_p = close.iloc[-1]
    if current_p <= bb_lower:
        signals['Bollinger (20,2)'] = {'direction': 'BUY', 'desc': 'Price near Lower Band'}
    elif current_p >= bb_upper:
        signals['Bollinger (20,2)'] = {'direction': 'SELL', 'desc': 'Price near Upper Band'}
    else:
        signals['Bollinger (20,2)'] = {'direction': 'NEUTRAL', 'desc': 'Inside Bands'}

    # 6. Price Action
    prev_close = close.iloc[-2]
    if current_p > prev_close:
        signals['Price action'] = {'direction': 'BUY', 'desc': 'Bullish Candle'}
    else:
        signals['Price action'] = {'direction': 'SELL', 'desc': 'Bearish Candle'}

    # 7. ADX (14) - Trend Strength
    adx = ta.trend.adx(high, low, close, window=14).iloc[-1]
    adx_pos = ta.trend.adx_pos(high, low, close, window=14).iloc[-1]
    adx_neg = ta.trend.adx_neg(high, low, close, window=14).iloc[-1]
    if adx > 20:
        direction = 'BUY' if adx_pos > adx_neg else 'SELL'
        signals['ADX (14) · Trend strength'] = {'direction': direction, 'desc': f'Strong Trend ({adx:.1f})'}
    else:
        signals['ADX (14) · Trend strength'] = {'direction': 'NEUTRAL', 'desc': f'Weak Trend ({adx:.1f})'}

    # 8. Volume Trend
    vol_sma = ta.trend.sma_indicator(volume, window=20).iloc[-1]
    curr_vol = volume.iloc[-1]
    if curr_vol > vol_sma:
        direction = 'BUY' if current_p > prev_close else 'SELL'
        signals['Volume trend'] = {'direction': direction, 'desc': 'High Volume'}
    else:
        signals['Volume trend'] = {'direction': 'NEUTRAL', 'desc': 'Low Volume'}

    # Count Agreements
    buy_count = sum(1 for v in signals.values() if v['direction'] == 'BUY')
    sell_count = sum(1 for v in signals.values() if v['direction'] == 'SELL')

    if buy_count >= sell_count:
        final_dir = 'BUY'
        score = buy_count
    else:
        final_dir = 'SELL'
        score = sell_count

    # Signal Logic according to Pic 1 rules
    if score >= 7:
        status = f"STRONG CALL (BUY) 🟢" if final_dir == 'BUY' else f"STRONG PUT (SELL) 🔴"
        color = "#22c55e"
    elif score in [5, 6]:
        status = f"WEAK CALL (BUY) 🟡" if final_dir == 'BUY' else f"WEAK PUT (SELL) 🟡"
        color = "#eab308"
    else:
        status = "PLEASE WAIT / RISKY MARKET ⚪"
        color = "#9ca3af"

    return {
        'signals': signals,
        'score': score,
        'total_indicators': 8,
        'status': status,
        'color': color,
        'latest_price': f"${current_p:,.2f}"
    }

@app.route('/')
def home():
    with open('index.html', 'r', encoding='utf-8') as f:
        return f.read()

@app.route('/api/analyze', methods=['GET'])
def api_analyze():
    pair = request.args.get('pair', 'BTC/USDT')
    try:
        df = get_binance_klines(pair)
        result = analyze_indicators(df)
        return jsonify({'success': True, 'data': result, 'pair': pair})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)