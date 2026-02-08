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


def run_js(js_code):
    with open('/tmp/tmall_spider.js', 'w') as f:
        f.write(js_code)
    
    cmd = '''osascript <<'AS'
tell application "Safari"
    set jsFile to "/tmp/tmall_spider.js"
    set js to do shell script "cat " & quoted form of jsFile
    set theResult to do JavaScript js in current tab of front window
    return theResult
end tell
AS'''
    
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=60)
    return result.stdout.strip()


def check_and_solve_slider():
    """检查并解决滑块验证"""
    js_check = '''var slider = document.querySelector('.nc_wrapper, .nc_iconfont.btn_slide, [class*="slide"], [class*="slider"]');
JSON.stringify({hasSlider: !!slider});'''
    
    result = run_js(js_check)
    
    try:
        data = json.loads(result) if result else {}
        if data.get('hasSlider'):
            print("      ⚠️ 检测到滑块验证！")
            time.sleep(5)  # 等待用户手动解决
    except:
        pass


def scroll_to_bottom():
    """小步滚动到底部，每次间隔2秒"""
    max_scrolls = 100  # 最多滚动100次
    scroll_count = 0
    
    while scroll_count < max_scrolls:
        # 获取当前滚动位置和页面高度
        js = '''var h = {
    scrollTop: document.documentElement.scrollTop || document.body.scrollTop,
    scrollHeight: document.documentElement.scrollHeight || document.body.scrollHeight,
    clientHeight: document.documentElement.clientHeight || document.body.clientHeight
};
JSON.stringify(h);'''
        
        result = run_js(js)
        
        try:
            data = json.loads(result) if result else {}
            current_scroll = data.get('scrollTop', 0)
            scroll_height = data.get('scrollHeight', 0)
            client_height = data.get('clientHeight', 0)
            
            # 判断是否到底
            if current_scroll + client_height >= scroll_height - 50:
                print(f"      ✅ 滚动到底部 (第{scroll_count}次)")
                break
            
            # 小步滚动
            js_scroll = 'window.scrollBy(0, 400)'
            run_js(js_scroll)
            
            scroll_count += 1
            time.sleep(2)  # 每次间隔2秒
            
        except Exception as e:
            print(f"      ⚠️ 滚动出错: {e}")
            break
    
    if scroll_count >= max_scrolls:
        print(f"      ⚠️ 达到最大滚动次数 ({max_scrolls})")
    
    time.sleep(3)


def get_products_from_page():
    """从当前页面获取商品列表"""
    scroll_to_bottom()
    
    js = '''var products = [];
var rows = document.querySelectorAll('.item4line1');
for(var r=0; r<rows.length; r++) {
    var row = rows[r];
    var items = row.querySelectorAll('[class*="item"]');
    for(var i=0; i<items.length; i++) {
        var item = items[i];
        var productId = item.getAttribute('data-id');
        if(!productId) continue;
        
        var link = item.querySelector('a');
        var url = link ? link.href : "";
        var img = item.querySelector('img');
        var imgUrl = img ? (img.src || img['data-src'] || img['data-original'] || "") : "";
        var title = img ? (img.alt || img.title || "") : "";
        
        if(productId) {
            products.push({
                id: productId,
                url: url,
                img: imgUrl,
                title: title,
                price: 0,
                status: "pending"
            });
        }
    }
}
JSON.stringify(products);'''
    
    result = run_js(js)
    
    try:
        products = json.loads(result) if result else []
        if products:
            print(f"      🔍 解析到 {len(products)} 个商品")
        return products
    except:
        return []


def get_price_from_detail(url):
    """从详情页获取价格（15-25秒等待）"""
    subprocess.run(['osascript', '-e', f'tell application "Safari" to open location "{url}"'])
    time.sleep(15 + random.uniform(10, 10))
    
    # 检查滑块
    check_and_solve_slider()
    
    # 检查是否预售
    js_check = '''var title = document.querySelector('.mainTitle--R75fTcZL');
var text = title ? title.innerText : "";
JSON.stringify({isPreSale: text.includes("预售") || text.includes("新品"), title: text.substring(0, 50)});'''
    
    result = run_js(js_check)
    
    try:
        data = json.loads(result) if result else {}
        if data.get('isPreSale'):
            print(f"         🚫 预售，跳过")
            subprocess.run(['osascript', '-e', 'tell application "Safari" to close front window'])
            return None, "pending", data.get('title', '')
    except:
        pass
    
    # 获取价格
    js_price = '''var priceElem = document.querySelector('.text--LP7Wf49z');
var priceText = priceElem ? priceElem.innerText : "";
var price = parseFloat(priceText.replace(/[^0-9.]/g, '')) || 0;
JSON.stringify({price: price});'''
    
    result2 = run_js(js_price)
    
    subprocess.run(['osascript', '-e', 'tell application "Safari" to close front window'])
    
    try:
        data = json.loads(result2) if result2 else {}
        return data.get('price', 0), "available", ""
    except:
        return 0, "pending", ""


def save_products(products, shop):
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
        cursor.execute("SELECT id FROM tmall_products WHERE product_id=?", (p['id'],))
        if cursor.fetchone():
            print(f"         ⏭️ 已存在，跳过")
            continue
        
        # 获取价格
        print(f"         获取详情...")
        price, status, title = get_price_from_detail(p['url'])
        
        if price is None:
            print(f"         🚫 预售，跳过")
            continue
        
        print(f"         ✅ ¥{price}")
        
        # 保存商品
        try:
            cursor.execute("""
                INSERT INTO tmall_products 
                    (product_id, product_url, image_url, title, price, status, shop_name, shop_url, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                p['id'], p['url'], p['img'], title or p['title'][:500],
                price, status,
                shop['name'], shop['url'],
                datetime.now().isoformat(), datetime.now().isoformat()
            ))
            conn.commit()
        except Exception as e:
            print(f"         ❌ 保存失败: {e}")
            continue
        
        # 获取自增ID
        cursor.execute("SELECT id FROM tmall_products WHERE product_id=?", (p['id'],))
        result = cursor.fetchone()
        product_row_id = result[0] if result else None
        
        # 保存价格历史
        if price > 0 and product_row_id:
            cursor.execute("SELECT id FROM tmall_price_history WHERE product_id=? AND created_at=?", 
                          (product_row_id, today))
            if not cursor.fetchone():
                try:
                    cursor.execute("""
                        INSERT INTO tmall_price_history (product_id, product_url, price, created_at)
                        VALUES (?, ?, ?, ?)
                    """, (product_row_id, p['url'], price, today))
                    conn.commit()
                except:
                    pass
        
        new_count += 1
    
    conn.close()
    return new_count, style_count


def go_to_shop(shop):
    subprocess.run(['osascript', '-e', f'tell application "Safari" to open location "{shop["url"]}"'])
    time.sleep(15 + random.uniform(5, 5))
    check_and_solve_slider()


def crawl_shop(shop):
    print(f"\n{'='*80}")
    print(f"🏪 {shop['name']}")
    print(f"{'='*80}")
    
    print(f"\nOpening shop...")
    go_to_shop(shop)
    
    print(f"\nParsing products...")
    products = get_products_from_page()
    
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
    
    conn.close()
    
    print(f"\n" + "="*80)
    print("Final Stats")
    print("="*80)
    print(f"  Total: {total_products} | New: {total_new}")
    print(f"  Available: {available_count} | Pending: {pending_count}")
    print(f"  History: {history}")
    print(f"\nDone!")
    print("="*80)


if __name__ == '__main__':
    main()
