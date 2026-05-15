# -*- coding: utf-8 -*-
import redis
import json
from config import REDIS_CONFIG, VECTOR_DIMENSION

r = redis.Redis(**REDIS_CONFIG)

# 检查索引
print("检查Redis索引状态:")
try:
    idx_info = r.execute_command('FT.INFO', 'workorder_knowledge_idx')
    print("索引存在: workorder_knowledge_idx")
    for i in range(0, len(idx_info), 2):
        key = idx_info[i]
        val = idx_info[i+1]
        if isinstance(key, bytes):
            key = key.decode()
        print(f"  {key}: {val}")
except Exception as e:
    print(f"索引不存在或错误: {e}")

# 检查向量维度配置
print(f"\n配置的向量维度: {VECTOR_DIMENSION}")

# 检查一个文档的向量维度
keys = r.keys('workorder:*')
doc_keys = [k for k in keys if b'filename_idx' not in k and b'type_idx' not in k and b'fp:' not in k]
if doc_keys:
    sample_key = doc_keys[0]
    doc = r.execute_command('JSON.GET', sample_key, '$')
    doc_data = json.loads(doc)[0]
    emb = doc_data.get('embedding', [])
    print(f"文档向量维度: {len(emb)}")
