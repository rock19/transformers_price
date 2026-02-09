#!/usr/bin/env python3
"""
天猫爬虫 - 3页分别调试
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

# 3个URL
PAGE1_URL = "https://thetransformers.tmall.com/category.htm?spm=a1z10.3-b.w5001-22116109517.10.77742409X6wOMa&search=y&orderType=hotsell_desc&scene=taobao_shop"
PAGE2_URL = "https://thetransformers.tmall.com/category.htm?spm=a1z10.3-b.w4011-22116109545.508.5ecd2409eajMbv&search=y&orderType=hotsell_desc&scene=taobao_shop&pageNo=2"
PAGE3_URL = "https://thetransformers.tmall.com/category.htm?spm=a1z10.3-b.w4011-22116109545.509.1a132409FfGkP2&search=y&orderType=hotsell_desc&scene=taobao_shop&pageNo=3"


def run_js(js_code):
    """执行JavaScript"""
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


def open_url(url):
    """打开URL（替换当前窗口）"""
    subprocess.run(['osascript', '-e', f'tell application "Safari" to set URL of front document to "{url}"'])


def is_login_page():
    """检测是否登录页面"""
    js = '''var isLogin = false;
var bodyText = document.body ? document.body.innerText || "" : "";
if(bodyText.indexOf("密码登录") > -1 || bodyText.indexOf("短信登录") > -1) {
    isLogin = true;
}
JSON.stringify({isLogin: isLogin});'''
    
    result = run_js(js)
    try:
        data = eval(result) if result else {}
        return data.get('isLogin', False)
    except:
        return False


def scroll_and_get_products():
    """滚动并获取商品"""
    # 滚动10次
    for i in range(10):
        run_js('window.scrollBy(0, 500)')
        time.sleep(1.5)
    time.sleep(3)
    
    # 获取商品
    js = '''var products = [];
var items = document.querySelectorAll("[data-id]");
for(var i=0; i<items.length; i++) {
    var item = items[i];
    var pid = item.getAttribute("data-id");
    if(!pid) continue;
    
    var link = item.querySelector("a[href*='item']");
    if(!link) link = item.querySelector("a");
    var url = link ? link.href : "";
    if(!url || url.indexOf("item") < 0) continue;
    
    var img = item.querySelector("img");
    var imgUrl = img ? (img.src || img.getAttribute("data-src") || "") : "";
    var title = img ? (img.alt || img.title || "") : "";
    
    var priceElem = item.querySelector(".c-price") || item.querySelector("[class*='price']");
    var encryptedPrice = priceElem ? priceElem.innerText.trim() : "";
    
    if(encryptedPrice) {
        products.push({id: pid, url: url, img: imgUrl, title: title, encryptedPrice: encryptedPrice});
    }
}
console.log("找到" + products.length + "个有价格的商品");
JSON.stringify(products);'''
    
    result = run_js(js)
    try:
        return eval(result) if result else []
    except Exception as e:
        print(f"      ❌ 解析失败: {e}")
        return []


def decrypt_price(encrypted):
    """解密价格"""
    if not encrypted:
        return 0
    try:
        font = TTFont(FONT_PATH)
        cmap = font['cmap'].getBestCmap()
        base = {'.':'.', 'zero':'0', 'one':'1', 'two':'2', 'three':'3', 'four':'4', 'five':'5', 'six':'6', 'seven':'7', 'eight':'8', 'nine':'9'}
        price = ''
        for c in encrypted:
            name = cmap.get(ord(c))
            if name and name in base:
                price += base[name]
        font.close()
        return round(float(price) / 100, 2) if price else 0
    except:
        return 0


def extract_level(title):
    """识别级别"""
    title = title.upper()
    if 'MP-' in title or 'MPG-' in title or '大师级' in title:
        return '大师级'
    elif '泰坦级' in title or title.endswith('L级'):
        return '泰坦级'
    elif '指挥官级' in title or '领袖级' in title:
        return '领袖级'
    elif '航行家级' in title:
        return '航行家级'
    elif '加强级' in title or title.endswith('C级'):
        return '加强级'
    elif '核心级' in title:
        return '核心级'
    return ''


def save_products(products, page_name, page_url):
    """保存商品"""
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
            print(f"     ⏭️ 已存在")
            continue
        
        price = decrypt_price(p.get('encryptedPrice', ''))
        if price == 0:
            print(f"     ❌ 解密失败: {p.get('encryptedPrice', '')}")
            continue
        
        level = extract_level(p.get('title', ''))
        print(f"     ✅ ¥{price} {'🏷️ '+level if level else ''}")
        
        try:
            cursor.execute("""
                INSERT INTO tmall_products 
                    (product_id, product_url, image_url, title, price, preprice, style_name, status, 
                     is_deposit, created_at, updated_at, shop_name, shop_url, is_purchased, is_followed, level)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                p['id'], p['url'], p['img'], p['title'][:500], price, '', '', 'available',
                0, datetime.now().isoformat(), datetime.now().isoformat(),
                '变形金刚玩具旗舰店', page_url, '否', '否', level
            ))
            
            cursor.execute("SELECT id FROM tmall_products WHERE product_id=?", (p['id'],))
            row_id = cursor.fetchone()[0]
            
            cursor.execute("SELECT id FROM tmall_price_history WHERE product_id=? AND created_at=?", (row_id, today))
            if not cursor.fetchone():
                cursor.execute("INSERT INTO tmall_price_history VALUES (?, ?, ?, ?, ?, ?)",
                            (None, row_id, p['url'], price, '', today))
            
            conn.commit()
            new_count += 1
        except Exception as e:
            print(f"     ❌ 保存失败: {e}")
    
    conn.close()
    return new_count


