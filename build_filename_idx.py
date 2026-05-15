# -*- coding: utf-8 -*-
import redis
import json
from config import REDIS_CONFIG

r = redis.Redis(**REDIS_CONFIG)

print("建立文件名索引...")

# 获取所有文档
keys = r.keys('workorder:*')
doc_keys = [k for k in keys if b'filename_idx' not in k and b'type_idx' not in k and b'fp:' not in k]
print(f"文档数量: {len(doc_keys)}")

# 建立索引
idx_key = 'workorder:filename_idx'
pipe = r.pipeline()
count = 0

for key in doc_keys:
    try:
        doc = r.execute_command('JSON.GET', key, '$')
        doc_data = json.loads(doc)[0]
        file_name = doc_data.get('file_name', '')
        if file_name:
            fn_lower = file_name.lower()
            # 存储文件名到键的映射
            pipe.hset(idx_key, fn_lower, json.dumps([key.decode() if isinstance(key, bytes) else key]))
            count += 1
            if count % 100 == 0:
                pipe.execute()
                pipe = r.pipeline()
                print(f"已处理 {count} 个文档...")
    except Exception as e:
        print(f"错误: {e}")
        continue

pipe.execute()
print(f"索引建立完成，共 {count} 条记录")

# 验证
idx_count = r.hlen(idx_key)
print(f"索引条目数: {idx_count}")
