#!/usr/bin/env python3
"""
京东爬虫 - 简化版
根据京东HTML结构解析，一个详情页对应一个款式
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


def get_page_html():
    return run_js("document.documentElement.outerHTML")


def get_page_text():
    return run_js("document.body.innerText")


def parse_jd_products_from_html(html):
    """
    解析京东商品列表页
    
    结构:
    <div class="j-module">
      <li style...>
        <div class="jItem">
          <div class="jPic">
            <a href="商品URL">
              <img src="商品图片">
              <img alt="商品标题">
          <div class="jdPrice">
            <span class="jdNum" preprice="价格">
            或: data-hide-price="true" (待发布)
    """
    products = []
    
    # 找到 j-module 容器
    jmodule_match = re.search(r'<div[^>]*class="j-module"[^>]*>(.*?)</div>', html, re.DOTALL)
    if not jmodule_match:
        print("   ⚠️ 未找到 j-module 容器")
        return products
    
    jmodule_html = jmodule_match.group(1)
    
    # 找到所有 <li> 标签
    li_pattern = r'<li[^>]*style[^>]*>(.*?)</li>'
    li_items = re.findall(li_pattern, jmodule_html, re.DOTALL)
    
    print(f"   📦 找到 {len(li_items)} 个 <li> 元素")
    
    for i, li_html in enumerate(li_items):
        try:
            # 解析 jItem
            jitem_match = re.search(r'<div[^>]*class="jItem"[^>]*>(.*?)</div>', li_html, re.DOTALL)
            if not jitem_match:
                continue
            
            jitem_html = jitem_match.group(1)
            
            # 提取商品URL
            url_match = re.search(r'<a[^>]*href=["\']([^"\']*)["\'][^>]*>', jitem_html)
            product_url = url_match.group(1) if url_match else ""
            if product_url and not product_url.startswith('http'):
                product_url = 'https:' + product_url if product_url.startswith('//') else product_url
            
            # 提取商品ID
            product_id_match = re.search(r'item\.jd\.com/(\d+)\.html', product_url)
            product_id = product_id_match.group(1) if product_id_match else ""
            
            if not product_id:
                continue
            
            # 提取图片URL
            img_match = re.search(r'<img[^>]*src=["\']([^"\']*)["\'][^>]*>', jitem_html)
            image_url = img_match.group(1) if img_match else ""
            
            # 提取标题 (alt属性)
            alt_match = re.search(r'<img[^>]*alt=["\']([^"\']*)["\'][^>]*>', jitem_html)
            title = alt_match.group(1) if alt_match else ""
            title = unescape(title) if title else ""
            
            # 备选：title属性
            if not title:
                title_match = re.search(r'<a[^>]*title=["\']([^"\']*)["\']', jitem_html)
                title = title_match.group(1) if title_match else ""
                title = unescape(title) if title else ""
            
            # 清理标题
            title = re.sub(r'<[^>]+>', '', title)
            title = title.strip()[:500]
            if not title:
                title = f"商品 {product_id}"
            
            # 提取价格
            price = 0.0
            preprice = ""
            is_pending = False
            
            # 检查是否有 data-hide-price (待发布)
            if 'data-hide-price="true"' in jitem_html:
                is_pending = True
            elif 'hide-price' in jitem_html.lower():
                is_pending = True
            
            # 提取 jdNum 和 preprice
            jdnum_match = re.search(r'<span[^>]*class="jdNum"[^>]*preprice=["\']([^"\']*)["\'][^>]*>', jitem_html)
            if jdnum_match:
                preprice = jdnum_match.group(1)
                try:
                    price = float(preprice) if preprice else 0.0
                except:
                    price = 0.0
            else:
                # 备选：查找价格文本
                price_match = re.search(r'[¥￥](\d+\.?\d*)', jitem_html)
                if price_match:
                    try:
                        price = float(price_match.group(1))
                    except:
                        price = 0.0
            
            # 如果没有价格，也标记为待发布
            if price == 0.0 and not is_pending:
                if not re.search(r'jdNum|jdPrice|price', jitem_html, re.IGNORECASE):
                    is_pending = True
            
            status = 'pending' if is_pending else 'available'
            
            product = {
                'product_id': product_id,
                'product_url': product_url,
                'image_url': image_url,
                'title': title,
                'price': price,
                'preprice': preprice,
                'status': status,
                'is_deposit': 1 if is_pending else 0
            }
            
            products.append(product)
            status_mark = '⏭️' if is_pending else '✅'
            print(f"   {status_mark} [{i+1}] {product_id}: {title[:30]}... ¥{price or '?'}")
            
        except Exception as e:
            print(f"   ⚠️ 解析第 {i+1} 个商品失败: {e}")
            continue
    
    return products


def get_style_name_from_detail():
    """
    从详情页获取款式名称
    
    结构:
    <div class="specification-item-sku has-image specification-item-sku--selected">
      <span class="specification-item-sku-text">
        款式名称
    """
    js = """(function(){
        var selected = document.querySelector('.specification-item-sku.has-image.specification-item-sku--selected');
        if(selected) {
            var textElem = selected.querySelector('.specification-item-sku-text');
            if(textElem) {
                return textElem.innerText.trim();
            }
        }
        // 备选：查找任意选中的款式
        var allElems = document.querySelectorAll('.specification-item-sku-text');
        if(allElems && allElems.length > 0) {
            return allElems[0].innerText.trim();
        }
        return '';
    })()"""
    
    result = run_js(js)
    return result.strip() if result else ""


def save_to_jd_table(products):
    """保存到京东商品表"""
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
            # 更新价格和状态
            cursor.execute("""
                UPDATE jd_products SET 
                    price=?, preprice=?, status=?, is_deposit=?, updated_at=?
                WHERE product_id=?
            """, (p['price'], p['preprice'], p['status'], p['is_deposit'], 
                  datetime.now().isoformat(), p['product_id']))
        else:
            # 新增
            cursor.execute("""
                INSERT INTO jd_products 
                    (product_id, product_url, image_url, title, price, preprice, 
                     status, is_deposit, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                p['product_id'], p['product_url'], p['image_url'], p['title'],
                p['price'], p['preprice'], p['status'], p['is_deposit'],
                datetime.now().isoformat(), datetime.now().isoformat()
            ))
            
            if p['is_deposit']:
                pending_count += 1
            else:
                new_count += 1
    
    conn.commit()
    conn.close()
    
    return new_count, pending_count


