#!/usr/bin/env python3
"""
补充款式名称
"""

import subprocess
import sqlite3
import time
import random
from datetime import datetime

DB_PATH = 'data/transformers.db'


def random_wait(min_sec=3, max_sec=5):
    wait_time = random.uniform(min_sec, max_sec)
    print(f"   waiting {wait_time:.1f}s...")
    time.sleep(wait_time)


def run_js(js_code):
    with open('/tmp/jd_spider.js', 'w') as f:
        f.write(js_code)
    
    cmd = '''osascript <<'AS'
tell application "Safari"
    set jsFile to "/tmp/jd_spider.js"
    set js to do shell script "cat " & quoted form of jsFile
    set result to do JavaScript js in current tab of front window
    return result
end tell
AS'''
    
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=60)
    return result.stdout.strip()


def get_style_name(product_url):
    """从详情页获取款式名称"""
    subprocess.run(['osascript', '-e', f'tell application "Safari" to open location "{product_url}"'])
    time.sleep(6)
    
    js = '''var selected = document.querySelector('.specification-item-sku.has-image.specification-item-sku--selected');
var textElem = selected ? selected.querySelector('.specification-item-sku-text') : null;
textElem ? textElem.innerText.trim() : 'NOT_FOUND';'''
    
    result = run_js(js)
    
    subprocess.run(['osascript', '-e', 'tell application "Safari" to close front window'])
    
    if result and result != 'NOT_FOUND':
        return result
    return ''


def main():
    print("\n" + "="*80)
    print("补充款式名称")
    print("="*80)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 获取需要补充款式名称的商品
    cursor.execute("""
        SELECT id, product_id, product_url, title
        FROM jd_products
        WHERE status = 'available'
        AND (style_name IS NULL OR style_name = '')
        ORDER BY id
    """)
    
    products = cursor.fetchall()
    
    print(f"\n需要补充: {len(products)} 个商品")
    print(f"预计时间: 约 {len(products) * 8 // 60} 分钟\n")
    
    updated = 0
    skipped = 0
    
    for i, (db_id, product_id, url, title) in enumerate(products, 1):
        print(f"[{i}/{len(products)}] {product_id}")
        print(f"   {title[:40]}...")
        
        # 获取款式名称
        style = get_style_name(url)
        
        if style:
            print(f"   ✅ {style}")
            cursor.execute("UPDATE jd_products SET style_name=?, updated_at=? WHERE id=?",
                (style, datetime.now().isoformat(), db_id))
            updated += 1
        else:
            print(f"   ⚠️ 未获取到")
        
        if i < len(products):
            random_wait(3, 5)
    
    conn.commit()
    conn.close()
    
    # 统计
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM jd_products WHERE style_name IS NOT NULL AND style_name != ''")
    with_style = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM jd_products")
    total = cursor.fetchone()[0]
    conn.close()
    
    print(f"\n" + "="*80)
    print("完成")
    print("="*80)
    print(f"   补充: {updated}")
    print(f"   总有款式: {with_style}/{total}")
    print("="*80)


if __name__ == '__main__':
    main()
