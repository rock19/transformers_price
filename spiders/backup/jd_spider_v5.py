#!/usr/bin/env python3
"""
京东爬虫 - 简化版
直接解析所有商品链接和价格
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


def get_all_products_from_page():
    """从当前页面提取所有商品"""
    html = run_js("document.documentElement.outerHTML")
    
    products = []
    
    # 获取所有唯一的商品链接
    all_links = re.findall(r'item\.jd\.com/\d+\.html', html)
    unique_links = list(set(all_links))
    
    print(f"   找到 {len(unique_links)} 个商品链接")
    
    for link in unique_links:
        # 构建完整URL
        product_url = 'https:' + link if link.startswith('//') else link
        
        # 提取ID
        id_match = re.search(r'item\.jd\.com/(\d+)\.html', product_url)
        product_id = id_match.group(1) if id_match else ""
        
        if not product_id:
            continue
        
        # 获取上下文（链接前后300字符）来提取价格
        pos = html.find(link)
        if pos == -1:
            continue
        
        context_start = max(0, pos - 300)
        context_end = min(len(html), pos + 300)
        context = html[context_start:context_end]
        
        # 查找价格
        price = 0.0
        price_match = re.search(r'[¥￥](\d+\.?\d*)', context)
        if price_match:
            try:
                price = float(price_match.group(1))
            except:
                price = 0.0
        
        # 查找标题（img alt 或 a title）
        title = ""
        title_match = re.search(r'<img[^>]*alt=["\']([^"\']*)["\'][^>]*>', context)
        if title_match:
            title = unescape(title_match.group(1))
        
        # 检查是否待发布（无价格或明确标注）
        is_pending = False
        if price == 0.0:
            # 检查上下文是否有待发布相关关键词
            context_lower = context.lower()
            if any(kw in context_lower for kw in ['待发布', '暂无价格', 'hide-price', 'data-hide-price']):
                is_pending = True
        
        status = 'pending' if is_pending else 'available'
        
        products.append({
            'product_id': product_id,
            'product_url': product_url,
            'title': title or f"商品 {product_id}",
            'price': price,
            'status': status
        })
        
        mark = '⏭️' if is_pending else '✅'
        print(f"   {mark} {product_id}: {title[:30] if title else '商品'}... ¥{price or '?'}")
    
    return products


def save_to_db(products):
    """保存到数据库"""
    if not products:
        return 0, 0
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    new_count = 0
    pending_count = 0
    
    for p in products:
        # 检查是否已存在
        cursor.execute("SELECT id, status FROM jd_products WHERE product_id=?", (p['product_id'],))
        existing = cursor.fetchone()
        
        if existing:
            # 更新
            cursor.execute("""
                UPDATE jd_products SET 
                    price=?, status=?, updated_at=?
                WHERE product_id=?
            """, (p['price'], p['status'], datetime.now().isoformat(), p['product_id']))
        else:
            # 新增
            cursor.execute("""
                INSERT INTO jd_products 
                    (product_id, product_url, title, price, status, is_deposit, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                p['product_id'], p['product_url'], p['title'][:500],
                p['price'], p['status'], 1 if p['status']=='pending' else 0,
                datetime.now().isoformat(), datetime.now().isoformat()
            ))
            
            if p['status'] == 'pending':
                pending_count += 1
            else:
                new_count += 1
    
    conn.commit()
    conn.close()
    
    return new_count, pending_count


def click_next_page():
    """点击下一页"""
    js = """(function(){
        var nextBtn = document.querySelector('.pn-next, [class*="next"]');
        if(nextBtn) { nextBtn.click(); return 'OK'; }
        return 'FAIL';
    })()"""
    return 'OK' in run_js(js)


def get_current_url():
    """获取当前URL"""
    return run_js("window.location.href")


def main():
    print("\n" + "="*80)
    print("🚀 京东爬虫 - 简化版")
    print("="*80)
    
    # 只打开一次浏览器
    print("\n🛒 打开店铺...")
    subprocess.run(['osascript', '-e', f'tell application "Safari" to make new document with properties {{URL:"{SHOP_URL}"}}'])
    
    random_wait(8, 12)
    
    # 检查登录
    is_login = 'true' in run_js("document.cookie.indexOf('pin=') >= 0")
    print(f"   登录: {'✅' if is_login else '❌'}")
    
    processed = set()
    total_new = 0
    total_pending = 0
    page = 1
    
    while page <= 50:
        print(f"\n" + "="*80)
        print(f"📄 第 {page} 页")
        print("="*80)
        
        random_wait(5, 15)
        
        # 获取当前URL
        current_url = get_current_url()
        
        # 提取商品
        products = get_all_products_from_page()
        
        if not products:
            print("   ⚠️ 无商品")
            break
        
        # 保存
        new_count, pending_count = save_to_db(products)
        total_new += new_count
        total_pending += pending_count
        
        for p in products:
            processed.add(p['product_id'])
        
        # 翻页
        print(f"\n   ⏭️ 翻页...")
        if not click_next_page():
            print("   ✅ 最后一页")
            break
        
        page += 1
        random_wait(5, 15)
    
    # 关闭
    print(f"\n🛑 关闭浏览器...")
    subprocess.run(['osascript', '-e', 'tell application "Safari" to close front window'])
    
    # 统计
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM jd_products")
    db_total = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM jd_products WHERE status='available'")
    available = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM jd_products WHERE status='pending'")
    pending = cursor.fetchone()[0]
    conn.close()
    
    print(f"\n" + "="*80)
    print("📊 统计")
    print("="*80)
    print(f"   访问商品: {len(processed)} 个")
    print(f"   新增: {total_new} 个")
    print(f"   数据库: {db_total} 个")
    print(f"   在售: {available} 个")
    print(f"   待发布: {pending} 个")
    print(f"\n✅ 完成!")
    print("="*80)


if __name__ == '__main__':
    random.seed()
    main()
