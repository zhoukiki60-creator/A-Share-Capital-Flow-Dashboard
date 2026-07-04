"""
Flask后端 - 资金流向看板（云端精简版）
自动从URL下载数据，无需ifind，无需本地文件
"""

import json
import os
import time
import threading
import logging
import urllib.request
from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)

# 数据源URL（每次刷新后自动更新）
DATA_URL = 'https://ggh36hbbghehq.ok.kimi.link/static/data.json'

# 数据缓存
_cache = {'market': {}, 'sectors': [], 'update_time': None}
_lock = threading.Lock()

app = Flask(__name__, static_folder='.')
CORS(app)

def load_data():
    try:
        req = urllib.request.Request(DATA_URL, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read().decode('utf-8'))
        with _lock:
            _cache['market'] = data.get('market', {})
            _cache['sectors'] = data.get('sectors', [])
            _cache['update_time'] = data.get('update_time')
        logger.info(f"数据加载成功: {data.get('update_time')}")
        return True
    except Exception as e:
        logger.error(f"数据加载失败: {e}")
        return False

# 启动时加载
load_data()

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/api/market')
def api_market():
    return jsonify({'success': True, 'data': _cache['market'], 'update_time': _cache['update_time']})

@app.route('/api/sectors')
def api_sectors():
    return jsonify({'success': True, 'data': _cache['sectors'], 'update_time': _cache['update_time']})

@app.route('/api/sectors/<int:sector_id>/stocks')
def api_sector_stocks(sector_id):
    for s in _cache['sectors']:
        if s['id'] == sector_id:
            return jsonify({'success': True, 'data': s, 'update_time': _cache['update_time']})
    return jsonify({'success': False, 'error': '板块不存在'}), 404

@app.route('/api/refresh', methods=['POST'])
def api_refresh():
    if load_data():
        return jsonify({'success': True, 'message': '已刷新', 'update_time': _cache['update_time']})
    return jsonify({'success': False, 'message': '刷新失败'}), 500

@app.route('/api/status')
def api_status():
    return jsonify({'success': True, 'update_time': _cache['update_time'], 'source': DATA_URL})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
