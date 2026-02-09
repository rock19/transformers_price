#!/usr/bin/env python3
"""
Transformers 价格追踪系统 - Web应用
"""

from flask import Flask, render_template, jsonify, request
import sqlite3
from datetime import datetime, timedelta
import os

app = Flask(__name__, 
            template_folder='templates',
            static_folder='static')

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
        
        latest = price_history[0]
        
        min_30d = None
        for ph in price_history:
            created_at = ph['created_at']
            if created_at and created_at < str(today):
                price = ph['price']
                if min_30d is None or price < min_30d:
                    min_30d = price
        
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


@app.route('/test')
def test():
    """测试页面"""
    return render_template('test_complete.html')


@app.route('/debug')
def debug():
    """调试页面"""
    return render_template('index_debug.html')


@app.route('/')
def index():
    """主页面 - 服务端渲染"""
    conn = get_db()
    
    today = datetime.now().strftime('%Y%m%d')
    three_days_ago = (datetime.now() - timedelta(days=3)).strftime('%Y-%m-%d')
    
    # 京东商品
    jd_products_raw = conn.execute('''
        SELECT id, product_id, product_url, image_url, title, style_name, 
               shop_name, created_at, is_purchased, is_followed
        FROM jd_products
        ORDER BY id DESC
    ''').fetchall()
    
    jd_products = []
    for p in jd_products_raw:
        p = dict(p)
        price_stats = get_price_stats(p['id'], 'jd_price_history')
        p['min_price_30d'] = price_stats['min_price_30d']
        p['latest_price'] = price_stats['latest_price']
        p['latest_date'] = price_stats['latest_date']
        p['min_price_all'] = price_stats['min_price_all']
        
        # 判断是否3天内新建
        p['is_new'] = False
        created_at_str = str(p['created_at'])[:10] if p['created_at'] else ''
        if created_at_str >= three_days_ago:
            p['is_new'] = True
        
        # 格式化创建日期
        if created_at_str:
            p['created_at_display'] = created_at_str
        else:
            p['created_at_display'] = '-'
        
        jd_products.append(p)
    
    # 天猫商品通过 API 动态加载，不再服务端渲染
    conn.close()
    
    return render_template('index.html', jd_products=jd_products)


@app.route('/api/jd-prices')
def api_jd_prices():
    """获取京东价格列表（支持筛选）"""
    conn = get_db()
    
    # 获取筛选参数（都是可选的）
    filter_purchased = request.args.get('purchased', '')
    filter_followed = request.args.get('followed', '')
    
    # 构建查询条件
    where_conditions = []
    params = []
    
    # 是否购买：全部/未购买/已购买
    if filter_purchased in ['未购买', '购买']:
        where_conditions.append('is_purchased = ?')
        params.append(filter_purchased)
    
    # 是否关注：全部/未关注/已关注
    if filter_followed in ['未关注', '关注']:
        where_conditions.append('is_followed = ?')
        params.append(filter_followed)
    
    where_sql = ' AND '.join(where_conditions) if where_conditions else '1=1'
    
    products = conn.execute(f'''
        SELECT id, product_id, product_url, image_url, title, style_name, 
               shop_name, created_at, is_purchased, is_followed
        FROM jd_products
        WHERE {where_sql}
        ORDER BY id DESC
    ''', params).fetchall()
    
    conn.close()
    
    result = []
    today = datetime.now()
    three_days_ago = (today - timedelta(days=3)).strftime('%Y-%m-%d')
    
    for p in products:
        p = dict(p)
        price_stats = get_price_stats(p['id'], 'jd_price_history')
        p['min_price_30d'] = price_stats['min_price_30d']
        p['latest_price'] = price_stats['latest_price']
        p['latest_date'] = price_stats['latest_date']
        p['min_price_all'] = price_stats['min_price_all']
        
        p['is_new'] = False
        created_at_str = str(p['created_at'])[:10] if p['created_at'] else ''
        if created_at_str >= three_days_ago:
            p['is_new'] = True
        
        p['created_at_display'] = created_at_str if created_at_str else '-'
        
        result.append(p)
    
    return jsonify(result)


