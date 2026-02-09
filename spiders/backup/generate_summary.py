#!/usr/bin/env python3
"""
生成商品总表：京东和天猫产品匹配
匹配规则：
1. 角色名匹配（擎天柱、大黄蜂、探长等）
2. 级别匹配（泰坦级、领袖级、航行家级、加强级、大师级）
3. 版本匹配（86大电影、决战塞伯坦、起源、传世、经典电影）
4. 型号匹配（G编号、SS编号、MP系列）
"""

import sqlite3
import re
from datetime import datetime

DB_PATH = 'data/transformers.db'


def clean_title(title):
    """清理标题：移除前缀、特殊字符"""
    if not title:
        return ""
    
    # 移除前缀
    title = re.sub(r'^【[^】]+】', '', title)
    # 移除开头固定文字
    title = re.sub(r'^变形金刚[（(]Transformers[）)]*', '', title)
    title = re.sub(r'^孩之宝', '', title)
    # 移除特殊字符
    title = re.sub(r'[【】\(\)（）]', '', title)
    return title.strip()


def extract_role(title):
    """提取角色名"""
    roles = [
        '擎天柱', '威震天', '大黄蜂', '铁皮', '救护车', '警车', '红蜘蛛', '震荡波',
        '探长', '千斤顶', '热破', '热浪', '横炮', '飞毛腿', '弹簧', '大无畏',
        '钢锁', '通天晓', '大力神', '大力金刚', '老鼠', '犀牛', '侏罗', '渣客',
        '路障', '声波', '机器狗', '飞天虎', '飙车', '狂飙', '泰山', '幽浮',
        '利格拉斯', '艾丽塔', '黑寡妇', '天火', '达拉克', '索莉拉',
        '腹地', '轰隆隆', '大火车', '幻影', '机器昆虫'
    ]
    for role in roles:
        if role in title:
            return role
    return ""


def extract_level(title):
    """提取级别"""
    title = title.upper()  # 统一大写
    
    if 'MPM-' in title:
        return '至高级'
    elif 'MP-' in title or 'MPG-' in title or '大师级' in title:
        return '大师级'
    elif '泰坦级' in title or title.endswith('L级') or 'V级' in title:
        return '泰坦级'
    elif '领袖级' in title:
        return '领袖级'
    elif '航行家级' in title:
        return '航行家级'
    elif '加强级' in title or title.endswith('C级') or '-BASIC' in title:
        return '加强级'
    elif '核心级' in title:
        return '核心级'
    return ""


def extract_version(title):
    """提取版本/作品"""
    versions = [
        '86大电影', '起源', '决战塞伯坦', '围城', '地出', '传世', '天元',
        '40周年', '周年纪念', '战损', '限定', '限量', '复古挂卡', '机器恐龙',
        '经典电影', '电影7', '电影6', '电影4', '雷霆救援队', '超能勇士',
        '王国', 'SDCC', 'PULSE', 'YELLOW'
    ]
    for v in versions:
        if v in title:
            return v
    return ""


def extract_model(title):
    """提取型号（编号）"""
    # G编号
    g_match = re.search(r'G(\d{3,4})', title)
    if g_match:
        return f"G{g_match.group(1)}"
    
    # SS编号
    ss_match = re.search(r'SS(\d{2,4})', title, re.IGNORECASE)
    if ss_match:
        return f"SS{ss_match.group(1)}"
    
    # MP/MPG/MPM编号
    mp_match = re.search(r'(MP[GM]?-\d{2,4}|MPM-\d+)', title, re.IGNORECASE)
    if mp_match:
        return mp_match.group(1).upper()
    
    # E编号
    e_match = re.search(r'E(\d{4})', title)
    if e_match:
        return f"E{e_match.group(1)}"
    
    # F编号
    f_match = re.search(r'F(\d{4})', title)
    if f_match:
        return f"F{f_match.group(1)}"
    
    return ""


