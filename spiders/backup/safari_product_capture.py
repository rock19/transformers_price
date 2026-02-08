"""
Safari 京东商品抓取器
通过 AppleScript 从 Safari 获取当前页面商品信息
"""

import subprocess
import json
import re
import os
import sqlite3
from datetime import datetime

# 数据库路径
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'transformers.db')


def get_safari_url():
	"""获取 Safari 当前页面 URL"""
	result = subprocess.run([
		'osascript', '-e',
		'tell application "Safari" to URL of current tab of front window'
	], capture_output=True, text=True)
	return result.stdout.strip() if result.returncode == 0 else None


def get_safari_title():
	"""获取 Safari 当前页面标题"""
	result = subprocess.run([
		'osascript', '-e',
		'tell application "Safari" to name of current tab of front window'
	], capture_output=True, text=True)
	return result.stdout.strip() if result.returncode == 0 else None


def get_product_name():
	"""获取商品名称"""
	selectors = ['.sku-name', '#name h1', '.itemName', '.p-name em']
	for selector in selectors:
		result = subprocess.run([
			'osascript', '-e',
			f'''tell application "Safari" to do JavaScript "document.querySelector('{selector}') ? document.querySelector('{selector}').innerText.trim() : null" in current tab of front window'''
		], capture_output=True, text=True)
		name = result.stdout.strip()
		if name and name != 'null':
			return name[:200]
	return None


def get_product_price():
	"""获取商品价格"""
	selectors = ['.p-price i', '.price', '[id*="price"]', '.J_pPrice']
	for selector in selectors:
		result = subprocess.run([
			'osascript', '-e',
			f'''tell application "Safari" to do JavaScript "document.querySelector('{selector}') ? document.querySelector('{selector}').innerText : null" in current tab of front window'''
		], capture_output=True, text=True)
		price = result.stdout.strip()
		if price and price != 'null':
			# 提取数字
			match = re.search(r'([\d.]+)', price)
			if match:
				return float(match.group(1))
	return 0.0


def extract_product_id(url):
	"""从 URL 提取商品 ID"""
	if not url:
		return None
	match = re.search(r'item\.jd\.com/(\d+)\.html', url)
	return match.group(1) if match else None


def is_jd_product(url):
	"""判断是否是京东商品页"""
	return 'item.jd.com' in url if url else False


def save_to_database(product_info):
	"""保存商品到数据库"""
	conn = sqlite3.connect(DB_PATH)
	cursor = conn.cursor()
	
	# 检查是否已存在
	cursor.execute("SELECT id FROM products WHERE jd_product_id=?", 
					(product_info['product_id'],))
	existing = cursor.fetchone()
	
	if existing:
		print(f"\n⚠️ 商品已存在: {product_info['name'][:40]}...")
		
		# 更新价格
		cursor.execute(
			"""INSERT INTO product_prices 
			   (product_id, product_id_on_platform, price, platform, product_url, captured_at) 
			   VALUES (?, ?, ?, ?, ?, ?)""",
			(product_info['db_id'], product_info['product_id'], product_info['price'], 
			 'jd', product_info['url'], datetime.now().isoformat())
		)
		print(f"  ✅ 价格已更新: ¥{product_info['price']}")
	else:
		# 新增商品
		cursor.execute(
			"""INSERT INTO products 
			   (name, jd_product_id, jd_product_url, status, created_at) 
			   VALUES (?, ?, ?, 'not_purchased', ?)""",
			(product_info['name'], product_info['product_id'], 
			 product_info['url'], datetime.now().isoformat())
		)
		product_db_id = cursor.lastrowid
		
		# 记录价格
		cursor.execute(
			"""INSERT INTO product_prices 
			   (product_id, product_id_on_platform, price, platform, product_url, captured_at) 
			   VALUES (?, ?, ?, ?, ?, ?)""",
			(product_db_id, product_info['product_id'], product_info['price'], 
			 'jd', product_info['url'], datetime.now().isoformat())
		)
		
		print(f"\n✅ 新增商品!")
		print(f"  名称: {product_info['name'][:50]}...")
		print(f"  ID: {product_info['product_id']}")
		print(f"  价格: ¥{product_info['price']}")
	
	conn.commit()
	conn.close()


def get_current_product():
	"""获取当前 Safari 京东商品"""
	
	url = get_safari_url()
	
	if not url:
		print("❌ 未找到 Safari 窗口")
		return None
	
	print(f"📄 当前页面: {url}")
	
	if not is_jd_product(url):
		print("⚠️ 当前页面不是京东商品页")
		print("💡 请在 Safari 中打开一个京东商品页面")
		return None
	
	# 获取商品信息
	name = get_product_name()
	price = get_product_price()
	product_id = extract_product_id(url)
	
	if not product_id:
		print("❌ 无法提取商品 ID")
		return None
	
	product_info = {
		'url': url,
		'name': name or '未知商品',
		'price': price,
		'product_id': product_id,
		'platform': 'jd',
		'captured_at': datetime.now()
	}
	
	return product_info


def main():
	print("=" * 60)
	print("🔍 Safari 京东商品抓取器")
	print("=" * 60)
	
	product = get_current_product()
	
	if product:
		# 添加 db_id
		conn = sqlite3.connect(DB_PATH)
		cursor = conn.cursor()
		cursor.execute("SELECT id FROM products WHERE jd_product_id=?", (product['product_id'],))
		existing = cursor.fetchone()
		product['db_id'] = existing[0] if existing else None
		conn.close()
		
		print("\n📦 商品信息:")
		print(f"  名称: {product['name'][:60]}...")
		print(f"  ID: {product['product_id']}")
		print(f"  价格: ¥{product['price']}")
		
		save_to_database(product)
	
	print("\n" + "=" * 60)
	print("💡 使用方法:")
	print("   1. 在 Safari 京东中打开商品页面")
	print("   2. 运行此脚本")
	print("=" * 60)


if __name__ == '__main__':
	main()
