#!/usr/bin/env python3
"""
Transformers 价格追踪系统 - Web应用
"""

from flask import Flask, render_template, jsonify, request
import sqlite3
from datetime import datetime
import os

app = Flask(__name__, 
            template_folder='templates',
            static_folder='static')

import os

# 使用绝对路径
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, 'data', 'transformers.db')


def get_db():
    """获取数据库连接"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def parse_date(date_str):
    """安全解析日期，返回标准格式或None"""
    if not date_str:
        return None
    try:
        # 尝试多种格式
        for fmt in ['%Y-%m-%d', '%Y%m%d', '%Y-%m-%d %H:%M:%S']:
            try:
                return datetime.strptime(str(date_str)[:10], fmt).strftime('%Y-%m-%d')
            except:
                continue
        return None
    except:
        return None


@app.route('/')
def index():
    """主页面"""
    return render_template('index.html')


@app.route('/api/stats')
def api_stats():
    """获取统计数据"""
    conn = get_db()
    
    try:
        jd_total = conn.execute('SELECT COUNT(*) FROM jd_products').fetchone()[0]
        jd_available = conn.execute('SELECT COUNT(*) FROM jd_products WHERE status="available"').fetchone()[0]
        jd_pending = conn.execute('SELECT COUNT(*) FROM jd_products WHERE status="pending"').fetchone()[0]
        jd_history = conn.execute('SELECT COUNT(*) FROM jd_price_history').fetchone()[0]
        
        tmall_total = conn.execute('SELECT COUNT(*) FROM tmall_products').fetchone()[0]
        tmall_available = conn.execute('SELECT COUNT(*) FROM tmall_products WHERE status="available"').fetchone()[0]
        tmall_pending = conn.execute('SELECT COUNT(*) FROM tmall_products WHERE status="pending"').fetchone()[0]
        tmall_history = conn.execute('SELECT COUNT(*) FROM tmall_price_history').fetchone()[0]
    except:
        jd_total = jd_available = jd_pending = jd_history = 0
        tmall_total = tmall_available = tmall_pending = tmall_history = 0
    
    conn.close()
    
    return jsonify({
        'jd': {
            'total': jd_total,
            'available': jd_available,
            'pending': jd_pending,
            'history': jd_history
        },
        'tmall': {
            'total': tmall_total,
            'available': tmall_available,
            'pending': tmall_pending,
            'history': tmall_history
        }
    })


def get_price_stats(product_row_id, price_table):
    """获取价格统计"""
    if not product_row_id:
        return {'latest_price': None, 'latest_date': None, 'min_price_30d': None, 'min_price_all': None}
    
    conn = get_db()
    
    try:
        today = datetime.now().strftime('%Y%m%d')
        price_history = conn.execute(f'''
            SELECT price, created_at
            FROM {price_table}
            WHERE product_id = ?
            ORDER BY created_at DESC
        ''', (product_row_id,)).fetchall()
        
        conn.close()
        
        if not price_history:
            return {'latest_price': None, 'latest_date': None, 'min_price_30d': None, 'min_price_all': None}
        
        # 最新价格
        latest = price_history[0]
        
        # 30日内最低（不包含今天）
        min_30d = None
        for ph in price_history:
            created_at = ph['created_at']
            if created_at and created_at < str(today):
                price = ph['price']
                if min_30d is None or price < min_30d:
                    min_30d = price
        
        # 历史最低
        min_all = min(ph['price'] for ph in price_history if ph['price'])
        
        return {
            'latest_price': latest['price'],
            'latest_date': latest['created_at'],
            'min_price_30d': min_30d,
            'min_price_all': min_all
        }
    except Exception as e:
        print(f"Price stats error: {e}")
        return {'latest_price': None, 'latest_date': None, 'min_price_30d': None, 'min_price_all': None}


@app.route('/api/jd-prices')
def api_jd_prices():
    """获取京东价格列表"""
    conn = get_db()
    
    try:
        products = conn.execute('''
            SELECT id, product_id, product_url, image_url, title, style_name, 
                   shop_name, created_at, updated_at
            FROM jd_products
            ORDER BY id DESC
        ''').fetchall()
    except:
        products = []
    
    conn.close()
    
    result = []
    today = datetime.now()
    
    for p in products:
        p = dict(p)
        
        # 解析创建日期
        created_at = parse_date(p.get('created_at'))
        p['created_at'] = created_at
        
        # 判断是否3天内新建
        p['is_new'] = False
        if created_at:
            try:
                created_date = datetime.strptime(created_at, '%Y-%m-%d')
                if (today - created_date).days <= 3:
                    p['is_new'] = True
            except:
                pass
        
        # 获取价格统计
        price_stats = get_price_stats(p['id'], 'jd_price_history')
        p['latest_price'] = price_stats['latest_price']
        p['latest_date'] = price_stats['latest_date']
        p['min_price_30d'] = price_stats['min_price_30d']
        p['min_price_all'] = price_stats['min_price_all']
        
        result.append(p)
    
    return jsonify(result)


@app.route('/api/tmall-prices')
def api_tmall_prices():
    """获取天猫价格列表"""
    conn = get_db()
    
    try:
        products = conn.execute('''
            SELECT id, product_id, product_url, image_url, title, style_name, 
                   shop_name, created_at, updated_at
            FROM tmall_products
            ORDER BY id DESC
        ''').fetchall()
    except:
        products = []
    
    conn.close()
    
    result = []
    today = datetime.now()
    
    for p in products:
        p = dict(p)
        
        # 解析创建日期
        created_at = parse_date(p.get('created_at'))
        p['created_at'] = created_at
        
        # 判断是否3天内新建
        p['is_new'] = False
        if created_at:
            try:
                created_date = datetime.strptime(created_at, '%Y-%m-%d')
                if (today - created_date).days <= 3:
                    p['is_new'] = True
            except:
                pass
        
        # 获取价格统计
        price_stats = get_price_stats(p['id'], 'tmall_price_history')
        p['latest_price'] = price_stats['latest_price']
        p['latest_date'] = price_stats['latest_date']
        p['min_price_30d'] = price_stats['min_price_30d']
        p['min_price_all'] = price_stats['min_price_all']
        
        result.append(p)
    
    return jsonify(result)


@app.route('/api/price-history/<product_id>')
def api_price_history(product_id):
    """获取价格历史"""
    source = request.args.get('source', 'jd')
    
    if source == 'jd':
        table = 'jd_price_history'
    else:
        table = 'tmall_price_history'
    
    conn = get_db()
    
    try:
        history = conn.execute(f'''
            SELECT id, product_id, price, created_at, style_name
            FROM {table}
            WHERE product_id = ?
            ORDER BY created_at DESC
        ''', (product_id,)).fetchall()
    except:
        history = []
    
    conn.close()
    
    return jsonify([dict(row) for row in history])


if __name__ == '__main__':
    print("🚀 Transformers 价格追踪系统")
    print("📍 访问地址: http://localhost:8080")
    app.run(host='0.0.0.0', port=8080, debug=True)
