#!/usr/bin/env python3
"""
京东爬虫 - 最终版
使用 osascript <<'AS' 语法执行 JavaScript
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
    """从正确的模块提取商品"""
    js = '''var m = document.querySelector(".j-module[module-function*=saleAttent][module-param*=product]");
var items = m ? m.querySelectorAll(".jItem") : [];
var products = [];
for(var i=0; i<items.length; i++) {
    var img = items[i].querySelector(".jPic img");
    var url = img ? img.parentElement.href : "";
    var idMatch = url.match(/item.jd.com\\/(\\d+).html/);
    if(idMatch) {
        products.push({
            id: idMatch[1],
            title: (img ? img.alt : "NO_TITLE").substring(0, 40),
            url: url
        });
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


def get_detail_price():
    """从详情页获取价格"""
    js = '''var price = 0;
var selectors = ['.p-price i', '.jd-price', '.price', '[class*="price"]'];
for(var i=0; i<selectors.length; i++) {
    var elem = document.querySelector(selectors[i]);
    if(elem) {
        var text = elem.innerText || elem.textContent;
        var match = text.match(/(\\d+\\.?\\d*)/);
        if(match) { price = parseFloat(match[1]); break; }
    }
}
if(price === 0) {
    var bodyText = document.body.innerText;
    var matches = bodyText.match(/[¥￥](\\d+\\.?\\d*)/g);
    if(matches) {
        for(var j=0; j<matches.length; j++) {
            var p = parseFloat(matches[j].replace(/[¥￥]/, ''));
            if(p > 10 && p < 10000) { price = p; break; }
        }
    }
}
price;'''
    
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
        cursor.execute("SELECT id FROM jd_products WHERE product_id=?", (p['id'],))
        if not cursor.fetchone():
            cursor.execute("""
                INSERT INTO jd_products 
                    (product_id, product_url, title, shop_name, shop_url, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (p['id'], p['url'], p['title'], shop_name, shop_url,
                  datetime.now().isoformat(), datetime.now().isoformat()))
            new_count += 1
    
    conn.commit()
    conn.close()
    return new_count


def update_price(product_id, price):
    if price <= 0:
        return
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("UPDATE jd_products SET price=?, updated_at=? WHERE product_id=?",
                   (price, datetime.now().isoformat(), product_id))
    conn.commit()
    conn.close()


def main():
    print("\n" + "="*80)
    print("🚀 京东爬虫 - 最终版")
    print("="*80)
    
    # 打开店铺
    print("\n🛒 打开店铺...")
    subprocess.run(['open', '-a', 'Safari', SHOP_URL])
    
    random_wait(12, 18)
    
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
    
    print(f"   📦 获取 {len(products)} 个商品\n")
    
    # 显示商品
    for i, p in enumerate(products, 1):
        print(f"   {i:2}. [{p['id']}] {p['title']}...")
    
    # 保存
    new_count = save_to_db(products, shop_name, shop_url)
    print(f"\n   ✅ 保存 {new_count} 个新商品")
    
    # 关闭
    print(f"\n🛑 关闭浏览器...")
    subprocess.run(['osascript', '-e', 'tell application "Safari" to close every window'])
    
    # 统计
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM jd_products")
    total = cursor.fetchone()[0]
    conn.close()
    
    print(f"\n" + "="*80)
    print("📊 统计")
    print("="*80)
    print(f"   商品: {total} 个")
    print(f"\n✅ 完成!")
    print("="*80)


if __name__ == '__main__':
    random.seed()
    main()
