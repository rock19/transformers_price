#!/usr/bin/env python3
"""
京东爬虫 - 使用 osascript 直接获取 Safari 内容
"""

import subprocess
import sqlite3
import re
import time
from datetime import datetime

DB_PATH = 'data/transformers.db'
SHOP_URL = 'https://mall.jd.com/view_search-396211-17821117-99-1-20-1.html'


def run_apple_script(script):
	"""运行 AppleScript 并返回结果"""
	result = subprocess.run(
		['osascript', '-e', script],
		capture_output=True,
		text=True,
		timeout=120
	)
	return result.stdout.strip(), result.stderr.strip()


def get_safari_tabs():
	"""获取所有 Safari 标签页"""
	script = '''
	tell application "Safari"
		set tabList to {}
		repeat with aWindow in every window
			repeat with aTab in every tab of aWindow
				set end of tabList to {name of aTab, URL of aTab}
			end repeat
		end repeat
		return tabList
	end tell
	'''
	stdout, stderr = run_apple_script(script)
	return stdout


def close_all_windows():
	"""关闭所有 Safari 窗口"""
	subprocess.run(['osascript', '-e', 'tell application "Safari" to close every window'])
	time.sleep(1)


def open_new_window(url):
	"""打开新窗口"""
	subprocess.run([
		'osascript', '-e',
		f'tell application "Safari" to make new document at front with properties {{URL:"{url}"}}'
	])
	time.sleep(5)


def get_page_html_appleScript():
	"""用 AppleScript 获取完整 HTML"""
	script = '''
	tell application "Safari"
		set currentTab to current tab of front window
		set pageData to {}
		
		-- 获取 URL
		set url to URL of currentTab
		set end of pageData to url
		
		-- 获取 body 内容
		set bodyContent to ""
		try
			set bodyContent to do JavaScript "document.body.innerHTML" in currentTab
		on error
			set bodyContent to ""
		end try
		set end of pageData to bodyContent
		
		-- 获取页面文本
		set pageText to ""
		try
			set pageText to do JavaScript "document.body.innerText" in currentTab
		on error
			set pageText to ""
		end try
		set end of pageData to pageText
		
		return pageData
	end tell
	'''
	
	stdout, stderr = run_apple_script(script)
	lines = [l for l in stdout.split('\n') if l.strip()]
	
	if len(lines) >= 3:
		return {
			'url': lines[0],
			'html': lines[1],
			'text': lines[2]
		}
	return None


def extract_product_links(html):
	"""从 HTML 提取商品链接"""
	if not html:
		return []
	
	links = re.findall(r'item\.jd\.com/(\d+)\.html', html)
	unique = list(set([f'https://item.jd.com/{pid}.html' for pid in links]))
	return unique


def get_page_count(text):
	"""获取总页数"""
	# 查找 "共X页" 格式
	match = re.search(r'共(\d+)页', text)
	if match:
		return int(match.group(1))
	
	# 查找分页信息
	match = re.search(r'pagination|page.*?(\d+).*?of.*?(\d+)', text, re.IGNORECASE)
	if match:
		return int(match.group(2))
	
	return 1


def get_current_page(text):
	"""获取当前页码"""
	match = re.search(r'>(\d+)</[^>]*class="[^"]*pn-curr[^"]*"', text)
	if match:
		return int(match.group(1))
	
	# 查找当前页
	match = re.search(r'class="[^"]*pn-curr[^"]*"[^>]*>(\d+)<', text)
	if match:
		return int(match.group(1))
	
	return 1


def go_to_next_page(text, current_url):
	"""翻到下一页"""
	# 查找下一页 URL
	next_patterns = [
		r'href=["\']([^"\']*page=\d+[^"\']*)["\']',
		r'href=["\']([^"\']*next[^"\']*)["\']',
	]
	
	for pattern in next_patterns:
		match = re.search(pattern, text, re.IGNORECASE)
		if match:
			next_url = match.group(1)
			# 补全相对路径
			if next_url.startswith('/'):
				next_url = 'https://mall.jd.com' + next_url
			elif not next_url.startswith('http'):
				next_url = current_url.split('?')[0] + '?' + next_url
			
			subprocess.run([
				'osascript', '-e',
				f'tell application "Safari" to open location "{next_url}"'
			])
			time.sleep(3)
			return True
	
	return False


def get_product_info_from_text(text, html):
	"""从页面文本获取商品信息"""
	# 价格
	price_match = re.search(r'[¥￥](\d+\.?\d*)', text)
	price = float(price_match.group(1)) if price_match else 0.0
	
	# 标题
	title_match = re.search(r'<title>([^<]+)</title>', html)
	title = title_match.group(1) if title_match else ""
	title = re.sub(r'_京东.*', '', title)
	title = re.sub(r'<[^>]+>', '', title).strip()[:200]
	
	# 判断定金
	deposit_keywords = ['定金', '预付', '预售', '预约', '预定', '预热', '抢先', '预售价']
	is_deposit = any(kw in text for kw in deposit_keywords)
	
	return {
		'name': title,
		'price': price,
		'is_deposit': is_deposit
	}


