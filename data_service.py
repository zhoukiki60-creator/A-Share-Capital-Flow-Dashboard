"""
资金流向聚合计算服务
基于ifind实时数据（成交额+涨跌幅）估算超大单/大单/中单/小单资金流向
"""

import json
import math
import time
import subprocess
import csv
import io
from datetime import datetime, timedelta
from threading import Lock
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)

# 加载板块配置
with open('/mnt/agents/upload/28大板块A股完整代表性个股 ## 1..txt', 'r', encoding='utf-8') as f:
    content = f.read()

import re

SECTORS = []
current_sector = None

for line in content.split('\n'):
    line = line.strip()
    if not line:
        continue
    sector_match = re.match(r'##\s*(\d+)\.\s*(.+)', line)
    if sector_match:
        sector_id = int(sector_match.group(1))
        sector_name = sector_match.group(2).strip()
        sector_name = re.sub(r'[（(].*?[）)]', '', sector_name).strip()
        current_sector = {
            'id': sector_id,
            'name': sector_name,
            'stocks': []
        }
        SECTORS.append(current_sector)
        continue
    
    stock_match = re.match(r'(\d+)\.\s*([\u4e00-\u9fa5]+)\s+(\d{6})', line)
    if stock_match and current_sector:
        stock_name = stock_match.group(2)
        stock_code = stock_match.group(3)
        code_num = int(stock_code)
        if code_num >= 688000:
            suffix = '.SH'
        elif code_num >= 600000:
            suffix = '.SH'
        elif code_num >= 300000:
            suffix = '.SZ'
        else:
            suffix = '.SZ'
        
        ticker = f"{stock_code}{suffix}"
        current_sector['stocks'].append({
            'name': stock_name,
            'code': stock_code,
            'ticker': ticker
        })

# 建立股票到板块的映射
STOCK_TO_SECTOR = {}
for sector in SECTORS:
    for stock in sector['stocks']:
        STOCK_TO_SECTOR[stock['ticker']] = {
            'sector_id': sector['id'],
            'sector_name': sector['name'],
            'stock_name': stock['name']
        }

ALL_TICKERS = list(STOCK_TO_SECTOR.keys())
logger.info(f"加载完成: {len(SECTORS)}个板块, {len(ALL_TICKERS)}只个股")

# 资金流向模型参数
# 超大单/大单/中单/小单的分配比例（按绝对值）
ORDER_RATIOS = {
    'super_large': 0.40,
    'large': 0.30,
    'medium': 0.20,
    'small': 0.10
}

# 缓存
cache = {
    'stock_data': {},      # 个股原始数据
    'sector_data': [],     # 板块聚合数据
    'market_data': {},     # 大盘聚合数据
    'last_update': None,
    'updating': False
}
cache_lock = Lock()


def estimate_fund_flow(amount, pct_change):
    """
    基于成交额和涨跌幅估算资金流向
    
    模型说明:
    - 涨跌幅方向决定流入/流出方向
    - 成交额大小决定资金量级的基数
    - 使用tanh使涨跌幅影响非线性饱和（避免极端涨跌幅导致不合理的大额）
    
    返回: {
        'net': 净流入(可正可负),
        'super_large': 超大单,
        'large': 大单,
        'medium': 中单,
        'small': 小单
    }
    """
    if amount is None or pct_change is None:
        return {'net': 0, 'super_large': 0, 'large': 0, 'medium': 0, 'small': 0}
    
    # 涨跌幅转小数 (如 1.5% -> 0.015)
    pc = pct_change / 100.0
    
    # 使用tanh使涨跌幅影响非线性: tanh(3*x) 在±10%涨跌时接近饱和
    direction = math.tanh(3 * pc)
    
    # 净流入 = 成交额 * 方向系数
    # 当涨跌幅为0时，净流约为0；涨跌幅越大，方向越明确
    net_inflow = amount * direction * 0.5
    
    # 按固定比例分配到各单型
    abs_net = abs(net_inflow)
    sign = 1 if net_inflow >= 0 else -1
    
    return {
        'net': round(net_inflow, 2),
        'super_large': round(abs_net * ORDER_RATIOS['super_large'] * sign, 2),
        'large': round(abs_net * ORDER_RATIOS['large'] * sign, 2),
        'medium': round(abs_net * ORDER_RATIOS['medium'] * sign, 2),
        'small': round(abs_net * ORDER_RATIOS['small'] * sign, 2)
    }


