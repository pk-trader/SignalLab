import os
import requests
import pandas as pd
import ta
from flask import Flask, jsonify, request, send_from_directory
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__, static_folder='.', template_folder='.')

@app.route('/')
def home():
    # index.html অথবা index (1).html উভয় নামই চেক করবে
    if os.path.exists('index.html'):
        return send_from_directory('.', 'index.html')
    elif os.path.exists('index (1).html'):
        return send_from_directory('.', 'index (1).html')
    return "<h1>Index HTML file not found in repository!</h1>", 404

@app.route('/api/analyze', methods=['GET'])
def api_analyze():
    pair = request.args.get('pair', 'BTC/USDT')
    try:
        df = get_binance_klines(pair)
        result = analyze_indicators(df)
        return jsonify({'success': True, 'data': result, 'pair': pair})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# get_binance_klines এবং analyze_indicators ফাংশনগুলো আগের মতোই থাকবে...