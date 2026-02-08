#!/usr/bin/env python3
"""
京东爬虫 - 完整版（含价格和状态）
"""

import subprocess
import sqlite3
import re
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
    """执行 JavaScript"""
    script = f'''osascript <<'AS'
tell application "Safari"
    set jsFile to "/tmp/jd_spider_js.js"
    set js to do shell script "cat " & quoted form of jsFile
    set result to do JavaScript js in current tab of front window
    return result
end tell
AS'''
    
    with open('/tmp/jd_spider_js.js', 'w') as f:
        f.write(js_code)
    
    result = subprocess.run(script, shell=True, capture_output=True, text=True, timeout=60)
    return result.stdout.strip()


def get_products():
    """
    获取商品列表（含价格和状态）
    价格在 <span class="jdNum" preprice="价格">
    待发布：data-hide-price="true"
    """
    js = '''var m = document.querySelector(".j-module[module-function*=saleAttent][module-param*=product]");
var products = [];
if(m) {
    var items = m.querySelectorAll(".jItem");
    for(var i=0; i<items.length; i++) {
        var item = items[i];
        var img = item.querySelector(".jPic img");
        var priceElem = item.querySelector(".jdNum");
        var jGoodsInfo = item.querySelector(".jGoodsInfo");
        
        var url = img ? img.parentElement.href : "";
        var idMatch = url.match(/item.jd.com\\/(\\d+).html/);
        var productId = idMatch ? idMatch[1] : "";
        
        var title = img ? img.alt : "";
        if(!title) {
            var link = item.querySelector(".jDesc a");
            title = link ? link.innerText.trim() : "";
        }
        
        // 价格从 preprice 获取
        var price = 0;
        if(priceElem && priceElem.getAttribute("preprice")) {
            var preprice = priceElem.getAttribute("preprice");
            price = parseFloat(preprice) || 0;
        }
        
        // 待发布状态：data-hide-price="true"
        var status = "available";
        if(jGoodsInfo && jGoodsInfo.getAttribute("data-hide-price") === "true") {
            status = "pending";
        }
        // 没有价格也是待发布
        if(price === 0 && status === "available") {
            status = "pending";
        }
        
        if(productId) {
            products.push({
                id: productId,
                title: title,
                url: url,
                price: price,
                status: status
            });
        }
    }
}
JSON.stringify(products);'''
    
    result = run_js(js)
    
    try:
        products = json.loads(result) if result else []
        return products
    except Exception as e:
        print(f"   ⚠️ 解析失败: {e}")
        return []


def save_to_db(products, shop_name, shop_url):
    """保存到数据库"""
    if not products:
        return 0
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    new_count = 0
    for p in products:
        cursor.execute("SELECT id FROM jd_products WHERE product_id=?", (p['id'],))
        if not cursor.fetchone():
            cursor.execute("""
                INSERT INTO jd_products 
                    (product_id, product_url, title, price, status, shop_name, shop_url, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (p['id'], p['url'], p['title'][:500], p['price'], p['status'],
                  shop_name, shop_url, datetime.now().isoformat(), datetime.now().isoformat()))
            new_count += 1
    
    conn.commit()
    conn.close()
    return new_count


def main():
    print("\n" + "="*80)
    print("🚀 京东爬虫 - 完整版（含价格和状态）")
    print("="*80)
    
    # 打开店铺
    print("\n🛒 打开店铺...")
    subprocess.run(['open', '-a', 'Safari', SHOP_URL])
    
    random_wait(12, 18)
    
    # 登录检查
    is_login = 'true' in run_js("document.cookie.indexOf('pin=') >= 0")
    print(f"   登录: {'✅' if is_login else '❌'}")
    
    # 获取商品列表
    print(f"\n📄 解析商品列表...")
    products = get_products()
    
    if not products:
        print("   ⚠️ 未找到商品")
        return
    
    # 统计
    available = sum(1 for p in products if p['status'] == 'available')
    pending = sum(1 for p in products if p['status'] == 'pending')
    
    print(f"   📦 获取 {len(products)} 个商品")
    print(f"   ✅ 在售: {available}")
    print(f"   ⏭️ 待发布: {pending}\n")
    
    # 显示商品
    for i, p in enumerate(products, 1):
        status_mark = "✅" if p['status'] == 'available' else "⏭️"
        price_str = f"¥{p['price']}" if p['price'] > 0 else "待发布"
        print(f"   {status_mark} {i:2}. [{p['id']}] {p['title'][:35]}... {price_str}")
    
    # 保存
    new_count = save_to_db(products, "孩之宝京东自营旗舰店", SHOP_URL)
    print(f"\n   ✅ 保存 {new_count} 个新商品")
    
    # 关闭
    print(f"\n🛑 关闭浏览器...")
    subprocess.run(['osascript', '-e', 'tell application "Safari" to close every window'])
    
    # 统计
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM jd_products")
    total = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM jd_products WHERE status='available'")
    available = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM jd_products WHERE status='pending'")
    pending = cursor.fetchone()[0]
    conn.close()
    
    print(f"\n" + "="*80)
    print("📊 统计")
    print("="*80)
    print(f"   商品: {total} 个")
    print(f"   在售: {available} 个")
    print(f"   待发布: {pending} 个")
    print(f"\n✅ 完成!")
    print("="*80)


if __name__ == '__main__':
    random.seed()
    main()
