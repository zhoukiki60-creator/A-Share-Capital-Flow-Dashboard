"""
Flask后端 - 资金流向看板API
"""

from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS
from data_service import (
    update_data, get_cached_data, get_sector_stocks,
    SECTORS, ALL_TICKERS
)
import threading
import time
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__, static_folder='static')
CORS(app)

# ============ API路由 ============

@app.route('/')
def index():
    """主页面"""
    return send_from_directory('static', 'index.html')


@app.route('/api/market')
def api_market():
    """大盘资金流向"""
    data = get_cached_data()
    return jsonify({
        'success': True,
        'data': data['market'],
        'update_time': data['update_time'],
        'stock_count': data['stock_count']
    })


@app.route('/api/sectors')
def api_sectors():
    """板块资金流向列表"""
    data = get_cached_data()
    # 清理个股明细，只返回概要
    sectors_clean = []
    for s in data['sectors']:
        sectors_clean.append({
            'id': s['id'],
            'name': s['name'],
            'net_inflow': s['net_inflow'],
            'super_large': s['super_large'],
            'large': s['large'],
            'medium': s['medium'],
            'small': s['small'],
            'main_force': s['main_force'],
            'retail': s['retail'],
            'stock_count': s['stock_count'],
            'amount_total': s.get('amount_total', 0)
        })
    
    return jsonify({
        'success': True,
        'data': sectors_clean,
        'update_time': data['update_time']
    })


@app.route('/api/sectors/<int:sector_id>/stocks')
def api_sector_stocks(sector_id):
    """板块内个股资金流向明细"""
    sector = get_sector_stocks(sector_id)
    if not sector:
        return jsonify({'success': False, 'error': '板块不存在'}), 404
    
    return jsonify({
        'success': True,
        'data': {
            'id': sector['id'],
            'name': sector['name'],
            'net_inflow': sector['net_inflow'],
            'super_large': sector['super_large'],
            'large': sector['large'],
            'medium': sector['medium'],
            'small': sector['small'],
            'main_force': sector['main_force'],
            'retail': sector['retail'],
            'stocks': sector['stocks']
        },
        'update_time': get_cached_data()['update_time']
    })


@app.route('/api/config')
def api_config():
    """板块配置信息"""
    return jsonify({
        'success': True,
        'data': {
            'sectors': [{'id': s['id'], 'name': s['name'], 'stock_count': len(s['stocks'])} for s in SECTORS],
            'total_stocks': len(ALL_TICKERS)
        }
    })


@app.route('/api/refresh', methods=['POST'])
def api_refresh():
    """手动触发数据刷新"""
    threading.Thread(target=update_data, daemon=True).start()
    return jsonify({'success': True, 'message': '刷新任务已启动'})


# ============ 定时更新 ============

def scheduled_update():
    """定时更新数据（每60秒）"""
    while True:
        try:
            update_data()
        except Exception as e:
            logger.error(f"定时更新异常: {e}")
        time.sleep(60)


# ============ 启动 ============

if __name__ == '__main__':
    logger.info("启动资金流向看板服务...")
    
    # 启动时立即更新一次数据
    logger.info("首次数据加载...")
    update_data()
    
    # 启动定时更新线程
    updater = threading.Thread(target=scheduled_update, daemon=True)
    updater.start()
    
    logger.info("服务启动完成，监听端口5000")
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)
