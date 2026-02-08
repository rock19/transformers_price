"""
京东爬虫 - 孩之宝官方旗舰店
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


class JD_Spider:
	"""京东爬虫"""

	def __init__(self):
		self.session = requests.Session()
		self.session.headers.update(SpiderConfig.HEADERS)
		self.driver = None

	def _init_driver(self):
		"""初始化Chrome浏览器"""
		options = Options()
		# options.add_argument('--headless')  # 暂时注释掉，方便调试
		options.add_argument('--no-sandbox')
		options.add_argument('--disable-dev-shm-usage')
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

		# 尝试加载已保存的 cookies
		self._load_cookies_to_driver()

	def _load_cookies_to_driver(self):
		"""从文件加载 cookies 到 WebDriver"""
		# 使用绝对路径
		base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
		cookies_path = os.path.join(base_dir, 'data', 'jd_cookies.json')
		
		if not os.path.exists(cookies_path):
			print(f"未找到 cookies 文件: {cookies_path}")
			return

		try:
			with open(cookies_path, 'r') as f:
				cookies = json.load(f)

			# 先访问京东首页
			self.driver.get('https://www.jd.com/')

			# 添加 cookies
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

			print(f"已加载 {added}/{len(cookies)} 个 cookies")
			
			# 刷新页面
			self.driver.refresh()

		except Exception as e:
			print(f"加载 cookies 失败: {e}")

	def _close_driver(self):
		"""关闭浏览器"""
		if self.driver:
			self.driver.quit()
			self.driver = None

	def _save_cookies(self, cookies):
		"""保存cookies"""
		os.makedirs('data', exist_ok=True)
		with open('data/jd_cookies.json', 'w') as f:
			json.dump(cookies, f)

	def _load_cookies(self):
		"""加载cookies"""
		try:
			with open('data/jd_cookies.json', 'r') as f:
				cookies = json.load(f)
				for cookie in cookies:
					self.session.cookies.set(cookie['name'], cookie['value'])
				return True
		except:
			return False

	def login_and_save_cookies(self):
		"""打开浏览器让用户手动登录，然后保存cookies"""
		self._init_driver()
		self.driver.get("https://www.jd.com/")
		
		input("请在浏览器中完成京东登录，然后按回车继续...")
		
		cookies = self.driver.get_cookies()
		self._save_cookies(cookies)
		print("Cookies 已保存！")
		
		self._close_driver()

	def _ensure_logged_in(self):
		"""确保有登录态，如果没有则提示登录"""
		if not self._load_cookies():
			print("未找到京东登录态，正在打开浏览器...")
			self.login_and_save_cookies()

	def login_if_needed(self):
		"""需要登录时执行登录"""
		url = "https://www.jd.com/allSort.aspx"
		response = self.session.get(url, timeout=SpiderConfig.TIMEOUT)

		if '登录' in response.text or '我的京东' not in response.text:
			print("需要登录京东，正在打开浏览器...")
			self._init_driver()
			self.driver.get(url)

			input("请在浏览器中完成登录，然后按回车继续...")

			cookies = self.driver.get_cookies()
			self._save_cookies(cookies)

			self._close_driver()

	def get_store_products(self, store_url: str = None):
		"""获取店铺商品列表"""
		# 初始化浏览器（会自动加载 cookies）
		self._init_driver()

		if store_url is None:
			store_url = SpiderConfig.JD_STORE_URL

		url = f"{store_url}?page=1"

		products = []

		# 使用Selenium处理动态加载
		self._init_driver()

		try:
			page = 1
			while True:
				print(f"正在爬取第 {page} 页...")
				self.driver.get(f"{store_url}?page={page}")

				# 等待商品加载
				time.sleep(3)

				# 滚动页面加载更多
				for i in range(3):
					self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
					time.sleep(1)

				# 解析商品列表
				soup = BeautifulSoup(self.driver.page_source, 'html.parser')
				goods_list = soup.find_all('li', class_='gl-item')

				if not goods_list:
					break

				for goods in goods_list:
					try:
						# 商品ID
						data_sku = goods.get('data-sku', '')
						if not data_sku:
							continue

						# 商品名称
						name_elem = goods.find('div', class_='p-name')
						name = name_elem.get_text(strip=True) if name_elem else ''

						# 商品链接
						link_elem = goods.find('a', class_='p-img')
						product_url = 'https:' + link_elem.get('href', '') if link_elem else ''

						# 图片链接
						img_elem = goods.find('img', class_='err-product')
						image_url = img_elem.get('src', '') or img_elem.get('data-lazy-img', '') if img_elem else ''
						if image_url and not image_url.startswith('http'):
							image_url = 'https:' + image_url

						# 价格（需要单独请求）
						price = self._get_price(data_sku)

						product = {
							'product_id': data_sku,
							'name': name,
							'url': product_url,
							'image_url': image_url,
							'price': price,
							'platform': 'jd'
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

	def _get_price(self, product_id: str) -> float:
		"""获取商品价格"""
		price_url = f"https://p.3.cn/prices/mgets?skuIds=J_{product_id}"

		try:
			response = self.session.get(price_url, timeout=SpiderConfig.TIMEOUT)
			data = response.json()

			if data and len(data) > 0:
				price_info = data[0]
				return float(price_info.get('p', 0))
		except Exception as e:
			print(f"获取价格失败: {e}")

		return 0.0

	def get_product_detail(self, product_id: str) -> dict:
		"""获取商品详情"""
		url = f"https://item.jd.com/{product_id}.html"

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
			name_elem = soup.find('div', class_='sku-name')
			if name_elem:
				detail['name'] = name_elem.get_text(strip=True)

			# 商品图片
			img_elem = soup.find('img', id='spec-img')
			if img_elem:
				detail['image_url'] = 'https:' + img_elem.get('data-origin', img_elem.get('src', ''))

			# 店铺名称
			shop_elem = soup.find('a', class_='shop-name')
			if shop_elem:
				detail['shop_name'] = shop_elem.get_text(strip=True)

		except Exception as e:
			print(f"获取商品详情失败: {e}")

		return detail

	def search_products(self, keyword: str, max_pages: int = 5) -> list:
		"""搜索商品"""
		# 初始化浏览器（会自动加载 cookies）
		self._init_driver()

		products = []

		try:
			for page in range(1, max_pages + 1):
				print(f"搜索 {keyword}，正在爬取第 {page} 页...")
				url = base_url + f"&page={page}"
				self.driver.get(url)

				time.sleep(2)

				# 滚动加载
				for i in range(2):
					self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
					time.sleep(1)

				soup = BeautifulSoup(self.driver.page_source, 'html.parser')
				goods_list = soup.find_all('li', class_='gl-item')

				if not goods_list:
					break

				for goods in goods_list:
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
							'name': name,
							'url': product_url,
							'price': price,
							'platform': 'jd'
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
		print("开始爬取京东孩之宝官方旗舰店...")

		# 先检查登录
		# self.login_if_needed()

		# 爬取商品列表
		products = self.get_store_products()

		print(f"共爬取到 {len(products)} 个商品")

		# 保存到数据库
		self.save_to_database(products)

		return products

	def save_to_database(self, products: list):
		"""保存商品到数据库"""
		from database.models import Product, ProductDAO

		conn = get_connection()
		cursor = conn.cursor()

		for p in products:
			# 检查是否已存在
			cursor.execute("SELECT id FROM products WHERE jd_product_id=?", (p['product_id'],))
			existing = cursor.fetchone()

			if existing:
				print(f"商品已存在: {p['name'][:20]}...")
				continue

			# 插入新商品
			product = Product(
				name=p['name'][:200],  # 限制长度
				jd_product_id=p['product_id'],
				jd_product_url=p.get('url', ''),
			)
			ProductDAO.insert(product)
			print(f"新增商品: {p['name'][:20]}...")

		conn.close()
		print("商品保存完成！")


def main():
	"""主函数"""
	spider = JD_Spider()

	# 爬取店铺
	products = spider.crawl_store()

	# 打印结果
	for p in products[:5]:  # 前5个
		print(f"- {p['name'][:30]}... | ¥{p['price']}")


if __name__ == "__main__":
	main()
