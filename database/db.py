"""
数据库连接管理
"""

import sqlite3
from contextlib import contextmanager
from config import DATABASE_PATH


def get_connection():
    """获取数据库连接"""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row  # 允许通过列名访问
    conn.text_factory = str
    return conn


def init_db():
    """初始化数据库"""
    from database.models import init_database
    init_database()


def close_connection(conn):
    """关闭数据库连接"""
    if conn:
        conn.close()


# 测试
if __name__ == "__main__":
    print(f"数据库路径: {DATABASE_PATH}")
    conn = get_connection()
    print("数据库连接成功！")
    close_connection(conn)