def crawl_page1():
    """爬取第1页"""
    print("\n" + "="*60)
    print("📄 第1页")
    print("="*60)
    
    # 打开第1页（替换当前窗口）
    print(f"🔗 打开第1页...")
    open_url(PAGE1_URL)
    time.sleep(30)
    
    # 检测登录
    if is_login_page():
        print("⚠️ 检测到登录页面！请登录...")
        return 0
    
    # 滚动并获取商品
    print("📜 滚动加载...")
    products = scroll_and_get_products()
    
    if not products:
        print("⚠️ 无商品")
        return 0
    
    # 保存
    print(f"💾 保存 {len(products)} 个商品...")
    new_count = save_products(products, "第1页", PAGE1_URL)
    
    print(f"✅ 第1页完成，新增 {new_count} 个")
    return new_count


def crawl_page2():
    """爬取第2页"""
    print("\n" + "="*60)
    print("📄 第2页")
    print("="*60)
    
    print(f"🔗 打开第2页...")
    open_url(PAGE2_URL)
    time.sleep(30)
    
    if is_login_page():
        print("⚠️ 检测到登录页面！请登录...")
        return 0
    
    print("📜 滚动加载...")
    products = scroll_and_get_products()
    
    if not products:
        print("⚠️ 无商品")
        return 0
    
    print(f"💾 保存 {len(products)} 个商品...")
    new_count = save_products(products, "第2页", PAGE2_URL)
    
    print(f"✅ 第2页完成，新增 {new_count} 个")
    return new_count


def crawl_page3():
    """爬取第3页"""
    print("\n" + "="*60)
    print("📄 第3页")
    print("="*60)
    
    print(f"🔗 打开第3页...")
    open_url(PAGE3_URL)
    time.sleep(30)
    
    if is_login_page():
        print("⚠️ 检测到登录页面！请登录...")
        return 0
    
    print("📜 滚动加载...")
    products = scroll_and_get_products()
    
    if not products:
        print("⚠️ 无商品")
        return 0
    
    print(f"💾 保存 {len(products)} 个商品...")
    new_count = save_products(products, "第3页", PAGE3_URL)
    
    print(f"✅ 第3页完成，新增 {new_count} 个")
    return new_count


def main():
    print("="*60)
    print("🚀 天猫爬虫 - 分别爬取3页")
    print("="*60)
    
    try:
        font = TTFont(FONT_PATH)
        font.close()
        print("✅ 字体加载成功\n")
    except:
        print("⚠️ 字体加载失败\n")
    
    # 先测试第1页
    new1 = crawl_page1()
    
    print("\n" + "="*60)
    print("📊 第1页测试完成")
    print("="*60)
    
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
    
    print(f"\n📊 统计:")
    print(f"   总商品: {total}")
    print(f"   有价格: {with_price}")
    print(f"   有级别: {with_level}")
    print(f"   第1页新增: {new1}")


if __name__ == '__main__':
    main()
