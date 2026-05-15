# -*- coding: utf-8 -*-
"""调试存储问题"""

import os
import sys

# 设置环境变量
if sys.platform == 'win32':
    os.environ['PYTHONIOENCODING'] = 'utf-8'

from file_parser import FileParser
from vector_store import RedisVectorStore

print("=" * 70)
print("存储问题调试")
print("=" * 70)

# 测试目录
data_dir = r"D:\工作文档\cbss2.0体验版\沃工单问题定位"

# 1. 测试文件解析
print("\n1. 测试文件解析...")
parser = FileParser()
documents = parser.parse_directory(data_dir)

print(f"共解析到 {len(documents)} 个文档")

if documents:
    print("\n前3个文档:")
    for i, doc in enumerate(documents[:3], 1):
        print(f"\n文档 {i}:")
        print(f"  文件名: {doc.get('file_name')}")
        print(f"  文件类型: {doc.get('file_type')}")
        content = doc.get('content', '')
        print(f"  内容长度: {len(content)}")
        if content:
            print(f"  内容前100字符: {content[:100]}...")

# 2. 测试存储
print("\n" + "=" * 70)
print("2. 测试存储...")

vector_store = RedisVectorStore()

# 先清空存储
print("\n清空现有存储...")
vector_store.clear_all()

# 测试存储
if documents:
    print(f"\n尝试存储 {len(documents)} 个文档...")
    success_count = vector_store.add_documents(documents)
    print(f"成功存储: {success_count} 个文档")
else:
    print("没有文档可存储")

# 3. 测试统计
print("\n" + "=" * 70)
print("3. 测试统计...")

stats = vector_store.get_statistics()
print(f"知识库统计: {stats}")

# 4. 测试搜索
print("\n" + "=" * 70)
print("4. 测试搜索...")

query = "开户"
results = vector_store.search(query)
print(f"搜索 '{query}' 结果: {len(results)} 条")

if results:
    print("\n前2个结果:")
    for i, result in enumerate(results[:2], 1):
        print(f"\n结果 {i}:")
        print(f"  文件名: {result.get('file_name')}")
        print(f"  相似度: {result.get('similarity', 0):.2f}")
        content = result.get('content', '')
        if content:
            print(f"  内容前100字符: {content[:100]}...")

vector_store.close()

print("\n" + "=" * 70)
print("调试完成!")
print("=" * 70)
