#!/usr/bin/env python3
"""
天猫爬虫 - 修正版
问题修正：
1. 款式名称：从标题提取（去掉品牌前缀"变形金刚"和货号后缀）
2. 图片：从class="photo"的img获取
3. 爬完关闭Safari
4. 增加滚动次数，确保滚到底
"""

import subprocess
import sqlite3
import time
import random
import os
import re
import json
from datetime import datetime
from fontTools.ttLib import TTFont

DB_PATH = '../data/transformers.db'
FONT_PATH = '../data/fonts/tmall_price.woff'
COOKIE_PATH = '../data/tmall_cookies.json'

PAGE1_URL = "https://thetransformers.tmall.com/category.htm?spm=a1z10.3-b.w5001-22116109517.10.77742409X6wOMa&search=y&orderType=hotsell_desc&scene=taobao_shop"
PAGE2_URL = "https://thetransformers.tmall.com/category.htm?spm=a1z10.3-b.w4011-22116109545.508.5ecd2409eajMbv&search=y&orderType=hotsell_desc&scene=taobao_shop&pageNo=2"
PAGE3_URL = "https://thetransformers.tmall.com/category.htm?spm=a1z10.3-b.w4011-22116109545.509.1a132409FfGkP2&search=y&orderType=hotsell_desc&scene=taobao_shop&pageNo=3"


def save_cookies():
    """保存Safari的cookie到文件"""
    js = '''var cookies = [];
try {
    var cookies = document.cookie.split(';').filter(function(c) { return c.trim().length > 0; });
    JSON.stringify({cookies: cookies});
} catch(e) { JSON.stringify({error: e.message}); }'''
    
    result = run_js(js)
    try:
        data = eval(result) if result else {}
        if 'cookies' in data:
            with open(COOKIE_PATH, 'w') as f:
                json.dump(data['cookies'], f)
            print(f"✅ Cookie已保存: {len(data['cookies'])} 条")
            return True
    except:
        pass
    return False


def load_cookies():
    """加载cookie到当前页面"""
    if not os.path.exists(COOKIE_PATH):
        return False
    
    try:
        with open(COOKIE_PATH, 'r') as f:
            cookies = json.load(f)
        
        # 通过JavaScript设置cookie
        js = ''
        for cookie in cookies:
            js += f'document.cookie = "{cookie.strip()}";'
        
        if js:
            run_js(js)
        print(f"✅ Cookie已加载: {len(cookies)} 条")
        return True
    except:
        pass
    return False


def run_js(js_code):
    """执行JavaScript"""
    with open('/tmp/tmall_spider.js', 'w') as f:
        f.write(js_code)
    
    cmd = '''osascript <<'AS'
tell application "Safari"
    set jsFile to "/tmp/tmall_spider.js"
    set js to do shell script "cat " & quoted form of jsFile
    try
        set theResult to do JavaScript js in current tab of front window
        if theResult is missing value then
            return "OK"
        else
            return theResult
        end if
    on error errMsg
        return "ERROR:" & errMsg
    end try
end tell
AS'''
    
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=60)
    return result.stdout.strip()


def open_url(url):
    """打开URL"""
    # 确保Safari已打开
    subprocess.run(['open', '-a', 'Safari'])
    time.sleep(3)
    
    # 创建新文档
    subprocess.run(['osascript', '-e', 'tell application "Safari" to make new document'])
    time.sleep(2)
    
    # 设置URL
    subprocess.run(['osascript', '-e', f'tell application "Safari" to set URL of front document to "{url}"'])
    print(f"✅ 已打开: {url[:60]}...")


def close_safari():
    """关闭Safari"""
    subprocess.run(['osascript', '-e', 'tell application "Safari" to close every window'])
    time.sleep(2)


def scroll_to_bottom(scroll_steps=50):
    """滚动到底部（分N步，逐步加载图片 - 参考京东爬虫）"""
    step = 0
    
    # 先滚动到顶部
    run_js('window.scrollTo(0, 0)')
    time.sleep(2)
    
    for i in range(scroll_steps):
        step += 1
        result = run_js('window.scrollBy(0, 500)')  # 每次滚动500像素
        
        # 检查是否滚动失败
        if result.startswith('ERROR'):
            print(f"      ⚠️ 滚动失败: {result}")
        
        time.sleep(1.5)  # 等待1.5秒
        
        # 每步打印进度
        if step % 10 == 0 or step == scroll_steps:
            print(f"      滚动 {step}/{scroll_steps}")
    
    # 滚动回顶部
    time.sleep(3)  # 等待页面完全加载
    run_js('window.scrollTo(0, 0)')
    time.sleep(3)


def is_login_page():
    """检测登录页面"""
    js = '''var bodyText = document.body ? document.body.innerText || "" : "";
var isLogin = bodyText.indexOf("密码登录") > -1 || bodyText.indexOf("短信登录") > -1;
JSON.stringify({isLogin: isLogin});'''
    
    result = run_js(js)
    try:
        if result.startswith("ERROR:"):
            return False
        data = eval(result) if result else {}
        return data.get('isLogin', False)
    except:
        return False


