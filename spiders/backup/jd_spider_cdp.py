"""
京东爬虫 - CDP 方案
使用 Chrome DevTools Protocol 控制浏览器，直接获取 cookies 和请求
"""

import json
import os
import time
import websocket
import threading

try:
    import requests
except ImportError:
    requests = None

from database.db import get_connection
from database.models import Product, ProductDAO


class JD_Spider_CDP:
	"""京东爬虫 - 使用 CDP 控制 Chrome"""

	def __init__(self, ws_url="ws://localhost:9223/devtools/browser/44bff90a-2126-4691-9567-047f74df73a4"):
		self.ws_url = ws_url
		self.ws = None
		self.cookies = {}
		self.is_login = False
		self._connect()
	
	def _connect(self):
		"""连接 Chrome WebSocket"""
		try:
			self.ws = websocket.create_connection(self.ws_url, timeout=30)
			print("✅ CDP 连接成功")
			
			# 启用 Network 域
			self._send_command("Network.enable", {})
			
			# 启用 Page 域
			self._send_command("Page.enable", {})
			
			# 检查登录状态
			self._check_login()
			
		except Exception as e:
			print(f"❌ CDP 连接失败: {e}")
	
	def _send_command(self, method, params):
		"""发送 CDP 命令"""
		msg_id = int(time.time() * 1000)
		msg = json.dumps({"id": msg_id, "method": method, "params": params})
		self.ws.send(msg)
		
		# 接收响应
		response = self.ws.recv()
		return json.loads(response)
	
	def _receive_messages(self):
		"""接收 CDP 消息（后台线程）"""
		while True:
			try:
				msg = self.ws.recv()
				data = json.loads(msg)
				# 处理消息
				if "method" in data:
					self._handle_event(data)
			except:
				break
	
	def _handle_event(self, event):
		"""处理 CDP 事件"""
		method = event.get("method", "")
		params = event.get("params", {})
		
		if method == "Network.cookieAdded":
			# 新增 cookie
			cookie = params.get("cookie", {})
			self.cookies[cookie.get("name")] = cookie.get("value")
		
		elif method == "Network.responseReceived":
			# 收到响应
			resp = params.get("response", {})
			url = resp.get("url", "")
			if "jd.com" in url and resp.get("status") == 200:
				pass
	
	def _check_login(self):
		"""检查登录状态"""
		# 访问订单页验证
		self.navigate("https://order.jd.com/center/list.action")
		time.sleep(2)
		
		# 获取当前 URL
		result = self._send_command("Page.getNavigationHistory", {})
		current_index = result.get("result", {}).get("currentEntryIndex", -1)
		entries = result.get("result", {}).get("entries", [])
		
		if current_index >= 0:
			current_url = entries[current_index].get("url", "")
			if "order.jd.com" in current_url:
				self.is_login = True
				print("✅ 登录态有效")
				return True
		
		print("⚠️ 未检测到登录态")
		return False
	
	def navigate(self, url):
		"""导航到 URL"""
		self._send_command("Page.navigate", {"url": url})
		time.sleep(3)  # 等待加载
	
	def get_cookies(self):
		"""获取所有 cookies"""
		result = self._send_command("Network.getAllCookies", {})
		cookies = result.get("result", {}).get("cookies", [])
		
		self.cookies = {}
		for c in cookies:
			self.cookies[c.get("name")] = c.get("value")
		
		return self.cookies
	
	def search_products(self, keyword, max_pages=1):
		"""搜索商品"""
		if not self.is_login:
			print("❌ 未登录")
			return []
		
		products = []
		
		# 搜索 URL
		url = f"https://search.jd.com/Search?keyword={keyword}&page={2 * max_pages - 1}"
		self.navigate(url)
		
		time.sleep(random.uniform(3, 5))
		
		# 获取页面内容
		result = self._send_command("Page.getFrameTree", {})
		
		# 获取 HTML
		result = self._send_command("DOM.getDocument", {})
		root_id = result.get("result", {}).get("root", {}).get("nodeId", 0)
		
		# 尝试获取页面 HTML
		result = self._send_command("Runtime.evaluate", {
			"expression": "document.documentElement.outerHTML"
		})
		
		if result.get("result", {}).get("result"):
			html = result["result"]["result"]["value"]
			
			# 解析 HTML
			from bs4 import BeautifulSoup
			soup = BeautifulSoup(html, 'html.parser')
			
			# 查找商品
			goods = soup.select("li.gl-item")
			print(f"找到 {len(goods)} 个商品")
			
			for g in goods[:10]:
				try:
					data_sku = g.get("data-sku", "")
					name_elem = g.find("em")
					name = name_elem.text if name_elem else ""
					
					link_elem = g.find("a", class_="p-img")
					product_url = "https:" + link_elem.get("href", "") if link_elem else ""
					
					products.append({
						"product_id": data_sku,
						"name": name[:200],
						"url": product_url,
						"platform": "jd"
					})
					
					print(f"  - {name[:35]}...")
				except:
					continue
		
		return products
	
	def get_price_by_api(self, product_id):
		"""使用价格 API 获取价格（无需登录）"""
		try:
			url = f"https://p.3.cn/prices/mgets?skuIds=J_{product_id}"
			resp = requests.get(url, timeout=10)
			data = resp.json()
			if data:
				return float(data[0].get("p", 0))
		except:
			pass
		return 0.0
	
	def save_cookies_to_file(self):
		"""保存 cookies 到文件"""
		cookies_file = "data/jd_cookies_cdp.json"
		os.makedirs(os.path.dirname(cookies_file), exist_ok=True)
		
		with open(cookies_file, 'w') as f:
			json.dump(self.cookies, f, indent=2)
		
		print(f"✅ Cookies 已保存到 {cookies_file}")
	
	def close(self):
		"""关闭连接"""
		if self.ws:
			self.ws.close()


def main():
	spider = JD_Spider_CDP()
	
	if spider.is_login:
		products = spider.search_products("变形金刚", max_pages=1)
		
		if products:
			# 获取价格
			for p in products:
				p["price"] = spider.get_price_by_api(p["product_id"])
				print(f"  {p['name'][:30]}... ¥{p['price']}")
			
			# 保存到数据库
			conn = get_connection()
			for p in products:
				cursor = conn.cursor()
				cursor.execute("SELECT id FROM products WHERE jd_product_id=?", (p["product_id"],))
				if not cursor.fetchone():
					product = Product(name=p["name"], jd_product_id=p["product_id"], jd_product_url=p["url"])
					ProductDAO.insert(product)
					print(f"新增: {p['name'][:30]}...")
			conn.close()
	
	spider.close()
	print("\n完成")


if __name__ == '__main__':
	import random
	main()
