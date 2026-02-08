"""
京东自动登录脚本 - 支持验证码处理
"""

import asyncio
import json
import time
from playwright.async_api import async_playwright


async def login_jd():
    async with async_playwright() as p:
        print('启动 Chrome...')
        browser = await p.chromium.launch(
            headless=False,
            executable_path='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
        )
        context = await browser.new_context()
        page = await context.new_page()
        
        print('打开京东登录页...')
        await page.goto('https://passport.jd.com/new/login.aspx')
        await page.wait_for_timeout(3000)
        
        print(f'标题: {await page.title()}')
        
        # 检查是否已有登录态
        if '我的京东' in await page.content():
            print('✅ 已登录！')
            cookies = await context.cookies()
            with open('data/jd_cookies.json', 'w') as f:
                json.dump(cookies, f, indent=2)
            print(f'保存 {len(cookies)} 个 cookies')
            await browser.close()
            return True
        
        # 查找登录框
        loginname = page.locator('#loginname')
        if await loginname.count() > 0:
            print('输入账号密码...')
            await loginname.fill('zy90221@sina.com')
            await page.locator('#nloginpwd').fill('Inside58.58.')
            await page.locator('.login-btn').click()
            print('点击登录按钮')
            
            # 等待验证码或登录结果
            print('等待 30 秒...')
            await page.wait_for_timeout(30000)
            
            # 检查当前状态
            current_title = await page.title()
            print(f'当前标题: {current_title}')
            
            # 检查是否需要验证码
            page_content = await page.content()
            if '滑动' in page_content or '验证' in page_content or '验证码' in page_content:
                print('⚠️ 检测到验证码！')
                print('请手动完成滑动验证，完成后按回车继续...')
                input()
            
            # 再等一会儿
            await page.wait_for_timeout(5000)
            print(f'最终标题: {await page.title()}')
        
        # 访问首页确认登录
        await page.goto('https://www.jd.com/')
        await page.wait_for_timeout(3000)
        
        # 保存 cookies
        cookies = await context.cookies()
        with open('data/jd_cookies.json', 'w') as f:
            json.dump(cookies, f, indent=2)
        print(f'保存 {len(cookies)} 个 cookies')
        
        # 检查登录结果
        final_content = await page.content()
        if '我的京东' in final_content or '退出' in final_content:
            print('✅ 登录成功！')
        else:
            print('⚠️ 登录可能失败，请检查 cookies')
        
        await browser.close()
        return True


if __name__ == '__main__':
    print('=== 京东登录脚本 ===')
    print('注意：如果出现验证码，请手动完成')
    print()
    
    asyncio.run(login_jd())
    print('\n完成！')
