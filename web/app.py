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

DB_PATH = 'data/transformers.db'


def get_db():
    """获取数据库连接"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


@app.route('/')
def index():
    """主页面"""
    return render_template('index.html')


@app.route('/api/stats')
def api_stats():
    """获取统计数据"""
    conn = get_db()
    
    # 京东
    jd_total = conn.execute('SELECT COUNT(*) FROM jd_products').fetchone()[0]
    jd_available = conn.execute('SELECT COUNT(*) FROM jd_products WHERE status="available"').fetchone()[0]
    jd_pending = conn.execute('SELECT COUNT(*) FROM jd_products WHERE status="pending"').fetchone()[0]
    jd_history = conn.execute('SELECT COUNT(*) FROM jd_price_history').fetchone()[0]
    
    # 天猫
    tmall_total = conn.execute('SELECT COUNT(*) FROM tmall_products').fetchone()[0]
    tmall_available = conn.execute('SELECT COUNT(*) FROM tmall_products WHERE status="available"').fetchone()[0]
    tmall_pending = conn.execute('SELECT COUNT(*) FROM tmall_products WHERE status="pending"').fetchone()[0]
    tmall_history = conn.execute('SELECT COUNT(*) FROM tmall_price_history').fetchone()[0]
    
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


@app.route('/api/tmall-prices')
def api_tmall_prices():
    """获取天猫价格列表"""
    conn = get_db()
    
    products = conn.execute('''
        SELECT id, product_id, product_url, image_url, title, style_name, 
               shop_name, created_at, updated_at
        FROM tmall_products
        ORDER BY id DESC
    ''').fetchall()
    
    result = []
    today = datetime.now().strftime('%Y%m%d')
    thirty_days_ago = datetime.now()
    thirty_days_ago = (thirty_days_ago - datetime.timedelta(days=30)).strftime('%Y%m%d')
    
    for p in products:
        product_id = p['product_id']
        created_at = p['created_at'] or ''
        
        is_new = False
        if created_at:
            try:
                created_date = datetime.strptime(created_at[:10], '%Y-%m-%d')
                if (datetime.now() - created_date).days <= 3:
                    is_new = True
            except:
                pass
        
        price_history = conn.execute('''
            SELECT price, created_at
            FROM tmall_price_history
            WHERE product_id = ?
            ORDER BY created_at DESC
        ''', (p['id'],)).fetchall()
        
        latest_price = None
        latest_date = None
        if price_history:
            latest_price = price_history[0]['price']
            latest_date = price_history[0]['created_at']
        
        min_price_30d = None
        if price_history:
            for ph in price_history:
                if ph['created_at'] and ph['created_at'] < today:
                    if min_price_30d is None or ph['price'] < min_price_30d:
                        min_price_30d = ph['price']
        
        min_price_all = None
        if price_history:
            min_price_all = min(ph['price'] for ph in price_history if ph['price'])
        
        result.append({
            'id': p['id'],
            'product_id': product_id,
            'product_url': p['product_url'],
            'image_url': p['image_url'],
            'title': p['title'],
            'style_name': p['style_name'] or '',
            'shop_name': p['shop_name'],
            'created_at': created_at,
            'updated_at': p['updated_at'],
            'is_new': is_new,
            'latest_price': latest_price,
            'latest_date': latest_date,
            'min_price_30d': min_price_30d,
            'min_price_all': min_price_all
        })
    
    conn.close()
    return jsonify(result)


@app.route('/api/price-history/<product_id>')
def api_price_history(product_id):
    """获取价格历史"""
    source = request.args.get('source', 'jd')
    
    if source == 'jd':
        table = 'jd_price_history'
        product_table = 'jd_products'
    else:
        table = 'tmall_price_history'
        product_table = 'tmall_products'
    
    conn = get_db()
    
    # 获取价格历史
    history = conn.execute(f'''
        SELECT ph.id, ph.product_id, ph.price, ph.created_at, ph.style_name
        FROM {table} ph
        WHERE ph.product_id = ?
        ORDER BY ph.created_at DESC
    ''', (product_id,)).fetchall()
    
    conn.close()
    
    return jsonify([dict(row) for row in history])


if __name__ == '__main__':
    print("🚀 Transformers 价格追踪系统")
    print("📍 访问地址: http://localhost:8080")
    app.run(host='0.0.0.0', port=8080, debug=True)
