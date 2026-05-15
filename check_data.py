# -*- coding: utf-8 -*-
import redis
import json
from config import REDIS_CONFIG

r = redis.Redis(**REDIS_CONFIG)

# 检查文档数量
keys = r.keys('workorder:*')
doc_keys = [k for k in keys if b'filename_idx' not in k and b'type_idx' not in k and b'fp:' not in k]
print(f'文档数量: {len(doc_keys)}')

# 检查索引
idx_key = 'workorder:filename_idx'
idx_exists = r.exists(idx_key)
print(f'文件名索引存在: {idx_exists}')

if idx_exists:
    idx_count = r.hlen(idx_key)
    print(f'索引条目数: {idx_count}')

# 检查一个示例文档
if doc_keys:
    sample_key = doc_keys[0]
    doc = r.execute_command('JSON.GET', sample_key, '$')
    doc_data = json.loads(doc)[0]
    print(f'示例文档:')
    print(f'  file_name: {doc_data.get("file_name", "")}')
    print(f'  source: {doc_data.get("source", "")}')

# 检查特定文件
target = "6938737-红黄牌拦截问题.txt"
print(f'\n查找文件: {target}')

# 直接扫描
found = False
for key in doc_keys[:100]:  # 只检查前100个
    doc = r.execute_command('JSON.GET', key, '$')
    doc_data = json.loads(doc)[0]
    fn = doc_data.get('file_name', '')
    if target.lower() in fn.lower():
        print(f'找到: {fn}')
        print(f'  source: {doc_data.get("source", "")}')
        found = True
        break

if not found:
    print('未找到该文件')
