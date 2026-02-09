#!/usr/bin/env python3
"""
天猫爬虫 - 3页策略
1. 打开第1页 → 爬取 → 间隔15-40秒
2. 打开第2页 → 间隔50-70秒 → 刷新 → 爬取 → 间隔15-40秒
3. 打开第3页 → 间隔50-70秒 → 刷新 → 爬取
"""

import subprocess
import sqlite3
import time
import random
import os
from datetime import datetime
from fontTools.ttLib import TTFont

DB_PATH = 'data/transformers.db'
FONT_PATH = 'data/fonts/tmall_price.woff'

# 3个页面URL
PAGES = [
    ("第1页", "https://thetransformers.tmall.com/category.htm?search=y&orderType=hotsell_desc&scene=taobao_shop&pageNo=1"),
    ("第2页", "https://thetransformers.tmall.com/category.htm?search=y&orderType=hotsell_desc&scene=taobao_shop&pageNo=2"),
    ("第3页", "https://thetransformers.tmall.com/category.htm?search=y&orderType=hotsell_desc&scene=taobao_shop&pageNo=3"),
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


def scroll_and_get():
    """滚动页面并获取商品"""
    print("      📜 滚动加载...")
    for _ in range(10):
        run_js('window.scrollBy(0, 500)')
        time.sleep(1.5)
    time.sleep(3)
    
    js = '''var products = [];
var items = document.querySelectorAll("[data-id]");
for(var i=0; i<items.length; i++) {
    var item = items[i];
    var pid = item.getAttribute("data-id");
    if(!pid) continue;
    var link = item.querySelector("a");
    var url = link ? link.href : "";
    if(!url) continue;
    var img = item.querySelector("img");
    var imgUrl = img ? (img.src || img.getAttribute("data-src") || "") : "";
    var title = img ? (img.alt || img.title || "") : "";
    var priceElem = item.querySelector(".c-price") || item.querySelector("[class*='price']");
    var encryptedPrice = priceElem ? priceElem.innerText.trim() : "";
    products.push({id: pid, url: url, img: imgUrl, title: title, encryptedPrice: encryptedPrice});
}
console.log("找到" + products.length + "个商品");
JSON.stringify(products);'''
    
    result = run_js(js)
    try:
        products = eval(result) if result else []
        print(f"      🔍 获取到 {len(products)} 个")
        return products
    except Exception as e:
        print(f"      ❌ 解析失败: {e}")
        return []


def decrypt_price(encrypted):
    if not encrypted:
        return 0
    try:
        font = TTFont(FONT_PATH)
        cmap = font['cmap'].getBestCmap()
        base = {'.':'.', '0':'0', '1':'1', '2':'2', '3':'3', '4':'4', '5':'5', '6':'6', '7':'7', '8':'8', '9':'9'}
        price = ''
        for c in encrypted:
            name = cmap.get(ord(c))
            if name and name in base:
                price += base[name]
        font.close()
        return float(price) if price else 0
    except:
        return 0


def extract_level(title):
    title = title.upper()
    if 'MP-' in title or 'MPG-' in title or '大师级' in title:
        return '大师级'
    elif '泰坦级' in title or title.endswith('L级'):
        return '泰坦级'
    elif '领袖级' in title:
        return '领袖级'
    elif '航行家级' in title:
        return '航行家级'
    elif '加强级' in title or title.endswith('C级'):
        return '加强级'
    elif '核心级' in title:
        return '核心级'
    return ''


def save_products(products, page_name):
    if not products:
        return 0
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    new_count = 0
    today = datetime.now().strftime('%Y%m%d')
    
    for i, p in enumerate(products, 1):
        print(f"  [{i}/{len(products)}] {p['id']}")
        
        cursor.execute("SELECT id FROM tmall_products WHERE product_id=?", (p['id'],))
        if cursor.fetchone():
            print(f"    ⏭️ 已存在")
            continue
        
        price = decrypt_price(p.get('encryptedPrice', ''))
        if price == 0:
            print(f"    ⚠️ 无价格")
            continue
        
        level = extract_level(p.get('title', ''))
        if level:
            print(f"    ✅ ¥{price} 🏷️ {level}")
        else:
            print(f"    ✅ ¥{price}")
        
        try:
            cursor.execute("""
                INSERT INTO tmall_products 
                    (product_id, product_url, image_url, title, price, status, shop_name, shop_url, level, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                p['id'], p['url'], p['img'], p['title'][:500],
                price, 'available',
                "变形金刚玩具旗舰店", PAGES[int(page_name[-1])-1][1], level,
                datetime.now().isoformat(), datetime.now().isoformat()
            ))
            
            cursor.execute("SELECT id FROM tmall_products WHERE product_id=?", (p['id'],))
            row_id = cursor.fetchone()[0]
            
            cursor.execute("SELECT id FROM tmall_price_history WHERE product_id=? AND created_at=?", (row_id, today))
            if not cursor.fetchone():
                cursor.execute("INSERT INTO tmall_price_history VALUES (?, ?, ?, ?, ?)",
                            (None, row_id, p['url'], price, today))
            
            conn.commit()
            new_count += 1
        except Exception as e:
            print(f"    ❌ 失败: {e}")
    
    conn.close()
    return new_count


def main():
    print("="*60)
    print("🚀 天猫爬虫 - 3页策略")
    print("="*60)
    
    # 加载字体
    try:
        font = TTFont(FONT_PATH)
        font.close()
        print("✅ 字体加载成功\n")
    except:
        print("⚠️ 字体加载失败\n")
    
    total_new = 0
    
    for idx, (name, url) in enumerate(PAGES):
        print(f"\n{'='*60}")
        print(f"📄 {name}")
        print(f"{'='*60}")
        
        # 打开页面
        print(f"🔗 打开页面...")
        subprocess.run(['osascript', '-e', f'tell application "Safari" to make new document with properties {{URL:"{url}"}}'])
        
        # 第1页：间隔15-40秒后打开第2页
        if idx == 0:
            wait = random.uniform(15, 40)
            print(f"⏰ 等待 {wait:.0f} 秒...")
            time.sleep(wait)
        # 第2页：间隔50-70秒后刷新
        elif idx == 1:
            wait = random.uniform(50, 70)
            print(f"⏰ 等待 {wait:.0f} 秒后刷新...")
            time.sleep(wait)
            print("🔄 刷新页面...")
            subprocess.run(['osascript', '-e', 'tell application "Safari" to do JavaScript "location.reload()" in current tab of front window'])
            time.sleep(15)
        # 第2页和第3页之间：间隔15-40秒
        elif idx == 2:
            wait = random.uniform(15, 40)
            print(f"⏰ 等待 {wait:.0f} 秒...")
            time.sleep(wait)
            # 第3页：间隔50-70秒后刷新
            wait = random.uniform(50, 70)
            print(f"⏰ 等待 {wait:.0f} 秒后刷新...")
            time.sleep(wait)
            print("🔄 刷新页面...")
            subprocess.run(['osascript', '-e', 'tell application "Safari" to do JavaScript "location.reload()" in current tab of front window'])
            time.sleep(15)
        
        # 等待页面加载
        print("⏳ 等待页面加载...")
        time.sleep(20 + random.uniform(5, 10))
        
        # 爬取数据
        products = scroll_and_get()
        
        if products:
            new = save_products(products, name)
            total_new += new
            print(f"  📦 新增 {new} 个")
        else:
            print(f"  ⚠️ 无数据")
    
    # 关闭Safari
    subprocess.run(['osascript', '-e', 'tell application "Safari" to close every window'])
    
    # 统计
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM tmall_products")
    total = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM tmall_products WHERE price > 0")
    with_price = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM tmall_products WHERE level != ''")
    with_level = cursor.fetchone()[0]
    conn.close()
    
    print(f"\n" + "="*60)
    print("📊 最终统计")
    print("="*60)
    print(f"  总商品: {total}")
    print(f"  有价格: {with_price}")
    print(f"  有级别: {with_level}")
    print(f"  本次新增: {total_new}")
    print("="*60)


if __name__ == '__main__':
    main()
