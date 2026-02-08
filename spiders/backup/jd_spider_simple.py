#!/usr/bin/env python3
"""
京东爬虫 - 简洁版
只打开一次浏览器，完成后关闭
"""

import subprocess
import sqlite3
import re
import time
from datetime import datetime

DB_PATH = 'data/transformers.db'
SHOP_URL = 'https://mall.jd.com/view_search-396211-17821117-99-1-20-1.html'


def run_js(code):
    result = subprocess.run(
        ['osascript', '-e', f'tell application "Safari" to do JavaScript "{code}" in current tab of front window'],
        capture_output=True, text=True, timeout=60
    )
    return result.stdout.strip()


def get_product_links():
    """获取当前页所有商品链接"""
    js = """(function(){ 
        var links=[]; 
        var as=document.querySelectorAll('a'); 
        for(var i=0;i<as.length;i++){ 
            if(as[i].href.indexOf('item.jd.com')>-1){ 
                links.push(as[i].href); 
            } 
        } 
        return [...new Set(links)].join('|||'); 
    })()"""
    result = run_js(js)
    return [l for l in result.split('|||') if l and 'item.jd.com' in l]


def get_product_info():
    """获取当前商品详情"""
    url = run_js("window.location.href")
    product_id = run_js("window.location.href.match(/item\\.jd\\.com\\/(\\d+)\\.html/)")
    product_id = product_id if product_id and product_id != 'null' else ''
    
    price_match = run_js("document.body.innerText.match(/[¥￥](\\d+\\.?\\d*)/)")
    try:
        price = float(price_match) if price_match and price_match != 'null' else 0.0
    except:
        price = 0.0
    
    title = run_js("document.title")
    title = re.sub(r'_京东.*', '', title)
    title = re.sub(r'<[^>]+>', '', title).strip()[:200]
    
    text = (title + str(price)).lower()
    is_deposit = any(kw in text for kw in ['定金', '预付', '预售', '预约', '预定'])
    
    return {'product_id': product_id, 'name': title, 'price': price, 'url': url, 'is_deposit': is_deposit}


def click_link(link):
    """点击链接"""
    js = f"""(function(){{ 
        var as=document.querySelectorAll('a'); 
        for(var i=0;i<as.length;i++){{ 
            if(as[i].href.indexOf('{link}')>-1){{ 
                as[i].click(); return 'OK'; 
            }} 
        }} 
        return 'FAIL'; 
    }})()"""
    return 'OK' in run_js(js)


def go_back():
    """返回"""
    run_js("history.back()")
    time.sleep(3)


def click_next():
    """点击下一页"""
    js = """(function(){
        var nextBtn = document.querySelector('.pn-next, [class*="next"]');
        if(nextBtn){ nextBtn.click(); return 'OK'; }
        return 'FAIL';
    })()"""
    return 'OK' in run_js(js)


def save_to_db(product):
    if not product or not product.get('product_id'):
        return False
    
    pid = product['product_id']
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("SELECT id FROM products WHERE jd_product_id=?", (pid,))
    if cursor.fetchone():
        conn.close()
        return False
    
    if product['is_deposit']:
        print(f"   ⏭️ 定金/预售")
        conn.close()
        return False
    
    cursor.execute("""
        INSERT INTO products (name, jd_product_id, jd_product_url, shop_id, status, is_deposit, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (product['name'], pid, product['url'], 'haseba', 'not_purchased', 0, datetime.now().isoformat()))
    
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
    print("🚀 京东爬虫")
    print("="*80)
    
    # 只打开一次浏览器
    print("\n🛒 打开店铺...")
    subprocess.run(['osascript', '-e', f'tell application "Safari" to make new document with properties {{URL:"{SHOP_URL}"}}'])
    time.sleep(5)
    
    # 检查登录
    is_login = 'true' in run_js("document.cookie.indexOf('pin=') >= 0")
    print(f"   登录: {'✅' if is_login else '❌'}")
    
    processed = set()
    saved = 0
    page = 1
    
    while page <= 50:
        print(f"\n📄 第 {page} 页")
        
        time.sleep(2)
        links = get_product_links()
        print(f"   商品: {len(links)} 个")
        
        if not links:
            print("   ⚠️ 无商品")
            break
        
        # 只处理新商品
        new_links = [l for l in links if l not in processed][:20]
        for i, link in enumerate(new_links):
            if link in processed:
                continue
            processed.add(link)
            
            print(f"\n   🛒 [{i+1}/{len(new_links)}] {link[-30:]}")
            
            if not click_link(link):
                continue
            
            time.sleep(3)
            product = get_product_info()
            
            if product.get('product_id') and save_to_db(product):
                print(f"   ✅ {product['name'][:35]}... ¥{product['price']}")
                saved += 1
            
            go_back()
        
        # 翻页
        print(f"\n   ⏭️ 翻页...")
        if not click_next():
            print("   ✅ 最后一页")
            break
        
        page += 1
        time.sleep(3)
    
    # 只关闭一次
    print(f"\n🛑 关闭浏览器...")
    subprocess.run(['osascript', '-e', 'tell application "Safari" to close front window'])
    
    # 统计
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM products")
    total = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM products WHERE is_deposit=0")
    buyable = cursor.fetchone()[0]
    conn.close()
    
    print(f"\n📊 访问: {len(processed)} | 新增: {saved} | 数据库: {total} | 可购买: {buyable}")
    print("✅ 完成!")


if __name__ == '__main__':
    main()