def calculate_match_score(jd, tm):
    """计算两个产品的匹配分数"""
    jd_title = clean_title(jd[2])  # title
    tm_title = clean_title(tm[2])  # title
    
    jd_extra = (jd[3] or "") + " " + (jd[4] or "")  # style_name + extra
    tm_extra = (tm[3] or "") + " " + (tm[4] or "")
    
    full_jd = jd_title + " " + jd_extra
    full_tm = tm_title + " " + tm_extra
    
    score = 0
    details = []
    
    # 1. 角色匹配（最高权重）
    jd_role = extract_role(full_jd)
    tm_role = extract_role(full_tm)
    if jd_role and tm_role and jd_role == tm_role:
        score += 30
        details.append(f"角色:{jd_role}")
    
    # 2. 级别匹配
    jd_level = extract_level(full_jd)
    tm_level = extract_level(full_tm)
    if jd_level and tm_level and jd_level == tm_level:
        score += 20
        details.append(f"级别:{jd_level}")
    
    # 3. 版本匹配
    jd_version = extract_version(full_jd)
    tm_version = extract_version(full_tm)
    if jd_version and tm_version and jd_version == tm_version:
        score += 15
        details.append(f"版本:{jd_version}")
    elif jd_version and tm_version:
        # 部分版本匹配
        if jd_version in ['86大电影'] and tm_version in ['86大电影']:
            score += 15
            details.append(f"版本:{jd_version}")
        elif jd_version in ['决战塞伯坦', '围城'] and tm_version in ['决战塞伯坦', '王国']:
            score += 10
            details.append(f"版本:决战塞伯坦系列")
        elif jd_version in ['经典电影'] and '电影' in tm_version:
            score += 10
            details.append(f"版本:电影系列")
    
    # 4. 型号匹配（最高权重）
    jd_model = extract_model(full_jd)
    tm_model = extract_model(full_tm)
    if jd_model and tm_model and jd_model.upper() == tm_model.upper():
        score += 40
        details.append(f"型号:{jd_model}")
    
    # 5. 特殊组合匹配
    # 40周年探长
    if '40周年' in full_jd and '40周年' in full_tm and '探长' in full_jd and '探长' in full_tm:
        score += 50
        details.append("40周年探长组合")
    
    # 86大电影声波
    if '86大电影' in full_jd and '86大电影' in full_tm and '声波' in full_jd and '声波' in full_tm:
        score += 50
        details.append("86大电影声波组合")
    
    return score, "; ".join(details)


