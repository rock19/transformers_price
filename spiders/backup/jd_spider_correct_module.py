#!/usr/bin/env python3
"""
京东爬虫 - 正确模块版
从 module-function="saleAttent" module-param="*product*" 模块提取
"""

import subprocess
import sqlite3
import re
import time
import random
import base64
import json
from datetime import datetime

DB_PATH = 'data/transformers.db'
SHOP_URL = 'https://mall.jd.com/view_search-396211-17821117-99-1-20-1.html'


def random_wait(min_sec=5, max_sec=15):
    wait_time = random.uniform(min_sec, max_sec)
    print(f"   ⏳ 等待 {wait_time:.1f} 秒...")
    time.sleep(wait_time)


def run_js(js_code):
    """执行 JavaScript（通过 base64 编码）"""
    js_bytes = js_code.encode('utf-8')
    js_base64 = base64.b64encode(js_bytes).decode('ascii')
    
    cmd = f'''osascript -e "tell application \\"Safari\\" to do JavaScript (do shell script \\"echo {js_base64} | base64 -d\\") in current tab of front window"'''
    
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=60)
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
    """
    从正确的模块提取商品
    模块: <div class="j-module" module-function="saleAttent" module-param="*product*">
    标题来源: <img alt=""> 或 <a> innerText
    """
    js_code = '''
var m = document.querySelector('.j-module[module-function*=saleAttent][module-param*=product]');
var products = [];
if(m) {
    var items = m.querySelectorAll('.jItem');
    for(var i=0; i<items.length; i++) {
        var item = items[i];
        var link = item.querySelector('.jDesc a');
        var img = item.querySelector('.jPic img');
        
        var url = link ? link.href : '';
        var idMatch = url.match(/item.jd.com\\/(\\d+).html/);
        var productId = idMatch ? idMatch[1] : '';
        
        // 标题从 img alt 或 link innerText 获取
        var title = '';
        if(img && img.alt) {
            title = img.alt;
        } else if(link && link.innerText) {
            title = link.innerText.trim();
        }
        
        if(!title) title = '商品 ' + productId;
        
        // 价格
        var priceElem = item.querySelector('.jdNum');
        var price = 0;
        if(priceElem) {
            var priceText = priceElem.innerText || priceElem.textContent;
            var match = priceText.match(/(\\d+\\.?\\d*)/);
            if(match) price = parseFloat(match[1]);
        }
        
        if(productId) {
            products.push({
                product_id: productId,
                product_url: url,
                title: title,
                price: price
            });
        }
    }
}
JSON.stringify(products);
'''
    
    result = run_js(js_code)
    
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
        cursor.execute("SELECT id FROM jd_products WHERE product_id=?", (p['product_id'],))
        if not cursor.fetchone():
            cursor.execute("""
                INSERT INTO jd_products 
                    (product_id, product_url, title, price, shop_name, shop_url, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (p['product_id'], p['product_url'], p['title'][:500],
                  p.get('price', 0), shop_name, shop_url,
                  datetime.now().isoformat(), datetime.now().isoformat()))
            new_count += 1
        else:
            # 更新价格
            if p.get('price', 0) > 0:
                cursor.execute("UPDATE jd_products SET price=?, updated_at=? WHERE product_id=?",
                              (p['price'], datetime.now().isoformat(), p['product_id']))
    
    conn.commit()
    conn.close()
    return new_count


def main():
    print("\n" + "="*80)
    print("🚀 京东爬虫 - 正确模块版")
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
    
    # 去重
    seen = set()
    unique_products = []
    for p in products:
        if p['product_id'] not in seen:
            seen.add(p['product_id'])
            unique_products.append(p)
    
    print(f"   📦 去重后 {len(unique_products)} 个商品\n")
    
    # 显示商品
    for i, p in enumerate(unique_products, 1):
        price_str = f"¥{p.get('price', 0)}" if p.get('price', 0) > 0 else "¥?"
        print(f"   {i:2}. [{p['product_id']}] {p['title'][:40]}... {price_str}")
    
    # 保存
    new_count = save_to_db(unique_products, shop_name, shop_url)
    print(f"\n   ✅ 保存 {new_count} 个新商品")
    
    # 关闭
    print(f"\n🛑 关闭浏览器...")
    subprocess.run(['osascript', '-e', 'tell application "Safari" to close front window'])
    
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
