"""
京东爬虫 - 模拟真人操作
"""

import json
import time
import random
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.action_chains import ActionChains


class JD_Spider_Real:
	"""京东爬虫 - 模拟真人"""

	def __init__(self):
		self.driver = None

	def _init_driver(self):
		options = Options()
		options.add_argument('--no-sandbox')
		options.add_argument('--disable-dev-shm-usage')
		options.add_argument('--window-size=1920,1080')
		options.add_argument('--disable-blink-features=AutomationControlled')
		options.add_experimental_option('excludeSwitches', ['enable-automation'])
		
		service = Service('/Users/xiaoke/Downloads/chromedriver-mac-arm64/chromedriver')
		self.driver = webdriver.Chrome(service=service, options=options)
		
		# 反检测
		self.driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
			'source': 'Object.defineProperty(navigator, "webdriver", {get: () => undefined})'
		})

	def _load_cookies(self):
		"""加载 cookies"""
		with open('data/jd_cookies.json', 'r') as f:
			cookies = json.load(f)
		
		self.driver.get('https://www.jd.com/')
		time.sleep(random.uniform(2, 3))
		
		for cookie in cookies:
			try:
				self.driver.add_cookie({
					'name': cookie['name'],
					'value': cookie['value'],
					'domain': cookie['domain'],
					'path': cookie.get('path', '/'),
				})
			except:
				pass
		
		self.driver.refresh()
		time.sleep(random.uniform(2, 3))

	def _human_delay(self, min_sec=2, max_sec=4):
		"""真人延迟"""
		time.sleep(random.uniform(min_sec, max_sec))

	def _human_scroll(self):
		"""真人滚动"""
		for _ in range(3):
			scroll = random.randint(300, 600)
			self.driver.execute_script(f'window.scrollBy(0, {scroll})')
			time.sleep(random.uniform(1, 2))

	def _human_move(self):
		"""真人鼠标移动"""
		actions = ActionChains(self.driver)
		for _ in range(2):
			x = random.randint(200, 800)
			y = random.randint(200, 500)
			actions.move_by_offset(x, y)
			time.sleep(random.uniform(0.3, 0.8))
		actions.perform()

	def search(self, keyword, max_pages=2):
		"""搜索商品"""
		self._init_driver()
		self._load_cookies()
		
		products = []
		base_url = f'https://search.jd.com/Search?keyword={keyword}&enc=utf-8&wq={keyword}'
		
		for page in range(1, max_pages + 1):
			print(f'\n=== 第 {page} 页 ===')
			
			url = base_url + f'&page={page}'
			self.driver.get(url)
			
			# 模拟真人等待页面加载
			print('等待页面加载...')
			self._human_delay(5, 7)
			
			# 模拟真人浏览行为
			print('模拟浏览...')
			self._human_scroll()
			self._human_move()
			self._human_delay(2, 3)
			
			# 再次滚动
			self._human_scroll()
			self._human_delay(2, 3)
			
			# 解析页面
			soup = BeautifulSoup(self.driver.page_source, 'html.parser')
			goods_list = soup.find_all('li', class_='gl-item')
			
			if not goods_list:
				# 尝试其他选择器
				goods_list = soup.find_all('li', class_='J_goodsList')
			
			print(f'找到 {len(goods_list)} 个商品')
			
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
					
					print(f'  - {name[:35]}... | ¥{price}')
					
				except Exception as e:
					continue
			
			# 翻页延迟
			if page < max_pages:
				print('翻页等待...')
				self._human_delay(3, 5)
		
		self.driver.quit()
		return products

	def _get_price(self, product_id):
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


if __name__ == '__main__':
	from bs4 import BeautifulSoup
	
	spider = JD_Spider_Real()
	products = spider.search('变形金刚', max_pages=1)
	
	print(f'\n\n共找到 {len(products)} 个商品')
