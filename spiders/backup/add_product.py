"""
手动添加京东商品 - 演示如何添加商品链接
"""

import requests
from database.db import get_connection
from database.models import Product, ProductDAO


def add_product_by_url(jd_url: str, name: str = None):
    """
    通过京东商品链接添加商品
    
    参数:
        jd_url: 京东商品链接，如 https://item.jd.com/1000123456.html
        name: 商品名称（可选，从页面提取）
    
    返回:
        商品ID
    """
    # 从 URL 提取商品 ID
    # https://item.jd.com/1000123456.html -> 1000123456
    import re
    match = re.search(r'item\.jd\.com/(\d+)\.html', jd_url)
    if not match:
        raise ValueError("无效的京东商品链接")
    
    product_id = match.group(1)
    
    # 如果没有提供名称，使用 ID 作为名称
    if not name:
        name = f"京东商品 {product_id}"
    
    # 获取商品价格（京东价格 API）
    price = get_jd_price(product_id)
    
    # 创建商品
    product = Product(
        name=name,
        jd_product_id=product_id,
        jd_product_url=jd_url,
    )
    
    product_id = ProductDAO.insert(product)
    
    print(f"✅ 添加商品成功: {name}")
    print(f"   商品ID: {product_id}")
    print(f"   京东ID: {product_id}")
    print(f"   当前价格: ¥{price}")
    
    return product_id


def get_jd_price(product_id: str) -> float:
    """获取京东商品价格"""
    try:
        url = f"https://p.3.cn/prices/mgets?skuIds=J_{product_id}"
        response = requests.get(url, timeout=10)
        data = response.json()
        if data and len(data) > 0:
            return float(data[0].get('p', 0))
    except Exception as e:
        print(f"获取价格失败: {e}")
    return 0.0


def batch_add_products(urls: list):
    """批量添加商品"""
    conn = get_connection()
    cursor = conn.cursor()
    
    added = 0
    for url in urls:
        try:
            product_id = add_product_by_url(url)
            added += 1
        except Exception as e:
            print(f"❌ 添加失败 {url}: {e}")
    
    conn.close()
    print(f"\n共添加 {added} 个商品")
    return added


if __name__ == "__main__":
    # 示例：添加一些变形金刚商品
    # 实际使用时，把你复制的京东商品链接粘贴到下面
    
    demo_urls = [
        # 示例格式，实际使用时替换为真实的京东链接
        # "https://item.jd.com/1000000.html",
    ]
    
    # 如果有商品链接，运行：
    # batch_add_products(demo_urls)
    
    print("=== 手动添加京东商品 ===")
    print("使用方法：")
    print("1. 在京东官网搜索变形金刚")
    print("2. 右键商品 -> 复制链接地址")
    print("3. 调用 add_product_by_url(商品链接, 商品名称)")
    print()
    print("示例：")
    print('  add_product_by_url("https://item.jd.com/1000000.html", "变形金刚 G1 威震天")')
