#!/usr/bin/env python3
"""
京东爬虫 - 详情页增强版
1. 先获取商品链接列表
2. 进入每个详情页获取标题和价格
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


def get_all_product_links():
    """获取当前页所有商品链接"""
    html = run_js("document.documentElement.outerHTML")
    links = re.findall(r'item\.jd\.com/\d+\.html', html)
    return list(set(['https:' + l if l.startswith('//') else l for l in links]))


def get_product_detail():
    """获取当前详情页信息"""
    # URL
    url = run_js("window.location.href")
    
    # 商品ID
    match = re.search(r'item\.jd\.com/(\d+)\.html', url)
    product_id = match.group(1) if match else ""
    
    # 标题
    title = run_js("document.title")
    title = re.sub(r'_京东.*', '', title)
    title = re.sub(r'<[^>]+>', '', title).strip()[:500]
    
    # 价格
    price = 0.0
    price_match = re.search(r'[¥￥](\d+\.?\d*)', run_js("document.body.innerText"))
    if price_match:
        try:
            price = float(price_match.group(1))
        except:
            price = 0.0
    
    # 图片
    img_match = re.search(r'<img[^>]*class="[^"]*viewer[^"]*"[^>]*src="([^"]*)"', run_js("document.documentElement.outerHTML"))
    if not img_match:
        img_match = re.search(r'<img[^>]*id="[^"]*img[^"]*"[^>]*src="([^"]*)"', run_js("document.documentElement.outerHTML"))
    image_url = img_match.group(1) if img_match else ""
    if image_url and not image_url.startswith('http'):
        image_url = 'https:' + image_url
    
    # 判断是否待发布
    body_text = run_js("document.body.innerText").lower()
    is_pending = any(kw in body_text for kw in ['待发布', '暂无价格', '暂时缺货', '到货通知'])
    
    status = 'pending' if is_pending else 'available'
    
    return {
        'product_id': product_id,
        'product_url': url,
        'title': title or f"商品 {product_id}",
        'price': price,
        'image_url': image_url,
        'status': status
    }


def save_to_db(product):
    """保存到数据库"""
    if not product or not product.get('product_id'):
        return False
    
    pid = product['product_id']
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 检查是否存在
    cursor.execute("SELECT id, title FROM jd_products WHERE product_id=?", (pid,))
    existing = cursor.fetchone()
    
    if existing:
        # 更新
        cursor.execute("""
            UPDATE jd_products SET 
                title=?, price=?, image_url=?, status=?, updated_at=?
            WHERE product_id=?
        """, (
            product['title'][:500], product['price'], 
            product['image_url'], product['status'],
            datetime.now().isoformat(), pid
        ))
        conn.commit()
        conn.close()
        return False  # 已存在，不重复计数
    
    # 新增
    cursor.execute("""
        INSERT INTO jd_products 
            (product_id, product_url, image_url, title, price, status, is_deposit, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        pid, product['product_url'], product['image_url'], product['title'][:500],
        product['price'], product['status'],
        1 if product['status']=='pending' else 0,
        datetime.now().isoformat(), datetime.now().isoformat()
    ))
    
    conn.commit()
    conn.close()
    return True


def go_back():
    """返回"""
    run_js("history.back()")


def main():
    print("\n" + "="*80)
    print("🚀 京东爬虫 - 详情页增强版")
    print("="*80)
    
    # 打开浏览器
    print("\n🛒 打开店铺...")
    subprocess.run(['osascript', '-e', f'tell application "Safari" to make new document with properties {{URL:"{SHOP_URL}"}}'])
    
    random_wait(8, 12)
    
    # 检查登录
    is_login = 'true' in run_js("document.cookie.indexOf('pin=') >= 0")
    print(f"   登录: {'✅' if is_login else '❌'}")
    
    # 获取商品列表
    product_links = get_all_product_links()
    print(f"\n📦 找到 {len(product_links)} 个商品")
    
    processed = set()
    saved = 0
    
    for i, link in enumerate(product_links[:30], 1):
        if link in processed:
            continue
        processed.add(link)
        
        print(f"\n📄 [{i}/{len(product_links)}] {link[-40:]}")
        
        # 打开详情页
        subprocess.run(['osascript', '-e', f'tell application "Safari" to open location "{link}"'])
        random_wait(5, 10)
        
        # 获取详情
        product = get_product_detail()
        
        # 保存
        if save_to_db(product):
            saved += 1
            print(f"   ✅ {product['title'][:40]}... ¥{product['price'] or '?'}")
        else:
            print(f"   ⏭️ 已存在")
        
        # 返回列表
        go_back()
        random_wait(3, 8)
    
    # 关闭
    print(f"\n🛑 关闭浏览器...")
    subprocess.run(['osavascript', '-e', 'tell application "Safari" to close front window'])
    
    # 统计
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM jd_products")
    total = cursor.fetchone()[0]
    conn.close()
    
    print(f"\n" + "="*80)
    print("📊 统计")
    print("="*80)
    print(f"   访问: {len(processed)} 个")
    print(f"   新增: {saved} 个")
    print(f"   数据库: {total} 个")
    print(f"\n✅ 完成!")
    print("="*80)


if __name__ == '__main__':
    random.seed()
    main()
