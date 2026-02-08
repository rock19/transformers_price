#!/usr/bin/env python3
"""
京东爬虫 - 优化版
1. 列表页直接获取标题和价格
2. 过滤"待发布"商品
3. 比对数据库，避免重复点击
"""

import subprocess
import sqlite3
import re
import time
import random
from datetime import datetime

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


def get_all_products_on_page():
    """获取列表页所有商品信息"""
    # 获取页面 HTML
    html = run_js("document.documentElement.outerHTML")
    
    products = []
    
    # 使用正则提取商品信息
    # 格式: item.jd.com/ID.html
    item_pattern = r'item\.jd\.com/(\d+)\.html'
    items = re.findall(item_pattern, html)
    
    # 获取每个商品的标题和价格
    # 查找商品名称（通常在 a 标签的 title 属性或文本中）
    name_pattern = r'<a[^>]*title="([^"]*)"[^>]*href="[^"]*item\.jd\.com/(\d+)\.html'
    names = re.findall(name_pattern, html)
    
    # 查找价格
    price_pattern = r'[¥￥](\d+\.?\d*)'
    prices = re.findall(price_pattern, html)
    
    # 构建商品列表
    for item_id in items:
        product = {
            'product_id': item_id,
            'url': f'https://item.jd.com/{item_id}.html',
            'name': f'商品 {item_id}',
            'price': 0.0,
            'is_deposit': False
        }
        products.append(product)
    
    # 去重
    seen = set()
    unique_products = []
    for p in products:
        if p['product_id'] not in seen:
            seen.add(p['product_id'])
            unique_products.append(p)
    
    return unique_products


def get_product_info_from_list():
    """从列表页获取所有商品信息（标题、价格、是否待发布）"""
    js = """(function(){
        var products = [];
        var as = document.querySelectorAll('a');
        
        as.forEach(function(a) {
            var href = a.href;
            if(href && href.indexOf('item.jd.com') > -1) {
                var text = a.innerText || '';
                var parent = a.parentElement;
                var grandparent = parent ? parent.parentElement : null;
                
                // 获取价格（查找附近的人民币符号）
                var priceText = '';
                var sibling = a.nextElementSibling;
                while(sibling) {
                    if(sibling.innerText && sibling.innerText.indexOf('¥') > -1) {
                        priceText = sibling.innerText;
                        break;
                    }
                    sibling = sibling.nextElementSibling;
                }
                
                // 获取价格（查找父元素附近）
                if(!priceText && parent) {
                    var parentText = parent.innerText || '';
                    var priceMatch = parentText.match(/[¥￥](\\d+\\.?\\d*)/);
                    if(priceMatch) priceText = priceMatch[0];
                }
                
                products.push({
                    url: href,
                    text: text.substring(0, 100),
                    price: priceText
                });
            }
        });
        
        return JSON.stringify(products);
    })()"""
    
    result = run_js(js)
    try:
        import json
        products = json.loads(result)
        return products
    except:
        return []


def is_deposit_product(price_text, name_text):
    """判断是否为定金/待发布商品"""
    text = (price_text + ' ' + name_text).lower()
    if '待发布' in text:
        return True
    if any(kw in text for kw in ['定金', '预付', '预售', '预约', '预定', '预热', '抢先']):
        return True
    return False


