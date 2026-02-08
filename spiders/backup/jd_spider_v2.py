#!/usr/bin/env python3
"""
京东爬虫 - 修复版
"""

import subprocess
import sqlite3
import time
import random
import json
from datetime import datetime

DB_PATH = 'data/transformers.db'
SHOP_URL = 'https://mall.jd.com/view_search-396211-17821117-99-1-20-1.html'


def random_wait(min_sec=5, max_sec=15):
    wait_time = random.uniform(min_sec, max_sec)
    print(f"   ⏳ 等待 {wait_time:.1f} 秒...")
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


def get_products():
    js = '''var m = document.querySelector(".j-module[module-function*=saleAttent][module-param*=product]");
var products = [];
if(m) {
    var items = m.querySelectorAll(".jItem");
    for(var i=0; i<items.length; i++) {
        var item = items[i];
        var img = item.querySelector(".jPic img");
        var link = item.querySelector(".jDesc a");
        var priceElem = item.querySelector(".jdNum");
        var url = link ? link.href : "";
        var idMatch = url.match(/item.jd.com\\/(\\d+).html/);
        var id = idMatch ? idMatch[1] : "";
        var title = img ? img.alt : "";
        var imgUrl = img ? img.src : "";
        if(imgUrl) imgUrl = imgUrl.replace(/\\/n\\d+\\_/, '/n0_');
        var preprice = priceElem ? priceElem.getAttribute("preprice") : null;
        var innerText = priceElem ? (priceElem.innerText || "").trim() : "";
        var status = "unknown";
        var price = 0;
        if(preprice && parseFloat(preprice) > 0) {
            status = "available";
            price = parseFloat(preprice);
        } else if(innerText === "待发布") {
            status = "pending";
        } else {
            status = "need_check";
        }
        if(id && url) {
            products.push({id: id, url: url, img: imgUrl, title: title, price: price, status: status});
        }
    }
}
JSON.stringify(products);'''
    
    result = run_js(js)
    try:
        return json.loads(result) if result else []
    except:
        return []


def get_price_from_detail(url):
    subprocess.run(['osascript', '-e', f'tell application "Safari" to open location "{url}"'])
    time.sleep(6)
    
    js_price = '''var priceElem = document.querySelector('span[class*=price], i[class*=price], .p-price span');
if(priceElem) { var text = priceElem.innerText; var match = text.match(/(\\d+\\.?\\d*)/); match ? match[1] : '0'; } else { '0'; }'''
    
    result_price = run_js(js_price)
    price = float(result_price) if result_price and result_price != '0' else 0
    
    js_style = '''var selected = document.querySelector('.specification-item-sku.has-image.specification-item-sku--selected');
var textElem = selected ? selected.querySelector('.specification-item-sku-text') : null;
textElem ? textElem.innerText.trim() : 'NOT_FOUND';'''
    
    result_style = run_js(js_style)
    style = result_style if result_style and result_style != 'NOT_FOUND' else ''
    
    js_pending = '''var text = document.body.innerText;
(text.indexOf('待发布') >= 0 || text.indexOf('即将开始') >= 0) ? 'pending' : 'available';'''
    
    result_pending = run_js(js_pending)
    status = 'pending' if result_pending and 'pending' in result_pending else 'available'
    
    subprocess.run(['osascript', '-e', 'tell application "Safari" to close front window'])
    
    return price, style, status


def save(product):
    if product['status'] == 'pending' or not product['price'] or product['price'] <= 0:
        print(f"      ⏭️ 待发布，跳过")
        return False
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("SELECT id FROM jd_products WHERE product_id=?", (product['id'],))
    if cursor.fetchone():
        print(f"      ⏭️ 已存在，跳过")
        conn.close()
        return False
    
    today = datetime.now().strftime('%Y-%m-%d')
    
    cursor.execute("""
        INSERT INTO jd_products 
            (product_id, product_url, image_url, title, price, status, shop_name, shop_url, style_name, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        product['id'], product['url'], product['img'], product['title'][:500],
        product['price'], 'available',
        "孩之宝京东自营旗舰店", SHOP_URL,
        product.get('style_name', ''),
        datetime.now().isoformat(), datetime.now().isoformat()
    ))
    
    try:
        cursor.execute("""
            INSERT INTO jd_price_history (product_id, price, price_date, captured_at)
            VALUES (?, ?, ?, ?)
        """, (product['id'], product['price'], today, datetime.now().isoformat()))
        print(f"      💾 价格历史已保存")
    except:
        print(f"      ⚠️ 今天价格已存在")
    
    conn.commit()
    conn.close()
    return True


def main():
    print("\n" + "="*80)
    print("🚀 京东爬虫 - 修复版")
    print("="*80)
    
    print("\n🛒 打开店铺...")
    subprocess.run(['open', '-a', 'Safari', SHOP_URL])
    random_wait(12, 18)
    
    print("\n📄 解析商品列表...")
    products = get_products()
    
    if not products:
        print("   ⚠️ 未找到商品")
        return
    
    available = sum(1 for p in products if p.get('status') == 'available')
    pending = sum(1 for p in products if p.get('status') == 'pending')
    need_check = sum(1 for p in products if p.get('status') == 'need_check')
    
    print(f"   📦 获取 {len(products)} 个商品 (有价格: {available}, 待发布: {pending}, 待检查: {need_check})\n")
    
    new_count = 0
    skip_count = 0
    
    for i, p in enumerate(products, 1):
        status_icon = {'available': '✅', 'pending': '⏭️', 'need_check': '🔍'}[p.get('status', 'unknown')]
        print(f"   [{i}/{len(products)}] {p['id']} {status_icon}")
        
        if p.get('status') == 'available':
            print(f"      🔍 获取款式名称...")
            price, style, status = get_price_from_detail(p['url'])
            p['price'] = price
            p['style_name'] = style
            p['status'] = status
            print(f"      ✅ {style} | ¥{price}")
        
        if p.get('status') == 'need_check':
            print(f"      🔍 进入详情页检查...")
            price, style, status = get_price_from_detail(p['url'])
            p['price'] = price
            p['style_name'] = style
            p['status'] = status
            print(f"      { '⏭️ 待发布' if status == 'pending' else '✅ ' + style + ' | ¥' + str(price) }")
        
        if save(p):
            new_count += 1
            print(f"      💾 已保存")
        else:
            skip_count += 1
    
    print(f"\n🛑 关闭浏览器...")
    subprocess.run(['osascript', '-e', 'tell application "Safari" to close every window'])
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM jd_products")
    total = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM jd_price_history")
    history = cursor.fetchone()[0]
    conn.close()
    
    print(f"\n" + "="*80)
    print("📊 统计")
    print("="*80)
    print(f"   新增: {new_count} | 跳过: {skip_count}")
    print(f"   商品表: {total} | 价格历史: {history}")
    print(f"\n✅ 完成!")
    print("="*80)


if __name__ == '__main__':
    random.seed()
    main()
