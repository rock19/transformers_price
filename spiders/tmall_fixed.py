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

DB_PATH = 'data/transformers.db'
FONT_PATH = 'data/fonts/tmall_price.woff'
COOKIE_PATH = 'data/tmall_cookies.json'

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
        return theResult
    on error errMsg
        return "ERROR:" & errMsg
    end try
end tell
AS'''
    
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=60)
    return result.stdout.strip()


def open_url(url):
    """打开URL"""
    # 先确保Safari已打开
    subprocess.run(['open', '-a', 'Safari'])
    time.sleep(3)
    
    # 设置URL
    subprocess.run(['osascript', '-e', f'tell application "Safari" to set URL of front document to "{url}"'])


def close_safari():
    """关闭Safari"""
    subprocess.run(['osascript', '-e', 'tell application "Safari" to close every window'])
    time.sleep(2)


def scroll_to_bottom(scroll_steps=50):
    """滚动到底部（分N步，逐步加载图片 - 参考京东爬虫）"""
    step = 0
    for i in range(scroll_steps):
        step += 1
        run_js('window.scrollBy(0, 200)')  # 每次滚动200像素
        time.sleep(1.5)  # 等待1.5秒
        
        # 每步打印进度
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
console.log("找到 " + items.length + " 个商品");

for(var i=0; i<items.length; i++) {
    var item = items[i];
    var pid = item.getAttribute("data-id");
    if(!pid) continue;
    
    // 查找链接
    var link = item.querySelector("a[href*='item']");
    if(!link) link = item.querySelector("a");
    var url = link ? link.href : "";
    if(!url || url.indexOf("item") < 0) continue;
    
    // 查找图片 - 优先从photo class
    var photoDiv = item.querySelector(".photo");
    var img = photoDiv ? photoDiv.querySelector("img") : null;
    if(!img) img = item.querySelector("img");
    var imgUrl = img ? (img.src || img.getAttribute("data-src") || "") : "";
    
    // 只保留.jpg结尾的图片URL
    if(imgUrl && !imgUrl.endsWith(".jpg") && !imgUrl.endsWith(".JPG")) {
        imgUrl = "";
    }
    
    // 获取标题
    var title = img ? (img.alt || img.title || "") : "";
    
    // 获取价格
    var priceElem = item.querySelector(".c-price") || item.querySelector("[class*='price']");
    var encryptedPrice = priceElem ? priceElem.innerText.trim() : "";
    
    if(encryptedPrice) {
        // 提取款式名称（去掉【】及括号内容、去掉"变形金刚"）
        var styleName = title.replace(/变形金刚/g, "").replace(/【[^】]*】/g, "").replace(/\([^)]*\)/g, "").replace(/\（[^）]*\）/g, "").trim();
        
        products.push({
            id: pid, 
            url: url, 
            img: imgUrl, 
            title: title, 
            styleName: styleName,
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
    """保存商品（去重：根据product_url和title）"""
    if not products:
        return 0
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    new_count = 0
    today = datetime.now().strftime('%Y%m%d')
    
    for i, p in enumerate(products, 1):
        print(f"  [{i}/{len(products)}] {p['id']}")
        
        # 过滤【尾款专属链接】
        title = p.get('title', '')
        if '【尾款专属链接】' in title:
            print(f"     ⏭️ 跳过（尾款专属）")
            continue
        
        # 根据product_id去重（最重要）
        cursor.execute("SELECT id FROM tmall_products WHERE product_id=?", (p['id'],))
        if cursor.fetchone():
            print(f"     ⏭️ 已存在（product_id重复）")
            continue
        
        price = decrypt_price(p.get('encryptedPrice', ''))
        if price == 0:
            print(f"     ❌ 解密失败")
            continue
        
        level = extract_level(p.get('title', ''))
        style_name = extract_style_name(p.get('title', ''))
        
        print(f"     ✅ ¥{price} | {style_name} | {'🏷️'+level if level else ''}")
        
        try:
            cursor.execute("""
                INSERT INTO tmall_products 
                    (product_id, product_url, image_url, title, price, preprice, style_name, status, 
                     is_deposit, created_at, updated_at, shop_name, shop_url, is_purchased, is_followed, level)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                p['id'], p['url'], p.get('img', ''), p.get('title', '')[:500], price, '', style_name, 'available',
                0, datetime.now().isoformat(), datetime.now().isoformat(),
                '变形金刚玩具旗舰店', page_url, '否', '否', level
            ))
            
            cursor.execute("SELECT id FROM tmall_products WHERE product_id=?", (p['id'],))
            row_id = cursor.fetchone()[0]
            
            cursor.execute("SELECT id FROM tmall_price_history WHERE product_id=? AND created_at=?", (row_id, today))
            if not cursor.fetchone():
                cursor.execute("INSERT INTO tmall_price_history VALUES (?, ?, ?, ?, ?, ?)",
                            (None, row_id, p['url'], price, style_name, today))
            
            conn.commit()
            new_count += 1
        except Exception as e:
            print(f"     ❌ 保存失败: {e}")
    
    conn.close()
    return new_count


def crawl_page(url, page_name, scroll_steps=30):
    """爬取单页"""
    print(f"\n{'='*60}")
    print(f"📄 {page_name}")
    print("="*60)
    
    # 打开页面
    print(f"🔗 打开页面...")
    open_url(url)
    time.sleep(30)  # 等待页面加载
    
    # 尝试加载cookie
    load_cookies()
    time.sleep(10)  # 等待cookie加载
    
    # 检测登录
    if is_login_page():
        print("⚠️ 检测到登录页面！")
        print("💡 请在浏览器中登录天猫...")
        print("💡 登录成功后，按回车继续...")
        input()
        
        # 保存登录后的cookie
        print("💾 保存登录状态...")
        save_cookies()
        time.sleep(10)
    
    # 等待页面完全加载
    print("⏳ 等待页面加载...")
    time.sleep(15)
    
    # 滚动到底部
    print(f"📜 滚动到底部 ({scroll_steps}步)...")
    scroll_to_bottom(scroll_steps)
    
    # 等待数据加载
    print("⏳ 等待数据加载...")
    time.sleep(10)
    
    # 获取商品
    print("🔍 获取商品...")
    products = get_products()
    
    if not products:
        print("⚠️ 无商品，尝试重新获取...")
        time.sleep(20)
        products = get_products()
    
    if not products:
        print("⚠️ 仍然无商品")
        close_safari()
        return 0
    
    print(f"✅ 获取到 {len(products)} 个商品")
    
    # 保存
    print(f"💾 保存 {len(products)} 个商品...")
    new_count = save_products(products, page_name, url)
    
    # 保存cookie
    print("💾 保存Cookie...")
    save_cookies()
    
    # 关闭Safari
    print("🔒 关闭Safari...")
    close_safari()
    
    print(f"✅ {page_name} 完成，新增 {new_count} 个")
    return new_count


def main():
    print("="*60)
    print("🚀 天猫爬虫 - 3页完整版")
    print("="*60)
    
    try:
        font = TTFont(FONT_PATH)
        font.close()
        print("✅ 字体加载成功\n")
    except Exception as e:
        print(f"⚠️ 字体加载失败: {e}\n")
    
    # 爬取3页（每页间隔30秒）
    new1 = crawl_page(PAGE1_URL, "第1页", 50)      # 50步滚动
    print("\n⏳ 间隔30秒后再爬第2页...")
    time.sleep(30)
    
    new2 = crawl_page(PAGE2_URL, "第2页", 50)      # 50步滚动
    print("\n⏳ 间隔30秒后再爬第3页...")
    time.sleep(30)
    
    new3 = crawl_page(PAGE3_URL, "第3页", 50)      # 50步滚动
    
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
    conn.close()
    
    print(f"\n" + "="*60)
    print("📊 最终统计")
    print("="*60)
    print(f"   总商品: {total}")
    print(f"   有价格: {with_price}")
    print(f"   有级别: {with_level}")
    print(f"   有款式: {with_style}")
    print(f"   第1页新增: {new1}")
    print(f"   第2页新增: {new2}")
    print(f"   第3页新增: {new3}")
    print("="*60)


if __name__ == '__main__':
    main()
