"""
使用 Chrome DevTools Protocol 登录京东
"""

import asyncio
import json

async def login_jd():
    """登录京东"""
    import websockets
    
    # 连接到 Chrome DevTools
    async with websockets.connect('ws://localhost:9222/devtools/browser/6cc1d97c-6af2-4095-a160-0ad87d1fef7c') as ws:
        print('已连接调试 Chrome')
        
        # 获取页面列表
        await ws.send(json.dumps({
            'id': 1,
            'method': 'Target.getTargets'
        }))
        resp = await asyncio.wait_for(ws.recv(), timeout=10)
        print('收到响应')
        print(resp[:500])

if __name__ == '__main__':
    asyncio.run(login_jd())
