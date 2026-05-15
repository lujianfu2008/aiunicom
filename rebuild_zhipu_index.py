# -*- coding: utf-8 -*-
"""
使用智谱AI embedding重建索引
"""

import os
import sys
import time
import redis
import json
import hashlib
from config import REDIS_CONFIG, DATA_DIR, ZHIPU_CONFIG
from zhipu_llm import ZhipuLLM
from file_parser import FileParser

ZHIPU_EMBEDDING_DIM = 1024
REQUEST_INTERVAL = 1.0

def get_embedding_with_retry(llm, text, max_retries=5):
    """带重试的获取embedding"""
    for i in range(max_retries):
        try:
            emb = llm.get_embedding(text)
            if emb:
                return emb
        except Exception as e:
            if "429" in str(e) or "Too Many Requests" in str(e):
                wait_time = (i + 1) * 5
                print(f"\nAPI限流，等待{wait_time}秒后重试...")
                time.sleep(wait_time)
            else:
                print(f"\n获取embedding错误: {e}")
                break
    return None

def rebuild_index_with_zhipu():
    """使用智谱AI embedding重建索引"""
    
    print("=" * 60)
    print("使用智谱AI embedding重建索引")
    print("=" * 60)
    
    # 连接Redis
    r = redis.Redis(**REDIS_CONFIG)
    print(f"\n已连接Redis: {REDIS_CONFIG['host']}:{REDIS_CONFIG['port']}")
    
    # 初始化智谱AI
    llm = ZhipuLLM(ZHIPU_CONFIG)
    if not llm.api_key:
        print("错误: 智谱AI未配置API Key")
        return False
    print(f"智谱AI已初始化")
    
    # 初始化文件解析器
    parser = FileParser()
    
    # 获取所有现有文档
    print("\n获取现有文档...")
    all_keys = r.keys('workorder:*')
    doc_keys = [k for k in all_keys if b':' not in k[10:]]
    print(f"找到 {len(doc_keys)} 个文档")
    
    # 删除旧索引
    print("\n删除旧索引...")
    try:
        r.execute_command('FT.DROPINDEX', 'workorder_knowledge_idx', 'DD')
        print("旧索引已删除")
    except:
        print("旧索引不存在或已删除")
    
    # 删除所有旧文档
    print("删除旧文档...")
    deleted = 0
    for key in doc_keys:
        r.delete(key)
        deleted += 1
    print(f"已删除 {deleted} 个旧文档")
    
    # 删除指纹
    fp_keys = r.keys('workorder_fp:*')
    for key in fp_keys:
        r.delete(key)
    print(f"已删除 {len(fp_keys)} 个指纹")
    
    # 扫描数据目录
    print(f"\n扫描数据目录: {DATA_DIR}")
    data_dir = DATA_DIR
    if not os.path.exists(data_dir):
        print(f"错误: 数据目录不存在: {data_dir}")
        return False
    
    # 收集所有文件
    all_files = []
    for root, dirs, files in os.walk(data_dir):
        for file in files:
            if file.startswith('~$') or file.startswith('.'):
                continue
            file_path = os.path.join(root, file)
            all_files.append(file_path)
    
    print(f"找到 {len(all_files)} 个文件")
    
    # 处理文件并重建索引
    print("\n开始重建索引...")
    success_count = 0
    error_count = 0
    
    for i, file_path in enumerate(all_files):
        try:
            # 解析文件
            result = parser.parse_file(file_path)
            if not result or not result.get('content'):
                continue
            
            content = result.get('content', '')
            if len(content.strip()) < 10:
                continue
            
            # 获取文件名
            file_name = os.path.basename(file_path)
            
            # 生成文档ID
            doc_id = hashlib.md5(file_path.encode()).hexdigest()[:32]
            key = f"workorder:{doc_id}"
            
            # 获取embedding
            print(f"[{i+1}/{len(all_files)}] 处理: {file_name[:40]}...", end=" ", flush=True)
            
            # 限制内容长度
            content_for_emb = content[:2000] if len(content) > 2000 else content
            
            embedding = get_embedding_with_retry(llm, content_for_emb)
            if not embedding:
                print("embedding失败")
                error_count += 1
                continue
            
            # 存储文档
            doc_data = {
                'problem_id': os.path.splitext(file_name)[0].split('-')[0],
                'problem_type': '未知',
                'file_name': file_name,
                'content': content[:5000] if len(content) > 5000 else content,
                'solution': '',
                'source': file_path,
                'created_time': int(time.time()),
                'embedding': embedding
            }
            
            r.execute_command('JSON.SET', key, '$', json.dumps(doc_data, ensure_ascii=False))
            
            # 存储指纹
            fp_key = f"workorder_fp:{doc_id}"
            file_stat = os.stat(file_path)
            r.hset(fp_key, mapping={
                'path': file_path,
                'mtime': str(file_stat.st_mtime),
                'size': str(file_stat.st_size)
            })
            r.expire(fp_key, 30 * 24 * 3600)
            
            success_count += 1
            print("OK")
            
            # 避免API限流
            time.sleep(REQUEST_INTERVAL)
            
        except Exception as e:
            print(f"错误: {e}")
            error_count += 1
            continue
    
    print(f"\n处理完成: 成功 {success_count}, 失败 {error_count}")
    
    # 创建新索引
    print("\n创建新索引...")
    try:
        from redis.commands.search.field import TextField, NumericField, VectorField
        from redis.commands.search.indexDefinition import IndexDefinition, IndexType
        
        schema = (
            TextField("$.problem_id", as_name="problem_id"),
            TextField("$.problem_type", as_name="problem_type"),
            TextField("$.file_name", as_name="file_name"),
            TextField("$.content", as_name="content"),
            TextField("$.solution", as_name="solution"),
            TextField("$.source", as_name="source"),
            NumericField("$.created_time", as_name="created_time"),
            VectorField(
                "$.embedding",
                "FLAT",
                {
                    "TYPE": "FLOAT32",
                    "DIM": ZHIPU_EMBEDDING_DIM,
                    "DISTANCE_METRIC": "COSINE"
                },
                as_name="embedding"
            )
        )
        
        definition = IndexDefinition(
            prefix=["workorder:"],
            index_type=IndexType.JSON
        )
        
        r.ft("workorder_knowledge_idx").create_index(
            fields=schema,
            definition=definition
        )
        print("新索引创建成功!")
        
    except Exception as e:
        print(f"创建索引失败: {e}")
        return False
    
    print("\n" + "=" * 60)
    print("索引重建完成!")
    print("=" * 60)
    
    return True

if __name__ == "__main__":
    rebuild_index_with_zhipu()
