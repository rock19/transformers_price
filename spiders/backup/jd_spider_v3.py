#!/usr/bin/env python3
"""
京东爬虫 - 优化版
1. 列表页识别所有商品
2. 点击商品进入详情
3. 获取信息后返回列表
4. 遍历完当前页后翻页
"""

import subprocess
import sqlite3
import re
import time
from datetime import datetime

DB_PATH = 'data/transformers.db'
SHOP_URL = 'https://mall.jd.com/view_search-396211-17821117-99-1-20-1.html'


def run_js(code):
    """执行 JavaScript"""
    script = f'''#!/bin/bash
osascript << 'EOF'
tell application "Safari"
    try
        set result to do JavaScript "{code}" in current tab of front window
        return result
    on error
        return "ERROR"
    end try
end tell
EOF'''
    result = subprocess.run(['bash', '-c', script], capture_output=True, text=True, timeout=60)
    return result.stdout.strip()


def get_page_text():
    """获取页面纯文本"""
    return run_js("document.body.innerText")


def get_page_html():
    """获取页面 HTML"""
    return run_js("document.documentElement.outerHTML")


def get_product_links_on_list():
    """获取列表页所有商品链接元素"""
    # 返回 JavaScript 代码执行结果
    js_result = run_js("""
        var links = [];
        var as = document.querySelectorAll('a');
        as.forEach(function(a) {
            if(a.href && a.href.indexOf('item.jd.com') > -1 && a.href.indexOf('comment') == -1) {
                links.push(a.href);
            }
        });
        return links.slice(0, 50).join('|||');
    """)
    links = [l for l in js_result.split('|||') if l and 'item.jd.com' in l]
    return list(set(links))


def get_total_pages():
    """获取总页数"""
    text = get_page_text()
    match = re.search(r'共(\d+)页', text)
    return int(match.group(1)) if match else 1


def get_current_page():
    """获取当前页码"""
    text = get_page_text()
    match = re.search(r'class="[^"]*pn-curr[^"]*"[^>]*>(\d+)<', text)
    if match:
        return int(match.group(1))
    # 备选方案
    match = re.search(r'>\s*(\d+)\s*</[^>]*class="[^"]*pn[^"]*"', text)
    if match:
        return int(match.group(1))
    return 1


def click_product(index):
    """点击第 index 个商品（0-based）"""
    js_code = f"""
        var links = [];
        var as = document.querySelectorAll('a');
        var count = 0;
        as.forEach(function(a) {{
            if(a.href && a.href.indexOf('item.jd.com') > -1 && a.href.indexOf('comment') == -1) {{
                if(count == {index}) {{
                    a.click();
                    'CLICKED';
                }}
                count++;
            }}
        }});
        'NOT_FOUND';
    """
    result = run_js(js_code)
    return 'CLICKED' in result


def get_product_info():
    """获取当前商品详情页的信息"""
    # 获取商品ID
    match = run_js("window.location.href.match(/item\\.jd\\.com\\/(\\d+)\\.html/)")
    product_id = match if match and match != 'null' else ''
    
    # 获取价格
    price_match = run_js("document.body.innerText.match(/[¥￥](\\d+\\.?\\d*)/)")
    try:
        price = float(price_match) if price_match and price_match != 'null' else 0.0
    except:
        price = 0.0
    
    # 获取标题
    title = run_js("document.title")
    title = re.sub(r'_京东.*', '', title)
    title = re.sub(r'<[^>]+>', '', title).strip()[:200]
    
    # 判断是否为定金/预售
    html = get_page_html()
    text = (title + str(price)).lower()
    is_deposit = any(kw in text for kw in ['定金', '预付', '预售', '预约', '预定', '预热', '抢先'])
    
    # 获取当前URL
    url = run_js("window.location.href")
    
    return {
        'product_id': product_id,
        'name': title,
        'price': price,
        'url': url,
        'is_deposit': is_deposit
    }


def back_to_list():
    """返回列表页"""
    run_js("history.back()")
    time.sleep(3)


def click_next_page():
    """点击下一页"""
    js_code = """
        var nextBtn = document.querySelector('.pn-next, [class*="pn-next"], [class*="next"], a[class*="next"]');
        if(nextBtn) {
            nextBtn.click();
            'SUCCESS';
        } else {
            'FAIL';
        }
    """
    result = run_js(js_code)
    return 'SUCCESS' in result


