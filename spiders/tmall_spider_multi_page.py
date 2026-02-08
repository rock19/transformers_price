#!/usr/bin/env python3
"""
天猫爬虫 - 多店铺版（包含款式名称）
"""

import subprocess
import sqlite3
import time
import random
import json
from datetime import datetime

DB_PATH = 'data/transformers.db'

# 店铺配置：支持多店铺
SHOPS = [
    {
        "name": "变形金刚玩具旗舰店",
        "url": "https://thetransformers.tmall.com/category.htm?spm=a1z10.1-b.w5001-22116109517.10.67755bd938bATH&search=y&orderType=hotsell_desc&scene=taobao_shop"
    }
]


def random_wait(min_sec=3, max_sec=5):
    wait_time = random.uniform(min_sec, max_sec)
    print(f"   waiting {wait_time:.1f}s...")
    time.sleep(wait_time)


def run_js(js_code):
    with open('/tmp/tmall_spider.js', 'w') as f:
        f.write(js_code)
    
    cmd = '''osascript <<'AS'
tell application "Safari"
    set jsFile = "/tmp/tmall_spider.js"
    set js = do shell script "cat " & quoted form of jsFile
    set result = do JavaScript js in current tab of front window
    return result
end tell
AS'''
    
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=60)
    return result.stdout.strip()


def scroll_page():
    """分15次小滚动，每次200像素，间隔1.5秒"""
    for i in range(15):
        js = 'window.scrollBy(0, 200)'
        run_js(js)
        time.sleep(1.5)
    
    time.sleep(5)


def get_products_from_page():
    """从当前页面获取商品ID列表"""
    scroll_page()
    
    # 天猫商品列表的DOM结构需要根据实际页面调整
    js = '''var products = [];
var items = document.querySelectorAll('.item');
if(items.length === 0) {
    items = document.querySelectorAll('[class*="item"]');
}
for(var i=0; i<items.length; i++) {
    var item = items[i];
    var link = item.querySelector('a[href*="item.taobao.com"]');
    var img = item.querySelector('img');
    var priceElem = item.querySelector('[class*="price"]');
    
    var url = link ? link.href : "";
    var idMatch = url.match(/id=(\\d+)/);
    var productId = idMatch ? idMatch[1] : "";
    var title = img ? (img.alt || img.title || "") : "";
    var imgUrl = img ? (img.src || img['data-src'] || "") : "";
    var price = priceElem ? parseFloat(priceElem.innerText.replace(/[^0-9.]/g, '')) : 0;
    
    if(productId) {
        products.push({
            id: productId,
            url: url,
            img: imgUrl,
            title: title,
            price: price,
            status: price > 0 ? "available" : "pending"
        });
    }
}
JSON.stringify(products);'''
    
    result = run_js(js)
    try:
        return json.loads(result) if result else []
    except:
        return []


def get_style_name(product_url):
    """从详情页获取款式名称"""
    # 打开详情页
    subprocess.run(['osascript', '-e', f'tell application "Safari" to open location "{product_url}"'])
    time.sleep(6)
    
    # 获取款式名称（天猫的DOM结构需要调整）
    js = '''var spec = document.querySelector('.tb-sku');
var text = "";
if(spec) {
    var selected = spec.querySelector('.tb-selected');
    if(selected) {
        text = selected.innerText.trim();
    }
}
text || 'NOT_FOUND';'''
    
    result = run_js(js)
    
    # 关闭详情页
    subprocess.run(['osascript', '-e', 'tell application "Safari" to close front window'])
    
    if result and result != 'NOT_FOUND':
        return result
    return ''


