# -*- coding: utf-8 -*-
"""调试存储问题"""

import os
import sys
import time

# 设置环境变量
if sys.platform == 'win32':
    os.environ['PYTHONIOENCODING'] = 'utf-8'

from file_parser import FileParser
from vector_store import RedisVectorStore
from knowledge_base import KnowledgeBase

print("=" * 70)
print("存储问题调试")
print("=" * 70)

# 1. 测试文件解析
data_dir = r"D:\工作文档\cbss2.0体验版\沃工单问题定位"
parser = FileParser()

print("\n1. 测试文件解析...")
documents = parser.parse_directory(data_dir)
print(f"共解析到 {len(documents)} 个文档")

if not documents:
    print("没有解析到文档，退出测试")
    sys.exit(1)

# 2. 测试Redis连接
print("\n2. 测试Redis连接...")
try:
    vector_store = RedisVectorStore()
    print("Redis连接成功 ✓")
except Exception as e:
    print(f"Redis连接失败: {e}")
    sys.exit(1)

# 3. 测试索引
print("\n3. 测试索引...")
try:
    existing_indices = vector_store.client.execute_command('FT._LIST')
    print(f"现有索引: {[i.decode() for i in existing_indices]}")
    
    # 检查我们的索引是否存在
    from config import INDEX_NAME
    if INDEX_NAME.encode() in existing_indices:
        print(f"索引 {INDEX_NAME} 存在 ✓")
    else:
        print(f"索引 {INDEX_NAME} 不存在，正在创建...")
        vector_store._create_index(force_recreate=True)
except Exception as e:
    print(f"索引测试失败: {e}")

# 4. 测试存储
print("\n4. 测试存储...")
print(f"尝试存储 {len(documents)} 个文档...")

# 清空现有存储
print("清空现有存储...")
vector_store.clear_all()

# 存储文档
success_count = vector_store.add_documents(documents)
print(f"成功存储: {success_count} 个文档")

# 5. 测试Redis键
print("\n5. 测试Redis键...")
try:
    from config import KEY_PREFIX, FILE_FINGERPRINT_PREFIX
    
    # 检查文档键
    doc_keys = list(vector_store.client.scan_iter(match=f"{KEY_PREFIX}*"))
    print(f"文档键数量: {len(doc_keys)}")
    if doc_keys:
        print("前3个文档键:")
        for key in doc_keys[:3]:
            print(f"  {key.decode()}")
    
    # 检查指纹键
    fp_keys = list(vector_store.client.scan_iter(match=f"{FILE_FINGERPRINT_PREFIX}*"))
    print(f"指纹键数量: {len(fp_keys)}")
    if fp_keys:
        print("前3个指纹键:")
        for key in fp_keys[:3]:
            print(f"  {key.decode()}")
    
except Exception as e:
    print(f"检查Redis键失败: {e}")

# 6. 测试统计
print("\n6. 测试统计...")
stats = vector_store.get_statistics()
print(f"知识库统计: {stats}")

# 7. 测试搜索
print("\n7. 测试搜索...")
query = "开户"
results = vector_store.search(query)
print(f"搜索 '{query}' 结果: {len(results)}")

vector_store.close()

print("\n" + "=" * 70)
print("调试完成!")
print("=" * 70)
