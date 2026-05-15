# -*- coding: utf-8 -*-
"""
向量搜索诊断修复脚本
排查全量重置后智能搜索（向量搜索）无结果的问题
"""

import sys
import os
import time
import json
import hashlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
import redis


# ============================================================
# 颜色输出
# ============================================================
class C:
    OK = '\033[92m'
    WARN = '\033[93m'
    FAIL = '\033[91m'
    BOLD = '\033[1m'
    END = '\033[0m'

def ok(msg):    print(f"  {C.OK}[通过]{C.END} {msg}")
def warn(msg):  print(f"  {C.WARN}[警告]{C.END} {msg}")
def fail(msg):  print(f"  {C.FAIL}[失败]{C.END} {msg}")
def info(msg):  print(f"  {C.BOLD}[信息]{C.END} {msg}")


def main():
    from config import (
        REDIS_CONFIG, INDEX_NAME, KEY_PREFIX, VECTOR_DIMENSION,
        SIMILARITY_THRESHOLD, VECTOR_MODEL_PROVIDER
    )

    print("=" * 60)
    print("  向量搜索诊断修复工具")
    print("=" * 60)

    problems_found = []

    # ----------------------------------------------------------
    # 1. Redis 连接检查
    # ----------------------------------------------------------
    print(f"\n{C.BOLD}[1] Redis 连接检查{C.END}")
    try:
        client = redis.Redis(
            host=REDIS_CONFIG['host'],
            port=REDIS_CONFIG['port'],
            password=REDIS_CONFIG['password'],
            db=REDIS_CONFIG['db'],
            decode_responses=False
        )
        client.ping()
        ok(f"Redis 连接成功 ({REDIS_CONFIG['host']}:{REDIS_CONFIG['port']})")
    except Exception as e:
        fail(f"Redis 连接失败: {e}")
        print("  请检查 config.ini 中的 Redis 配置")
        return
    problems = []

    # ----------------------------------------------------------
    # 2. 文档数据检查
    # ----------------------------------------------------------
    print(f"\n{C.BOLD}[2] 文档数据检查{C.END}")

    doc_keys = list(client.scan_iter(match=f"{KEY_PREFIX}*", count=500))
    doc_count = len(doc_keys)
    info(f"workorder:* 键数量: {doc_count}")

    if doc_count == 0:
        fail("没有任何文档数据！全量重置后可能 initialize() 失败或未完成")
        problems.append("NO_DOCUMENTS")
    else:
        ok(f"共有 {doc_count} 条文档")

        # 抽样检查 embedding 字段
        sample_size = min(doc_count, 10)
        import random
        sample_keys = random.sample(doc_keys, sample_size)

        no_embedding_count = 0
        bad_embedding_count = 0
        embedding_lengths = set()
        is_simple_encode = 0

        for key in sample_keys:
            try:
                doc_data = client.json().get(key)
                if doc_data is None:
                    continue
                embedding = doc_data.get('embedding')
                if embedding is None:
                    no_embedding_count += 1
                    continue

                arr = np.array(embedding, dtype=np.float32)
                embedding_lengths.add(len(arr))

                # 检测 _simple_encode 的特征：基于 MD5 seed 的随机向量
                # _simple_encode 产生的向量是 L2 归一化的，且对同一文本每次结果一样
                # 无法100%识别，但可以检查全零、维度不对等明显问题
                if len(arr) != VECTOR_DIMENSION:
                    bad_embedding_count += 1
                if np.all(arr == 0):
                    bad_embedding_count += 1

            except Exception as e:
                warn(f"读取文档失败 {key}: {e}")

        if no_embedding_count > 0:
            fail(f"{no_embedding_count}/{sample_size} 条文档缺少 embedding 字段")
            problems.append("MISSING_EMBEDDING")
        else:
            ok(f"所有抽样文档都有 embedding 字段")

        if bad_embedding_count > 0:
            fail(f"{bad_embedding_count}/{sample_size} 条文档 embedding 维度异常")
            problems.append("BAD_EMBEDDING")
        elif embedding_lengths:
            if embedding_lengths == {VECTOR_DIMENSION}:
                ok(f"embedding 维度正确: {VECTOR_DIMENSION}")
            else:
                fail(f"embedding 维度不一致: {embedding_lengths}，期望 {VECTOR_DIMENSION}")
                problems.append("BAD_EMBEDDING")

    # ----------------------------------------------------------
    # 3. 向量索引检查
    # ----------------------------------------------------------
    print(f"\n{C.BOLD}[3] 向量索引检查{C.END}")

    try:
        index_list = client.execute_command('FT._LIST')
        index_names = [idx.decode() if isinstance(idx, bytes) else idx for idx in index_list]
        info(f"现有索引: {index_names}")

        if INDEX_NAME in index_names:
            ok(f"向量索引 '{INDEX_NAME}' 存在")

            # 检查索引详情
            try:
                index_info = client.ft(INDEX_NAME).info()
                num_docs = index_info.get('num_docs', 'unknown')
                num_indexed = index_info.get('num_indexed', 'unknown')
                info(f"索引文档数: {num_docs}, 已索引数: {num_indexed}")

                if isinstance(num_docs, (int, str)):
                    num_docs_int = int(num_docs)
                    if num_docs_int == 0 and doc_count > 0:
                        fail(f"索引中有 0 条文档，但 Redis 中有 {doc_count} 条 workorder 数据")
                        problems.append("INDEX_EMPTY")
                    elif num_docs_int < doc_count * 0.9:
                        warn(f"索引文档数({num_docs_int})远少于实际文档数({doc_count})")
                        problems.append("INDEX_INCOMPLETE")
                    else:
                        ok(f"索引文档数量正常: {num_docs_int}")
            except Exception as e:
                warn(f"获取索引详情失败: {e}")
        else:
            fail(f"向量索引 '{INDEX_NAME}' 不存在！")
            problems.append("NO_INDEX")
    except Exception as e:
        fail(f"FT._LIST 执行失败: {e}")
        problems.append("INDEX_ERROR")

    # ----------------------------------------------------------
    # 4. Embedding 模型检查
    # ----------------------------------------------------------
    print(f"\n{C.BOLD}[4] Embedding 模型检查{C.END}")

    info(f"配置的向量模型提供商: {VECTOR_MODEL_PROVIDER}")

    from vector_store import EmbeddingModel
    embedding_model = EmbeddingModel()

    # 等待模型加载
    if hasattr(embedding_model, 'model_loaded'):
        info("等待模型加载...")
        waited = 0
        while not embedding_model.model_loaded and waited < 60:
            time.sleep(0.5)
            waited += 0.5
        if not embedding_model.model_loaded:
            fail("模型加载超时 (60秒)")
            problems.append("MODEL_TIMEOUT")
        else:
            ok(f"模型加载完成 (耗时约 {waited:.1f}s)")
    else:
        ok("模型标记为已加载")

    # 检查模型类型
    model_type = getattr(embedding_model, 'model', None)
    info(f"模型类型: {model_type}")

    if model_type == "zhipu":
        warn("当前使用智谱 AI embedding（配置要求 local 模型）")
        warn("说明本地模型加载失败，降级到了智谱 API")
        problems.append("FALLBACK_ZHIPU")
    elif model_type == "transformers":
        ok("使用 transformers 本地模型")
    elif model_type is not None and model_type != "transformers" and model_type != "zhipu":
        ok("使用 sentence-transformers 本地模型")
    elif model_type is None:
        fail("模型加载失败，当前使用 _simple_encode 降级方案（MD5 随机向量）")
        fail("这种向量无法提供有意义的搜索结果！")
        problems.append("SIMPLE_ENCODE")

    # 测试向量生成
    print(f"\n{C.BOLD}[5] 向量生成测试{C.END}")
    try:
        test_text = "开户报错测试"
        test_vector = embedding_model.encode_single(test_text)
        info(f"测试文本: '{test_text}'")
        info(f"向量维度: {test_vector.shape}, 类型: {test_vector.dtype}")

        if test_vector.shape[0] != VECTOR_DIMENSION:
            fail(f"向量维度错误: {test_vector.shape[0]}, 期望 {VECTOR_DIMENSION}")
            problems.append("VECTOR_DIM_WRONG")
        else:
            ok(f"向量维度正确: {VECTOR_DIMENSION}")

        # 检查是否全零
        if np.all(test_vector == 0):
            fail("生成的向量全为零！")
            problems.append("ZERO_VECTOR")
        else:
            ok("向量非零，有实际值")

        # 检查是否被归一化
        norm = np.linalg.norm(test_vector)
        info(f"向量 L2 范数: {norm:.6f}")

    except Exception as e:
        fail(f"向量生成失败: {e}")
        problems.append("ENCODE_FAILED")

    # ----------------------------------------------------------
    # 6. 向量搜索测试
    # ----------------------------------------------------------
    print(f"\n{C.BOLD}[6] 向量搜索测试{C.END}")

    if doc_count > 0 and "NO_INDEX" not in problems and "ENCODE_FAILED" not in problems:
        try:
            from redis.commands.search.query import Query

            query_text = "开户"
            query_embedding = embedding_model.encode_single(query_text)

            query_str = f"*=>[KNN 3 @embedding $query_vector AS score]"
            query_obj = Query(query_str) \
                .return_fields("problem_id", "content", "score") \
                .sort_by("score") \
                .dialect(2)

            results = client.ft(INDEX_NAME).search(
                query_obj,
                query_params={"query_vector": query_embedding.tobytes()}
            )

            if results.total == 0:
                fail(f"搜索 '{query_text}' 返回 0 条结果")
                problems.append("SEARCH_NO_RESULTS")
            else:
                ok(f"搜索 '{query_text}' 返回 {results.total} 条结果")
                for doc in results.docs[:3]:
                    similarity = 1 - float(doc.score)
                    threshold_mark = " (低于阈值)" if similarity < SIMILARITY_THRESHOLD else ""
                    print(f"    - 相似度: {similarity:.4f} | 内容: {doc.content[:60]}...{threshold_mark}")
        except Exception as e:
            fail(f"向量搜索执行失败: {e}")
            problems.append("SEARCH_ERROR")
    elif doc_count == 0:
        warn("无文档数据，跳过搜索测试")
    else:
        warn("索引不存在或向量生成失败，跳过搜索测试")

    # ----------------------------------------------------------
    # 7. 内容查找对比测试
    # ----------------------------------------------------------
    print(f"\n{C.BOLD}[7] 内容查找对比测试{C.END}")

    if doc_count > 0:
        try:
            from vector_store import RedisVectorStore
            vs = RedisVectorStore()
            content_results = vs.find_by_content("开户")
            if content_results:
                ok(f"内容查找 '开户' 返回 {len(content_results)} 条结果")
                if "SEARCH_NO_RESULTS" in problems:
                    warn("内容查找有结果但向量搜索无结果，确认是向量/embedding 问题")
            else:
                warn("内容查找 '开户' 也无结果")
        except Exception as e:
            warn(f"内容查找测试失败: {e}")

    # ----------------------------------------------------------
    # 诊断总结
    # ----------------------------------------------------------
    print("\n" + "=" * 60)
    print(f"  {C.BOLD}诊断总结{C.END}")
    print("=" * 60)

    if not problems:
        ok("未发现明显问题，向量搜索应正常工作")
        return

    print(f"\n  发现 {len(problems)} 个问题:\n")
    for i, p in enumerate(problems, 1):
        print(f"    {i}. {_PROBLEM_DESC.get(p, p)}")

    # ----------------------------------------------------------
    # 修复建议 & 自动修复
    # ----------------------------------------------------------
    print("\n" + "-" * 60)
    print(f"  {C.BOLD}修复建议{C.END}")
    print("-" * 60)

    _print_fix_advice(problems)

    # 自动修复提示
    fixable = _get_fixable_problems(problems)
    if fixable:
        print(f"\n  {C.BOLD}可以自动修复的问题: {len(fixable)} 个{C.END}")
        answer = input(f"\n  是否执行自动修复？(y/n): ").strip().lower()
        if answer == 'y':
            _do_fix(client, problems, embedding_model, VECTOR_MODEL_PROVIDER)
        else:
            print("  跳过自动修复。")
    else:
        print("\n  以上问题需要手动处理，无法自动修复。")