def match_products():
    """匹配京东和天猫产品"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 清空旧数据
    cursor.execute("DELETE FROM products_summary")
    
    # 获取产品
    cursor.execute("""
        SELECT id, product_id, product_url, title, style_name 
        FROM jd_products 
        WHERE status='available'
    """)
    jd_products = cursor.fetchall()
    
    cursor.execute("""
        SELECT id, product_id, product_url, title, style_name 
        FROM tmall_products 
        WHERE status='available'
    """)
    tmall_products = cursor.fetchall()
    
    print(f"京东产品: {len(jd_products)}")
    print(f"天猫产品: {len(tmall_products)}")
    
    # 计算所有匹配对
    all_matches = []
    for jd in jd_products:
        for tm in tmall_products:
            score, details = calculate_match_score(jd, tm)
            if score >= 30:  # 阈值
                all_matches.append({
                    'jd_id': jd[0],
                    'jd_url': jd[2],
                    'tmall_id': tm[0],
                    'tmall_url': tm[2],
                    'score': score,
                    'details': details,
                    'jd_title': jd[2],
                    'tm_title': tm[2],
                    'jd_model': extract_model(jd[2] + " " + (jd[3] or "")),
                    'tm_model': extract_model(tm[2] + " " + (tm[3] or ""))
                })
    
    # 按分数排序
    all_matches.sort(key=lambda x: -x['score'])
    
    # 去重匹配（每个产品只匹配一次，保留最高分）
    used_jd = set()
    used_tmall = set()
    final_matches = []
    
    for m in all_matches:
        if m['jd_id'] not in used_jd and m['tmall_id'] not in used_tmall:
            final_matches.append(m)
            used_jd.add(m['jd_id'])
            used_tmall.add(m['tmall_id'])
    
    print(f"\n匹配对数: {len(final_matches)}")
    
    # 生成产品名称并插入
    for m in final_matches:
        # 取京东标题作为基础
        name = clean_title(m['jd_title'])
        # 如果京东没有，取天猫
        if not name:
            name = clean_title(m['tm_title'])
        
        # 添加版本信息
        version = ""
        for v in ['86大电影', '40周年', '周年纪念', '起源', '决战塞伯坦', '传世', '经典电影', '天元']:
            if v in (m['jd_title'] + m['tm_title']):
                version = v
                break
        
        if version and version not in name:
            name = version + " " + name
        
        # 添加型号
        if m['jd_model']:
            name = name + " (" + m['jd_model'] + ")"
        elif m['tm_model']:
            name = name + " (" + m['tm_model'] + ")"
        
        product_type = extract_level(m['jd_title'] + " " + m['tm_title'])
        
        try:
            cursor.execute("""
                INSERT INTO products_summary 
                    (product_name, product_type, jd_url, tmall_url, jd_product_id, tmall_product_id)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (name, product_type, m['jd_url'], m['tmall_url'], m['jd_id'], m['tmall_id']))
        except Exception as e:
            print(f"插入失败: {e}")
    
    # 插入未匹配的京东产品
    for jd in jd_products:
        if jd[0] not in used_jd:
            name = clean_title(jd[2])
            version = extract_version(jd[2] + " " + (jd[3] or ""))
            if version and version not in name:
                name = version + " " + name
            
            model = extract_model(jd[2] + " " + (jd[3] or ""))
            if model:
                name = name + " (" + model + ")"
            
            product_type = extract_level(jd[2])
            
            try:
                cursor.execute("""
                    INSERT INTO products_summary 
                        (product_name, product_type, jd_url, jd_product_id)
                    VALUES (?, ?, ?, ?)
                """, (name, product_type, jd[2], jd[0]))
            except:
                pass
    
    # 插入未匹配的天猫产品
    for tm in tmall_products:
        if tm[0] not in used_tmall:
            name = clean_title(tm[2])
            version = extract_version(tm[2] + " " + (tm[3] or ""))
            if version and version not in name:
                name = version + " " + name
            
            model = extract_model(tm[2] + " " + (tm[3] or ""))
            if model:
                name = name + " (" + model + ")"
            
            product_type = extract_level(tm[2])
            
            try:
                cursor.execute("""
                    INSERT INTO products_summary 
                        (product_name, product_type, tmall_url, tmall_product_id)
                    VALUES (?, ?, ?, ?)
                """, (name, product_type, tm[2], tm[0]))
            except:
                pass
    
    conn.commit()
    
    # 统计
    cursor.execute("SELECT COUNT(*) FROM products_summary")
    total = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM products_summary WHERE jd_product_id IS NOT NULL")
    jd_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM products_summary WHERE tmall_product_id IS NOT NULL")
    tmall_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM products_summary WHERE jd_product_id IS NOT NULL AND tmall_product_id IS NOT NULL")
    both_count = cursor.fetchone()[0]
    
    print(f"\n总表统计:")
    print(f"  总数: {total}")
    print(f"  京东: {jd_count}")
    print(f"  天猫: {tmall_count}")
    print(f"  双方都有: {both_count}")
    
    # 显示部分匹配结果
    print("\n匹配样例:")
    cursor.execute("""
        SELECT id, product_name, product_type, jd_product_id, tmall_product_id 
        FROM products_summary 
        WHERE jd_product_id IS NOT NULL AND tmall_product_id IS NOT NULL
        LIMIT 10
    """)
    for row in cursor.fetchall():
        print(f"  {row[0]}: {row[1][:40]}...")
    
    conn.close()


if __name__ == '__main__':
    match_products()
