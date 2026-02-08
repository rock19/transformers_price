"""
统一爬虫入口 - 同时爬取京东和天猫
"""

import sys
import time
from datetime import datetime
from config import FEISHU_ENABLED, FEISHU_WEBHOOK_URL
from spiders.jd_spider import JD_Spider as JDSpider
from spiders.tmall_spider import TianMou_Spider as TianMouSpider
from database.db import get_connection
from database.models import Product, ProductPrice, ProductDAO, PriceDAO


class PriceCrawler:
    """统一价格爬虫"""
    
    def __init__(self):
        self.jd_spider = JDSpider()
        self.tmall_spider = TianMouSpider()
        self.notifications = []  # 价格预警通知
    
    def crawl_all(self):
        """爬取所有商品价格"""
        print("=" * 50)
        print(f"开始爬取价格 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 50)
        
        conn = get_connection()
        cursor = conn.cursor()
        
        # 获取所有未购买的商品
        cursor.execute("SELECT id, name, jd_product_id, tmall_product_id, status FROM products WHERE status='未购买'")
        products = cursor.fetchall()
        
        print(f"需要爬取 {len(products)} 个商品的价格")
        
        for product in products:
            product_id = product[0]
            name = product[1]
            jd_id = product[2]
            tmall_id = product[3]
            status = product[4]
            
            if status == '已购买':
                print(f"跳过已购买商品: {name}")
                continue
            
            print(f"\n正在爬取: {name}")
            
            # 爬取京东价格
            if jd_id:
                self._crawl_jd_price(product_id, jd_id)
                time.sleep(3)  # 避免请求过快
            
            # 爬取天猫价格
            if tmall_id:
                self._crawl_tmall_price(product_id, tmall_id)
                time.sleep(3)
        
        conn.close()
        
        print("\n" + "=" * 50)
        print("价格爬取完成！")
        
        # 发送飞书通知
        if self.notifications:
            self._send_feishu_notification()
    
    def _crawl_jd_price(self, product_id: int, jd_product_id: str):
        """爬取京东价格"""
        try:
            # 获取价格
            price = self.jd_spider._get_price(jd_product_id)
            
            if price > 0:
                # 保存价格记录
                price_record = ProductPrice(
                    product_id=product_id,
                    platform='jd',
                    product_id_on_platform=jd_product_id,
                    price=price,
                    captured_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                )
                PriceDAO.insert(price_record)
                print(f"  京东: ¥{price}")
                
                # 检查是否需要通知
                self._check_price_alert(product_id, 'jd', price)
            else:
                print(f"  京东: 获取价格失败")
                
        except Exception as e:
            print(f"  京东: 爬取失败 - {e}")
    
    def _crawl_tmall_price(self, product_id: int, tmall_product_id: str):
        """爬取天猫价格"""
        try:
            # 获取商品详情（包含价格）
            detail = self.tmall_spider.get_product_detail(tmall_product_id)
            price = detail.get('price', 0)
            
            if price > 0:
                price_record = ProductPrice(
                    product_id=product_id,
                    platform='tmall',
                    product_id_on_platform=tmall_product_id,
                    price=price,
                    product_url=detail.get('url', ''),
                    image_url=detail.get('image_url', ''),
                    captured_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                )
                PriceDAO.insert(price_record)
                print(f"  天猫: ¥{price}")
                
                # 检查是否需要通知
                self._check_price_alert(product_id, 'tmall', price)
            else:
                print(f"  天猫: 获取价格失败")
                
        except Exception as e:
            print(f"  天猫: 爬取失败 - {e}")
    
    def _check_price_alert(self, product_id: int, platform: str, current_price: float):
        """检查价格是否需要预警"""
        # 获取历史最低价
        min_price = PriceDAO.get_min_price(product_id, platform)
        
        if min_price and current_price < min_price:
            # 价格创新低，添加到通知列表
            conn = get_connection()
            cursor = conn.execute("SELECT name FROM products WHERE id=?", (product_id,)).fetchone()
            product_name = cursor[0] if cursor else '未知商品'
            
            platform_name = '京东' if platform == 'jd' else '天猫'
            
            self.notifications.append({
                'product_name': product_name,
                'platform': platform_name,
                'current_price': current_price,
                'min_price': min_price,
                'drop_percent': round((min_price - current_price) / min_price * 100, 1)
            })
    
    def _send_feishu_notification(self):
        """发送飞书价格预警通知"""
        if not FEISHU_ENABLED or not FEISHU_WEBHOOK_URL:
            print("\n飞书通知未启用，跳过...")
            return
        
        if not self.notifications:
            return
        
        # 构建消息
        content = "🔔 **价格预警** 🔔\n\n"
        
        for item in self.notifications:
            content += f"📦 **{item['product_name']}**\n"
            content += f"   平台: {item['platform']}\n"
            content += f"   当前价: ¥{item['current_price']}\n"
            content += f"   历史最低: ¥{item['min_price']}\n"
            content += f"   降幅: ↓{item['drop_percent']}%\n\n"
        
        # 发送请求
        import requests
        payload = {"msg_type": "text", "content": {"text": content}}
        
        try:
            response = requests.post(
                FEISHU_WEBHOOK_URL,
                json=payload,
                timeout=10
            )
            print(f"\n飞书通知发送成功！")
        except Exception as e:
            print(f"\n飞书通知发送失败: {e}")


def crawl_jd_store():
    """爬取京东店铺商品"""
    print("爬取京东店铺商品...")
    spider = JDSpider()
    spider.crawl_store()


def crawl_tmall_store():
    """爬取天猫店铺商品"""
    print("爬取天猫店铺商品...")
    spider = TianMouSpider()
    spider.crawl_store()


def crawl_prices():
    """爬取所有商品价格"""
    crawler = PriceCrawler()
    crawler.crawl_all()


def main():
    """主函数"""
    if len(sys.argv) < 2:
        print("用法: python crawler.py [jd|tmall|price|all]")
        print("  jd    - 爬取京东店铺商品")
        print("  tmall - 爬取天猫店铺商品")
        print("  price - 爬取所有商品价格")
        print("  all   - 全部执行")
        return
    
    command = sys.argv[1]
    
    if command == 'jd':
        crawl_jd_store()
    elif command == 'tmall':
        crawl_tmall_store()
    elif command == 'price':
        crawl_prices()
    elif command == 'all':
        crawl_jd_store()
        time.sleep(5)
        crawl_tmall_store()
        time.sleep(5)
        crawl_prices()
    else:
        print(f"未知命令: {command}")


if __name__ == "__main__":
    main()
