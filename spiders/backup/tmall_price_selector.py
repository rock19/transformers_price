#!/usr/bin/env python3
"""
天猫爬虫 - 多种价格选择器
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

PAGES = [
    ("第1页", "https://thetransformers.tmall.com/category.htm?spm=a1z10.3-b.w5001-22116109517.10.77742409X6wOMa&search=y&orderType=hotsell_desc&scene=taobao_shop"),
    ("第2页", "https://thetransformers.tmall.com/category.htm?spm=a1z10.3-b.w4011-22116109545.508.5ecd2409eajMbv&search=y&orderType=hotsell_desc&scene=taobao_shop&pageNo=2"),
    ("第3页", "https://thetransformers.tmall.com/category.htm?spm=a1z10.3-b.w4011-22116109545.509.1a132409FfGkP2&search=y&orderType=hotsell_desc&scene=taobao_shop&pageNo=3"),
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


def is_login_page():
    """检测是否登录页面"""
    js = '''var isLogin = false;
var url = window.location.href || "";
var title = document.title || "";
var bodyText = document.body ? document.body.innerText || "" : "";
if(url.indexOf("login") > -1 || title.indexOf("登录") > -1 || bodyText.indexOf("密码登录") > -1) {
    isLogin = true;
}
JSON.stringify({isLogin: isLogin});'''
    
    result = run_js(js)
    try:
        data = eval(result) if result else {}
        return data.get('isLogin', False)
    except:
        return False


def find_price_selectors():
    """查找价格元素的所有可能选择器"""
    js = '''var results = {};

// 1. 查找所有包含price的class
var all = document.getElementsByTagName("*");
var priceClasses = {};
for(var i=0; i<all.length; i++) {
    var cls = all[i].className || "";
    if(cls.toLowerCase().indexOf("price") >= 0) {
        priceClasses[cls] = true;
    }
}
results.priceClasses = Object.keys(priceClasses).slice(0, 5);

// 2. 查找包含¥的元素
var yenElements = [];
var all2 = document.querySelectorAll("*");
for(var i=0; i<all2.length; i++) {
    var txt = all2[i].innerText || "";
    if(txt.indexOf("¥") >= 0 && txt.indexOf("¥") < 10) {
        var parent = all2[i].parentElement;
        var pcls = parent ? parent.className : "";
        yenElements.push({class: pcls.substring(0,30), text: txt.substring(0,20)});
    }
}
results.yenElements = yenElements.slice(0, 5);

// 3. 查找第一个商品的价格
var items = document.querySelectorAll("[data-id]");
if(items.length > 0) {
    var firstItem = items[0];
    var children = firstItem.querySelectorAll("*");
    var prices = [];
    for(var i=0; i<children.length; i++) {
        var txt = children[i].innerText || "";
        var cls = children[i].className || "";
        if(txt.indexOf("¥") >= 0) {
            prices.push({class: cls.substring(0,40), text: txt.substring(0,30)});
        }
    }
    results.firstItemPrices = prices.slice(0, 3);
}

console.log(JSON.stringify(results));'''
    
    result = run_js(js)
    try:
        return eval(result) if result else {}
    except:
        return {}


def get_products_with_selector(price_selector):
    """使用指定选择器获取商品"""
    js = f'''var products = [];
var items = document.querySelectorAll("[data-id]");
console.log("找到" + items.length + "个商品");

for(var i=0; i<items.length; i++) {{
    var item = items[i];
    var pid = item.getAttribute("data-id");
    if(!pid) continue;
    
    var link = item.querySelector("a");
    var url = link ? link.href : "";
    if(!url) continue;
    
    var img = item.querySelector("img");
    var imgUrl = img ? (img.src || img.getAttribute("data-src") || "") : "";
    var title = img ? (img.alt || img.title || "") : "";
    
    // 使用价格选择器
    var priceElem = item.querySelector("{price_selector}");
    var encryptedPrice = priceElem ? priceElem.innerText.trim() : "";
    
    if(encryptedPrice) {{
        products.push({{id: pid, url: url, img: imgUrl, title: title, encryptedPrice: encryptedPrice}});
    }}
}}

console.log("解析到" + products.length + "个有价格的商品");
JSON.stringify(products);'''
    
    result = run_js(js)
    try:
        return eval(result) if result else []
    except:
        return []


def scroll_page():
    """滚动页面"""
    for _ in range(10):
        run_js('window.scrollBy(0, 500)')
        time.sleep(1.5)
    time.sleep(3)


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


def save_products(products, page_name, page_url):
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
            continue
        
        price = decrypt_price(p.get('encryptedPrice', ''))
        if price == 0:
            print(f"    ⚠️ 解密失败: {p.get('encryptedPrice', '')}")
            continue
        
        level = extract_level(p.get('title', ''))
        print(f"    ✅ ¥{price} {'🏷️ '+level if level else ''}")
        
        try:
            cursor.execute("""
                INSERT INTO tmall_products 
                    (product_id, product_url, image_url, title, price, status, shop_name, shop_url, level, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                p['id'], p['url'], p['img'], p['title'][:500],
                price, 'available',
                "变形金刚玩具旗舰店", page_url, level,
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
        except:
            pass
    
    conn.close()
    return new_count


def main():
    print("="*60)
    print("🚀 天猫爬虫 - 多种价格选择器")
    print("="*60)
    
    try:
        font = TTFont(FONT_PATH)
        font.close()
        print("✅ 字体加载成功\n")
    except:
        print("⚠️ 字体加载失败\n")
    
    for idx, (name, url) in enumerate(PAGES):
        print(f"\n{'='*60}")
        print(f"📄 {name}")
        print(f"{'='*60}")
        
        print(f"🔗 打开页面...")
        subprocess.run(['osascript', '-e', f'tell application "Safari" to make new document with properties {{URL:"{url}"}}'])
        
        print("⏳ 等待页面加载...")
        time.sleep(25 + random.uniform(5, 10))
        
        # 检测登录
        if is_login_page():
            print(f"\n⚠️ 检测到登录页面！请登录...")
            subprocess.run(['osascript', '-e', 'tell application "Safari" to close every window'])
            return
        
        # 滚动
        print("📜 滚动加载...")
        scroll_page()
        
        # 查找价格选择器
        print("🔍 查找价格选择器...")
        selectors = find_price_selectors()
        print(f"   包含price的class: {selectors.get('priceClasses', [])}")
        print(f"   包含¥的元素: {len(selectors.get('yenElements', []))} 个")
        print(f"   第一个商品价格元素: {selectors.get('firstItemPrices', [])}")
        
        # 尝试多种选择器
        price_selectors = [
            ".c-price",
            "[class*='price']", 
            "[class*='Price']",
            "[class*='PRICE']",
            ".tmall-pxprice",
            ".tm-price",
            ".price-text",
            "[class*='deal']",
            "[class*='priceText']",
        ]
        
        products = []
        for selector in price_selectors:
            print(f"   尝试: {selector}")
            products = get_products_with_selector(selector)
            if len(products) > 0:
                print(f"   ✅ 成功！获取到 {len(products)} 个")
                break
        
        if products:
            new = save_products(products, name, url)
            print(f"   📦 新增 {new} 个")
        else:
            print(f"   ⚠️ 无数据")
        
        subprocess.run(['osascript', '-e', 'tell application "Safari" to close every window'])
        time.sleep(2)
        
        if idx < len(PAGES) - 1:
            wait = random.uniform(15, 40)
            print(f"⏰ 间隔 {wait:.0f} 秒...")
            time.sleep(wait)
    
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
    print("="*60)


if __name__ == '__main__':
    main()
