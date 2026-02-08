"""
数据库模型定义
"""

import sqlite3
from datetime import datetime
from typing import Optional, List, Dict
from contextlib import contextmanager
from database.db import get_connection, init_db


class Product:
    """商品主表"""
    
    def __init__(
        self,
        id: Optional[int] = None,
        name: str = "",
        jd_product_id: Optional[str] = None,
        jd_product_url: Optional[str] = None,
        tmall_product_id: Optional[str] = None,
        tmall_product_url: Optional[str] = None,
        status: str = "未购买",
        created_at: Optional[str] = None,
        updated_at: Optional[str] = None,
    ):
        self.id = id
        self.name = name
        self.jd_product_id = jd_product_id  # 京东商品ID
        self.jd_product_url = jd_product_url  # 京东商品链接
        self.tmall_product_id = tmall_product_id  # 天猫商品ID
        self.tmall_product_url = tmall_product_url  # 天猫商品链接
        self.status = status  # 未购买/已购买/不感兴趣
        self.created_at = created_at or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.updated_at = updated_at or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "name": self.name,
            "jd_product_id": self.jd_product_id,
            "jd_product_url": self.jd_product_url,
            "tmall_product_id": self.tmall_product_id,
            "tmall_product_url": self.tmall_product_url,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class ProductPrice:
    """价格历史记录表"""
    
    def __init__(
        self,
        id: Optional[int] = None,
        product_id: int = 0,
        platform: str = "",  # jd / tmall
        product_id_on_platform: str = "",
        price: float = 0.0,
        original_price: float = 0.0,  # 原价
        product_url: str = "",
        image_url: str = "",
        captured_at: Optional[str] = None,
    ):
        self.id = id
        self.product_id = product_id
        self.platform = platform
        self.product_id_on_platform = product_id_on_platform
        self.price = price
        self.original_price = original_price
        self.product_url = product_url
        self.image_url = image_url
        self.captured_at = captured_at or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "product_id": self.product_id,
            "platform": self.platform,
            "product_id_on_platform": self.product_id_on_platform,
            "price": self.price,
            "original_price": self.original_price,
            "product_url": self.product_url,
            "image_url": self.image_url,
            "captured_at": self.captured_at,
        }


class ProductMatcher:
    """商品匹配记录表（用于手动调整对应关系）"""
    
    def __init__(
        self,
        id: Optional[int] = None,
        product_id: int = 0,
        jd_product_id: Optional[str] = None,
        tmall_product_id: Optional[str] = None,
        similarity: float = 0.0,  # 相似度
        is_auto_matched: bool = True,
        created_at: Optional[str] = None,
    ):
        self.id = id
        self.product_id = product_id
        self.jd_product_id = jd_product_id
        self.tmall_product_id = tmall_product_id
        self.similarity = similarity
        self.is_auto_matched = is_auto_matched
        self.created_at = created_at or datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# ============ 数据库操作类 ============

class ProductDAO:
    """商品数据访问对象"""
    
    @staticmethod
    def create_table():
        """创建商品表"""
        with get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS products (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    jd_product_id TEXT,
                    jd_product_url TEXT,
                    tmall_product_id TEXT,
                    tmall_product_url TEXT,
                    status TEXT DEFAULT '未购买',
                    created_at TEXT,
                    updated_at TEXT
                )
            """)
    
    @staticmethod
    def insert(product: Product) -> int:
        """插入商品"""
        with get_connection() as conn:
            cursor = conn.execute("""
                INSERT INTO products (name, jd_product_id, jd_product_url, tmall_product_id, tmall_product_url, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                product.name, product.jd_product_id, product.jd_product_url,
                product.tmall_product_id, product.tmall_product_url,
                product.status, product.created_at, product.updated_at
            ))
            return cursor.lastrowid
    
    @staticmethod
    def update(product: Product):
        """更新商品"""
        with get_connection() as conn:
            conn.execute("""
                UPDATE products SET name=?, jd_product_id=?, jd_product_url=?, tmall_product_id=?, tmall_product_url=?, status=?, updated_at=?
                WHERE id=?
            """, (
                product.name, product.jd_product_id, product.jd_product_url,
                product.tmall_product_id, product.tmall_product_url,
                product.status, product.updated_at, product.id
            ))
    
    @staticmethod
    def get_by_id(id: int) -> Optional[Product]:
        """根据ID查询"""
        with get_connection() as conn:
            row = conn.execute("SELECT * FROM products WHERE id=?", (id,)).fetchone()
            if row:
                return Product(*row)
            return None
    
    @staticmethod
    def get_all() -> List[Product]:
        """查询所有商品"""
        with get_connection() as conn:
            rows = conn.execute("SELECT * FROM products ORDER BY created_at DESC").fetchall()
            return [Product(*row) for row in rows]
    
    @staticmethod
    def get_by_status(status: str) -> List[Product]:
        """根据状态查询"""
        with get_connection() as conn:
            rows = conn.execute("SELECT * FROM products WHERE status=? ORDER BY created_at DESC", (status,)).fetchall()
            return [Product(*row) for row in rows]
    
    @staticmethod
    def get_not_purchased() -> List[Product]:
        """获取未购买的商品（需要爬取价格的）"""
        with get_connection() as conn:
            rows = conn.execute("SELECT * FROM products WHERE status='未购买' ORDER BY created_at DESC").fetchall()
            return [Product(*row) for row in rows]
    
    @staticmethod
    def delete(id: int):
        """删除商品"""
        with get_connection() as conn:
            conn.execute("DELETE FROM products WHERE id=?", (id,))


