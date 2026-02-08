#!/usr/bin/env python3
"""
查询京东商品表 - 表格形式输出
"""

import sqlite3

DB_PATH = 'data/transformers.db'


def main():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # SQL查询 - 所有字段 as 中文名称
    sql = """
    SELECT 
        id AS ID,
        product_id AS 商品ID,
        product_url AS 详情地址,
        image_url AS 图片地址,
        title AS 商品标题,
        price AS 价格,
        preprice AS 原价格,
        style_name AS 款式名称,
        CASE status WHEN 'available' THEN '✅在售' ELSE '⏭️待发布' END AS 售卖状态,
        CASE is_deposit WHEN 1 THEN '是' ELSE '否' END AS 是否定金,
        created_at AS 创建时间,
        updated_at AS 更新时间,
        shop_name AS 店铺名称,
        shop_url AS 店铺地址
    FROM jd_products
    ORDER BY id
    """
    
    cursor.execute(sql)
    rows = cursor.fetchall()
    
    if not rows:
        print("无数据")
        return
    
    # 获取列名
    col_names = [desc[0] for desc in cursor.description]
    
    # 计算每列宽度
    widths = [len(name) for name in col_names]
    for row in rows:
        for i, val in enumerate(row):
            val_str = str(val) if val else ''
            widths[i] = max(widths[i], len(val_str))
    
    # 打印表头
    header = ' | '.join(col_names[i].ljust(widths[i]) for i in range(len(col_names)))
    print('=' * len(header))
    print(header)
    print('=' * len(header))
    
    # 打印数据行
    for row in rows:
        line = ' | '.join(
            (str(val) if val else '').ljust(widths[i])
            for i, val in enumerate(row)
        )
        print(line)
    
    print('=' * len(header))
    print(f"共 {len(rows)} 条记录")
    
    conn.close()


if __name__ == '__main__':
    main()
