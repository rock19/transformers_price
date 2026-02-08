"""
获取京东商品信息 - 区分定金和购买
"""

import subprocess
import sqlite3
import re
from datetime import datetime

DB_PATH = 'data/transformers.db'


def get_product_info():
	"""从当前 Safari 页面获取商品信息"""
	
	# 获取 URL
	result = subprocess.run([
		'osascript', '-e',
		'tell application "Safari" to URL of current tab of front window'
	], capture_output=True, text=True)
	
	url = result.stdout.strip()
	if 'item.jd.com' not in url:
		return None
	
	product_id = re.search(r'item\.jd\.com/(\d+)\.html', url).group(1) if re.search(r'item\.jd\.com/(\d+)\.html', url) else None
	
	# 获取 HTML
	result2 = subprocess.run([
		'osascript', '-e',
		'''tell application "Safari"
			set currentTab to current tab of front window
			set jsResult to do JavaScript "document.documentElement.outerHTML" in currentTab
			return jsResult
		end tell'''
	], capture_output=True, text=True, timeout=30)
	
	html = result2.stdout.strip()
	
	# 提取名称
	title_match = re.search(r'<title>([^<]+)</title>', html)
	title = title_match.group(1) if title_match else ""
	title = re.sub(r'_京东.*', '', title)
	title = re.sub(r'<[^>]+>', '', title).strip()[:100]
	
	# 检测是否为定金/预售商品
	deposit_keywords = ['定金', '预付', '预售', '预约', '预定', '预热', '抢先']
	is_deposit = any(kw in html for kw in deposit_keywords)
	
	# 提取价格
	price_match = re.search(r'[¥￥](\d+\.?\d*)', html)
	price = float(price_match.group(1)) if price_match else 0.0
	
	# 提取价格描述（如"预售价"）
	price_type = "购买"
	if '预售' in html or '预付' in html:
		price_type = "预售"
	if '定金' in html:
		price_type = "定金"
	
	return {
		'product_id': product_id,
		'name': title,
		'url': url,
		'price': price,
		'price_type': price_type,
		'is_deposit': is_deposit
	}


def save_to_db(info):
	"""保存到数据库"""
	if not info:
		return False
	
	conn = sqlite3.connect(DB_PATH)
	cursor = conn.cursor()
	
	# 检查是否存在
	cursor.execute("SELECT id, name FROM products WHERE jd_product_id=?", (info['product_id'],))
	existing = cursor.fetchone()
	
	if not existing:
		# 跳过定金商品
		if info['is_deposit'] or info['price_type'] in ['定金', '预售']:
			print(f"   ⏭️ 跳过定金/预售: {info['name'][:30]}...")
			conn.close()
			return False
		
		status = 'not_purchased'
		cursor.execute(
			"INSERT INTO products (name, jd_product_id, jd_product_url, status, created_at) VALUES (?, ?, ?, ?, ?)",
			(info['name'], info['product_id'], info['url'], status, datetime.now().isoformat())
		)
		product_db_id = cursor.lastrowid
		
		# 记录价格
		cursor.execute(
			"""INSERT INTO product_prices 
			   (product_id, product_id_on_platform, price, price_type, platform, product_url, captured_at) 
			   VALUES (?, ?, ?, ?, ?, ?, ?)""",
			(product_db_id, info['product_id'], info['price'], info['price_type'], 
			 'jd', info['url'], datetime.now().isoformat())
		)
		
		print(f"   ✅ {info['name'][:40]}... ¥{info['price']} ({info['price_type']})")
	
	conn.commit()
	conn.close()
	return True


def get_all_products():
	"""获取所有已保存的商品"""
	conn = sqlite3.connect(DB_PATH)
	cursor = conn.cursor()
	
	cursor.execute("""
		SELECT p.id, p.jd_product_id, p.jd_product_url 
		FROM products p
		ORDER BY p.id DESC
	""")
	products = cursor.fetchall()
	conn.close()
	return products


def batch_update():
	"""批量更新所有商品"""
	products = get_all_products()
	
	print(f"\n检查 {len(products)} 个商品...\n")
	
	for i, (db_id, product_id, url) in enumerate(products, 1):
		print(f"{i}/{len(products)}. {product_id}...")
		
		# 打开页面
		subprocess.run([
			'osascript', '-e',
			f'tell application "Safari" to open location "{url}"'
		])
		
		import time
		time.sleep(3)
		
		# 获取信息
		info = get_product_info()
		
		if info:
			save_to_db(info)
		
		print()


def main():
	print("=" * 80)
	print("🔍 京东商品获取器 - 区分定金/购买")
	print("=" * 80)
	
	# 获取当前页面
	info = get_product_info()
	
	if info:
		print(f"\n当前商品:")
		print(f"  名称: {info['name']}")
		print(f"  ID: {info['product_id']}")
		print(f"  价格: ¥{info['price']}")
		print(f"  类型: {info['price_type']}")
		print(f"  定金: {'是' if info['is_deposit'] else '否'}")
		
		if info['is_deposit'] or info['price_type'] in ['定金', '预售']:
			print(f"\n⏭️ 定金/预售商品，已跳过")
		else:
			save_to_db(info)
	else:
		print("\n⚠️ 未检测到京东商品页")
	
	print("\n" + "=" * 80)


if __name__ == '__main__':
	main()
