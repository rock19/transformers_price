"""
天猫爬虫 - 变形金刚玩具旗舰店
"""

import os
import re
import time
import json
import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from config import SpiderConfig, DATABASE_PATH
from database.db import get_connection


class TianMou_Spider:
	"""天猫爬虫"""

	def __init__(self):
		self.session = requests.Session()
		self.session.headers.update(SpiderConfig.HEADERS)
		self.driver = None

	def _init_driver(self):
		"""初始化Chrome浏览器"""
		options = Options()
		options.add_argument('--headless')
		options.add_argument('--no-sandbox')
		options.add_argument('--disable-dev-shm-usage')
		options.add_argument('--disable-gpu')
		options.add_argument('--window-size=1920,1080')
		options.add_argument('--disable-blink-features=AutomationControlled')
		options.add_argument(SpiderConfig.HEADERS['User-Agent'])

		# 使用本地 ChromeDriver
		chromedriver_path = os.path.expanduser('~/Downloads/chromedriver-mac-arm64/chromedriver')
		service = Service(executable_path=chromedriver_path)
		self.driver = webdriver.Chrome(service=service, options=options)
		self.driver.set_page_load_timeout(30)

		# 反爬处理：移除 webdriver 标记
		self.driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
			'source': '''
				Object.defineProperty(navigator, 'webdriver', {
					get: () => undefined
				})
			'''
		})

	def _close_driver(self):
		"""关闭浏览器"""
		if self.driver:
			self.driver.quit()
			self.driver = None

	def _save_cookies(self, cookies):
		"""保存cookies"""
		os.makedirs('data', exist_ok=True)
		with open('data/tmall_cookies.json', 'w') as f:
			json.dump(cookies, f)

	def _load_cookies(self):
		"""加载cookies"""
		try:
			with open('data/tmall_cookies.json', 'r') as f:
				cookies = json.load(f)
				for cookie in cookies:
					self.session.cookies.set(cookie['name'], cookie['value'])
				return True
		except:
			return False

	def login_and_save_cookies(self):
		"""打开浏览器让用户手动登录，然后保存cookies"""
		self._init_driver()
		self.driver.get("https://www.tmall.com/")
		
		input("请在浏览器中完成天猫登录，然后按回车继续...")
		
		cookies = self.driver.get_cookies()
		self._save_cookies(cookies)
		print("Cookies 已保存！")
		
		self._close_driver()

	def _ensure_logged_in(self):
		"""确保有登录态，如果没有则提示登录"""
		if not self._load_cookies():
			print("未找到天猫登录态，正在打开浏览器...")
			self.login_and_save_cookies()

	def login_if_needed(self):
		"""需要登录时执行登录"""
		url = "https://www.tmall.com"
		response = self.session.get(url, timeout=SpiderConfig.TIMEOUT)

		if '登录' in response.text:
			print("需要登录天猫，正在打开浏览器...")
			self._init_driver()
			self.driver.get(url)

			input("请在浏览器中完成登录，然后按回车继续...")

			cookies = self.driver.get_cookies()
			self._save_cookies(cookies)

			self._close_driver()

	def get_store_products(self, store_url: str = None):
		"""获取店铺商品列表"""
		# 确保已登录
		self._ensure_logged_in()

		if store_url is None:
			store_url = SpiderConfig.TMALL_STORE_URL

		products = []

		self._init_driver()

		try:
			page = 1
			while True:
				print(f"正在爬取第 {page} 页...")
				self.driver.get(f"{store_url}?page={page}")

				# 等待加载
				time.sleep(3)

				# 滚动页面
				for i in range(3):
					self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
					time.sleep(1)

				soup = BeautifulSoup(self.driver.page_source, 'html.parser')

				# 天猫商品列表选择器（需要根据实际页面调整）
				goods_list = soup.find_all('div', class_='item')

				if not goods_list:
					# 尝试其他选择器
					goods_list = soup.find_all('li', class_='item')

				if not goods_list:
					break

				for goods in goods_list:
					try:
						# 商品ID
						data_id = goods.get('data-id', '')
						if not data_id:
							continue

						# 商品名称
						name_elem = goods.find('a', class_='item-name')
						name = name_elem.get_text(strip=True) if name_elem else ''

						# 商品链接
						product_url = name_elem.get('href', '') if name_elem else ''
						if product_url and not product_url.startswith('http'):
							product_url = 'https:' + product_url

						# 图片链接
						img_elem = goods.find('img', class_='item-img')
						image_url = img_elem.get('src', '') or img_elem.get('data-ks-lazyload', '') if img_elem else ''
						if image_url and not image_url.startswith('http'):
							image_url = 'https:' + image_url

						# 价格
						price_elem = goods.find('em', class_='tb-rmb')
						price_text = price_elem.get_text(strip=True) if price_elem else '0'
						price = float(re.sub(r'[^\d.]', '', price_text)) if price_text else 0

						product = {
							'product_id': data_id,
							'name': name,
							'url': product_url,
							'image_url': image_url,
							'price': price,
							'platform': 'tmall'
						}
						products.append(product)

					except Exception as e:
						print(f"解析商品失败: {e}")
						continue

				page += 1
				time.sleep(SpiderConfig.REQUEST_DELAY)

		except Exception as e:
			print(f"爬取出错: {e}")
		finally:
			self._close_driver()

		return products

	def get_product_detail(self, product_id: str) -> dict:
		"""获取商品详情"""
		url = f"https://detail.tmall.com/item.htm?id={product_id}"

		detail = {
			'product_id': product_id,
			'url': url,
			'name': '',
			'image_url': '',
			'shop_name': '',
		}

		try:
			response = self.session.get(url, timeout=SpiderConfig.TIMEOUT)
			soup = BeautifulSoup(response.text, 'html.parser')

			# 商品名称
			name_elem = soup.find('h1', class_='tb-title')
			if name_elem:
				detail['name'] = name_elem.get_text(strip=True)

			# 商品图片
			img_elem = soup.find('img', id='J_ImgBooth')
			if img_elem:
				detail['image_url'] = img_elem.get('src', '') or img_elem.get('data-bfs', '')

			# 店铺名称
			shop_elem = soup.find('a', class_='shop-name-link')
			if shop_elem:
				detail['shop_name'] = shop_elem.get_text(strip=True)

		except Exception as e:
			print(f"获取商品详情失败: {e}")

		return detail

	def search_products(self, keyword: str, max_pages: int = 5) -> list:
		"""搜索商品"""
		# 确保已登录
		self._ensure_logged_in()

		products = []
		base_url = f"https://s.tmall.com/search?q={keyword}"

		self._init_driver()

		try:
			for page in range(1, max_pages + 1):
				print(f"搜索 {keyword}，正在爬取第 {page} 页...")
				url = base_url + f"&page={page}"
				self.driver.get(url)

				time.sleep(2)

				for i in range(2):
					self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
					time.sleep(1)

				soup = BeautifulSoup(self.driver.page_source, 'html.parser')
				goods_list = soup.find_all('div', class_='item')

				if not goods_list:
					goods_list = soup.find_all('li', class_='item')

				if not goods_list:
					break

				for goods in goods_list:
					try:
						data_id = goods.get('data-id', '')
						if not data_id:
							continue

						name_elem = goods.find('a', class_='item-name')
						name = name_elem.get_text(strip=True) if name_elem else ''

						link_elem = goods.find('a', class_='item-link')
						product_url = 'https:' + link_elem.get('href', '') if link_elem else ''

						price_elem = goods.find('em', class_='tb-rmb')
						price_text = price_elem.get_text(strip=True) if price_elem else '0'
						price = float(re.sub(r'[^\d.]', '', price_text)) if price_text else 0

						products.append({
							'product_id': data_id,
							'name': name,
							'url': product_url,
							'price': price,
							'platform': 'tmall'
						})

					except Exception as e:
						print(f"解析商品失败: {e}")
						continue

				time.sleep(SpiderConfig.REQUEST_DELAY)

		except Exception as e:
			print(f"搜索爬取出错: {e}")
		finally:
			self._close_driver()

		return products

	def crawl_store(self):
		"""爬取店铺所有商品"""
		print("开始爬取天猫变形金刚玩具旗舰店...")

		# 检查登录
		# self.login_if_needed()

		products = self.get_store_products()

		print(f"共爬取到 {len(products)} 个商品")

		self.save_to_database(products)

		return products

	def save_to_database(self, products: list):
		"""保存商品到数据库"""
		from database.models import Product, ProductDAO

		conn = get_connection()
		cursor = conn.cursor()

		for p in products:
			cursor.execute("SELECT id FROM products WHERE tmall_product_id=?", (p['product_id'],))
			existing = cursor.fetchone()

			if existing:
				print(f"商品已存在: {p['name'][:20]}...")
				continue

			product = Product(
				name=p['name'][:200],
				tmall_product_id=p['product_id'],
				tmall_product_url=p.get('url', ''),
			)
			ProductDAO.insert(product)
			print(f"新增商品: {p['name'][:20]}...")

		conn.close()
		print("商品保存完成！")


def main():
	"""主函数"""
	spider = TianMou_Spider()
	products = spider.crawl_store()

	for p in products[:5]:
		print(f"- {p['name'][:30]}... | ¥{p['price']}")


if __name__ == "__main__":
	main()