@app.route('/api/tmall-prices')
def api_tmall_prices():
    """获取天猫价格列表（支持筛选）"""
    conn = get_db()
    
    # 获取筛选参数
    filter_purchased = request.args.get('purchased', '')
    filter_followed = request.args.get('followed', '')
    
    # 构建查询条件
    where_conditions = []
    params = []
    
    if filter_purchased in ['未购买', '购买']:
        where_conditions.append('is_purchased = ?')
        params.append(filter_purchased)
    
    if filter_followed in ['未关注', '关注']:
        where_conditions.append('is_followed = ?')
        params.append(filter_followed)
    
    where_sql = ' AND '.join(where_conditions) if where_conditions else '1=1'
    
    products = conn.execute(f'''
        SELECT id, product_id, product_url, image_url, title, style_name, 
               shop_name, created_at, is_purchased, is_followed
        FROM tmall_products
        WHERE {where_sql}
        ORDER BY id DESC
    ''', params).fetchall()
    
    conn.close()
    
    result = []
    today = datetime.now()
    three_days_ago = (today - timedelta(days=3)).strftime('%Y-%m-%d')
    
    for p in products:
        p = dict(p)
        price_stats = get_price_stats(p['id'], 'tmall_price_history')
        p['min_price_30d'] = price_stats['min_price_30d']
        p['latest_price'] = price_stats['latest_price']
        p['latest_date'] = price_stats['latest_date']
        p['min_price_all'] = price_stats['min_price_all']
        
        p['is_new'] = False
        created_at_str = str(p['created_at'])[:10] if p['created_at'] else ''
        if created_at_str >= three_days_ago:
            p['is_new'] = True
        
        p['created_at_display'] = created_at_str if created_at_str else '-'
        
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


@app.route('/api/jd-stats')
def api_jd_stats():
    """获取京东统计数据（不受筛选影响）"""
    conn = get_db()
    
    # 查询所有商品的统计数据
    stats = conn.execute('''
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN is_purchased = '购买' THEN 1 ELSE 0 END) as purchased,
            SUM(CASE WHEN is_purchased = '未购买' THEN 1 ELSE 0 END) as not_purchased,
            SUM(CASE WHEN is_followed = '关注' THEN 1 ELSE 0 END) as followed,
            SUM(CASE WHEN is_followed = '未关注' THEN 1 ELSE 0 END) as not_followed
        FROM jd_products
    ''').fetchone()
    
    conn.close()
    
    return jsonify({
        'total': stats['total'] or 0,
        'purchased': stats['purchased'] or 0,
        'not_purchased': stats['not_purchased'] or 0,
        'followed': stats['followed'] or 0,
        'not_followed': stats['not_followed'] or 0
    })


@app.route('/api/tmall-stats')
def api_tmall_stats():
    """获取天猫统计数据（不受筛选影响）"""
    conn = get_db()
    
    # 查询所有商品的统计数据
    stats = conn.execute('''
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN is_purchased = '购买' THEN 1 ELSE 0 END) as purchased,
            SUM(CASE WHEN is_purchased = '未购买' THEN 1 ELSE 0 END) as not_purchased,
            SUM(CASE WHEN is_followed = '关注' THEN 1 ELSE 0 END) as followed,
            SUM(CASE WHEN is_followed = '未关注' THEN 1 ELSE 0 END) as not_followed
        FROM tmall_products
    ''').fetchone()
    
    conn.close()
    
    return jsonify({
        'total': stats['total'] or 0,
        'purchased': stats['purchased'] or 0,
        'not_purchased': stats['not_purchased'] or 0,
        'followed': stats['followed'] or 0,
        'not_followed': stats['not_followed'] or 0
    })


@app.route('/api/update-product', methods=['POST'])
def api_update_product():
    """更新商品状态"""
    data = request.json
    
    product_id = data.get('id')
    source = data.get('source')  # 'jd' or 'tmall'
    is_purchased = data.get('is_purchased')
    is_followed = data.get('is_followed')
    
    if not product_id or not source:
        return jsonify({'error': '缺少必要参数'}), 400
    
    if source == 'jd':
        table = 'jd_products'
    else:
        table = 'tmall_products'
    
    conn = get_db()
    
    try:
        conn.execute(f'''
            UPDATE {table}
            SET is_purchased = ?, is_followed = ?
            WHERE id = ?
        ''', (is_purchased, is_followed, product_id))
        conn.commit()
        conn.close()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/maintain')
def maintain():
    """商品维护页面"""
    return render_template('maintain.html')


# ============ 总表维护相关API ============

