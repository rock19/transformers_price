"""
京东爬虫 - 基于 jd-assistant 项目方案
使用纯 requests 实现扫码登录
"""

import json
import os
import pickle
import random
import time
from datetime import datetime

import requests
from bs4 import BeautifulSoup

from config import SpiderConfig
from database.db import get_connection
from database.models import Product, ProductPrice, ProductDAO, PriceDAO


class JD_Spider_QR:
	"""京东爬虫 - 扫码登录版"""

	def __init__(self):
		self.sess = requests.session()
		self.sess.headers.update(SpiderConfig.HEADERS)
		self.headers = SpiderConfig.HEADERS
		self.is_login = False
		self.nick_name = ''
		
		# 尝试加载已保存的 cookies
		self._load_cookies()

	def _load_cookies(self):
		"""加载本地保存的 cookies"""
		# 优先使用 pickle 格式
		pkl_path = self._get_cookies_path()
		if os.path.exists(pkl_path):
			try:
				with open(pkl_path, 'rb') as f:
					cookies = pickle.load(f)
				self.sess.cookies.update(cookies)
				self.is_login = self._validate_cookies()
				if self.is_login:
					self.nick_name = self._get_user_info()
					print(f"✅ 已登录: {self.nick_name}")
					return
			except Exception as e:
				print(f"加载 pickle cookies 失败: {e}")
		
		# 尝试加载 json 格式
		json_path = self._get_cookies_json_path()
		if os.path.exists(json_path):
			try:
				with open(json_path, 'r') as f:
					cookies = json.load(f)
				
				# 转换为 requests 格式
				for cookie in cookies:
					self.sess.cookies.set(
						cookie['name'],
						cookie['value'],
						domain=cookie['domain'],
						path=cookie.get('path', '/')
					)
				
				self.is_login = self._validate_cookies()
				if self.is_login:
					self.nick_name = self._get_user_info()
					print(f"✅ 已登录: {self.nick_name}")
					# 保存为 pickle 格式以便下次使用
					self._save_cookies()
			except Exception as e:
				print(f"加载 json cookies 失败: {e}")

	def _save_cookies(self):
		"""保存 cookies"""
		cookies_file = self._get_cookies_path()
		directory = os.path.dirname(cookies_file)
		if not os.path.exists(directory):
			os.makedirs(directory)
		with open(cookies_file, 'wb') as f:
			pickle.dump(self.sess.cookies, f)
		print(f"✅ cookies 已保存")

	def _get_cookies_path(self):
		"""获取 cookies 文件路径"""
		base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
		return os.path.join(base_dir, 'data', 'jd_cookies.pkl')
	
	def _get_cookies_json_path(self):
		"""获取 json 格式 cookies 路径"""
		base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
		return os.path.join(base_dir, 'data', 'jd_cookies.json')

	def _get_login_page(self):
		"""访问登录页面"""
		url = "https://passport.jd.com/new/login.aspx"
		resp = self.sess.get(url, headers=self.headers)
		return resp

	def _get_QRcode(self):
		"""下载二维码"""
		url = 'https://qr.m.jd.com/show'
		params = {
			'appid': 133,
			'size': 147,
			't': str(int(time.time() * 1000)),
		}
		headers = {
			'Referer': 'https://passport.jd.com/new/login.aspx',
		}
		resp = self.sess.get(url, headers=headers, params=params)
		
		if resp.status_code != 200:
			print('❌ 获取二维码失败')
			return False

		QRCode_file = 'data/QRcode.png'
		directory = os.path.dirname(QRCode_file)
		if not os.path.exists(directory):
			os.makedirs(directory)
		
		with open(QRCode_file, 'wb') as f:
			f.write(resp.content)
		
		print('✅ 二维码已保存到 data/QRcode.png')
		print('请打开京东APP扫描登录')
		return True

	def _get_QRcode_ticket(self):
		"""获取扫码结果 ticket"""
		url = 'https://qr.m.jd.com/check'
		params = {
			'appid': '133',
			'callback': f'jQuery{random.randint(1000000, 9999999)}',
			'token': self.sess.cookies.get('wlfstk_smdl'),
			'_': str(int(time.time() * 1000)),
		}
		headers = {
			'Referer': 'https://passport.jd.com/new/login.aspx',
		}
		resp = self.sess.get(url, headers=headers, params=params)
		
		try:
			# 解析响应，格式: jQuery1234567({"code": 200, "ticket": "xxx"})
			text = resp.text
			start = text.find('({"')
			end = text.rfind('"})')
			if start == -1 or end == -1:
				return None
			
			json_str = text[start+1:end+1]
			data = json.loads(json_str)
			
			if data.get('code') == 200:
				return data.get('ticket')
			else:
				print(f"扫码状态: {data.get('msg', '等待中...')}")
				return None
		except Exception as e:
			return None

	def _validate_QRcode_ticket(self, ticket):
		"""验证 ticket 获取登录态"""
		url = 'https://passport.jd.com/uc/qrCodeTicketValidation'
		params = {'t': ticket}
		headers = {
			'Referer': 'https://passport.jd.com/uc/login?ltype=logout',
		}
		resp = self.sess.get(url, headers=headers, params=params)
		
		try:
			data = resp.json()
			if data.get('returnCode') == 0:
				return True
			else:
				print(f"验证失败: {data}")
				return False
		except Exception as e:
			print(f"验证异常: {e}")
			return False

	def _validate_cookies(self):
		"""验证 cookies 是否有效"""
		url = 'https://order.jd.com/center/list.action'
		params = {'rid': str(int(time.time() * 1000))}
		try:
			resp = self.sess.get(url, params=params, allow_redirects=False)
			# 如果未登录，会重定向到登录页
			return resp.status_code == 200
		except:
			return False

	def _get_user_info(self):
		"""获取用户昵称"""
		url = 'https://passport.jd.com/user/petName/getUserInfoForMiniJd.action'
		params = {
			'callback': f'jQuery{random.randint(1000000, 9999999)}',
			'_': str(int(time.time() * 1000)),
		}
		headers = {
			'Referer': 'https://order.jd.com/center/list.action',
		}
		try:
			resp = self.sess.get(url, params=params, headers=headers)
			text = resp.text
			start = text.find('({"')
			end = text.rfind('"})')
			if start != -1 and end != -1:
				json_str = text[start+1:end+1]
				data = json.loads(json_str)
				return data.get('nickName', 'jd')
		except:
			pass
		return 'jd'

	def login_by_QRcode(self):
		"""扫码登录"""
		if self.is_login:
			print('✅ 已登录')
			return True

		print('准备扫码登录...')
		self._get_login_page()
		
		if not self._get_QRcode():
			return False
		
		# 轮询获取 ticket
		ticket = None
		retry_times = 85  # 85 * 2 = 170 秒
		for i in range(retry_times):
			ticket = self._get_QRcode_ticket()
			if ticket:
				break
			if i % 10 == 0:
				print(f'等待扫码... ({i+1}/{retry_times})')
			time.sleep(2)
		
		if not ticket:
			print('❌ 二维码已过期')
			return False
		
		# 验证 ticket
		if not self._validate_QRcode_ticket(ticket):
			print('❌ 验证失败')
			return False
		
		# 登录成功
		self.is_login = True
		self.nick_name = self._get_user_info()
		self._save_cookies()
		print(f'✅ 登录成功: {self.nick_name}')
		return True

	def search_products(self, keyword, max_pages=3):
		"""搜索商品"""
		if not self.is_login:
			print('❌ 请先登录')
			return []

		products = []
		
		for page in range(1, max_pages + 1):
			print(f'\n搜索 "{keyword}" 第 {page} 页...')
			
			url = f'https://search.jd.com/Search?keyword={keyword}&enc=utf-8&wq={keyword}&page={page}'
			resp = self.sess.get(url, headers=self.headers)
			
			# 随机延迟
			time.sleep(random.uniform(2, 4))
			
			soup = BeautifulSoup(resp.text, 'html.parser')
			goods_list = soup.find_all('li', class_='gl-item')
			
			if not goods_list:
				break
			
			for goods in goods_list[:10]:
				try:
					data_sku = goods.get('data-sku', '')
					if not data_sku:
						continue
					
					name_elem = goods.find('div', class_='p-name')
					name = name_elem.get_text(strip=True) if name_elem else ''
					
					link_elem = goods.find('a', class_='p-img')
					product_url = 'https:' + link_elem.get('href', '') if link_elem else ''
					
					# 获取价格
					price = self._get_price(data_sku)
					
					products.append({
						'product_id': data_sku,
						'name': name[:200],
						'url': product_url,
						'price': price,
						'platform': 'jd'
					})
					
					print(f'  - {name[:40]}... | ¥{price}')
					
				except Exception as e:
					continue
			
			# 翻页延迟
			time.sleep(random.uniform(2, 4))
		
		return products

	def _get_price(self, product_id):
		"""获取商品价格（京东价格 API）"""
		try:
			url = f'https://p.3.cn/prices/mgets?skuIds=J_{product_id}'
			resp = self.sess.get(url, timeout=10)
			data = resp.json()
			if data:
				return float(data[0].get('p', 0))
		except:
			pass
		return 0.0

	def save_products_to_db(self, products):
		"""保存商品到数据库"""
		conn = get_connection()
		cursor = conn.cursor()
		
		for p in products:
			# 检查是否已存在
			cursor.execute("SELECT id FROM products WHERE jd_product_id=?", (p['product_id'],))
			existing = cursor.fetchone()
			
			if existing:
				print(f'商品已存在: {p["name"][:30]}...')
				continue
			
			# 插入新商品
			product = Product(
				name=p['name'],
				jd_product_id=p['product_id'],
				jd_product_url=p['url'],
			)
			ProductDAO.insert(product)
			print(f'新增商品: {p["name"][:30]}...')
		
		conn.close()
		print('\n✅ 商品保存完成！')


def main():
	"""测试"""
	spider = JD_Spider_QR()
	
	# 如果未登录，触发扫码登录
	if not spider.is_login:
		spider.login_by_QRcode()
	
	# 测试搜索
	if spider.is_login:
		products = spider.search_products('变形金刚', max_pages=1)
		print(f'\n共找到 {len(products)} 个商品')
		
		# 保存到数据库
		spider.save_products_to_db(products)


if __name__ == '__main__':
	main()
