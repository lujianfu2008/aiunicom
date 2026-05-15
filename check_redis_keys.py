# -*- coding: utf-8 -*-
"""
检查Redis中的键值
"""

import redis
from config import REDIS_CONFIG, KEY_PREFIX

# 连接Redis
client = redis.Redis(**REDIS_CONFIG)

# 检查连接
print("检查Redis连接...")
try:
    client.ping()
    print("Redis连接成功")
except Exception as e:
    print(f"Redis连接失败: {e}")
    exit(1)

# 检查键数量
print("\n检查知识库键数量...")
try:
    keys = list(client.scan_iter(match=f"{KEY_PREFIX}*"))
    print(f"找到 {len(keys)} 个文档键")
    if keys:
        print("示例键:")
        for key in keys[:10]:
            print(f"  - {key.decode()}")
            # 查看键的内容
            try:
                content = client.json().get(key)
                if content:
                    print(f"    文件名: {content.get('file_name', 'N/A')}")
                    print(f"    内容长度: {len(content.get('content', ''))}")
            except Exception as e:
                print(f"    读取键失败: {e}")
except Exception as e:
    print(f"检查键失败: {e}")

# 检查文件指纹
print("\n检查文件指纹...")
try:
    fp_keys = list(client.scan_iter(match="workorder_fp:*"))
    print(f"找到 {len(fp_keys)} 个文件指纹")
    if fp_keys:
        print("示例指纹:")
        for key in fp_keys[:5]:
            print(f"  - {key.decode()}")
except Exception as e:
    print(f"检查文件指纹失败: {e}")

# 关闭连接
client.close()
print("\n检查完成")