def extract_style_name(title):
    """提取款式名称（去掉【】及括号内容、去掉"变形金刚"）"""
    if not title:
        return ""
    
    # 去掉品牌前缀"变形金刚"
    title = title.replace("变形金刚", "").strip()
    
    # 去掉【】及其中内容
    title = re.sub(r'【[^】]*】', '', title).strip()
    
    # 去掉所有括号及中内容（中文括号和英文括号）
    title = re.sub(r'\([^（）]*\)', '', title).strip()
    title = re.sub(r'\（[^（）]*\）', '', title).strip()
    
    return title.strip()


def get_products():
    """获取商品"""
    js = '''var products = [];
var items = document.querySelectorAll("[data-id]");
console.log("Found " + items.length + " items");

for(var i=0; i<items.length; i++) {
    var item = items[i];
    var pid = item.getAttribute("data-id");
    if(!pid) continue;
    
    var link = item.querySelector("a[href*='item']");
    if(!link) link = item.querySelector("a");
    var url = link ? link.href : "";
    if(!url || url.indexOf("item") < 0) continue;
    
    // 获取标题
    var img = item.querySelector("img");
    var title = img ? (img.alt || img.title || "") : "";
    
    var priceElem = item.querySelector(".c-price");
    var encryptedPrice = priceElem ? priceElem.innerText.trim() : "";
    
    if(encryptedPrice) {
        products.push({
            id: pid, 
            url: url, 
            title: title,
            encryptedPrice: encryptedPrice
        });
    }
}

console.log("有价格: " + products.length);
JSON.stringify(products);'''
    
    result = run_js(js)
    if result.startswith("ERROR:"):
        print(f"      JS错误: {result}")
        return []
    
    try:
        import json
        return json.loads(result) if result else []
    except Exception as e:
        print(f"      解析失败: {e}")
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
    """保存商品
    规则：
    1. 过滤尾款/预售/定金类商品（不入库）
    2. 根据商品URL中的id查询商品表（product_id）
    3. 存在则更新；不存在则跳过
    4. 历史价格表：根据 product_id + 日期查询，有则更新，没有则插入
    """
    if not products:
        return 0
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    updated_count = 0
    today = datetime.now().strftime('%Y%m%d')
    
    # 过滤尾款/预售/定金类商品
    PRESALE_KEYWORDS = ['尾款', '预售', '定金', '预付', '预订', '全款预售']
    original_count = len(products)
    products = [p for p in products if not any(kw in p.get('title', '') for kw in PRESALE_KEYWORDS)]
    filtered_count = original_count - len(products)
    
    if filtered_count > 0:
        print(f"  🚫 过滤掉 {filtered_count} 个尾款/预售类商品")
    
    for i, p in enumerate(products, 1):
        url = p.get('url', '')
        
        # 从URL中提取id
        match = re.search(r'id=(\d+)', url)
        if not match:
            print(f"  [{i}/{len(products)}] ❌ URL格式错误")
            continue
        
        product_id_from_url = match.group(1)
        print(f"  [{i}/{len(products)}] ID:{product_id_from_url}...", end='')
        
        # 解密价格
        price = decrypt_price(p.get('encryptedPrice', ''))
        if price == 0:
            print(f" ⚠️ 价格解密失败，继续...")
        else:
            print(f" ¥{price}")
        
        # 根据 id 查询商品表
        cursor.execute("SELECT id, price FROM tmall_products WHERE product_id = ?", (product_id_from_url,))
        row = cursor.fetchone()
        
        if row:
            db_id = row[0]
            old_price = row[1]
            
            # 更新商品价格
            if old_price != price:
                cursor.execute("UPDATE tmall_products SET price=?, updated_at=? WHERE id=?",
                            (price, datetime.now().isoformat(), db_id))
                print(f" ✅ ¥{price} (¥{old_price}→¥{price})")
            else:
                print(f" ✅ ¥{price} (未变)")
            
            # 历史价格表：根据 product_id + 日期查询
            cursor.execute("SELECT id FROM tmall_price_history WHERE product_id = ? AND created_at = ?", 
                        (db_id, today))
            if cursor.fetchone():
                cursor.execute("UPDATE tmall_price_history SET price=? WHERE product_id=? AND created_at=?",
                            (price, db_id, today))
                print(f"    📜 更新历史")
            else:
                cursor.execute("INSERT INTO tmall_price_history (product_id, product_url, price, style_name, created_at) VALUES (?, ?, ?, ?, ?)",
                            (db_id, url, price, '', today))
                print(f"    📜 新增历史")
            
            updated_count += 1
        else:
            # 商品不存在，插入新记录（即使价格解密失败也要保存）
            title = p.get('title', '')[:500]
            style_name = extract_style_name(title)
            level = extract_level(title)
            
            cursor.execute("""
                INSERT INTO tmall_products 
                    (product_id, product_url, title, price, status, shop_name, shop_url, level, style_name, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                product_id_from_url, url, title,
                price, "available",
                "变形金刚玩具旗舰店", url,
                level, style_name,
                datetime.now().isoformat(), datetime.now().isoformat()
            ))
            conn.commit()
            
            if price > 0:
                print(f" ✅ ¥{price} 🆕")
            else:
                print(f" ⚠️ 价格解密失败 🆕")
            
            # 新商品也记录历史
            if price > 0:
                cursor.execute("SELECT id FROM tmall_products WHERE product_id = ?", (product_id_from_url,))
                new_row = cursor.fetchone()
                if new_row:
                    cursor.execute("INSERT INTO tmall_price_history (product_id, product_url, price, style_name, created_at) VALUES (?, ?, ?, ?, ?)",
                                (new_row[0], url, price, '', today))
                    print(f"    📜 新增历史")
            
            updated_count += 1
    
    conn.commit()
    conn.close()
    return updated_count


def crawl_one_page(url, page_name, scroll_steps):
    """爬取单页（打开Safari → 下载字体 → 滚动 → 爬数据 → 关闭Safari）"""
    print(f"\n{'='*60}")
    print(f"📄 {page_name}: {url[:60]}...")
    print("="*60)
    
    # 1. 打开Safari，输入网址
    print(f"🔗 打开Safari，输入网址...")
    open_url(url)
    time.sleep(30)  # 等待页面加载
    
    # 确认页面已打开
    result = run_js('document.URL')
    print(f"✅ 当前页面: {result[:80]}...")
    
    # 2. 使用固定字体文件（不下载新字体，避免映射错误）
    print(f"🔤 使用固定字体文件...")
    
    # 等待页面完全加载
    print("⏳ 等待页面加载...")
    time.sleep(15)
    
    # 3. 逐步下拉
    print(f"📜 逐步下拉 ({scroll_steps}次)...")
    scroll_to_bottom(scroll_steps)
    
    # 等待数据加载
    print("⏳ 等待数据加载...")
    time.sleep(10)
    
    # 4. 爬取页面数据
    print("🔍 获取商品...")
    products = get_products()
    
    if not products:
        print("⚠️ 无商品，尝试重新获取...")
        time.sleep(20)
        products = get_products()
    
    if not products:
        print("⚠️ 仍然无商品")
        return 0
    
    print(f"✅ 获取到 {len(products)} 个商品")
    
    # 保存
    print(f"💾 保存 {len(products)} 个商品...")
    new_count = save_products(products, page_name, url)
    
    # 保存cookie
    print("💾 保存Cookie...")
    save_cookies()
    
    # 5. 关闭Safari
    print("🔒 关闭Safari...")
    close_safari()
    
    print(f"✅ {page_name} 完成，新增 {new_count} 个")
    return new_count


def main():
    print("="*60)
    print("🚀 天猫爬虫 - 3页完整版")
    print("="*60)
    print("结构：打开Safari → 下载字体 → 下拉滚动 → 爬数据 → 关闭Safari")
    print("="*60)
    
    # 第1页：50步滚动
    print("\n📄 爬取第1页（50步滚动）...")
    new1 = crawl_one_page(PAGE1_URL, "第1页", 50)
    
    # 间隔30秒
    print("\n⏳ 间隔30秒后再爬第2页...")
    time.sleep(30)
    
    # 第2页：50步滚动
    print("\n📄 爬取第2页（50步滚动）...")
    new2 = crawl_one_page(PAGE2_URL, "第2页", 50)
    
    # 间隔30秒
    print("\n⏳ 间隔30秒后再爬第3页...")
    time.sleep(30)
    
    # 第3页：10步滚动
    print("\n📄 爬取第3页（10步滚动）...")
    new3 = crawl_one_page(PAGE3_URL, "第3页", 10)
    
    # 统计
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM tmall_products")
    total = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM tmall_products WHERE price > 0")
    with_price = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM tmall_products WHERE level != ''")
    with_level = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM tmall_products WHERE style_name != ''")
    with_style = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM tmall_price_history")
    price_history_count = cursor.fetchone()[0]
    conn.close()
    
    print(f"\n" + "="*60)
    print("📊 最终统计")
    print("="*60)
    print(f"   新增商品: {new1 + new2 + new3}")
    print(f"   总商品数量: {total}")
    print(f"   价格记录数量: {price_history_count}")
    print(f"   有价格: {with_price}")
    print(f"   有级别: {with_level}")
    print(f"   有款式: {with_style}")
    print(f"   第1页新增: {new1}")
    print(f"   第2页新增: {new2}")
    print(f"   第3页新增: {new3}")
    print("="*60)
    
    print("\n🎉 爬虫完成！")


if __name__ == '__main__':
    main()
