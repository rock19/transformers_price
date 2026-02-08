#!/usr/bin/env python3
"""
导出 Safari 的 cookies 用于爬虫 - 自动检测登录状态
"""

import json
import time
from playwright.sync_api import sync_playwright

def check_login(page, max_wait=120):
    """检查是否已登录天猫"""
    print("检查登录状态...")
    
    for i in range(max_wait):
        # 检查 cookie 中是否有登录信息
        try:
            cookies = page.context.cookies()
            cookie_names = [c['name'] for c in cookies]
            
            # 检查是否有关键 cookie
            if 'cookie2' in cookie_names or '_tb_token_' in cookie_names:
                print("✅ 检测到登录状态！")
                return True
            
            # 检查 URL 是否跳转到已登录页面
            if 'login' not in page.url and 'tmall.com' in page.url:
                print("✅ 已离开登录页面，可能已登录")
                return True
        except:
            pass
        
        time.sleep(1)
        if (i + 1) % 10 == 0:
            print(f"  等待中... {i+1}/{max_wait} 秒")
    
    return False

def export_cookies():
    """导出 cookies"""
    cookies = None
    
    with sync_playwright() as p:
        browser = p.webkit.launch(headless=False)
        
        context = browser.new_context(
            viewport={'width': 1280, 'height': 800},
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Safari/605.1.15'
        )
        
        page = context.new_page()
        
        # 打开登录页面
        print("打开天猫登录页面...")
        page.goto('https://login.tmall.com')
        
        # 自动检测登录状态
        if not check_login(page, max_wait=180):  # 等待3分钟
            print("⚠️ 未检测到登录状态，请手动登录")
            print("登录后窗口会自动关闭并保存 cookies")
            input("按 Enter 手动结束并保存...")
        
        # 获取 cookies
        print("正在保存 cookies...")
        cookies = context.cookies()
        
        # 关闭浏览器
        browser.close()
    
    # 保存 cookies
    with open('data/safari_cookies.json', 'w') as f:
        json.dump(cookies, f, indent=2)
    
    print(f"\n✅ Cookies 已保存到 data/safari_cookies.json")
    print(f"共 {len(cookies)} 个 cookies")
    
    return cookies

if __name__ == '__main__':
    export_cookies()
