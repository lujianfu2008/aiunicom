"""轻量级索引重建脚本 - 逐文件处理，避免内存溢出，带 API 限流"""
import os
import sys
import time
import gc
import hashlib

# 确保在正确目录
os.chdir(os.path.dirname(os.path.abspath(__file__)))

from config import REDIS_CONFIG, KEY_PREFIX, FILE_FINGERPRINT_PREFIX, MAX_CONTENT_LENGTH, VECTOR_MODEL_PROVIDER
import redis
import json


def rebuild_lightweight():
    """逐文件解析并入库，内存友好，带速率限制"""
    from file_parser import FileParser
    from vector_store import EmbeddingModel

    r = redis.Redis(**REDIS_CONFIG)
    parser = FileParser()
    embedding_model = EmbeddingModel()

    data_dir = '/home/ubuntu/AIknowledge/knowledge/沃工单问题定位'

    # 不再清空 - 增量模式，跳过已有指纹的文件
    existing_fps = set(k.decode() if isinstance(k, bytes) else k
                       for k in r.keys(f'{FILE_FINGERPRINT_PREFIX}*'))
    print(f'已有指纹: {len(existing_fps)} 个')

    # 逐文件处理
    success = 0
    fail = 0
    skip = 0
    skipped_existing = 0
    total = 0
    start_time = time.time()
    consecutive_429 = 0

    for root, dirs, files in os.walk(data_dir):
        for filename in files:
            total += 1
            file_path = os.path.join(root, filename)

            try:
                # 0. 检查指纹是否已存在（跳过已处理的）
                try:
                    mtime = os.path.getmtime(file_path)
                    mtime_str = str(int(mtime))
                except:
                    mtime_str = "0"
                key_str = f"{file_path}|{filename}|{mtime_str}"
                key_hash = hashlib.md5(key_str.encode()).hexdigest()
                fp_key = f"{FILE_FINGERPRINT_PREFIX}{key_hash}"

                if fp_key in existing_fps:
                    skipped_existing += 1
                    continue

                # 1. 解析文件
                doc = parser.parse_file(file_path)
                if not doc or not doc.get('content'):
                    skip += 1
                    continue

                content = doc['content'][:MAX_CONTENT_LENGTH]

                # 2. 生成 embedding（带重试和退避）
                max_retries = 5
                embedding = None
                for attempt in range(max_retries):
                    try:
                        embedding = embedding_model.encode_single(content)
                        consecutive_429 = 0
                        break
                    except Exception as e:
                        if '429' in str(e):
                            consecutive_429 += 1
                            wait = min(5 * (2 ** consecutive_429), 60)
                            print(f'  429 限流，等待 {wait}s...')
                            time.sleep(wait)
                        else:
                            raise

                if embedding is None:
                    fail += 1
                    print(f'  embedding 失败（重试用尽）: {filename}')
                    continue

                # 3. 生成 key
                doc_key = f"{KEY_PREFIX}{key_hash}"

                # 4. 写入 Redis
                from knowledge_base import extract_solution
                _, solution = extract_solution(content)

                doc_data = {
                    'problem_id': doc.get('problem_id', ''),
                    'problem_type': doc.get('problem_type', ''),
                    'file_name': filename,
                    'content': content,
                    'solution': solution,
                    'source': file_path,
                    'created_time': time.time(),
                    'embedding': embedding.tolist()
                }
                r.json().set(doc_key, '$', doc_data)

                # 5. 写入指纹
                fp = hashlib.md5(content.encode()).hexdigest()
                r.setex(fp_key, 30 * 24 * 3600, fp)
                existing_fps.add(fp_key)

                success += 1
                if success % 20 == 0:
                    elapsed = time.time() - start_time
                    rate = success / elapsed * 60 if elapsed > 0 else 0
                    print(f'  [{success}] 已入库 {success} 篇, '
                          f'跳过 {skip}, 已有 {skipped_existing}, 失败 {fail}, '
                          f'速度 {rate:.1f}篇/分')

                # 6. 限流：每次请求间隔 0.3 秒，避免触发 429
                time.sleep(0.3)

                # 7. 释放内存
                del doc, embedding, doc_data
                if success % 100 == 0:
                    gc.collect()

            except Exception as e:
                fail += 1
                if fail <= 10:
                    print(f'  失败: {filename}: {e}')
                continue

    elapsed = time.time() - start_time
    print(f'\n重建完成! 耗时 {elapsed:.0f} 秒 ({elapsed/60:.1f} 分钟)')
    print(f'  新增: {success}, 已有跳过: {skipped_existing}, 无内容: {skip}, 失败: {fail}, 总文件: {total}')
    final_count = len(list(r.keys(f'{KEY_PREFIX}*')))
    print(f'  Redis 文档总数: {final_count}')


if __name__ == '__main__':
    rebuild_lightweight()