def save_to_db(product):
    """保存商品到数据库"""
    if not product or not product.get('product_id'):
        return False
    
    pid = product['product_id']
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 检查是否已存在
    cursor.execute("SELECT id, is_deposit FROM products WHERE jd_product_id=?", (pid,))
    existing = cursor.fetchone()
    
    if existing:
        # 更新状态
        cursor.execute("UPDATE products SET is_deposit=?, updated_at=? WHERE id=?",
            (1 if product['is_deposit'] else 0, datetime.now().isoformat(), existing[0]))
        conn.commit()
        conn.close()
        return False
    
    # 跳过定金商品
    if product['is_deposit']:
        print(f"   ⏭️ 定金/预售: {product['name'][:40]}...")
        conn.close()
        return False
    
    # 保存
    status = 'not_purchased'
    cursor.execute("""
        INSERT INTO products (name, jd_product_id, jd_product_url, shop_id, status, is_deposit, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (product['name'], pid, product['url'], 'haseba', status, 0, datetime.now().isoformat()))
    
    db_id = cursor.lastrowid
    
    cursor.execute("""
        INSERT INTO product_prices (product_id, product_id_on_platform, price, price_type, platform, product_url, captured_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (db_id, pid, product['price'], '购买', 'jd', product['url'], datetime.now().isoformat()))
    
    conn.commit()
    conn.close()
    return True


def main():
    print("\n" + "="*80)
    print("🚀 京东爬虫 - 优化版")
    print("="*80)
    
    # 关闭旧窗口，打开新窗口
    print("\n🛑 关闭旧窗口...")
    subprocess.run(['osascript', '-e', 'tell application "Safari" to close every window'])
    time.sleep(2)
    
    print(f"\n🛒 打开 {SHOP_URL}...")
    subprocess.run(['osascript', '-e', f'tell application "Safari" to make new document with properties {{URL:"{SHOP_URL}"}}'])
    time.sleep(5)
    
    # 统计
    processed_products = set()
    total_saved = 0
    
    # 外层循环：遍历页码
    page = 1
    while page <= 50:
        print(f"\n{'='*80}")
        print(f"📄 第 {page} 页")
        print("="*80)
        
        # 等待页面加载
        time.sleep(2)
        
        # 获取页码信息
        total_pages = get_total_pages()
        current_page = get_current_page()
        print(f"   总页数: {total_pages} | 当前: {current_page}")
        
        # 内层循环：遍历当前页商品
        print(f"\n   📦 遍历当前页商品...")
        
        # 获取当前页所有商品链接
        product_links = get_product_links_on_list()
        print(f"   找到 {len(product_links)} 个商品")
        
        if not product_links:
            print("   ⚠️ 未找到商品，停止")
            break
        
        for i, link in enumerate(product_links):
            # 跳过已处理的商品
            if link in processed_products:
                continue
            processed_products.add(link)
            
            print(f"\n   🛒 [{i+1}/{len(product_links)}] 点击商品...")
            
            # 点击商品进入详情页
            if not click_product(i):
                print(f"   ❌ 点击失败: {link}")
                continue
            
            # 等待详情页加载
            time.sleep(3)
            
            # 获取商品信息
            product = get_product_info()
            
            if product and product.get('product_id'):
                # 保存到数据库
                if save_to_db(product):
                    print(f"   ✅ {product['name'][:40]}... ¥{product['price']}")
                    total_saved += 1
            
            # 返回列表页
            print(f"   🔙 返回列表页...")
            back_to_list()
            time.sleep(2)
        
        # 检查是否最后一页
        if current_page >= total_pages:
            print(f"\n✅ 已是最后一页")
            break
        
        # 点击下一页
        print(f"\n   ⏭️ 点击下一页...")
        if not click_next_page():
            print("   ❌ 翻页失败")
            break
        
        page += 1
        time.sleep(3)
    
    # 关闭浏览器
    print(f"\n🛑 关闭浏览器...")
    subprocess.run(['osascript', '-e', 'tell application "Safari" to close front window'])
    
    # 统计数据库
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM products")
    db_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM products WHERE is_deposit=0")
    buyable_count = cursor.fetchone()[0]
    conn.close()
    
    print(f"\n{'='*80}")
    print("📊 统计")
    print("="*80)
    print(f"   访问商品: {len(processed_products)} 个")
    print(f"   新增商品: {total_saved} 个")
    print(f"   数据库总计: {db_count} 个")
    print(f"   可购买: {buyable_count} 个")
    print(f"   定金/预售: {db_count - buyable_count} 个")
    print(f"\n✅ 完成!")
    print("="*80)


if __name__ == '__main__':
    main()