def save_product_to_db(product_id, name, url, price, source='list'):
    """保存商品到数据库"""
    if not product_id:
        return False
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 检查是否存在
    cursor.execute("SELECT id, name FROM products WHERE jd_product_id=?", (product_id,))
    existing = cursor.fetchone()
    
    if existing:
        conn.close()
        return False  # 已存在，不重复保存
    
    # 判断是否定金
    is_deposit = is_deposit_product(str(price), name)
    
    if is_deposit:
        print(f"   ⏭️ 定金/待发布: {name[:40]}...")
        cursor.execute("""
            INSERT INTO products (name, jd_product_id, jd_product_url, shop_id, status, is_deposit, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (name[:200], product_id, url, 'haseba', 'not_purchased', 1, datetime.now().isoformat()))
        conn.commit()
        conn.close()
        return True
    
    # 保存可购买的商品
    try:
        price_float = float(re.search(r'[\d.]+', str(price)).group()) if re.search(r'[\d.]+', str(price)) else 0.0
    except:
        price_float = 0.0
    
    cursor.execute("""
        INSERT INTO products (name, jd_product_id, jd_product_url, shop_id, status, is_deposit, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (name[:200], product_id, url, 'haseba', 'not_purchased', 0, datetime.now().isoformat()))
    
    db_id = cursor.lastrowid
    
    cursor.execute("""
        INSERT INTO product_prices (product_id, product_id_on_platform, price, price_type, platform, product_url, captured_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (db_id, product_id, price_float, '购买', 'jd', url, datetime.now().isoformat()))
    
    conn.commit()
    conn.close()
    return True


def click_product(link):
    """点击商品进入详情页"""
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


def get_product_from_detail():
    """从详情页获取商品信息"""
    js = """(function(){
        var info = {
            url: window.location.href,
            title: document.title || '',
            price: '',
            is_deposit: false
        };
        
        // 价格
        var priceMatch = document.body.innerText.match(/[¥￥](\\d+\\.?\\d*)/);
        if(priceMatch) info.price = priceMatch[0];
        
        // 定金判断
        var text = (document.title + ' ' + document.body.innerText).toLowerCase();
        if(text.indexOf('待发布') > -1 || text.indexOf('定金') > -1 || 
           text.indexOf('预售') > -1 || text.indexOf('预约') > -1) {
            info.is_deposit = true;
        }
        
        return JSON.stringify(info);
    })()"""
    
    result = run_js(js)
    try:
        import json
        return json.loads(result)
    except:
        return None


def main():
    print("\n" + "="*80)
    print("🚀 京东爬虫 - 优化版")
    print("="*80)
    
    # 只打开一次浏览器
    print("\n🛒 打开店铺...")
    subprocess.run(['osascript', '-e', f'tell application "Safari" to make new document with properties {{URL:"{SHOP_URL}"}}'])
    
    random_wait(8, 12)
    
    # 检查登录
    is_login = 'true' in run_js("document.cookie.indexOf('pin=') >= 0")
    print(f"   登录: {'✅' if is_login else '❌'}")
    
    processed = set()
    saved = 0
    page = 1
    
    while page <= 50:
        print(f"\n{'='*80}")
        print(f"📄 第 {page} 页")
        print("="*80)
        
        random_wait(5, 15)
        
        # 从列表页获取所有商品
        products = get_all_products_on_page()
        print(f"   找到 {len(products)} 个商品")
        
        if not products:
            print("   ⚠️ 无商品")
            break
        
        # 获取详情页价格信息
        detail_prices = get_product_info_from_list()
        
        # 遍历商品
        new_count = 0
        for i, product in enumerate(products[:30], 1):
            pid = product['product_id']
            url = product['url']
            
            if pid in processed:
                continue
            processed.add(pid)
            
            print(f"\n   🛒 [{i}/{len(products)}] {pid}")
            
            # 从详情获取价格
            detail_info = None
            if url:
                if click_product(url):
                    random_wait(5, 15)
                    detail_info = get_product_from_detail()
                    
                    # 获取价格
                    price = detail_info.get('price', '') if detail_info else ''
                    is_deposit = detail_info.get('is_deposit', False) if detail_info else False
                    
                    # 清理标题
                    title = run_js("document.title")
                    title = re.sub(r'_京东.*', '', title)
                    title = re.sub(r'<[^>]+>', '', title).strip()[:200]
                    
                    # 保存到数据库
                    if save_product_to_db(pid, title, url, price):
                        if not is_deposit:
                            print(f"   ✅ {title[:35]}... ¥{price}")
                            saved += 1
                        else:
                            print(f"   ⏭️ 定金/待发布: {title[:35]}...")
                        new_count += 1
                    
                    # 返回列表
                    run_js("history.back()")
                    random_wait(5, 15)
                else:
                    print(f"   ❌ 点击失败")
            else:
                print(f"   ❌ 无链接")
        
        print(f"\n   本页新增: {new_count} 个")
        
        # 翻页
        print(f"\n   ⏭️ 翻页...")
        if not click_next():
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
    cursor.execute("SELECT COUNT(*) FROM products")
    total = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM products WHERE is_deposit=0")
    buyable = cursor.fetchone()[0]
    conn.close()
    
    print(f"\n{'='*80}")
    print("📊 统计")
    print("="*80)
    print(f"   访问商品: {len(processed)} 个")
    print(f"   新增: {saved} 个")
    print(f"   数据库: {total} 个")
    print(f"   可购买: {buyable} 个")
    print(f"   定金: {total - buyable} 个")
    print(f"\n✅ 完成!")
    print("="*80)


def click_next():
    """点击下一页"""
    js = """(function(){
        var nextBtn = document.querySelector('.pn-next, [class*="next"]');
        if(nextBtn){ nextBtn.click(); return 'OK'; }
        return 'FAIL';
    })()"""
    return 'OK' in run_js(js)


if __name__ == '__main__':
    random.seed()
    main()
