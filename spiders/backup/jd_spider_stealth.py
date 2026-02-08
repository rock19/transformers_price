"""
京东爬虫 - 使用 selenium-stealth
方案1: stealth 插件反检测
"""

import os
import time
import json
import random
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium_stealth import stealth
from config import SpiderConfig


class JD_Spider_Stealth:
	"""京东爬虫 - 使用 stealth 插件"""

	def __init__(self):
		self.driver = None

	def _init_driver(self):
		"""初始化浏览器（使用 stealth 插件）"""
		options = Options()
		
		# 基础设置
		options.add_argument('--no-sandbox')
		options.add_argument('--disable-dev-shm-usage')
		options.add_argument('--window-size=1920,1080')
		options.add_argument('--disable-blink-features=AutomationControlled')
		options.add_experimental_option('excludeSwitches', ['enable-automation'])
		options.add_experimental_option('useAutomationExtension', False)
		
		# User-Agent
		options.add_argument('--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36')

		# 使用本地 ChromeDriver
		chromedriver_path = os.path.expanduser('~/Downloads/chromedriver-mac-arm64/chromedriver')
		service = Service(executable_path=chromedriver_path)
		self.driver = webdriver.Chrome(service=service, options=options)

		# 使用 stealth 插件
		stealth(self.driver,
			languages=["zh-CN", "zh", "en"],
			vendor="Google Inc.",
			platform="MacIntel",
			webgl_vendor="Intel Inc.",
			blink_settings="default",
			fix_hairline=True,
		)
		
		print("stealth 插件已应用")

	def _random_delay(self, min_sec=1, max_sec=3):
		"""随机延迟"""
		delay = random.uniform(min_sec, max_sec)
		time.sleep(delay)

	def _load_cookies(self):
		"""加载 cookies"""
		base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
		cookies_path = os.path.join(base_dir, 'data', 'jd_cookies.json')
		
		if not os.path.exists(cookies_path):
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

	def search_products(self, keyword: str, max_pages: int = 2) -> list:
		"""搜索商品"""
		self._init_driver()

		products = []
		base_url = f"https://search.jd.com/Search?keyword={keyword}&enc=utf-8&wq={keyword}"

		try:
			for page in range(1, max_pages + 1):
				print(f"搜索 {keyword}，第 {page} 页...")
				
				url = base_url + f"&page={page}"
				self.driver.get(url)
				
				# 等待加载
				self._random_delay(4, 6)
				
				# 检查登录状态
				if '登录' in self.driver.title:
					print("⚠️ 需要登录，请扫码...")
					input("登录后按回车继续...")
				
				# 滚动页面
				for _ in range(3):
					self.driver.execute_script("window.scrollBy(0, 500)")
					time.sleep(0.5)
				
				time.sleep(2)

				# 解析
				soup = BeautifulSoup(self.driver.page_source, 'html.parser')
				goods_list = soup.find_all('li', class_='gl-item')

				print(f"找到 {len(goods_list)} 个商品")

				for goods in goods_list[:10]:
					try:
						data_sku = goods.get('data-sku', '')
						if not data_sku:
							continue

						name_elem = goods.find('div', class_='p-name')
						name = name_elem.get_text(strip=True) if name_elem else ''

						link_elem = goods.find('a', class_='p-img')
						product_url = 'https:' + link_elem.get('href', '') if link_elem else ''

						price = self._get_price(data_sku)

						products.append({
							'product_id': data_sku,
							'name': name[:200],
							'url': product_url,
							'price': price,
							'platform': 'jd'
						})

					except Exception as e:
						continue

				self._random_delay(2, 4)

		except Exception as e:
			print(f"爬取出错: {e}")
		finally:
			self._close_driver()

		return products

	def _get_price(self, product_id: str) -> float:
		"""获取价格"""
		try:
			import requests
			resp = requests.get(f'https://p.3.cn/prices/mgets?skuIds=J_{product_id}', timeout=10)
			data = resp.json()
			if data:
				return float(data[0].get('p', 0))
		except:
			pass
		return 0.0


def main():
	"""测试"""
	spider = JD_Spider_Stealth()
	
	print("测试 stealth 版本爬虫...")
	products = spider.search_products("变形金刚", max_pages=1)
	
	print(f"\n找到 {len(products)} 个商品:")
	for i, p in enumerate(products[:5]):
		print(f"{i+1}. {p['name'][:40]}... | ¥{p['price']}")


if __name__ == "__main__":
	main()