def call_ifind_realtime(tickers):
    """调用ifind获取实时价格数据，返回解析后的dict"""
    ticker_str = ','.join(tickers)
    output_path = f'/tmp/ifind_{int(time.time()*1000)}.csv'
    
    cmd = [
        'python3', 'scripts/ifind_tool.py', 'call',
        '--api-name', 'ifind_get_stock_realtime_price',
        '--params-json', json.dumps({
            'ticker': ticker_str,
            'type': 'realtime_price',
            'file_path': output_path
        })
    ]
    
    try:
        result = subprocess.run(
            cmd, cwd='/app/.agents/plugins/ifind',
            capture_output=True, text=True, timeout=60
        )
        
        if result.returncode != 0:
            logger.error(f"ifind调用失败: {result.stderr}")
            return {}
        
        # 解析CSV
        with open(output_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        
        data = {}
        for row in rows:
            ticker = row.get('ts_code', '')
            if ticker:
                data[ticker] = row
        
        return data
        
    except Exception as e:
        logger.error(f"获取数据异常: {e}")
        return {}


def fetch_all_stocks():
    """获取所有201只个股的实时数据（分批，每批3只）"""
    all_data = {}
    batch_size = 3
    total = len(ALL_TICKERS)
    
    for i in range(0, total, batch_size):
        batch = ALL_TICKERS[i:i+batch_size]
        logger.info(f"获取数据 {i+1}-{min(i+batch_size, total)}/{total}")
        
        batch_data = call_ifind_realtime(batch)
        all_data.update(batch_data)
        
        # 短暂延时避免请求过快
        if i + batch_size < total:
            time.sleep(0.3)
    
    return all_data


def aggregate_data(stock_raw_data):
    """
    聚合计算：个股 -> 板块 -> 大盘
    
    返回: {
        'stocks': {ticker: {name, code, sector_id, sector_name, price, pct_change, amount, volume, fund_flow: {net, super_large, large, medium, small}}},
        'sectors': [{id, name, net_inflow, super_large, large, medium, small, main_force, retail, stock_count, stocks: [...]}],
        'market': {super_large, large, medium, small, main_force, retail}
    }
    """
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    # 1. 个股数据 + 资金流向估算
    stocks_result = {}
    for ticker, raw in stock_raw_data.items():
        try:
            info = STOCK_TO_SECTOR.get(ticker, {})
            close = float(raw.get('close', 0) or 0)
            pct_change = float(raw.get('pct_change', 0) or 0)
            amount = float(raw.get('amount', 0) or 0)
            volume = float(raw.get('vol', 0) or 0)
            
            fund_flow = estimate_fund_flow(amount, pct_change)
            
            stocks_result[ticker] = {
                'ticker': ticker,
                'name': info.get('stock_name', ticker),
                'code': ticker.split('.')[0],
                'sector_id': info.get('sector_id', 0),
                'sector_name': info.get('sector_name', ''),
                'price': close,
                'pct_change': round(pct_change, 2),
                'amount': round(amount, 2),
                'volume': int(volume),
                'fund_flow': fund_flow
            }
        except (ValueError, TypeError) as e:
            logger.warning(f"解析{ticker}数据失败: {e}")
            continue
    
    # 2. 板块聚合
    sector_map = {}
    for s in SECTORS:
        sector_map[s['id']] = {
            'id': s['id'],
            'name': s['name'],
            'net_inflow': 0,
            'super_large': 0,
            'large': 0,
            'medium': 0,
            'small': 0,
            'main_force': 0,  # 超大单+大单
            'retail': 0,       # 中单+小单
            'stock_count': 0,
            'amount_total': 0,
            'stocks': []
        }
    
    for ticker, sd in stocks_result.items():
        sid = sd['sector_id']
        if sid not in sector_map:
            continue
        
        ff = sd['fund_flow']
        sm = sector_map[sid]
        sm['net_inflow'] += ff['net']
        sm['super_large'] += ff['super_large']
        sm['large'] += ff['large']
        sm['medium'] += ff['medium']
        sm['small'] += ff['small']
        sm['main_force'] += (ff['super_large'] + ff['large'])
        sm['retail'] += (ff['medium'] + ff['small'])
        sm['stock_count'] += 1
        sm['amount_total'] += sd['amount']
        sm['stocks'].append(sd)
    
    # 转换为列表并排序（按净流入降序）
    sectors_list = list(sector_map.values())
    for s in sectors_list:
        s['net_inflow'] = round(s['net_inflow'], 2)
        s['super_large'] = round(s['super_large'], 2)
        s['large'] = round(s['large'], 2)
        s['medium'] = round(s['medium'], 2)
        s['small'] = round(s['small'], 2)
        s['main_force'] = round(s['main_force'], 2)
        s['retail'] = round(s['retail'], 2)
        # 按净流入排序个股
        s['stocks'].sort(key=lambda x: x['fund_flow']['net'], reverse=True)
    
    # 3. 大盘聚合
    market = {
        'super_large': round(sum(s['super_large'] for s in sectors_list), 2),
        'large': round(sum(s['large'] for s in sectors_list), 2),
        'medium': round(sum(s['medium'] for s in sectors_list), 2),
        'small': round(sum(s['small'] for s in sectors_list), 2),
        'main_force': round(sum(s['main_force'] for s in sectors_list), 2),
        'retail': round(sum(s['retail'] for s in sectors_list), 2),
        'net_inflow': round(sum(s['net_inflow'] for s in sectors_list), 2)
    }
    
    return {
        'stocks': stocks_result,
        'sectors': sectors_list,
        'market': market,
        'update_time': now
    }


def update_data():
    """完整的数据更新流程"""
    with cache_lock:
        if cache['updating']:
            logger.info("数据更新中，跳过")
            return
        cache['updating'] = True
    
    try:
        logger.info("开始获取全量数据...")
        start_time = time.time()
        
        raw_data = fetch_all_stocks()
        if not raw_data:
            logger.error("获取数据失败")
            return
        
        result = aggregate_data(raw_data)
        
        with cache_lock:
            cache['stock_data'] = result['stocks']
            cache['sector_data'] = result['sectors']
            cache['market_data'] = result['market']
            cache['last_update'] = result['update_time']
        
        elapsed = round(time.time() - start_time, 1)
        logger.info(f"数据更新完成: {len(raw_data)}只个股, {len(result['sectors'])}个板块, 耗时{elapsed}秒")
        
    except Exception as e:
        logger.error(f"数据更新异常: {e}")
    finally:
        with cache_lock:
            cache['updating'] = False


def get_cached_data():
    """获取缓存数据（线程安全）"""
    with cache_lock:
        return {
            'market': cache['market_data'].copy() if cache['market_data'] else {},
            'sectors': cache['sector_data'][:],  # 浅拷贝列表
            'update_time': cache['last_update'],
            'stock_count': len(cache['stock_data'])
        }


def get_sector_stocks(sector_id):
    """获取指定板块的个股明细"""
    with cache_lock:
        for sector in cache['sector_data']:
            if sector['id'] == sector_id:
                return sector
    return None
