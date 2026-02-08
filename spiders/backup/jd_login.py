"""
京东自动登录脚本
模拟真人登录操作
"""

import time
import random
import os
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from webdriver_manager.chrome import ChromeDriverManager
import json


class JD_Login:
	"""京东自动登录"""

	def __init__(self):
		self.driver = None

	def _init_driver(self):
		"""初始化浏览器"""
		options = Options()
		options.add_argument('--no-sandbox')
		options.add_argument('--disable-dev-shm-usage')
		options.add_argument('--window-size=1920,1080')
		options.add_argument('--disable-blink-features=AutomationControlled')
		options.add_experimental_option('excludeSwitches', ['enable-automation'])
		
		# 伪装 User-Agent
		options.add_argument('--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36')

		# 使用 webdriver-manager 自动管理 ChromeDriver
		service = Service(ChromeDriverManager().install())
		self.driver = webdriver.Chrome(service=service, options=options)

		# 移除 webdriver 标记
		self.driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
			'source': 'Object.defineProperty(navigator, "webdriver", {get: () => undefined})'
		})

	def _human_type(self, element, text):
		"""模拟真人打字"""
		element.clear()
		for char in text:
			element.send_keys(char)
			time.sleep(random.uniform(0.05, 0.15))  # 随机延迟

	def _human_move(self):
		"""模拟真人鼠标移动"""
		actions = ActionChains(self.driver)
		for _ in range(3):
			x = random.randint(100, 800)
			y = random.randint(100, 600)
			actions.move_by_offset(x, y)
			time.sleep(random.uniform(0.2, 0.5))
		actions.perform()

	def login(self, username, password):
		"""执行登录"""
		print('打开京东登录页...')
		self.driver.get('https://passport.jd.com/new/login.aspx')
		
		# 等待页面加载
		time.sleep(random.uniform(2, 3))
		
		# 模拟鼠标移动
		self._human_move()
		
		try:
			# 检查是否有账号密码登录选项
			account_login = WebDriverWait(self.driver, 10).until(
				EC.presence_of_element_located((By.XPATH, '//a[contains(text(),"账户登录")]'))
			)
			account_login.click()
			print('点击账户登录')
			time.sleep(random.uniform(1, 2))
			
		except Exception as e:
			print(f'可能已经在账户登录页面: {e}')

		try:
			# 输入用户名
			username_input = WebDriverWait(self.driver, 10).until(
				EC.presence_of_element_located((By.ID, 'loginname'))
			)
			self._human_type(username_input, username)
			print('✅ 用户名已输入')
			time.sleep(random.uniform(0.5, 1))
			
			# 输入密码
			password_input = self.driver.find_element(By.ID, 'nloginpwd')
			self._human_type(password_input, password)
			print('✅ 密码已输入')
			time.sleep(random.uniform(0.5, 1))
			
			# 模拟鼠标移动后再点击
			self._human_move()
			
			# 点击登录按钮
			login_btn = self.driver.find_element(By.CLASS_NAME, 'login-btn')
			login_btn.click()
			print('✅ 点击登录按钮')
			
			# 等待登录结果
			time.sleep(random.uniform(5, 8))
			
			# 检查登录结果
			current_url = self.driver.current_url
			print(f'登录后 URL: {current_url}')
			
			if 'my.jd.com' in current_url or 'www.jd.com' in current_url:
				print('✅ 登录成功！')
				return True
			elif 'passport.jd.com' in current_url:
				# 可能需要验证码
				if '验证码' in self.driver.page_source:
					print('⚠️ 需要验证码，请手动处理')
					input('输入任意键继续...')
				
				# 再次检查
				time.sleep(3)
				if '我的京东' in self.driver.page_source:
					print('✅ 登录成功！')
					return True
			
			print('⚠️ 登录状态不确定，尝试访问首页...')
			self.driver.get('https://www.jd.com/')
			time.sleep(3)
			
			if '我的京东' in self.driver.page_source:
				print('✅ 登录成功！')
				return True
			
			return False
			
		except Exception as e:
			print(f'登录过程出错: {e}')
			return False

	def save_cookies(self, filepath='data/jd_cookies.json'):
		"""保存 cookies"""
		import os
		os.makedirs('data', exist_ok=True)
		
		cookies = self.driver.get_cookies()
		with open(filepath, 'w') as f:
			json.dump(cookies, f, indent=2)
		
		print(f'✅ 保存 {len(cookies)} 个 cookies 到 {filepath}')
		return len(cookies)

	def close(self):
		"""关闭浏览器"""
		if self.driver:
			self.driver.quit()


def main():
	"""测试登录"""
	# 替换为你的账号密码
	USERNAME = 'zy902211@163.com'
	PASSWORD = 'Inside58.58.'
	
	login = JD_Login()
	
	success = login.login(USERNAME, PASSWORD)
	
	if success:
		login.save_cookies()
	
	login.close()
	
	if not success:
		print('❌ 登录失败，请手动登录后保存 cookies')
		return 1
	
	return 0


if __name__ == "__main__":
	exit(main())
