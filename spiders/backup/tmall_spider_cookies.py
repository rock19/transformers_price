#!/usr/bin/env python3
"""
天猫爬虫 - 使用 cookies 登录版 + 字体解密 + 分页
"""

import subprocess
import sqlite3
import time
import random
import json
import os
import re
from datetime import datetime
from fontTools.ttLib import TTFont

DB_PATH = 'data/transformers.db'
FONT_DIR = 'data/fonts'
FONT_PATH = os.path.join(FONT_DIR, 'tmall_price.woff')
os.makedirs(FONT_DIR, exist_ok=True)

# 店铺配置
SHOPS = [
    {
        "name": "变形金刚玩具旗舰店",
        "url": "https://thetransformers.tmall.com/category.htm?spm=a1z10.1-b.w5001-22116109517.10.67755bd938bATH&search=y&orderType=hotsell_desc&scene=taobao_shop"
    }
]


# 全局字体缓存
_font_cache = None


def get_font():
    """获取字体对象（缓存）"""
    global _font_cache
    if _font_cache is None:
        try:
            if os.path.exists(FONT_PATH):
                _font_cache = TTFont(FONT_PATH)
                print(f"✅ 加载字体: {FONT_PATH}")
        except Exception as e:
            print(f"⚠️ 加载字体失败: {e}")
    return _font_cache


def decrypt_price(encrypted_chars):
    """解密价格：加密字符 -> 实际数字"""
    if not encrypted_chars:
        return 0
    
    font = get_font()
    if not font:
        print(f"      ⚠️ 字体文件不存在: {FONT_PATH}")
        return 0
    
    try:
        font_cmap = font['cmap'].getBestCmap()
        
        base_dict = {
            'period': '.',
            'zero': '0',
            'one': '1',
            'two': '2',
            'three': '3',
            'four': '4',
            'five': '5',
            'six': '6',
            'seven': '7',
            'eight': '8',
            'nine': '9',
        }
        
        price_str = ''
        for char in encrypted_chars:
            unicode_code = ord(char)
            name = font_cmap.get(unicode_code)
            if name and name in base_dict:
                price_str += base_dict[name]
        
        return float(price_str) if price_str else 0
    except Exception as e:
        print(f"      ⚠️ 字体解析失败: {e}")
        return 0


def extract_level(title):
    """识别变形金刚级别"""
    title = title.upper()
    
    if 'MP-' in title or 'MPG-' in title or '大师级' in title:
        return '大师级'
    elif '泰坦级' in title or title.endswith('L级') or ' V级' in title or 'V级' in title:
        return '泰坦级'
    elif '领袖级' in title:
        return '领袖级'
    elif '航行家级' in title:
        return '航行家级'
    elif '加强级' in title or title.endswith('-C') or title.endswith('C级'):
        return '加强级'
    elif '核心级' in title or '-BASIC' in title or 'BASIC' in title:
        return '核心级'
    return ''


def load_cookies():
    """加载 cookies"""
    try:
        with open('data/tmall_cookies.json', 'r') as f:
            cookies = json.load(f)
            print(f"✅ 加载了 {len(cookies)} 个 cookies")
            return cookies
    except Exception as e:
        print(f"⚠️ 加载 cookies 失败: {e}")
        return None


def apply_cookies_to_safari():
    """通过 Safari 设置 cookies"""
    cookies = load_cookies()
    if not cookies:
        return False
    
    for cookie in cookies:
        try:
            name = cookie.get('name', '')
            value = cookie.get('value', '')
            domain = cookie.get('domain', '.tmall.com')
            
            if not cookie.get('httpOnly', False):
                cmd = f'''
                osascript -e '
                tell application "Safari"
                    if name of every document is not "" then
                        do JavaScript "document.cookie=\\"{name}={value}; domain={domain}; path=/\\"" in current tab of front window
                    end if
                end tell
                '
                '''
                subprocess.run(cmd, shell=True, capture_output=True, text=True)
        except:
            pass
    
    print("✅ Cookies 已应用")
    return True


def run_js(js_code):
    """执行 JavaScript"""
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


def scroll_page():
    """滚动页面加载更多"""
    print(f"      📜 滚动加载...")
    for i in range(10):
        run_js('window.scrollBy(0, 600)')
        time.sleep(1.5)
    time.sleep(3)
    print(f"      ✅ 滚动完成")


def open_page(page_num):
    """打开指定页面"""
    base_url = "https://thetransformers.tmall.com/category.htm"
    # 关键：使用 pageNo 参数
    params = f"pageNo={page_num}&search=y&orderType=hotsell_desc&scene=taobao_shop"
    url = base_url + "?" + params
    
    print(f"      📄 打开第{page_num}页...")
    subprocess.run(['osascript', '-e', f'tell application "Safari" to make new document with properties {{URL:"{url}"}}'])
    time.sleep(12 + random.uniform(3, 5))


