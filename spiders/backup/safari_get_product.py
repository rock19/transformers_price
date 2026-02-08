"""
通过 Safari AppleScript 获取京东商品信息
无需读取 cookies，直接获取页面内容
"""

import subprocess
import json
import re

def get_safari_page_content():
	"""获取 Safari 当前页面内容"""
	
	# AppleScript 获取 Safari 当前标签页的 URL 和内容
	script = '''
	tell application "Safari"
		if (count of windows) = 0 then
			return "No Safari window open"
		end if
		
		set currentTab to current tab of front window
		set pageURL to URL of currentTab
		set pageTitle to name of currentTab
		
		-- 获取页面内容
		do JavaScript "document.body.innerText" in currentTab
		
		return pageURL & "|||" & pageTitle
	end tell
	'''
	
	try:
		result = subprocess.run(
			['osascript', '-e', script],
			capture_output=True,
			text=True,
			timeout=30
		)
		
		if result.returncode == 0:
			output = result.stdout.strip()
			if output == "No Safari window open":
				return None, None, None
			
			parts = output.split('|||')
			if len(parts) >= 2:
				return parts[0], parts[1], parts[2] if len(parts) > 2 else ""
		
		return None, None, None
		
	except Exception as e:
		print(f"AppleScript 执行失败: {e}")
		return None, None, None


def extract_jd_product_info(url, page_content):
	"""从京东商品页面提取信息"""
	
	info = {
		'url': url,
		'name': '',
		'price': 0,
		'product_id': ''
	}
	
	# 从 URL 提取商品 ID
	# 格式: https://item.jd.com/100012044378.html
	match = re.search(r'item\.jd\.com/(\d+)\.html', url)
	if match:
		info['product_id'] = match.group(1)
	
	# 从页面内容提取价格
	# 京东价格格式: ¥xxx.xx
	price_pattern = r'[¥￥](\d+\.?\d*)'
	prices = re.findall(price_pattern, page_content)
	if prices:
		# 取第一个合理的价格（通常是当前价格）
		for p in prices:
			if float(p) > 1 and float(p) < 100000:  # 合理价格范围
				info['price'] = float(p)
				break
	
	# 提取商品名称
	# 京东商品标题通常在页面顶部
	name_pattern = r'【.*?】|(.+?)-.*京东'
	name_match = re.search(name_pattern, page_content)
	if name_match:
		info['name'] = name_match.group(1)[:200] if name_match.group(1) else ''
	
	return info


def get_current_product():
	"""获取当前 Safari 京东商品信息"""
	
	url, title, content = get_safari_page_content()
	
	if not url:
		print("❌ 未找到 Safari 窗口")
		return None
	
	print(f"📄 当前页面 URL: {url}")
	
	if 'jd.com' not in url and 'jd\.com' not in url:
		print("⚠️ 当前页面不是京东")
		return None
	
	info = extract_jd_product_info(url, content)
	
	if info['product_id']:
		print(f"\n✅ 商品信息:")
		print(f"  ID: {info['product_id']}")
		if info['name']:
			print(f"  名称: {info['name'][:50]}...")
		if info['price']:
			print(f"  价格: ¥{info['price']}")
		return info
	else:
		print("❌ 无法提取商品 ID")
		return None


def get_all_jd_tabs():
	"""获取 Safari 所有京东标签页"""
	
	script = '''
	tell application "Safari"
		set jdTabs to {}
		set allWindows to every window
		
		repeat with aWindow in allWindows
			set allTabs to every tab of aWindow
			repeat with aTab in allTabs
				set tabURL to URL of aTab
				if tabURL contains "jd.com" then
					set end of jdTabs to tabURL
				end if
			end if
		end repeat
		
		return jdTabs
	end tell
	'''
	
	try:
		result = subprocess.run(
			['osascript', '-e', script],
			capture_output=True,
			text=True,
			timeout=30
		)
		
		if result.returncode == 0:
			urls = [u.strip() for u in result.stdout.strip().split(',') if u.strip()]
			return urls
		
	except Exception as e:
		print(f"获取标签页失败: {e}")
	
	return []


def main():
	print("=" * 60)
	print("通过 Safari 获取京东商品信息")
	print("=" * 60)
	
	# 获取当前商品
	product = get_current_product()
	
	if product:
		print(f"\n📦 商品 ID: {product['product_id']}")
		print(f"💰 价格: ¥{product['price']}")
		
		# 获取所有京东标签页
		tabs = get_all_jd_tabs()
		if len(tabs) > 1:
			print(f"\n📑 所有京东标签页 ({len(tabs)} 个):")
			for i, url in enumerate(tabs, 1):
				print(f"  {i}. {url}")
	else:
		print("\n💡 请在 Safari 京东中打开一个商品页面，然后重新运行")
		print("   或者运行: python3 spiders/safari_get_tabs.py 获取所有标签页")


if __name__ == '__main__':
	main()
