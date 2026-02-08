#!/usr/bin/env python3
"""
京东爬虫 - 完整版（包含款式名称）
"""

import subprocess
import sqlite3
import time
import random
import json
from datetime import datetime

DB_PATH = 'data/transformers.db'
BASE_URL = 'https://mall.jd.com/view_search-396211-17821117-{}-1-20-{}.html'


def random_wait(min_sec=3, max_sec=5):
    wait_time = random.uniform(min_sec, max_sec)
    print(f"   waiting {wait_time:.1f}s...")
    time.sleep(wait_time)


def run_js(js_code):
    with open('/tmp/jd_spider.js', 'w') as f:
        f.write(js_code)
    
    cmd = '''osascript <<'AS'
tell application "Safari"
    set jsFile to "/tmp/jd_spider.js"
    set js to do shell script "cat " & quoted form of jsFile
    set result to do JavaScript js in current tab of front window
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
    
    js = '''var m = document.querySelector(".j-module[module-function*=saleAttent][module-param*=product]");
var products = [];
if(m) {
    var items = m.querySelectorAll(".jItem");
    for(var i=0; i<items.length; i++) {
        var item = items[i];
        var img = item.querySelector(".jPic img");
        var link = item.querySelector(".jDesc a");
        var url = link ? link.href : "";
        var idMatch = url.match(/item.jd.com\\/(\\d+).html/);
        var id = idMatch ? idMatch[1] : "";
        var title = img ? img.alt : "";
        var imgUrl = img ? img.src : "";
        if(imgUrl) imgUrl = imgUrl.replace(/\\/n\\d+\\_/, '/n0_');
        var priceElem = item.querySelector(".jdNum");
        var preprice = priceElem ? priceElem.getAttribute("preprice") : null;
        var hidePrice = priceElem ? priceElem.getAttribute("data-hide-price") : null;
        
        if(preprice && parseFloat(preprice) > 0) {
            products.push({id: id, url: url, img: imgUrl, title: title, price: parseFloat(preprice), status: "available"});
        } else if(hidePrice === "true") {
            products.push({id: id, url: url, img: imgUrl, title: title, price: 0, status: "pending"});
        }
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
    
    # 获取款式名称
    js = '''var selected = document.querySelector('.specification-item-sku.has-image.specification-item-sku--selected');
var textElem = selected ? selected.querySelector('.specification-item-sku-text') : null;
textElem ? textElem.innerText.trim() : 'NOT_FOUND';'''
    
    result = run_js(js)
    
    # 关闭详情页
    subprocess.run(['osascript', '-e', 'tell application "Safari" to close front window'])
    
    if result and result != 'NOT_FOUND':
        return result
    return ''


def save_products(products, page_num):
    """保存商品到数据库"""
    if not products:
        return 0, 0
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    new_count = 0
    style_count = 0
    today = datetime.now().strftime('%Y%m%d')
    
    for i, p in enumerate(products, 1):
        print(f"      [{i}/{len(products)}] {p['id']}")
        
        # 检查是否已存在
        cursor.execute("SELECT id, style_name FROM jd_products WHERE product_id=?", (p['id'],))
        existing = cursor.fetchone()
        
        if existing:
            # 如果已有商品，检查是否需要获取款式名称
            if existing[1] is None or existing[1] == '':
                # 获取款式名称
                if p['status'] == 'available':
                    print(f"         Getting style name...")
                    style = get_style_name(p['url'])
                    if style:
                        cursor.execute("UPDATE jd_products SET style_name=?, updated_at=? WHERE product_id=?",
                            (style, datetime.now().isoformat(), p['id']))
                        print(f"         ✅ {style}")
                        style_count += 1
            continue
        
        # 获取款式名称（仅对有价格的商品）
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
                INSERT INTO jd_products 
                    (product_id, product_url, image_url, title, price, status, shop_name, shop_url, style_name, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                p['id'], p['url'], p['img'], p['title'][:500],
                p['price'], p['status'],
                "孩之宝京东自营旗舰店", BASE_URL.format('17821117', page_num),
                style_name,
                datetime.now().isoformat(), datetime.now().isoformat()
            ))
            conn.commit()  # 每条记录立即提交
        except Exception as e:
            print(f"         ❌ 保存商品失败: {e}")
            continue
        
        # 获取刚插入商品的 id（自增主键）
        cursor.execute("SELECT id FROM jd_products WHERE product_id=?", (p['id'],))
        result = cursor.fetchone()
        product_row_id = result[0] if result else None
        
        # 保存到价格历史表（用 jd_products.id 作为外键）
        if p['status'] == 'available' and product_row_id:
            try:
                cursor.execute("""
                    INSERT INTO jd_price_history (product_id, product_url, price, style_name, created_at)
                    VALUES (?, ?, ?, ?, ?)
                """, (product_row_id, p['url'], p['price'], style_name, today))
                conn.commit()  # 每条记录立即提交
            except Exception as e:
                print(f"         ❌ 保存价格历史失败: {e}")
        
        new_count += 1
    
    conn.close()
    return new_count, style_count


def go_to_page(page_num):
    url = BASE_URL.format('17821117', page_num)
    subprocess.run(['osascript', '-e', f'tell application "Safari" to open location "{url}"'])
    random_wait(15, 20)


def main():
    print("\n" + "="*80)
    print("JD Spider - With Style Names")
    print("="*80)
    
    total_products = 0
    total_new = 0
    total_styles = 0
    
    for page in range(1, 8):
        print(f"\n{'='*80}")
        print(f"Page {page}")
        print("="*80)
        
        print(f"\nOpening page {page}...")
        go_to_page(page)
        
        print(f"\nParsing products...")
        products = get_products_from_page()
        print(f"Found {len(products)} products")
        
        available = sum(1 for p in products if p['status'] == 'available')
        pending = sum(1 for p in products if p['status'] == 'pending')
        print(f"Available: {available} | Pending: {pending}")
        
        print(f"\nSaving products...")
        new_count, style_count = save_products(products, page)
        total_products += len(products)
        total_new += new_count
        total_styles += style_count
        
        for i, p in enumerate(products[:3], 1):
            status = 'OK' if p['status'] == 'available' else 'WAIT'
            price = f"¥{p['price']}" if p['status'] == 'available' else 'TBD'
            print(f"  {i}. {p['id']} [{status}] {price}")
        
        if len(products) > 3:
            print(f"  ... and {len(products) - 3} more")
    
    print(f"\nClosing browser...")
    subprocess.run(['osascript', '-e', 'tell application "Safari" to close every window'])
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM jd_products")
    total = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM jd_price_history")
    history = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM jd_products WHERE status='available'")
    available_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM jd_products WHERE status='pending'")
    pending_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM jd_products WHERE style_name IS NOT NULL AND style_name != ''")
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