def update_style_name(product_id, style_name):
    """更新款式名称"""
    if not style_name:
        return
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE jd_products SET style_name=?, updated_at=? WHERE product_id=?",
        (style_name, datetime.now().isoformat(), product_id)
    )
    conn.commit()
    conn.close()


def click_link_by_url(url):
    """根据URL点击链接"""
    match = re.search(r'item\.jd\.com/(\d+)\.html', url)
    if not match:
        return False
    
    product_id = match.group(1)
    
    js = f"""(function(){{
        var as = document.querySelectorAll('a');
        for(var i=0; i<as.length; i++) {{
            if(as[i].href && as[i].href.indexOf('{product_id}') > -1) {{
                as[i].click();
                return 'OK';
            }}
        }}
        return 'FAIL';
    }})()"""
    
    return 'OK' in run_js(js)


def go_back():
    """返回"""
    run_js("history.back()")


def click_next_page():
    """点击下一页"""
    js = """(function(){
        var nextBtn = document.querySelector('.pn-next, [class*="next"]');
        if(nextBtn) { nextBtn.click(); return 'OK'; }
        return 'FAIL';
    })()"""
    return 'OK' in run_js(js)


def get_total_pages():
    """获取总页数"""
    text = get_page_text()
    match = re.search(r'共(\d+)页', text)
    if match:
        return int(match.group(1))
    return 1


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
    
    print("")
    print("="*80)
    print("📊 统计")
    print("="*80)
    print(f"   访问商品: {len(processed)} 个")
    print(f"   新增: {total_new} 个")
    print(f"   数据库: {db_total} 个")
    print(f"   在售: {available} 个")
    print(f"   待发布: {pending} 个")
    print(f"\\n✅ 完成!")
    print("="*80)


if __name__ == '__main__':
    random.seed()
    main()
