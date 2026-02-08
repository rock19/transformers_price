"""
京东爬虫 - 增强版（方案3 + 方案4）
- 更多反检测措施
- 模拟真人行为
"""

import os
import re
import time
import json
import random
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.action_chains import ActionChains
from config import SpiderConfig, DATABASE_PATH
from database.db import get_connection


class JD_Spider_Enhanced:
	"""京东爬虫 - 增强版"""

	def __init__(self):
		self.driver = None

	def _init_driver(self):
		"""初始化浏览器（增强反检测）"""
		options = Options()
		
		# 基础设置
		options.add_argument('--no-sandbox')
		options.add_argument('--disable-dev-shm-usage')
		options.add_argument('--window-size=1920,1080')
		
		# 反检测措施
		options.add_argument('--disable-blink-features=AutomationControlled')
		options.add_experimental_option('excludeSwitches', ['enable-automation'])
		options.add_experimental_option('excludeSwitches', ['enable-logging'])
		options.add_experimental_option('useAutomationExtension', False)
		
		# 伪装真实浏览器
		options.add_argument('--disable-gpu')
		options.add_argument('--disable-software-rasterizer')
		options.add_argument('--disable-accelerated-2d-canvas')
		options.add_argument('--disable-extensions')
		options.add_argument('--disable-background-networking')
		options.add_argument('--disable-sync')
		options.add_argument('--disable-translate')
		options.add_argument('--metrics-recording-only')
		options.add_argument('--no-first-run')
		options.add_argument('--safebrowsing-disable-auto-update')
		
		# User-Agent
		options.add_argument('--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36')

		# 使用本地 ChromeDriver
		chromedriver_path = os.path.expanduser('~/Downloads/chromedriver-mac-arm64/chromedriver')
		service = Service(executable_path=chromedriver_path)
		self.driver = webdriver.Chrome(service=service, options=options)

		# 注入反检测脚本
		self._inject_anti_detection()
		
		# 加载 cookies
		self._load_cookies()

	def _inject_anti_detection(self):
		"""注入反检测脚本"""
		script = '''
			// 移除 webdriver 标记
			Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
			
			// 伪装 plugins
			Object.defineProperty(navigator, 'plugins', {get: () => [1,2,3,4,5]});
			
			// 伪装 languages
			Object.defineProperty(navigator, 'languages', {get: () => ['zh-CN', 'zh', 'en-US', 'en']});
			
			// 伪装 hardware concurrency
			Object.defineProperty(navigator, 'hardwareConcurrency', {get: () => 8});
			
			// 伪装 device memory
			Object.defineProperty(navigator, 'deviceMemory', {get: () => 8});
			
			// 移除 CDP 检测
			window.cdc_abc = undefined;
			window.cdc_asd = undefined;
			
			// 修改 window.chrome
			window.chrome = {app: {}, webstore: {}, runtime: {}};
			
			// 伪装连接信息
			Object.defineProperty(navigator, 'connection', {get: () => ({effectiveType: '4g', rtt: 50, downlink: 10})});
		'''
		self.driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {'source': script})

	def _random_delay(self, min_sec=1, max_sec=3):
		"""随机延迟（模拟真人）"""
		delay = random.uniform(min_sec, max_sec)
		time.sleep(delay)

	def _random_scroll(self):
		"""随机滚动页面（模拟真人浏览）"""
		for _ in range(3):
			scroll_amount = random.randint(300, 800)
			self.driver.execute_script(f"window.scrollBy(0, {scroll_amount})")
			time.sleep(random.uniform(0.5, 1.5))

	def _simulate_mouse_move(self):
		"""模拟鼠标移动"""
		# 随机移动到页面不同位置
		x = random.randint(100, 800)
		y = random.randint(100, 600)
		ActionChains(self.driver).move_by_offset(x, y).perform()
		self._random_delay(0.3, 0.8)

	def _load_cookies(self):
		"""加载 cookies"""
		base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
		cookies_path = os.path.join(base_dir, 'data', 'jd_cookies.json')
		
		if not os.path.exists(cookies_path):
			print("未找到 cookies 文件")
			return

		try:
			with open(cookies_path, 'r') as f:
				cookies = json.load(f)

			self.driver.get('https://www.jd.com/')
			time.sleep(2)

			added = 0
			for cookie in cookies:
				try:
					self.driver.add_cookie({
						'name': cookie['name'],
						'value': cookie['value'],
						'domain': cookie['domain'],
						'path': cookie.get('path', '/'),
					})
					added += 1
				except:
					pass

			print(f"已加载 {added} 个 cookies")
			self.driver.refresh()
			self._random_delay(1, 2)

		except Exception as e:
			print(f"加载 cookies 失败: {e}")

	def _close_driver(self):
		"""关闭浏览器"""
		if self.driver:
			self.driver.quit()
			self.driver = None

	def search_products(self, keyword: str, max_pages: int = 3) -> list:
		"""搜索商品（模拟真人行为）"""
		self._init_driver()

		products = []
		base_url = f"https://search.jd.com/Search?keyword={keyword}&enc=utf-8&wq={keyword}"

		try:
			for page in range(1, max_pages + 1):
				print(f"搜索 {keyword}，正在爬取第 {page} 页...")
				
				url = base_url + f"&page={page}"
				self.driver.get(url)
				
				# 模拟真人等待
				self._random_delay(3, 5)
				
				# 模拟真人浏览行为
				self._random_scroll()
				self._simulate_mouse_move()
				
				# 等待商品加载
				time.sleep(2)

				# 检查是否需要登录
				if '登录' in self.driver.title:
					print("⚠️ 需要登录，请手动登录...")
					input("登录完成后按回车继续...")
				
				# 解析商品列表
				soup = BeautifulSoup(self.driver.page_source, 'html.parser')
				goods_list = soup.find_all('li', class_='gl-item')

				if not goods_list:
					print("未找到商品，尝试其他选择器...")
					goods_list = soup.find_all('li', class_='J_goodsList')
				
				if not goods_list:
					print("页面可能有问题，保存截图...")
					self.driver.save_screenshot(f'jd_search_{page}.png')
					break

				for goods in goods_list[:10]:  # 每页最多10个
					try:
						data_sku = goods.get('data-sku', '')
						if not data_sku:
							continue

						name_elem = goods.find('div', class_='p-name')
						name = name_elem.get_text(strip=True) if name_elem else ''

						link_elem = goods.find('a', class_='p-img')
						product_url = 'https:' + link_elem.get('href', '') if link_elem else ''

						price = self._get_price(data_sku)

						product = {
							'product_id': data_sku,
							'name': name[:200],
							'url': product_url,
							'price': price,
							'platform': 'jd'
						}
						products.append(product)

					except Exception as e:
						print(f"解析商品失败: {e}")
						continue

				# 随机延迟后再翻页
				self._random_delay(2, 4)

		except Exception as e:
			print(f"爬取出错: {e}")
		finally:
			self._close_driver()

		return products

	def _get_price(self, product_id: str) -> float:
		"""获取商品价格"""
		price_url = f"https://p.3.cn/prices/mgets?skuIds=J_{product_id}"

		try:
			import requests
			response = requests.get(price_url, timeout=10)
			data = response.json()

			if data and len(data) > 0:
				return float(data[0].get('p', 0))
		except Exception as e:
			pass

		return 0.0


def main():
	"""测试"""
	spider = JD_Spider_Enhanced()
	
	print("测试搜索变形金刚...")
	products = spider.search_products("变形金刚", max_pages=1)
	
	print(f"\n找到 {len(products)} 个商品:")
	for i, p in enumerate(products[:5]):
		print(f"{i+1}. {p['name'][:40]}... | ¥{p['price']}")


if __name__ == "__main__":
	main()
