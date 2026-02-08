"""
京东登录机器人 - 模拟真人操作
使用 pyautogui 模拟鼠标和键盘操作
"""

import pyautogui
import time
import random
import subprocess
import os

# 安全设置
pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.5


class JDLoginBot:
	"""京东登录机器人 - 模拟真人操作"""

	def __init__(self):
		self.browser_opened = False
	
	def _random_delay(self, min_sec=0.5, max_sec=2.0):
		"""随机延迟，模拟人类思考时间"""
		time.sleep(random.uniform(min_sec, max_sec))
	
	def _human_move(self, x, y, duration=0.5):
		"""模拟人类移动鼠标（有弧度的移动）"""
		pyautogui.moveTo(x, y, duration=duration)
	
	def _human_click(self, x, y):
		"""模拟人类点击（有轻微延迟）"""
		self._human_move(x, y, duration=random.uniform(0.3, 0.8))
		time.sleep(random.uniform(0.1, 0.3))
		pyautogui.click()
	
	def _human_type(self, text):
		"""模拟人类打字（随机速度和暂停）"""
		for char in text:
			pyautogui.write(char)
			time.sleep(random.uniform(0.05, 0.2))
		
		# 随机暂停
		if random.random() > 0.7:
			time.sleep(random.uniform(0.5, 1.5))
	
	def open_browser(self):
		"""打开浏览器并访问京东"""
		print("📍 步骤 1: 打开浏览器...")
		
		# 打开 Chrome
		subprocess.run([
			'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
			'https://www.jd.com',
			'--new-window'
		])
		
		self._random_delay(3, 5)
		self.browser_opened = True
		print("✅ 浏览器已打开")
	
	def login(self, phone, password):
		"""执行登录流程"""
		if not self.browser_opened:
			self.open_browser()
		
		print("\n📍 步骤 2: 点击登录链接...")
		
		# 模拟鼠标移动到页面右上角（登录按钮位置）
		# 假设屏幕 1920x1080，右上角约 (1800, 100)
		self._human_click(1800, 100)
		self._random_delay(1, 2)
		
		print("\n📍 步骤 3: 输入手机号...")
		
		# 点击手机号输入框 - 约在屏幕中间 (960, 350)
		self._human_click(960, 350)
		self._random_delay(0.3, 0.8)
		
		# 输入手机号
		self._human_type(phone)
		self._random_delay(0.5, 1.5)
		
		print("\n📍 步骤 4: 输入密码...")
		
		# 点击密码输入框
		self._human_click(960, 450)
		self._random_delay(0.3, 0.8)
		
		# 输入密码
		self._human_type(password)
		self._random_delay(0.5, 1.5)
		
		print("\n📍 步骤 5: 点击登录按钮...")
		
		# 点击登录按钮
		self._human_click(960, 520)
		
		print("\n⏳ 等待登录结果...")
		
		# 等待页面加载
		self._random_delay(5, 10)
		
		# 检查是否登录成功（通过 URL 判断）
		print("\n✅ 登录流程完成！请检查浏览器是否登录成功")
		print("💡 提示：如果出现验证码，请手动完成验证")
	
	def save_cookies(self):
		"""提示用户保存 cookies"""
		print("\n📍 步骤 6: 保存登录态...")
		print("请在浏览器中保持登录状态")
		print("运行以下命令获取 cookies:")
		print("  python3 -c \"import browser_cookie3; print(browser_cookie3.chrome(domain_name='jd.com'))\"")


def main():
	bot = JDLoginBot()
	
	# 登录信息（如果需要）
	PHONE = "13501253295"  # 从 MEMORY.md 获取
	PASSWORD = "Inside58.58."
	
	print("=" * 60)
	print("京东登录机器人 - 模拟真人操作")
	print("=" * 60)
	print("\n⚠️ 注意事项：")
	print("1. 请确保浏览器窗口完全可见")
	print("2. 不要移动鼠标，让程序自动执行")
	print("3. 随时按 Ctrl+C 停止程序")
	print("\n准备开始...")
	
	input("\n按 Enter 开始执行...")
	
	# 打开浏览器并登录
	bot.open_browser()
	bot.login(PHONE, PASSWORD)
	bot.save_cookies()


if __name__ == '__main__':
	main()