def save_to_db(product, product_id, url):
	"""保存到数据库"""
	if not product_id:
		return False
	
	conn = sqlite3.connect(DB_PATH)
	cursor = conn.cursor()
	
	cursor.execute("SELECT id FROM products WHERE jd_product_id=?", (product_id,))
	if cursor.fetchone():
		conn.close()
		return False
	
	if product['is_deposit']:
		print(f"   ⏭️ 定金/预售: {product['name'][:40]}...")
		conn.close()
		return False
	
	status = 'not_purchased'
	cursor.execute(
		"""INSERT INTO products 
		   (name, jd_product_id, jd_product_url, shop_id, status, is_deposit, created_at) 
		   VALUES (?, ?, ?, ?, ?, ?, ?)""",
		(product['name'], product_id, url, 'haseba', status, 0, datetime.now().isoformat())
	)
	
	db_id = cursor.lastrowid
	
	cursor.execute(
		"""INSERT INTO product_prices 
		   (product_id, product_id_on_platform, price, price_type, platform, product_url, captured_at) 
		   VALUES (?, ?, ?, ?, ?, ?, ?)""",
		(db_id, product_id, product['price'], '购买', 'jd', url, datetime.now().isoformat())
	)
	
	conn.commit()
	conn.close()
	return True


def main():
	print("\n" + "="*80)
	print("🚀 京东商品爬虫 - 使用 AppleScript")
	print("="*80)
	
	# 关闭旧窗口
	print("\n🛑 关闭旧窗口...")
	close_all_windows()
	
	# 打开新窗口
	print(f"\n🛒 打开 {SHOP_URL}...")
	open_new_window(SHOP_URL)
	
	# 遍历所有页面
	processed = set()
	total_saved = 0
	page = 1
	
	while page <= 50:  # 最多50页
		print(f"\n{'='*80}")
		print(f"📄 第 {page} 页")
		print("="*80)
		
		# 获取页面信息
		page_data = get_page_html_appleScript()
		
		if not page_data:
			print("❌ 无法获取页面内容")
			break
		
		html = page_data.get('html', '')
		text = page_data.get('text', '')
		current_url = page_data.get('url', '')
		
		if not html:
			print("❌ HTML 为空")
			break
		
		# 页数
		page_count = get_page_count(text)
		current = get_current_page(text)
		
		print(f"   总页数: {page_count}")
		print(f"   当前页: {current}")
		
		# 获取商品链接
		links = extract_product_links(html)
		print(f"   商品数: {len(links)}")
		
		if len(links) == 0:
			print("⚠️ 没有商品，停止")
			break
		
		# 遍历商品
		new_count = 0
		for i, link in enumerate(links[:20], 1):  # 每页最多20个
			if link in processed:
				continue
			processed.add(link)
			
			print(f"\n   🛒 [{i}/{len(links)}] {link}")
			
			# 打开商品
			subprocess.run([
				'osascript', '-e',
				f'tell application "Safari" to open location "{link}"'
			])
			time.sleep(3)
			
			# 获取商品信息
			product_data = get_page_html_appleScript()
			
			if product_data:
				product_id_match = re.search(r'item\.jd\.com/(\d+)\.html', link)
				product_id = product_id_match.group(1) if product_id_match else None
				
				product = get_product_info_from_text(
					product_data.get('text', ''),
					product_data.get('html', '')
				)
				
				if save_to_db(product, product_id, link):
					print(f"   ✅ {product['name'][:40]}... ¥{product['price']}")
					new_count += 1
					total_saved += 1
		
		# 翻页
		if page >= page_count:
			print(f"\n✅ 最后一页完成")
			break
		
		print(f"\n⏭️ 翻到第 {page+1} 页...")
		if not go_to_next_page(text, current_url):
			print("⚠️ 无法翻页")
			break
		
		page += 1
		time.sleep(3)
	
	# 关闭窗口
	print(f"\n🛑 关闭爬虫窗口...")
	subprocess.run(['osascript', '-e', 'tell application "Safari" to close front window'])
	
	# 统计
	conn = sqlite3.connect(DB_PATH)
	cursor = conn.cursor()
	cursor.execute("SELECT COUNT(*) FROM products WHERE shop_id='haseba'")
	db_count = cursor.fetchone()[0]
	conn.close()
	
	print(f"\n{'='*80}")
	print("📊 统计")
	print("="*80)
	print(f"   访问商品: {len(processed)} 个")
	print(f"   新增商品: {total_saved} 个")
	print(f"   数据库总计: {db_count} 个")
	print(f"\n✅ 完成！")
	print("="*80)


if __name__ == '__main__':
	main()