def get_products_from_page():
    """获取页面商品列表"""
    scroll_page()
    
    js = '''var products = [];
var items = document.querySelectorAll("[class*='item']");
console.log("找到" + items.length + "个item元素");

for(var i=0; i<items.length; i++) {
    var item = items[i];
    var pid = item.getAttribute("data-id") || item.getAttribute("data-itemid") || item.getAttribute("id");
    if(!pid || pid.length < 5) continue;
    
    var link = item.querySelector("a[href*='item']") || item.querySelector("a");
    if(!link) continue;
    
    var url = link.href || "";
    if(!url || url.indexOf("item") < 0) continue;
    
    var img = item.querySelector("img") || link.querySelector("img");
    var imgUrl = img ? (img.src || img.getAttribute("data-src") || img.getAttribute("data-original") || "") : "";
    var title = img ? (img.alt || img.title || "") : "";
    
    var priceElem = item.querySelector(".c-price") || item.querySelector("[class*='price']");
    var encryptedPrice = priceElem ? priceElem.innerText.trim() : "";
    
    if(pid && url) {
        products.push({
            id: pid,
            url: url,
            img: imgUrl,
            title: title,
            encryptedPrice: encryptedPrice,
            price: 0,
            status: "pending"
        });
    }
}

console.log("解析到" + products.length + "个商品");
JSON.stringify(products);'''
    
    result = run_js(js)
    
    try:
        products = json.loads(result) if result else []
        if products:
            print(f"      🔍 本页: {len(products)} 个")
        return products
    except Exception as e:
        print(f"      ❌ 解析失败: {e}")
        return []


def save_products(products, shop):
    """保存商品到数据库"""
    if not products:
        return 0, 0
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    new_count = 0
    style_count = 0
    today = datetime.now().strftime('%Y%m%d')
    
    for i, p in enumerate(products, 1):
        print(f"      [{i}/{len(products)}] {p['id']}")
        
        # 检查是否已存在
        cursor.execute("SELECT id FROM tmall_products WHERE product_id=?", (p['id'],))
        if cursor.fetchone():
            print(f"         ⏭️ 已存在，跳过")
            continue
        
        # 解密价格
        price = 0
        if p.get('encryptedPrice'):
            print(f"         🔐 解密价格...")
            price = decrypt_price(p['encryptedPrice'])
            if price > 0:
                print(f"         ✅ ¥{price}")
        
        if price == 0:
            print(f"         ⚠️ 无法获取价格，跳过")
            continue
        
        # 识别级别
        level = extract_level(p.get('title', '') + ' ' + p.get('encryptedPrice', ''))
        if level:
            print(f"         🏷️ {level}")
        
        try:
            cursor.execute("""
                INSERT INTO tmall_products 
                    (product_id, product_url, image_url, title, price, status, shop_name, shop_url, level, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                p['id'], p['url'], p['img'], p['title'][:500],
                price, "available",
                shop['name'], shop['url'], level,
                datetime.now().isoformat(), datetime.now().isoformat()
            ))
            conn.commit()
        except Exception as e:
            print(f"         ❌ 保存失败: {e}")
            continue
        
        cursor.execute("SELECT id FROM tmall_products WHERE product_id=?", (p['id'],))
        result = cursor.fetchone()
        product_row_id = result[0] if result else None
        
        if price > 0 and product_row_id:
            cursor.execute("SELECT id FROM tmall_price_history WHERE product_id=? AND created_at=?", 
                          (product_row_id, today))
            if not cursor.fetchone():
                try:
                    cursor.execute("""
                        INSERT INTO tmall_price_history (product_id, product_url, price, created_at)
                        VALUES (?, ?, ?, ?)
                    """, (product_row_id, p['url'], price, today))
                    conn.commit()
                except:
                    pass
        
        new_count += 1
    
    conn.close()
    return new_count, style_count


def crawl_shop(shop):
    print(f"\n{'='*80}")
    print(f"🏪 {shop['name']}")
    print(f"{'='*80}")
    
    # 预加载字体
    get_font()
    
    # 应用cookies
    apply_cookies_to_safari()
    
    # 爬取多页
    all_products = []
    for page in range(1, 6):  # 先爬前5页测试
        print(f"\n--- 第 {page}/5 页 ---")
        
        if page > 1:
            open_page(page)
        
        products = get_products_from_page()
        all_products.extend(products)
    
    print(f"\n💾 保存 {len(all_products)} 个商品...")
    new_count, style_count = save_products(all_products, shop)
    
    return len(all_products), new_count, style_count


def main():
    print("\n" + "="*80)
    print("🚀 天猫爬虫 - Cookies 版 + 字体解密 + 分页")
    print("="*80)
    
    total_products = 0
    total_new = 0
    total_styles = 0
    
    for shop in SHOPS:
        products, new_count, style_count = crawl_shop(shop)
        total_products += products
        total_new += new_count
        total_styles += style_count
    
    print(f"\n🔒 关闭浏览器...")
    subprocess.run(['osascript', '-e', 'tell application "Safari" to close every window'])
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM tmall_products")
    total = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM tmall_price_history")
    history = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM tmall_products WHERE status='available'")
    available_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM tmall_products WHERE level != ''")
    level_count = cursor.fetchone()[0]
    
    conn.close()
    
    print(f"\n" + "="*80)
    print("📊 最终统计")
    print("="*80)
    print(f"  总商品: {total_products} | 新增: {total_new}")
    print(f"  有价格: {available_count} | 有级别: {level_count}")
    print(f"  历史记录: {history}")
    print(f"\n✅ 完成!")
    print("="*80)


if __name__ == '__main__':
    main()