# ============================================================
# 问题描述映射
# ============================================================
_PROBLEM_DESC = {
    "NO_DOCUMENTS":     "Redis 中没有文档数据，initialize() 可能失败",
    "MISSING_EMBEDDING":"部分文档缺少 embedding 字段",
    "BAD_EMBEDDING":    "部分文档 embedding 维度异常",
    "NO_INDEX":         "RediSearch 向量索引不存在",
    "INDEX_EMPTY":      "索引存在但文档数为 0",
    "INDEX_INCOMPLETE": "索引文档数远少于实际文档数",
    "MODEL_TIMEOUT":    "Embedding 模型加载超时",
    "FALLBACK_ZHIPU":   "本地模型加载失败，降级到智谱 API（不影响功能但说明本地模型有问题）",
    "SIMPLE_ENCODE":    "模型全部失败，使用了 _simple_encode 降级方案，向量无意义",
    "ENCODE_FAILED":    "向量生成失败",
    "VECTOR_DIM_WRONG": "向量维度与配置不匹配",
    "ZERO_VECTOR":      "生成的向量为全零",
    "SEARCH_NO_RESULTS":"向量搜索无返回结果",
    "SEARCH_ERROR":     "向量搜索执行异常",
}


def _print_fix_advice(problems):
    """根据问题类型给出修复建议"""
    if "SIMPLE_ENCODE" in problems:
        print("""
  [核心问题] Embedding 模型完全不可用，使用了 _simple_encode 降级方案
  影响：所有向量都是基于 MD5 的伪随机值，无法进行语义搜索

  修复方案：
    1. 检查本地模型路径是否存在:
       /home/ubuntu/AIknowledge/models/text2vec-base-chinese
    2. 如果路径不存在，下载 text2vec-base-chinese 模型到该路径
    3. 或在 config.ini 中设置 vector_model_provider = zhipu，使用智谱 API
    4. 修复后执行全量重置重新生成 embedding""")

    if "NO_DOCUMENTS" in problems:
        print("""
  [数据问题] Redis 中没有文档数据
  修复方案：
    1. 检查数据目录是否存在: /home/ubuntu/AIknowledge/knowledge/沃工单问题定位
    2. 确认目录中有可解析的文件
    3. 通过 Web UI 或 API 执行全量重置 (POST /api/init)
    4. 或运行本脚本自动修复""")

    if "NO_INDEX" in problems or "INDEX_EMPTY" in problems:
        print("""
  [索引问题] 向量索引缺失或为空
  修复方案：
    1. 删除旧索引并重新创建
    2. 如果文档数据存在，重建索引后数据会自动被索引
    3. 可通过本脚本自动修复""")

    if "INDEX_INCOMPLETE" in problems:
        print("""
  [索引问题] 索引不完整
  修复方案：
    1. 重建向量索引 (FT.DROPINDEX + 重新创建)
    2. 可通过本脚本自动修复""")

    if "SEARCH_NO_RESULTS" in problems and "SIMPLE_ENCODE" not in problems:
        print("""
  [搜索问题] 向量搜索无结果但文档和索引似乎正常
  可能原因：
    1. 文档中的 embedding 使用了 _simple_encode 生成（历史遗留）
    2. 需要重新生成所有文档的 embedding
    3. 可通过全量重置修复""")

    if "FALLBACK_ZHIPU" in problems:
        print("""
  [模型降级] 本地模型加载失败，已降级到智谱 API
  影响：功能可用但依赖网络和 API 配额
  修复方案：
    1. 检查本地模型路径和依赖 (transformers / torch)
    2. 确保 text2vec-base-chinese 模型文件完整""")


