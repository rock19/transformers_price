#!/usr/bin/env python3
"""
京东爬虫 - 正确解析版
1. 从列表页获取商品信息（标题、URL）
2. 进入详情页获取价格（价格动态加载）
"""

import subprocess
import sqlite3
import re
import time
import random
import json
from datetime import datetime
from html import unescape

DB_PATH = 'data/transformers.db'
SHOP_URL = 'https://mall.jd.com/view_search-396211-17821117-99-1-20-1.html'


def random_wait(min_sec=5, max_sec=15):
    wait_time = random.uniform(min_sec, max_sec)
    print(f"   ⏳ 等待 {wait_time:.1f} 秒...")
    time.sleep(wait_time)


def run_js_apple(js_code):
    """使用 AppleScript 执行 JavaScript"""
    script = f'''tell application "Safari"
        set js to "{js_code}"
        return do JavaScript js in current tab of front window
    end tell'''
    result = subprocess.run(['osascript', '-e', script], capture_output=True, text=True, timeout=60)
    return result.stdout.strip()


def run_js(code):
    """主函数：执行 JavaScript"""
    return run_js_apple(code)


def get_shop_info():
    """获取店铺信息"""
    title = run_js("document.title")
    
    shop_name = ""
    shop_url = ""
    
    title_match = re.search(r'-\s*([^京东]+?)\s*京东$', title)
    if title_match:
        shop_name = title_match.group(1).strip()
    
    shop_url_match = re.search(r'(https?://mall\.jd\.com/index-\d+\.html)', title)
    if shop_url_match:
        shop_url = shop_url_match.group(1)
    
    return shop_name, shop_url


def get_products_list():
    """从列表页获取商品信息"""
    # 获取商品数量
    count = run_js("document.querySelectorAll('.jItem').length")
    try:
        count = int(float(count))
    except:
        count = 0
    
    print(f"   📦 找到 {count} 个商品")
    
    if count == 0:
        return []
    
    # 获取所有商品信息
    js = f'''
    var items = document.querySelectorAll('.jItem');
    var products = [];
    for(var i=0; i<items.length; i++) {{
        var item = items[i];
        var desc = item.querySelector('.jDesc');
        var link = item.querySelector('.jDesc a');
        
        var url = link ? link.href : '';
        var idMatch = url.match(/item.jd.com\\/(\\d+).html/);
        var productId = idMatch ? idMatch[1] : '';
        
        var title = '商品 ' + productId;
        if(desc && desc.title) {{
            title = desc.title;
        }} else if(link && link.innerText) {{
            title = link.innerText.trim();
        }}
        
        if(productId) {{
            products.push({{
                product_id: productId,
                product_url: url,
                title: title
            }});
        }}
    }}
    JSON.stringify(products);
    '''
    
    result = run_js(js)
    
    try:
        products = json.loads(result) if result else []
        return products
    except Exception as e:
        print(f"   ⚠️ 解析失败: {e}")
        return []


def get_detail_price(url):
    """从详情页获取价格"""
    # 先打开详情页
    subprocess.run(['osascript', '-e', f'tell application "Safari" to open location "{url}"'])
    random_wait(5, 8)
    
    # 获取价格
    js = '''
    var price = 0;
    var priceElem = document.querySelector('.jd-price .price') || document.querySelector('.p-price i') || document.querySelector('[class*="price"]');
    if(priceElem) {
        var text = priceElem.innerText || priceElem.textContent;
        var match = text.match(/(\\d+\\.?\\d*)/);
        if(match) price = parseFloat(match[1]);
    }
    // 备选：从页面文本查找
    if(price === 0) {
        var bodyText = document.body.innerText;
        var priceMatch = bodyText.match(/[¥￥](\\d+\\.?\\d*)/);
        if(priceMatch) price = parseFloat(priceMatch[1]);
    }
    price;
    '''
    
    result = run_js(js)
    
    try:
        price = float(result) if result else 0.0
        return price
    except:
        return 0.0


def save_to_db(products, shop_name, shop_url):
    """保存到数据库"""
    if not products:
        return 0
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    new_count = 0
    for p in products:
        cursor.execute("SELECT id FROM jd_products WHERE product_id=?", (p['product_id'],))
        if not cursor.fetchone():
            cursor.execute("""
                INSERT INTO jd_products 
                    (product_id, product_url, title, shop_name, shop_url, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (p['product_id'], p['product_url'], p['title'][:500],
                  shop_name, shop_url, datetime.now().isoformat(), datetime.now().isoformat()))
            new_count += 1
    
    conn.commit()
    conn.close()
    return new_count


def update_price(product_id, price):
    """更新价格"""
    if price <= 0:
        return
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("UPDATE jd_products SET price=?, updated_at=? WHERE product_id=?",
                   (price, datetime.now().isoformat(), product_id))
    conn.commit()
    conn.close()


def go_back():
    """返回"""
    run_js("history.back()")


def main():
    print("\n" + "="*80)
    print("🚀 京东爬虫 - 正确解析版")
    print("="*80)
    
    print("\n🛒 打开店铺...")
    subprocess.run(['osascript', '-e', f'tell application "Safari" to open location "{SHOP_URL}"'])
    
    random_wait(8, 12)
    
    # 获取店铺信息
    shop_name, shop_url = get_shop_info()
    print(f"   店铺: {shop_name or '未知'}")
    
    # 登录检查
    is_login = 'true' in run_js("document.cookie.indexOf('pin=') >= 0")
    print(f"   登录: {'✅' if is_login else '❌'}")
    
    # 获取商品列表
    print(f"\n📄 解析商品列表...")
    products = get_products_list()
    
    if not products:
        print("   ⚠️ 未找到商品")
        return
    
    # 显示前10个商品
    print(f"\n   前10个商品:")
    for i, p in enumerate(products[:10], 1):
        print(f"   {i:2}. [{p['product_id']}] {p['title'][:40]}...")
    
    # 保存
    new_count = save_to_db(products, shop_name, shop_url)
    print(f"\n   ✅ 保存 {new_count} 个新商品")
    
    # 关闭
    print(f"\n🛑 关闭浏览器...")
    subprocess.run(['osascript', '-e', 'tell application "Safari" to close front window'])
    
    # 统计
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM jd_products")
    total = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM jd_products WHERE price > 0")
    with_price = cursor.fetchone()[0]
    conn.close()
    
    print(f"\n" + "="*80)
    print("📊 统计")
    print("="*80)
    print(f"   商品: {total} 个")
    print(f"   有价格: {with_price} 个")
    print(f"\n✅ 完成!")
    print("="*80)


if __name__ == '__main__':
    random.seed()
    main()
