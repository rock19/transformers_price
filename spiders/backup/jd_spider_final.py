#!/usr/bin/env python3
"""
京东爬虫 - 完整版
1. 遍历商品列表
2. 待发布的商品直接跳过（不进入详情页，不保存）
3. 有价格的商品获取款式名称后保存
4. 同时保存价格历史
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
    script = f'''osascript <<'AS'
tell application "Safari"
    set jsFile to "/tmp/jd_spider.js"
    set js to do shell script "cat " & quoted form of jsFile
    set result to do JavaScript js in current tab of front window
    return result
end tell
AS'''
    
    with open('/tmp/jd_spider.js', 'w') as f:
        f.write(js_code)
    
    result = subprocess.run(script, shell=True, capture_output=True, text=True, timeout=60)
    return result.stdout.strip()


def check_exists(product_id):
    """检查商品是否已存在"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM jd_products WHERE product_id=?", (product_id,))
    exists = cursor.fetchone() is not None
    conn.close()
    return exists


def save_product(product):
    """保存商品和价格历史"""
    if not product['price'] or product['price'] <= 0:
        print(f"      ⏭️ 待发布，跳过")
        return False
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    today = datetime.now().strftime('%Y-%m-%d')
    
    # 检查是否已存在
    cursor.execute("SELECT id FROM jd_products WHERE product_id=?", (product['id'],))
    if cursor.fetchone():
        print(f"      ⏭️ 已存在，跳过")
        conn.close()
        return False
    
    # 保存商品
    cursor.execute("""
        INSERT INTO jd_products 
            (product_id, product_url, image_url, title, price, status, shop_name, shop_url, style_name, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        product['id'], product['url'], product['img'], product['title'][:500],
        product['price'], 'available',
        "孩之宝京东自营旗舰店", SHOP_URL,
        product.get('style_name', ''),
        datetime.now().isoformat(), datetime.now().isoformat()
    ))
    
    # 保存价格历史
    try:
        cursor.execute("""
            INSERT INTO jd_price_history (product_id, price, price_date, captured_at)
            VALUES (?, ?, ?, ?)
        """, (product['id'], product['price'], today, datetime.now().isoformat()))
        print(f"      💾 价格历史已保存")
    except sqlite3.IntegrityError:
        print(f"      ⚠️ 今天价格已存在")
    
    conn.commit()
    conn.close()
    return True


def get_products_from_list():
    """从列表页获取商品"""
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
        var idMatch = url.match(/item.jd.com/(\\d+).html/);
        var id = idMatch ? idMatch[1] : "";
        
        var title = img ? img.alt : (link ? link.innerText.trim() : "");
        
        var imgUrl = img ? img.src : "";
        if(imgUrl) imgUrl = imgUrl.replace(/\\/n\\d+\\_/, '/n0_');
        
        // 价格
        var price = 0;
        if(priceElem) {
            var preprice = priceElem.getAttribute("preprice");
            if(preprice && parseFloat(preprice) > 0) {
                price = parseFloat(preprice);
            }
        }
        
        if(id && url) {
            products.push({id: id, url: url, img: imgUrl, title: title, price: price});
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
    random_wait(5, 8)
    
    js = '''var selected = document.querySelector('.specification-item-sku.has-image.specification-item-sku--selected');
var textElem = selected ? selected.querySelector('.specification-item-sku-text') : null;
textElem ? textElem.innerText.trim() : 'NOT_FOUND';'''
    
    result = run_js(js)
    
    # 关闭详情页
    subprocess.run(['osascript', '-e', 'tell application "Safari" to close front window'])
    
    if result and result != 'NOT_FOUND':
        return result
    return ''


def main():
    print("\n" + "="*80)
    print("🚀 京东爬虫 - 完整版")
    print("="*80)
    
    print("\n🛒 打开店铺...")
    subprocess.run(['open', '-a', 'Safari', SHOP_URL])
    random_wait(12, 18)
    
    # 登录检查
    is_login = 'true' in run_js("document.cookie.indexOf('pin=') >= 0")
    print(f"   登录: {'✅' if is_login else '❌'}")
    
    # 获取商品列表
    print(f"\n📄 解析商品列表...")
    products = get_products_from_list()
    
    if not products:
        print("   ⚠️ 未找到商品")
        return
    
    print(f"   📦 获取 {len(products)} 个商品\n")
    
    new_count = 0
    skip_count = 0
    
    for i, p in enumerate(products, 1):
        print(f"   [{i}/{len(products)}] {p['id']}")
        
        # 待发布直接跳过
        if not p['price'] or p['price'] <= 0:
            print(f"      ⏭️ 待发布，跳过")
            skip_count += 1
            continue
        
        # 检查是否已存在
        if check_exists(p['id']):
            print(f"      ⏭️ 已存在，跳过")
            skip_count += 1
            continue
        
        # 获取款式名称
        print(f"      🔍 获取款式名称...")
        style_name = get_style_name(p['url'])
        p['style_name'] = style_name
        print(f"      ✅ {style_name}" if style_name else "      ⚠️ 无款式")
        
        # 保存商品
        if save_product(p):
            new_count += 1
            print(f"      💾 已保存，价格: ¥{p['price']}")
        else:
            skip_count += 1
    
    # 关闭
    print(f"\n🛑 关闭浏览器...")
    subprocess.run(['osascript', '-e', 'tell application "Safari" to close every window'])
    
    # 统计
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
    print(f"   新增: {new_count} 个")
    print(f"   跳过: {skip_count} 个")
    print(f"   商品表: {total} 个")
    print(f"   价格历史: {history} 条")
    print(f"\n✅ 完成!")
    print("="*80)


if __name__ == '__main__':
    random.seed()
    main()
