"""
批量获取京东商品信息
逐个打开商品页面，获取名称和价格
"""

import subprocess
import sqlite3
import re
from datetime import datetime

DB_PATH = 'data/transformers.db'


def get_product_info_from_page():
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
	
	# 获取页面 HTML
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
	name_patterns = [
		r'<h1[^>]*>([^<]+)</h1>',
		r'class="sku-name"[^>]*>([^<]+)',
		r'class="[^"]*name[^"]*"[^>]*>([^<]+)',
		r'<title>([^<]+)</title>',
	]
	
	name = f"变形金刚 {product_id}"
	for pattern in name_patterns:
		match = re.search(pattern, html, re.IGNORECASE)
		if match:
			name = re.sub(r'<[^>]+>', '', match.group(1)).strip()
			break
	
	# 提取价格
	price_patterns = [
		r'[¥￥](\d+\.?\d*)',
		r'"price":"(\d+\.?\d*)"',
		r'"p":"(\d+\.?\d*)"',
	]
	
	price = 0.0
	for pattern in price_patterns:
		match = re.search(pattern, html)
		if match:
			try:
				price = float(match.group(1))
				break
			except:
				pass
	
	return {
		'product_id': product_id,
		'name': name[:200],
		'url': url,
		'price': price
	}


def update_product_in_db(product_info):
	"""更新数据库中的商品信息"""
	if not product_info:
		return False
	
	conn = sqlite3.connect(DB_PATH)
	cursor = conn.cursor()
	
	# 检查是否存在
	cursor.execute("SELECT id FROM products WHERE jd_product_id=?", (product_info['product_id'],))
	existing = cursor.fetchone()
	
	if existing:
		# 更新名称
		cursor.execute(
			"UPDATE products SET name=? WHERE jd_product_id=?",
			(product_info['name'], product_info['product_id'])
		)
		
		# 记录价格
		if product_info['price'] > 0:
			cursor.execute(
				"""INSERT INTO product_prices 
				   (product_id, product_id_on_platform, price, platform, product_url, captured_at) 
				   VALUES (?, ?, ?, ?, ?, ?)""",
				(existing[0], product_info['product_id'], product_info['price'], 
				 'jd', product_info['url'], datetime.now().isoformat())
			)
		
		conn.commit()
		conn.close()
		return True
	
	conn.close()
	return False


def get_all_products_from_db():
	"""从数据库获取所有商品"""
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


def main():
	print("=" * 60)
	print("🔍 京东商品信息获取器")
	print("=" * 60)
	
	products = get_all_products_from_db()
	print(f"\n数据库中有 {len(products)} 个商品\n")
	
	for i, (db_id, product_id, url) in enumerate(products, 1):
		print(f"{i}/{len(products)}. 打开商品 {product_id}...")
		
		# 打开商品页面
		subprocess.run([
			'osascript', '-e',
			f'tell application "Safari" to open location "{url}"'
		])
		
		# 等待加载
		import time
		time.sleep(3)
		
		# 获取信息
		info = get_product_info_from_page()
		
		if info:
			update_product_in_db(info)
			print(f"   ✅ {info['name'][:40]}... ¥{info['price']}")
		else:
			print(f"   ❌ 获取失败")
		
		print()
	
	print("=" * 60)
	print("完成！所有商品信息已更新")
	print("=" * 60)


if __name__ == '__main__':
	main()
