#!/usr/bin/env python3
"""
京东爬虫 - 正确解析版
1. 找到商品列表区域（<ul> 包含多个 <li>）
2. 提取URL、标题、图片
3. 进入详情页获取价格
"""

import subprocess
import sqlite3
import re
import time
import random
from datetime import datetime
from html import unescape

DB_PATH = 'data/transformers.db'
SHOP_URL = 'https://mall.jd.com/view_search-396211-17821117-99-1-20-1.html'


def random_wait(min_sec=5, max_sec=15):
    wait_time = random.uniform(min_sec, max_sec)
    print(f"   ⏳ 等待 {wait_time:.1f} 秒...")
    time.sleep(wait_time)


def run_js(code):
    result = subprocess.run(
        ['osascript', '-e', f'tell application "Safari" to do JavaScript "{code}" in current tab of front window'],
        capture_output=True, text=True, timeout=60
    )
    return result.stdout.strip()


def get_shop_info():
    """获取店铺信息"""
    title = run_js("document.title")
    
    # 从标题提取店铺名
    shop_name = ""
    shop_url = ""
    
    title_match = re.search(r'-\s*([^京东]+?)\s*京东$', title)
    if title_match:
        shop_name = title_match.group(1).strip()
    
    shop_url_match = re.search(r'(https?://mall\.jd\.com/index-\d+\.html)', title)
    if shop_url_match:
        shop_url = shop_url_match.group(1)
    
    return shop_name, shop_url


def get_products_from_list_page():
    """从列表页提取商品信息"""
    html = run_js("document.documentElement.outerHTML")
    products = []
    
    # 找到包含最多商品的 <ul>
    best_ul = None
    best_count = 0
    
    for m in re.finditer(r'<ul[^>]*>(.*?)</ul>', html, re.DOTALL):
        content = m.group(1)
        product_links = re.findall(r'item\.jd\.com/\d+', content)
        if len(product_links) > best_count:
            best_count = len(product_links)
            best_ul = content
    
    if not best_ul:
        return []
    
    print(f"   📦 找到 {best_count} 个商品")
    
    # 解析每个 <li>
    lis = re.findall(r'<li[^>]*>(.*?)</li>', best_ul, re.DOTALL)
    
    for li in lis:
        # URL
        url_match = re.search(r'<a[^>]*href="([^"]+)"', li)
        if not url_match:
            continue
        
        url = url_match.group(1)
        if not url.startswith('http'):
            url = 'https:' + url if url.startswith('//') else url
        
        # 商品ID
        id_match = re.search(r'item\.jd\.com/(\d+)\.html', url)
        product_id = id_match.group(1) if id_match else ""
        
        if not product_id:
            continue
        
        # 图片
        img_match = re.search(r'<img[^>]*src="([^"]+)"', li)
        image_url = img_match.group(1) if img_match else ""
        if image_url and not image_url.startswith('http'):
            image_url = 'https:' + image_url if image_url.startswith('//') else image_url
        
        # 标题
        alt_match = re.search(r'<img[^>]*alt="([^"]+)"', li)
        title = unescape(alt_match.group(1)) if alt_match else ""
        title = re.sub(r'<[^>]+>', '', title).strip()[:500]
        
        products.append({
            'product_id': product_id,
            'product_url': url,
            'image_url': image_url,
            'title': title or f"商品 {product_id}"
        })
    
    return products


def get_detail_price():
    """从详情页获取价格"""
    body_text = run_js("document.body.innerText")
    price_match = re.search(r'[¥￥](\d+\.?\d*)', body_text)
    if price_match:
        try:
            return float(price_match.group(1))
        except:
            return 0.0
    return 0.0


def save_to_db(products, shop_name, shop_url):
    """保存到数据库"""
    if not products:
        return 0, 0
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    new_count = 0
    pending_count = 0
    
    for p in products:
        cursor.execute("SELECT id, status FROM jd_products WHERE product_id=?", (p['product_id'],))
        existing = cursor.fetchone()
        
        if existing:
            cursor.execute("""
                UPDATE jd_products SET 
                    title=?, image_url=?, shop_name=?, shop_url=?, updated_at=?
                WHERE product_id=?
            """, (p['title'][:500], p['image_url'], shop_name, shop_url,
                  datetime.now().isoformat(), p['product_id']))
        else:
            cursor.execute("""
                INSERT INTO jd_products 
                    (product_id, product_url, image_url, title, shop_name, shop_url, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (p['product_id'], p['product_url'], p['image_url'], p['title'][:500],
                  shop_name, shop_url, datetime.now().isoformat(), datetime.now().isoformat()))
            new_count += 1
    
    conn.commit()
    conn.close()
    return new_count, pending_count


def update_price(product_id, price):
    """更新价格"""
    if price == 0:
        return
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("UPDATE jd_products SET price=?, updated_at=? WHERE product_id=?",
                   (price, datetime.now().isoformat(), product_id))
    conn.commit()
    conn.close()


def go_back():
    run_js("history.back()")


def main():
    print("\n" + "="*80)
    print("🚀 京东爬虫 - 正确解析版")
    print("="*80)
    
    print("\n🛒 打开店铺...")
    subprocess.run(['osascript', '-e', f'tell application "Safari" to make new document with properties {{URL:"{SHOP_URL}"}}'])
    
    random_wait(8, 12)
    
    # 获取店铺信息
    shop_name, shop_url = get_shop_info()
    print(f"   店铺: {shop_name}")
    
    # 登录检查
    is_login = 'true' in run_js("document.cookie.indexOf('pin=') >= 0")
    print(f"   登录: {'✅' if is_login else '❌'}")
    
    # 解析列表页
    print(f"\n📄 解析列表页...")
    products = get_products_from_list_page()
    
    if not products:
        print("   ❌ 未找到商品")
        return
    
    # 保存基本信息
    new_count, _ = save_to_db(products, shop_name, shop_url)
    print(f"   ✅ 保存 {new_count} 个新商品")
    
    # 尝试获取价格（前10个）
    print(f"\n💰 获取价格...")
    for i, p in enumerate(products[:10], 1):
        print(f"\n   [{i}/{min(10, len(products))}] {p['product_id']}")
        
        # 打开详情页
        subprocess.run(['osascript', '-e', f'tell application "Safari" to open location "{p["product_url"]}"'])
        random_wait(5, 8)
        
        # 获取价格
        price = get_detail_price()
        if price > 0:
            update_price(p['product_id'], price)
            print(f"   ✅ ¥{price}")
        else:
            print(f"   ⚠️ 无价格")
        
        # 返回
        go_back()
        random_wait(3, 6)
    
    # 关闭
    print(f"\n🛑 关闭浏览器...")
    subprocess.run(['osascript', '-e', 'tell application "Safari" to close front window'])
    
    # 统计
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM jd_products")
    total = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM jd_products WHERE price > 0")
    with_price = cursor.fetchone()[0]
    conn.close()
    
    print(f"\n" + "="*80)
    print("📊 统计")
    print("="*80)
    print(f"   商品: {total} 个")
    print(f"   有价格: {with_price} 个")
    print(f"\n✅ 完成!")
    print("="*80)


if __name__ == '__main__':
    random.seed()
    main()