@app.route('/api/summary-list')
def api_summary_list():
    """获取总表列表"""
    conn = get_db()
    
    products = conn.execute('''
        SELECT ps.id, ps.product_name, ps.product_type,
               jd.id AS jd_id, jd.product_id AS jd_product_id, jd.title AS jd_title, jd.image_url AS jd_image, jd.price AS jd_price, jd.latest_date AS jd_date,
               tm.id AS tmall_id, tm.product_id AS tmall_product_id, tm.title AS tmall_title, tm.image_url AS tmall_image, tm.price AS tmall_price, tm.latest_date AS tmall_date
        FROM products_summary ps
        LEFT JOIN (
            SELECT id, product_id, product_url, image_url, title, price, 
                   (SELECT created_at FROM jd_price_history WHERE product_id = jd_products.id ORDER BY created_at DESC LIMIT 1) AS latest_date,
                   level
            FROM jd_products
        ) jd ON ps.jd_product_id = jd.id
        LEFT JOIN (
            SELECT id, product_id, product_url, image_url, title, price,
                   (SELECT created_at FROM tmall_price_history WHERE product_id = tmall_products.id ORDER BY created_at DESC LIMIT 1) AS latest_date,
                   level
            FROM tmall_products
        ) tm ON ps.tmall_product_id = tm.id
        ORDER BY ps.id DESC
    ''').fetchall()
    
    conn.close()
    
    result = []
    for p in products:
        result.append({
            'id': p['id'],
            'product_name': p['product_name'],
            'product_type': p['product_type'],
            'jd': {
                'id': p['jd_id'],
                'product_id': p['jd_product_id'],
                'title': p['jd_title'],
                'image': p['jd_image'],
                'price': p['jd_price'],
                'date': p['jd_date']
            },
            'tmall': {
                'id': p['tmall_id'],
                'product_id': p['tmall_product_id'],
                'title': p['tmall_title'],
                'image': p['tmall_image'],
                'price': p['tmall_price'],
                'date': p['tmall_date']
            }
        })
    
    return jsonify(result)


@app.route('/api/summary-create', methods=['POST'])
def api_summary_create():
    """创建总表记录（关联京东和天猫商品）"""
    data = request.json
    
    jd_product_id = data.get('jd_product_id')  # 可以为None
    tmall_product_id = data.get('tmall_product_id')  # 可以为None
    product_name = data.get('product_name')
    product_type = data.get('product_type')
    
    if not product_name:
        return jsonify({'error': '产品名称不能为空'}), 400
    
    conn = get_db()
    
    try:
        conn.execute('''
            INSERT INTO products_summary (product_name, product_type, jd_product_id, tmall_product_id)
            VALUES (?, ?, ?, ?)
        ''', (product_name, product_type, jd_product_id, tmall_product_id))
        conn.commit()
        new_id = conn.execute('SELECT last_insert_rowid()').fetchone()[0]
        conn.close()
        return jsonify({'success': True, 'id': new_id})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/summary-update', methods=['POST'])
def api_summary_update():
    """更新总表记录"""
    data = request.json
    
    record_id = data.get('id')
    product_name = data.get('product_name')
    product_type = data.get('product_type')
    jd_product_id = data.get('jd_product_id')
    tmall_product_id = data.get('tmall_product_id')
    
    if not record_id:
        return jsonify({'error': '记录ID不能为空'}), 400
    
    conn = get_db()
    
    try:
        conn.execute('''
            UPDATE products_summary
            SET product_name = ?, product_type = ?, jd_product_id = ?, tmall_product_id = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (product_name, product_type, jd_product_id, tmall_product_id, record_id))
        conn.commit()
        conn.close()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/summary-delete', methods=['POST'])
def api_summary_delete():
    """删除总表记录"""
    data = request.json
    
    record_id = data.get('id')
    
    if not record_id:
        return jsonify({'error': '记录ID不能为空'}), 400
    
    conn = get_db()
    
    try:
        conn.execute('DELETE FROM products_summary WHERE id = ?', (record_id,))
        conn.commit()
        conn.close()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/summary-jd-options')
def api_summary_jd_options():
    """获取京东商品列表（用于选择）"""
    conn = get_db()
    
    products = conn.execute('''
        SELECT id, product_id, title, style_name, level, price,
               (SELECT created_at FROM jd_price_history WHERE product_id = jd_products.id ORDER BY created_at DESC LIMIT 1) AS latest_date
        FROM jd_products
        ORDER BY id DESC
    ''').fetchall()
    
    conn.close()
    
    result = []
    for p in products:
        result.append({
            'id': p['id'],
            'product_id': p['product_id'],
            'title': p['title'],
            'style_name': p['style_name'],
            'level': p['level'],
            'price': p['price'],
            'date': p['latest_date']
        })
    
    return jsonify(result)


@app.route('/api/summary-tmall-options')
def api_summary_tmall_options():
    """获取天猫商品列表（用于选择）"""
    conn = get_db()
    
    products = conn.execute('''
        SELECT id, product_id, title, style_name, level, price,
               (SELECT created_at FROM tmall_price_history WHERE product_id = tmall_products.id ORDER BY created_at DESC LIMIT 1) AS latest_date
        FROM tmall_products
        ORDER BY id DESC
    ''').fetchall()
    
    conn.close()
    
    result = []
    for p in products:
        result.append({
            'id': p['id'],
            'product_id': p['product_id'],
            'title': p['title'],
            'style_name': p['style_name'],
            'level': p['level'],
            'price': p['price'],
            'date': p['latest_date']
        })
    
    return jsonify(result)


if __name__ == '__main__':
    print("🚀 Transformers 价格追踪系统")
    print("📍 访问地址: http://localhost:8080")
    app.run(host='0.0.0.0', port=8080, debug=True)