def save_products(products, shop):
    """保存商品到数据库（天猫表）
    
    逻辑：
    1. 检查商品是否已存在
    2. 如果已存在：不打开详情页，不重复保存商品，但检查并保存价格历史
    3. 如果不存在：获取款式名称，保存商品，保存价格历史
    4. 同一天同一商品只能有一条价格历史
    """
    if not products:
        return 0, 0
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    new_count = 0
    style_count = 0
    today = datetime.now().strftime('%Y%m%d')
    
    for i, p in enumerate(products, 1):
        print(f"      [{i}/{len(products)}] {p['id']}")
        
        # 检查商品是否已存在
        cursor.execute("SELECT id, style_name FROM tmall_products WHERE product_id=?", (p['id'],))
        existing = cursor.fetchone()
        
        if existing:
            # 已存在商品：不打开详情页
            print(f"         ⏭️ 已存在，跳过详情页")
            
            # 检查并保存价格历史（同一天同一商品只有一条）
            if p['status'] == 'available':
                cursor.execute("""
                    SELECT id FROM tmall_price_history 
                    WHERE product_id=? AND created_at=?
                """, (existing[0], today))
                if cursor.fetchone():
                    print(f"         ⏭️ 今天已有价格记录，跳过")
                else:
                    try:
                        cursor.execute("""
                            INSERT INTO tmall_price_history (product_id, product_url, price, style_name, created_at)
                            VALUES (?, ?, ?, ?, ?)
                        """, (existing[0], p['url'], p['price'], existing[1], today))
                        conn.commit()
                        print(f"         ✅ 新增价格历史")
                    except Exception as e:
                        print(f"         ❌ 保存价格历史失败: {e}")
            continue
        
        # 商品不存在，需要获取款式名称
        style_name = ''
        if p['status'] == 'available':
            print(f"         Getting style name...")
            style_name = get_style_name(p['url'])
            if style_name:
                print(f"         ✅ {style_name}")
                style_count += 1
            else:
                print(f"         ⚠️ No style name")
        else:
            print(f"         ⏭️ Pending, skip")
        
        # 保存商品
        try:
            cursor.execute("""
                INSERT INTO tmall_products 
                    (product_id, product_url, image_url, title, price, status, shop_name, shop_url, style_name, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                p['id'], p['url'], p['img'], p['title'][:500],
                p['price'], p['status'],
                shop['name'], shop['url'],
                style_name,
                datetime.now().isoformat(), datetime.now().isoformat()
            ))
            conn.commit()
        except Exception as e:
            print(f"         ❌ 保存商品失败: {e}")
            continue
        
        # 获取刚插入商品的 id（自增主键）
        cursor.execute("SELECT id FROM tmall_products WHERE product_id=?", (p['id'],))
        result = cursor.fetchone()
        product_row_id = result[0] if result else None
        
        # 保存到价格历史表
        if p['status'] == 'available' and product_row_id:
            try:
                cursor.execute("""
                    INSERT INTO tmall_price_history (product_id, product_url, price, style_name, created_at)
                    VALUES (?, ?, ?, ?, ?)
                """, (product_row_id, p['url'], p['price'], style_name, today))
                conn.commit()
            except Exception as e:
                print(f"         ❌ 保存价格历史失败: {e}")
        
        new_count += 1
    
    conn.close()
    return new_count, style_count


def go_to_shop(shop):
    """打开店铺页面"""
    subprocess.run(['osascript', '-e', f'tell application "Safari" to open location "{shop["url"]}"'])
    random_wait(15, 20)


def crawl_shop(shop):
    """爬取单个店铺"""
    print(f"\n{'='*80}")
    print(f"🏪 {shop['name']}")
    print(f"{'='*80}")
    
    print(f"\nOpening shop...")
    go_to_shop(shop)
    
    print(f"\nParsing products...")
    products = get_products_from_page()
    print(f"Found {len(products)} products")
    
    available = sum(1 for p in products if p['status'] == 'available')
    pending = sum(1 for p in products if p['status'] == 'pending')
    print(f"Available: {available} | Pending: {pending}")
    
    print(f"\nSaving products...")
    new_count, style_count = save_products(products, shop)
    
    return len(products), new_count, style_count


def main():
    print("\n" + "="*80)
    print("🚀 天猫爬虫 - 多店铺版")
    print("="*80)
    
    total_products = 0
    total_new = 0
    total_styles = 0
    
    for shop in SHOPS:
        products, new_count, style_count = crawl_shop(shop)
        total_products += products
        total_new += new_count
        total_styles += style_count
    
    print(f"\nClosing browser...")
    subprocess.run(['osascript', '-e', 'tell application "Safari" to close every window'])
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM tmall_products")
    total = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM tmall_price_history")
    history = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM tmall_products WHERE status='available'")
    available_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM tmall_products WHERE status='pending'")
    pending_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM tmall_products WHERE style_name IS NOT NULL AND style_name != ''")
    styled_count = cursor.fetchone()[0]
    
    conn.close()
    
    print(f"\n" + "="*80)
    print("Final Stats")
    print("="*80)
    print(f"  Total: {total_products} | New: {total_new}")
    print(f"  Available: {available_count} | Pending: {pending_count}")
    print(f"  With Style: {styled_count} | History: {history}")
    print(f"\nDone!")
    print("="*80)


if __name__ == '__main__':
    random.seed()
    main()