def _get_fixable_problems(problems):
    """判断哪些问题可以自动修复"""
    fixable = []
    # 索引问题都可以自动修复
    if "NO_INDEX" in problems:
        fixable.append("NO_INDEX")
    if "INDEX_EMPTY" in problems:
        fixable.append("INDEX_EMPTY")
    if "INDEX_INCOMPLETE" in problems:
        fixable.append("INDEX_INCOMPLETE")
    # 无文档可以通过重新初始化修复
    if "NO_DOCUMENTS" in problems:
        fixable.append("NO_DOCUMENTS")
    # 搜索无结果但文档存在，可以尝试重建索引
    if "SEARCH_NO_RESULTS" in problems and "NO_DOCUMENTS" not in problems:
        fixable.append("SEARCH_NO_RESULTS")
    return fixable


def _do_fix(client, problems, embedding_model, model_provider):
    """执行自动修复"""
    from config import INDEX_NAME, KEY_PREFIX, VECTOR_DIMENSION

    print(f"\n  {C.BOLD}开始自动修复...{C.END}\n")

    # Step 1: 重建向量索引
    if any(p in problems for p in ["NO_INDEX", "INDEX_EMPTY", "INDEX_INCOMPLETE", "SEARCH_NO_RESULTS"]):
        print("  [步骤1] 重建向量索引...")
        try:
            # 删除旧索引
            try:
                client.ft(INDEX_NAME).dropindex(delete_documents=False)
                info("已删除旧索引")
            except Exception:
                info("旧索引不存在，跳过删除")

            # 创建新索引
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
                        "DIM": VECTOR_DIMENSION,
                        "DISTANCE_METRIC": "COSINE"
                    },
                    as_name="embedding"
                )
            )

            definition = IndexDefinition(
                prefix=[KEY_PREFIX],
                index_type=IndexType.JSON
            )

            client.ft(INDEX_NAME).create_index(fields=schema, definition=definition)
            ok("向量索引创建成功")

            # 等待索引完成
            time.sleep(2)
            index_info = client.ft(INDEX_NAME).info()
            num_indexed = index_info.get('num_docs', 'unknown')
            info(f"索引中已有 {num_indexed} 条文档")

        except Exception as e:
            fail(f"重建索引失败: {e}")
            return

    # Step 2: 如果没有文档，尝试初始化
    if "NO_DOCUMENTS" in problems:
        print("\n  [步骤2] 尝试初始化知识库...")
        try:
            from knowledge_base import KnowledgeBase
            kb = KnowledgeBase()
            success = kb.initialize()
            if success:
                ok("知识库初始化成功")
            else:
                fail("知识库初始化失败，请检查日志")
        except Exception as e:
            fail(f"初始化失败: {e}")

    # Step 3: 如果搜索无结果且文档存在，检查 embedding 质量
    if "SEARCH_NO_RESULTS" in problems and "NO_DOCUMENTS" not in problems:
        print("\n  [步骤3] 检查文档 embedding 质量...")

        # 检查是否是 _simple_encode 生成的向量（通过重建 embedding 修复）
        doc_keys = list(client.scan_iter(match=f"{KEY_PREFIX}*", count=500))
        if doc_keys and model_provider != 'simple':
            # 只重建索引还不够，可能需要重新生成 embedding
            # 检查 embedding 质量是否需要重新生成
            sample_key = doc_keys[0]
            doc_data = client.json().get(sample_key)
            if doc_data and 'embedding' in doc_data:
                info("文档包含 embedding 字段，索引已重建，再次测试搜索...")
                try:
                    from redis.commands.search.query import Query
                    test_query = "开户"
                    query_embedding = embedding_model.encode_single(test_query)
                    query_str = f"*=>[KNN 3 @embedding $query_vector AS score]"
                    query_obj = Query(query_str) \
                        .return_fields("problem_id", "content", "score") \
                        .sort_by("score") \
                        .dialect(2)
                    results = client.ft(INDEX_NAME).search(
                        query_obj,
                        query_params={"query_vector": query_embedding.tobytes()}
                    )
                    if results.total > 0:
                        ok(f"修复后搜索返回 {results.total} 条结果！")
                        for doc in results.docs[:3]:
                            similarity = 1 - float(doc.score)
                            print(f"    - 相似度: {similarity:.4f} | 内容: {doc.content[:60]}...")
                    else:
                        warn("搜索仍然无结果")
                        print("  可能是文档的 embedding 质量有问题（使用了 _simple_encode 生成）")
                        print("  建议: 通过 Web UI 执行「全量重置」重新生成所有 embedding")
                except Exception as e:
                    fail(f"测试搜索失败: {e}")

    print(f"\n  {C.BOLD}修复流程完成{C.END}")
    print("  如果问题仍然存在，请通过 Web UI 执行「全量重置」以重新生成所有 embedding。\n")


if __name__ == "__main__":
    main()