class PriceDAO:
    """价格数据访问对象"""
    
    @staticmethod
    def create_table():
        """创建价格表"""
        with get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS product_prices (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    product_id INTEGER NOT NULL,
                    platform TEXT NOT NULL,
                    product_id_on_platform TEXT NOT NULL,
                    price REAL NOT NULL,
                    original_price REAL DEFAULT 0,
                    product_url TEXT,
                    image_url TEXT,
                    captured_at TEXT,
                    FOREIGN KEY (product_id) REFERENCES products(id)
                )
            """)
            
            # 创建索引
            conn.execute("CREATE INDEX IF NOT EXISTS idx_price_product ON product_prices(product_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_price_platform ON product_prices(platform)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_price_time ON product_prices(captured_at)")
    
    @staticmethod
    def insert(price: ProductPrice):
        """插入价格记录"""
        with get_connection() as conn:
            conn.execute("""
                INSERT INTO product_prices (product_id, platform, product_id_on_platform, price, original_price, product_url, image_url, captured_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                price.product_id, price.platform, price.product_id_on_platform,
                price.price, price.original_price, price.product_url,
                price.image_url, price.captured_at
            ))
    
    @staticmethod
    def get_by_product_id(product_id: int, limit: int = 1000) -> List[ProductPrice]:
        """根据商品ID查询价格历史"""
        with get_connection() as conn:
            rows = conn.execute("""
                SELECT * FROM product_prices 
                WHERE product_id=? 
                ORDER BY captured_at DESC 
                LIMIT ?
            """, (product_id, limit)).fetchall()
            return [ProductPrice(*row) for row in rows]
    
    @staticmethod
    def get_price_trend(
        product_id: int, 
        start_time: Optional[str] = None, 
        end_time: Optional[str] = None,
        platform: Optional[str] = None
    ) -> Dict[str, List[ProductPrice]]:
        """获取价格趋势"""
        with get_connection() as conn:
            query = "SELECT * FROM product_prices WHERE product_id=?"
            params = [product_id]
            
            if platform:
                query += " AND platform=?"
                params.append(platform)
            
            if start_time:
                query += " AND captured_at>=?"
                params.append(start_time)
            
            if end_time:
                query += " AND captured_at<=?"
                params.append(end_time)
            
            query += " ORDER BY captured_at ASC"
            
            rows = conn.execute(query, params).fetchall()
            prices = [ProductPrice(*row) for row in rows]
            
            # 按平台分组
            result = {"jd": [], "tmall": []}
            for price in prices:
                if price.platform == "jd":
                    result["jd"].append(price)
                else:
                    result["tmall"].append(price)
            
            return result
    
    @staticmethod
    def get_latest_price(product_id: int, platform: str) -> Optional[ProductPrice]:
        """获取某商品某平台的最新价格"""
        with get_connection() as conn:
            row = conn.execute("""
                SELECT * FROM product_prices 
                WHERE product_id=? AND platform=? 
                ORDER BY captured_at DESC 
                LIMIT 1
            """, (product_id, platform)).fetchone()
            if row:
                return ProductPrice(*row)
            return None
    
    @staticmethod
    def get_min_price(product_id: int, platform: str) -> Optional[float]:
        """获取某商品某平台的历史最低价"""
        with get_connection() as conn:
            row = conn.execute("""
                SELECT MIN(price) FROM product_prices 
                WHERE product_id=? AND platform=?
            """, (product_id, platform)).fetchone()
            return row[0] if row else None
    
    @staticmethod
    def delete_by_time(start_time: str, end_time: str):
        """按时间段删除价格记录"""
        with get_connection() as conn:
            conn.execute("""
                DELETE FROM product_prices 
                WHERE captured_at>=? AND captured_at<=?
            """, (start_time, end_time))
    
    @staticmethod
    def delete_by_product_id(product_id: int):
        """删除某商品的所有价格记录"""
        with get_connection() as conn:
            conn.execute("DELETE FROM product_prices WHERE product_id=?", (product_id,))


class MatcherDAO:
    """匹配记录数据访问对象"""
    
    @staticmethod
    def create_table():
        """创建匹配表"""
        with get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS product_matchers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    product_id INTEGER NOT NULL,
                    jd_product_id TEXT,
                    tmall_product_id TEXT,
                    similarity REAL DEFAULT 0,
                    is_auto_matched INTEGER DEFAULT 1,
                    created_at TEXT,
                    FOREIGN KEY (product_id) REFERENCES products(id)
                )
            """)
    
    @staticmethod
    def insert(matcher: ProductMatcher):
        """插入匹配记录"""
        with get_connection() as conn:
            conn.execute("""
                INSERT INTO product_matchers (product_id, jd_product_id, tmall_product_id, similarity, is_auto_matched, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                matcher.product_id, matcher.jd_product_id, matcher.tmall_product_id,
                matcher.similarity, 1 if matcher.is_auto_matched else 0,
                matcher.created_at
            ))
    
    @staticmethod
    def get_by_product_id(product_id: int) -> Optional[ProductMatcher]:
        """根据商品ID查询匹配记录"""
        with get_connection() as conn:
            row = conn.execute("SELECT * FROM product_matchers WHERE product_id=?", (product_id,)).fetchone()
            if row:
                return ProductMatcher(*row)
            return None
    
    @staticmethod
    def update_manual_match(product_id: int, jd_product_id: str, tmall_product_id: str):
        """手动更新匹配关系"""
        with get_connection() as conn:
            conn.execute("""
                UPDATE product_matchers 
                SET jd_product_id=?, tmall_product_id=?, is_auto_matched=0
                WHERE product_id=?
            """, (jd_product_id, tmall_product_id, product_id))


# ============ 初始化数据库 ============

def init_database():
    """初始化所有表"""
    ProductDAO.create_table()
    PriceDAO.create_table()
    MatcherDAO.create_table()
    print("数据库初始化完成！")


if __name__ == "__main__":
    init_database()
