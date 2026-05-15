# -*- coding: utf-8 -*-
"""
向量化存储模块 - 使用Redis Stack和本地模型
"""

import sys
import os
import json
import logging
import hashlib
import warnings
import time
from typing import List, Dict, Optional, Tuple
import numpy as np

# 设置环境变量（Windows）
if sys.platform == 'win32':
    os.environ['PYTHONIOENCODING'] = 'utf-8'

# 禁用GPU警告
warnings.filterwarnings('ignore', message='Neither CUDA nor MPS are available')

import redis
import json
import numpy as np
from redis.commands.search.field import TextField, NumericField, VectorField
from redis.commands.search.indexDefinition import IndexDefinition, IndexType

from config import (
    REDIS_CONFIG, LOCAL_MODEL_PATH, VECTOR_DIMENSION,
    INDEX_NAME, KEY_PREFIX, CHUNK_SIZE, CHUNK_OVERLAP,
    SIMILARITY_THRESHOLD, TOP_K_RESULTS,
    FILE_FINGERPRINT_PREFIX, FINGERPRINT_EXPIRE_DAYS,
    MAX_CONTENT_LENGTH, VECTOR_MODEL_PROVIDER
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class EmbeddingModel:
    """文本向量化模型"""
    
    def __init__(self, model_path: str = LOCAL_MODEL_PATH, use_local_model: bool = None, use_zhipu: bool = None, vector_model_provider: str = None):
        self.model_path = model_path
        self.model = None
        self.tokenizer = None
        
        # 如果未指定参数，使用配置文件中的设置
        if vector_model_provider is None:
            vector_model_provider = VECTOR_MODEL_PROVIDER
        
        # 根据配置设置模型提供商
        if use_zhipu is None and use_local_model is None:
            self.use_local_model = (vector_model_provider == 'local')
            self.use_zhipu = (vector_model_provider == 'zhipu')
        else:
            self.use_local_model = use_local_model if use_local_model is not None else True
            self.use_zhipu = use_zhipu if use_zhipu is not None else False
        
        if self.use_zhipu:
            # 强制使用智谱 AI embedding
            self._use_zhipu_embedding()
        elif self.use_local_model:
            # 异步加载模型，避免卡住
            import threading
            self.model_loaded = False
            self.load_thread = threading.Thread(target=self._load_model)
            self.load_thread.daemon = True
            self.load_thread.start()
        # 注意：模型在后台加载中，不在这里检查
    
    def _load_model(self):
        """加载本地模型"""
        try:
            import os
            if not os.path.exists(self.model_path):
                logger.warning(f"模型路径不存在: {self.model_path}，尝试使用智谱AI embedding")
                self._use_zhipu_embedding()
                return
            
            # 方法1: 尝试使用transformers直接加载（低内存模式）
            try:
                from transformers import AutoTokenizer, AutoModel
                import torch
                
                logger.info("尝试加载transformers模型（低内存模式）...")
                self.tokenizer = AutoTokenizer.from_pretrained(self.model_path)
                
                # 使用低内存模式加载模型
                self.transformer_model = AutoModel.from_pretrained(
                    self.model_path,
                    low_cpu_mem_usage=True,
                    torch_dtype=torch.float32
                )
                
                # 如果有GPU，尝试移动到GPU
                if torch.cuda.is_available():
                    self.transformer_model = self.transformer_model.to('cuda')
                    logger.info("模型已加载到GPU")
                else:
                    logger.info("模型已加载到CPU")
                
                self.model = "transformers"  # 标记使用transformers
                logger.info(f"成功使用transformers加载模型: {self.model_path}")
                self.model_loaded = True
                return
            except Exception as e:
                logger.warning(f"transformers加载失败: {e}")
            
            # 方法2: 尝试使用sentence-transformers
            try:
                from sentence_transformers import SentenceTransformer
                logger.info("尝试加载sentence-transformers模型...")
                self.model = SentenceTransformer(self.model_path, device='cpu')
                logger.info(f"成功加载本地模型: {self.model_path}")
                self.model_loaded = True
                return
            except Exception as e:
                logger.warning(f"sentence-transformers加载失败: {e}")
            
            # 方法3: 使用智谱AI embedding
            logger.warning("本地模型加载失败，尝试使用智谱AI embedding")
            self._use_zhipu_embedding()
            
        except Exception as e:
            logger.warning(f"加载模型失败: {str(e)}，尝试使用智谱AI embedding")
            self._use_zhipu_embedding()
    
    def _use_zhipu_embedding(self):
        """使用智谱AI embedding作为备用"""
        try:
            from zhipu_llm import ZhipuLLM
            from config import ZHIPU_CONFIG
            
            self.zhipu_llm = ZhipuLLM(ZHIPU_CONFIG)
            if self.zhipu_llm.api_key:
                self.model = "zhipu"
                logger.info("成功使用智谱AI embedding")
            else:
                logger.warning("智谱AI未配置API Key，使用备用方法")
                self.model = None
            self.model_loaded = True
        except Exception as e:
            logger.warning(f"智谱AI embedding初始化失败: {e}，使用备用方法")
            self.model = None
            self.model_loaded = True
    
    def encode(self, texts: List[str]) -> np.ndarray:
        """
        将文本转换为向量
        
        Args:
            texts: 文本列表
            
        Returns:
            向量数组
        """
        # 使用智谱AI embedding
        if self.model == "zhipu":
            try:
                embeddings = []
                for text in texts:
                    emb = self.zhipu_llm.get_embedding(text)
                    if emb:
                        embeddings.append(emb)
                    else:
                        # 如果智谱AI失败，使用备用方法
                        embeddings.append(self._simple_encode([text])[0])
                return np.array(embeddings, dtype=np.float32)
            except Exception as e:
                logger.error(f"智谱AI向量化失败: {str(e)}")
                return self._simple_encode(texts)
        
        # 使用transformers模型
        if self.model == "transformers" and self.transformer_model is not None:
            try:
                import torch
                # 确定设备
                device = next(self.transformer_model.parameters()).device
                # 编码文本
                encoded_input = self.tokenizer(texts, padding=True, truncation=True, max_length=512, return_tensors='pt')
                # 将输入移动到模型所在设备
                encoded_input = {k: v.to(device) for k, v in encoded_input.items()}
                # 计算embeddings
                with torch.no_grad():
                    model_output = self.transformer_model(**encoded_input)
                # 使用mean pooling
                attention_mask = encoded_input['attention_mask']
                embeddings = self._mean_pooling(model_output, attention_mask)
                # 归一化
                embeddings = torch.nn.functional.normalize(embeddings, p=2, dim=1)
                return embeddings.cpu().numpy()
            except Exception as e:
                logger.error(f"transformers向量化失败: {str(e)}")
        
        # 使用sentence-transformers模型
        if self.model is not None and self.model != "transformers" and self.model != "zhipu":
            try:
                embeddings = self.model.encode(texts, normalize_embeddings=True)
                return embeddings
            except Exception as e:
                logger.error(f"向量化失败: {str(e)}")
        
        return self._simple_encode(texts)
    
    def _mean_pooling(self, model_output, attention_mask):
        """Mean Pooling"""
        import torch
        token_embeddings = model_output[0]
        input_mask_expanded = attention_mask.unsqueeze(-1).expand(token_embeddings.size()).float()
        return torch.sum(token_embeddings * input_mask_expanded, 1) / torch.clamp(input_mask_expanded.sum(1), min=1e-9)
    
    def _simple_encode(self, texts: List[str]) -> np.ndarray:
        """简单的向量化方法（备用）"""
        embeddings = []
        for text in texts:
            text_hash = hashlib.md5(text.encode()).hexdigest()
            np.random.seed(int(text_hash[:8], 16))
            embedding = np.random.randn(VECTOR_DIMENSION).astype(np.float32)
            embedding = embedding / np.linalg.norm(embedding)
            embeddings.append(embedding)
        return np.array(embeddings)
    
    def encode_single(self, text: str) -> np.ndarray:
        """转换单个文本为向量"""
        return self.encode([text])[0]


# Redis Lua 脚本：服务端关键词匹配，只返回匹配的 key，避免传输全量文档数据
_LUA_CONTENT_SEARCH = """
local pattern = ARGV[1]
local kw_str = ARGV[2]

local keywords = {}
for kw in string.gmatch(kw_str, '([^,]+)') do
    keywords[#keywords + 1] = kw
end

local cursor = '0'
local matched_keys = {}

repeat
    local reply = redis.call('SCAN', cursor, 'MATCH', pattern, 'COUNT', '500')
    cursor = tostring(reply[1])
    local keys = reply[2]

    for _, key in ipairs(keys) do
        local key_str = tostring(key)
        if not key_str:find('_idx') and not key_str:find('_cache') then
            local content = redis.call('JSON.GET', key, '$.content')
            local solution = redis.call('JSON.GET', key, '$.solution')
            local fname = redis.call('JSON.GET', key, '$.file_name')

            content = content and string.lower(tostring(content)) or ''
            solution = solution and string.lower(tostring(solution)) or ''
            fname = fname and string.lower(tostring(fname)) or ''

            local all_match = true
            for _, kw in ipairs(keywords) do
                if not (content:find(kw, 1, true) or solution:find(kw, 1, true) or fname:find(kw, 1, true)) then
                    all_match = false
                    break
                end
            end

            if all_match then
                matched_keys[#matched_keys + 1] = key_str
            end
        end
    end
until cursor == '0'

return matched_keys
"""


class RedisVectorStore:
    """Redis 向量存储"""
    
    def __init__(self, redis_config: Dict = None, use_zhipu: bool = None, vector_model_provider: str = None):
        self.redis_config = redis_config or REDIS_CONFIG
        self.client = None
        
        # 如果未指定参数，使用配置文件中的设置
        if vector_model_provider is None:
            vector_model_provider = VECTOR_MODEL_PROVIDER
        
        self.use_zhipu = (vector_model_provider == 'zhipu') if use_zhipu is None else use_zhipu
        self.embedding_model = EmbeddingModel(use_zhipu=self.use_zhipu, vector_model_provider=vector_model_provider)
        self._connect()
    
    def _connect(self):
        """连接Redis"""
        try:
            self.client = redis.Redis(
                host=self.redis_config['host'],
                port=self.redis_config['port'],
                password=self.redis_config['password'],
                db=self.redis_config['db'],
                decode_responses=False
            )
            self.client.ping()
            logger.info("成功连接Redis")
            self._create_index()
        except Exception as e:
            logger.error(f"连接Redis失败: {str(e)}")
            raise
    
    def _create_index(self, force_recreate: bool = False):
        """创建向量索引
        
        Args:
            force_recreate: 是否强制重建索引
        """
        try:
            existing_indices = self.client.execute_command('FT._LIST')
            
            # 如果索引已存在
            if INDEX_NAME.encode() in existing_indices:
                if force_recreate:
                    logger.info(f"删除现有索引: {INDEX_NAME}")
                    self.client.ft(INDEX_NAME).dropindex(delete_documents=True)
                else:
                    logger.info(f"索引 {INDEX_NAME} 已存在")
                    return
        except:
            pass
        
        try:
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
            
            self.client.ft(INDEX_NAME).create_index(
                fields=schema,
                definition=definition
            )
            logger.info(f"成功创建索引: {INDEX_NAME}")
            
        except Exception as e:
            logger.error(f"创建索引失败: {str(e)}")
    
    def _chunk_text(self, text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> List[str]:
        """
        将长文本分割成块
        
        Args:
            text: 原始文本
            chunk_size: 块大小
            overlap: 重叠大小
            
        Returns:
            文本块列表
        """
        if len(text) <= chunk_size:
            return [text]
        
        chunks = []
        start = 0
        
        while start < len(text):
            end = start + chunk_size
            chunk = text[start:end]
            
            if end < len(text):
                last_period = chunk.rfind('。')
                last_newline = chunk.rfind('\n')
                split_point = max(last_period, last_newline)
                
                if split_point > start + chunk_size // 2:
                    chunk = text[start:split_point + 1]
                    end = split_point + 1
            
            chunks.append(chunk.strip())
            start = end - overlap if end < len(text) else end
        
        return [c for c in chunks if c]
    
    def add_document(self, doc: Dict) -> bool:
        """
        添加文档到向量库
        
        Args:
            doc: 文档字典，包含file_path, file_name, content等字段
            
        Returns:
            是否成功
        """
        try:
            content = doc.get('content', '')
            if not content:
                return False
            
            chunks = self._chunk_text(content)
            
            for i, chunk in enumerate(chunks):
                embedding = self.embedding_model.encode_single(chunk)
                
                # 使用更安全的键生成方法，避免冲突
                import uuid
                content_hash = hashlib.md5(chunk.encode()).hexdigest()
                timestamp = str(int(time.time() * 1000000))
                unique_id = str(uuid.uuid4())[:8]
                doc_key = f"{KEY_PREFIX}{doc.get('problem_id', '')}_{content_hash}_{timestamp}_{unique_id}"
                
                doc_data = {
                    'problem_id': doc.get('problem_id', ''),
                    'problem_type': doc.get('problem_type', ''),
                    'file_name': doc.get('file_name', ''),
                    'file_path': doc.get('file_path', ''),
                    'content': chunk,
                    'chunk_index': i,
                    'total_chunks': len(chunks),
                    'solution': doc.get('solution', ''),
                    'source': doc.get('file_path', ''),
                    'created_time': doc.get('metadata', {}).get('modified_time', 0),
                    'embedding': embedding.tolist()
                }
                
                self.client.json().set(doc_key, '$', doc_data)
            
            return True
            
        except Exception as e:
            logger.error(f"添加文档失败: {str(e)}")
            return False
    
    def search(self, query: str, top_k: int = TOP_K_RESULTS) -> List[Dict]:
        """
        向量相似度搜索

        Args:
            query: 查询文本
            top_k: 返回结果数量

        Returns:
            搜索结果列表
        """
        try:
            # 检查是否支持Redis Stack搜索
            try:
                from redis.commands.search.query import Query
                from redis.commands.search import reducers
                return self._search_with_stack(query, top_k)
            except ImportError:
                logger.warning("Redis Stack搜索功能不可用，使用降级方案")
                return self._search_simple(query, top_k)

        except Exception as e:
            logger.error(f"搜索失败: {str(e)}")
            import traceback
            traceback.print_exc()
            return []

    def _search_with_stack(self, query: str, top_k: int) -> List[Dict]:
        """使用Redis Stack进行搜索"""
        try:
            from redis.commands.search.query import Query

            # 等待模型加载完成
            if hasattr(self.embedding_model, 'model_loaded'):
                import time
                max_wait = 30
                waited = 0
                while not self.embedding_model.model_loaded and waited < max_wait:
                    time.sleep(0.1)
                    waited += 0.1
                if not self.embedding_model.model_loaded:
                    logger.warning("模型加载超时，搜索结果可能不准确")

            query_embedding = self.embedding_model.encode_single(query)

            query_str = f"*=>[KNN {top_k} @embedding $query_vector AS score]"
            query_obj = Query(query_str) \
                .return_fields("problem_id", "problem_type", "file_name", "content",
                              "solution", "source", "score") \
                .sort_by("score") \
                .dialect(2)

            results = self.client.ft(INDEX_NAME).search(
                query_obj,
                query_params={"query_vector": query_embedding.tobytes()}
            )

            logger.info(f"搜索返回 {len(results.docs)} 条结果")
            documents = []
            for doc in results.docs:
                similarity = 1 - float(doc.score)
                logger.info(f"  文档 {doc.problem_id}: 相似度={similarity:.3f}, 阈值={SIMILARITY_THRESHOLD}")
                documents.append({
                    'problem_id': doc.problem_id,
                    'problem_type': doc.problem_type,
                    'file_name': doc.file_name,
                    'content': doc.content,
                    'solution': getattr(doc, 'solution', ''),
                    'source': doc.source,
                    'similarity': similarity,
                    'below_threshold': similarity < SIMILARITY_THRESHOLD
                })

            return documents

        except Exception as e:
            logger.error(f"Redis Stack搜索失败: {str(e)}")
            raise

    def _search_simple(self, query: str, top_k: int) -> List[Dict]:
        """简单的降级搜索方案"""
        try:
            logger.info("使用降级搜索方案")

            # 等待模型加载完成
            if hasattr(self.embedding_model, 'model_loaded'):
                import time
                max_wait = 30
                waited = 0
                while not self.embedding_model.model_loaded and waited < max_wait:
                    time.sleep(0.1)
                    waited += 0.1

            query_embedding = self.embedding_model.encode_single(query)

            # 获取所有文档（限制数量避免内存溢出）
            cursor = 0
            batch_size = 1000
            all_docs = []

            while True:
                cursor, keys = self.client.scan(cursor, match=f"{KEY_PREFIX}*", count=batch_size)

                for key in keys:
                    try:
                        doc_data = self.client.hgetall(key)
                        if doc_data:
                            # 从Redis获取向量（如果存在）
                            vector_key = f"{key}:vector"
                            vector_bytes = self.client.get(vector_key)

                            if vector_bytes:
                                # 计算相似度
                                doc_vector = np.frombuffer(vector_bytes, dtype=np.float32)
                                similarity = self._cosine_similarity(query_embedding, doc_vector)

                                if similarity >= SIMILARITY_THRESHOLD:
                                    # 构建文档信息
                                    doc_info = {}
                                    for k, v in doc_data.items():
                                        try:
                                            if isinstance(k, bytes):
                                                k = k.decode('utf-8')
                                            if isinstance(v, bytes):
                                                v = v.decode('utf-8')
                                            doc_info[k] = v
                                        except:
                                            continue

                                    doc_info['similarity'] = similarity
                                    all_docs.append(doc_info)
                            else:
                                # 如果没有向量，尝试重新生成
                                logger.warning(f"文档 {key} 没有向量数据")
                    except Exception as e:
                        logger.debug(f"处理文档 {key} 失败: {e}")
                        continue

                if cursor == 0:
                    break

            # 按相似度排序并返回前top_k个结果
            all_docs.sort(key=lambda x: x.get('similarity', 0), reverse=True)

            logger.info(f"降级搜索返回 {len(all_docs[:top_k])} 条结果")
            return all_docs[:top_k]

        except Exception as e:
            logger.error(f"降级搜索失败: {str(e)}")
            import traceback
            traceback.print_exc()
            return []

    def _cosine_similarity(self, a, b):
        """计算余弦相似度"""
        import numpy as np
        dot_product = np.dot(a, b)
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)

        if norm_a == 0 or norm_b == 0:
            return 0

        return dot_product / (norm_a * norm_b)
    
    def search_by_type(self, query: str, problem_type: str, top_k: int = TOP_K_RESULTS) -> List[Dict]:
        """
        按问题类型搜索
        
        Args:
            query: 查询文本
            problem_type: 问题类型
            top_k: 返回结果数量
            
        Returns:
            搜索结果列表
        """
        try:
            # 等待模型加载完成
            if hasattr(self.embedding_model, 'model_loaded'):
                import time
                max_wait = 30
                waited = 0
                while not self.embedding_model.model_loaded and waited < max_wait:
                    time.sleep(0.1)
                    waited += 0.1
                if not self.embedding_model.model_loaded:
                    logger.warning("模型加载超时，搜索结果可能不准确")
            
            query_embedding = self.embedding_model.encode_single(query)
            
            query_str = f"(@problem_type:{problem_type})=>[KNN {top_k} @embedding $query_vector AS score]"
            query_obj = Query(query_str) \
                .return_fields("problem_id", "problem_type", "file_name", "content", 
                              "solution", "source", "score") \
                .sort_by("score") \
                .dialect(2)
            
            results = self.client.ft(INDEX_NAME).search(
                query_obj, 
                query_params={"query_vector": query_embedding.tobytes()}
            )
            
            documents = []
            for doc in results.docs:
                similarity = 1 - float(doc.score)
                if similarity >= SIMILARITY_THRESHOLD:
                    documents.append({
                        'problem_id': doc.problem_id,
                        'problem_type': doc.problem_type,
                        'file_name': doc.file_name,
                        'content': doc.content,
                        'solution': getattr(doc, 'solution', ''),
                        'source': doc.source,
                        'similarity': similarity
                    })
            
            return documents
            
        except Exception as e:
            logger.error(f"按类型搜索失败: {str(e)}")
            return []
    
    def get_statistics(self) -> Dict:
        """获取知识库统计信息 - 使用缓存加速"""
        try:
            # 检查缓存
            cache_key = f"{KEY_PREFIX}stats_cache"
            cached = self.client.get(cache_key)
            if cached:
                import json
                return json.loads(cached)
            
            # 扫描文档键，获取实际数量
            doc_keys = list(self.client.scan_iter(match=f"{KEY_PREFIX}*"))
            valid_keys = [k for k in doc_keys if not k.endswith(b'filename_idx') and not k.endswith(b'_idx')]
            total_docs = len(valid_keys)
            
            # 实时统计问题归类 - 使用Pipeline批量获取
            type_distribution = {}
            
            # 批量获取problem_type
            pipe = self.client.pipeline()
            for key in valid_keys:
                pipe.json().get(key, '.problem_type')
            
            results = pipe.execute()
            
            for prob_type in results:
                if prob_type:
                    type_distribution[prob_type] = type_distribution.get(prob_type, 0) + 1
            
            # 只保存数量，不保存键列表
            stats = {
                'total_documents': total_docs,
                'type_distribution': type_distribution
            }
            
            # 缓存5分钟
            import json
            self.client.setex(cache_key, 300, json.dumps(stats))
            
            return stats
            
        except Exception as e:
            logger.error(f"获取统计信息失败: {str(e)}")
            return {'total_documents': 0, 'type_distribution': {}}
    
    def reconnect_redis(self):
        """重新连接Redis"""
        try:
            if self.client:
                self.client.close()
            
            self._connect()
            logger.info("Redis重连成功")
        except Exception as e:
            logger.error(f"Redis重连失败: {str(e)}")
            raise
    
    def find_document_by_filename(self, filename: str) -> List[Dict]:
        """
        按文件名或完整路径查找文档 - 使用索引加速
        
        Args:
            filename: 文件名或完整路径
            
        Returns:
            匹配的文档列表，包含文件路径和向量信息
        """
        # 优先使用索引
        if self.check_indexes():
            return self.find_by_filename_index(filename)
        
        # 回退到原来的扫描方式
        import os
        try:
            # 提取纯文件名（不含路径）
            base_filename = os.path.basename(filename).lower()
            # 完整路径（统一分隔符并转小写）
            full_path = filename.replace('\\', '/').lower()
            
            matched_docs = []
            
            # 扫描所有文档键
            doc_keys = list(self.client.scan_iter(match=f"{KEY_PREFIX}*", count=100))
            
            # 过滤掉非 JSON 的键（如 filename_idx、type_idx、stats_cache 等）
            valid_keys = [k for k in doc_keys if not k.endswith(b'filename_idx') and not k.endswith(b'type_idx') and not k.endswith(b'stats_cache') and not k.startswith(b'workorder_fp:')]
            
            # 使用Pipeline批量获取file_name（只获取文件名，不获取路径，避免路径不存在报错）
            pipe = self.client.pipeline()
            for key in valid_keys:
                pipe.json().get(key, '.file_name')
            
            file_names = pipe.execute()
            
            # 找到匹配的键（只基于文件名匹配）
            matched_keys = []
            
            # 检查是否是部分匹配（用户只输入了文件名的一部分）
            # 对于长文件名，也支持部分匹配
            search_patterns = [base_filename]
            if len(base_filename) > 10 and '-' in base_filename:
                parts = base_filename.split('-')
                for part in parts:
                    if len(part) >= 5:
                        search_patterns.append(part)
            
            for key, name in zip(valid_keys, file_names):
                if not name:
                    continue
                name_lower = name.lower()
                
                # 匹配条件：
                # 1. 文件名完全匹配
                if name_lower == base_filename:
                    matched_keys.append(key)
                # 2. 去掉扩展名的文件名匹配
                elif os.path.splitext(name_lower)[0] == os.path.splitext(base_filename)[0]:
                    matched_keys.append(key)
                # 3. 部分匹配（文件名包含搜索关键词）
                else:
                    for pattern in search_patterns:
                        if pattern in name_lower:
                            matched_keys.append(key)
                            break
            
            # 批量获取匹配的文档数据（包含file_path用于后续验证路径）
            if matched_keys:
                pipe = self.client.pipeline()
                for key in matched_keys:
                    pipe.json().get(key, '$')
                
                docs_data = pipe.execute()
                
                for doc in docs_data:
                    if isinstance(doc, list) and doc:
                        d = doc[0]
                        # 兼容两种存储方式：file_path 或 source
                        doc_file_path = d.get('file_path', '') or d.get('source', '')
                        path_lower = doc_file_path.replace('\\', '/').lower() if doc_file_path else ''
                        
                        # 如果用户提供了完整路径，需要验证路径是否匹配
                        # 如果路径不匹配但文件名匹配，仍然返回（因为用户可能只知道文件名）
                        matched_docs.append({
                            'file_name': d.get('file_name', ''),
                            'file_path': doc_file_path,
                            'problem_id': d.get('problem_id', ''),
                            'problem_type': d.get('problem_type', ''),
                            'content': d.get('content', ''),
                            'solution': d.get('solution', ''),
                            'chunk_index': d.get('chunk_index', 0),
                            'total_chunks': d.get('total_chunks', 1),
                            'embedding_length': 0,
                            'source': d.get('source', ''),
                            'created_time': d.get('created_time', 0)
                        })
            
            return matched_docs
            
        except Exception as e:
            logger.error(f"按文件名查找失败: {str(e)}")
            return []

    def build_indexes(self) -> bool:
        """建立索引以加速查询（百万级数据优化）"""
        try:
            logger.info("开始建立索引...")
            
            # 扫描所有文档键，排除索引键
            doc_keys = list(self.client.scan_iter(match=f"{KEY_PREFIX}*"))
            valid_keys = []
            for k in doc_keys:
                k_str = k.decode() if isinstance(k, bytes) else k
                if not k_str.endswith('_idx') and not k_str.endswith('_cache'):
                    valid_keys.append(k)
            
            logger.info(f"共有 {len(valid_keys)} 个文档需要建立索引")
            
            if not valid_keys:
                return True
            
            # 批量获取所有需要的字段
            pipe = self.client.pipeline()
            for key in valid_keys:
                pipe.json().get(key, '.file_name')
                pipe.json().get(key, '.problem_type')
            
            results = pipe.execute()
            
            # 建立索引
            filename_to_keys = {}  # 文件名 -> 文档键列表
            type_to_keys = {}     # 问题类型 -> 文档键列表
            
            for i, key in enumerate(valid_keys):
                file_name = results[i * 2]
                prob_type = results[i * 2 + 1]
                
                key_str = key.decode() if isinstance(key, bytes) else key
                
                if file_name:
                    fn_lower = file_name.lower()
                    if fn_lower not in filename_to_keys:
                        filename_to_keys[fn_lower] = []
                    filename_to_keys[fn_lower].append(key_str)
                    
                    # 去掉扩展名的索引
                    fn_base = fn_lower.rsplit('.', 1)[0] if '.' in fn_lower else fn_lower
                    if fn_base not in filename_to_keys:
                        filename_to_keys[fn_base] = []
                    filename_to_keys[fn_base].append(key_str)
                
                if prob_type:
                    if prob_type not in type_to_keys:
                        type_to_keys[prob_type] = []
                    type_to_keys[prob_type].append(key_str)
            
            # 保存文件名索引（使用Hash结构）
            filename_idx_key = f"{KEY_PREFIX}filename_idx"
            pipe = self.client.pipeline()
            pipe.delete(filename_idx_key)
            if filename_to_keys:
                for fn, keys in filename_to_keys.items():
                    pipe.hset(filename_idx_key, fn, json.dumps(keys))
            pipe.execute()
            
            # 保存类型索引
            type_idx_key = f"{KEY_PREFIX}type_idx"
            pipe = self.client.pipeline()
            pipe.delete(type_idx_key)
            if type_to_keys:
                for pt, keys in type_to_keys.items():
                    pipe.hset(type_idx_key, pt, json.dumps(keys))
            pipe.execute()
            
            # 更新统计信息缓存
            self._update_stats_cache(len(valid_keys), type_to_keys)
            
            logger.info(f"索引建立完成: 文件名索引 {len(filename_to_keys)} 条, 类型索引 {len(type_to_keys)} 条")
            return True
            
        except Exception as e:
            logger.error(f"建立索引失败: {str(e)}")
            return False
    
    def _update_stats_cache(self, total_docs: int, type_distribution: dict = None):
        """更新统计缓存"""
        try:
            if type_distribution is None:
                type_distribution = {}
            
            cache_key = f"{KEY_PREFIX}stats_cache"
            stats = {
                'total_documents': total_docs,
                'type_distribution': type_distribution
            }
            self.client.setex(cache_key, 300, json.dumps(stats))
        except Exception as e:
            logger.warning(f"更新缓存失败: {str(e)}")
    
    def find_by_filename_index(self, filename: str) -> List[Dict]:
        """使用索引快速查找文件"""
        import os
        try:
            base_filename = os.path.basename(filename).lower()
            fn_without_ext = base_filename.rsplit('.', 1)[0] if '.' in base_filename else base_filename
            
            # 从索引中查找
            filename_idx_key = f"{KEY_PREFIX}filename_idx"
            
            matched_keys = []
            
            # 先尝试精确匹配
            for key in self.client.hscan_iter(filename_idx_key, match=base_filename):
                key_name = key[0]
                key_val = key[1]
                if isinstance(key_name, bytes):
                    key_name = key_name.decode('utf-8')
                if isinstance(key_val, bytes):
                    key_val = key_val.decode('utf-8')
                if key_name == base_filename:
                    matched_keys.extend(json.loads(key_val))
                    break
            
            # 尝试无扩展名匹配
            if not matched_keys:
                for key in self.client.hscan_iter(filename_idx_key, match=fn_without_ext):
                    key_name = key[0]
                    key_val = key[1]
                    if isinstance(key_name, bytes):
                        key_name = key_name.decode('utf-8')
                    if isinstance(key_val, bytes):
                        key_val = key_val.decode('utf-8')
                    if key_name == fn_without_ext:
                        matched_keys.extend(json.loads(key_val))
                        break
            
            # 部分匹配（支持长文件名）
            if not matched_keys:
                # 对于长文件名，尝试匹配文件名的一部分
                search_patterns = [base_filename]
                
                # 如果文件名较长，尝试匹配关键部分
                if len(base_filename) > 10:
                    # 尝试匹配文件名的前半部分
                    if '-' in base_filename:
                        parts = base_filename.split('-')
                        for part in parts:
                            if len(part) >= 5:  # 只匹配较长的部分
                                search_patterns.append(part)
                
                for pattern in search_patterns:
                    for key in self.client.hscan_iter(filename_idx_key, match=f"*{pattern}*"):
                        key_name = key[0]
                        key_val = key[1]
                        if isinstance(key_name, bytes):
                            key_name = key_name.decode('utf-8')
                        if isinstance(key_val, bytes):
                            key_val = key_val.decode('utf-8')
                        if pattern in key_name:
                            matched_keys.extend(json.loads(key_val))
                            if len(matched_keys) >= 50:
                                break
                    if matched_keys:
                        break
            
            if not matched_keys:
                return []
            
            # 去重
            matched_keys = list(set(matched_keys))
            
            # 批量获取文档数据
            pipe = self.client.pipeline()
            for key in matched_keys:
                if isinstance(key, str):
                    key = key.encode()
                pipe.json().get(key, '$')
            
            docs_data = pipe.execute()
            
            matched_docs = []
            for doc in docs_data:
                if isinstance(doc, list) and doc:
                    d = doc[0]
                    # 兼容两种存储方式：file_path 或 source
                    doc_file_path = d.get('file_path', '') or d.get('source', '')
                    matched_docs.append({
                        'file_name': d.get('file_name', ''),
                        'file_path': doc_file_path,
                        'problem_id': d.get('problem_id', ''),
                        'problem_type': d.get('problem_type', ''),
                        'content': d.get('content', ''),
                        'solution': d.get('solution', ''),
                        'chunk_index': d.get('chunk_index', 0),
                        'total_chunks': d.get('total_chunks', 1),
                        'embedding_length': 0,
                        'source': d.get('source', ''),
                        'created_time': d.get('created_time', 0)
                    })
            
            return matched_docs
            
        except Exception as e:
            logger.error(f"索引查找失败: {str(e)}")
            return []
    
    def check_indexes(self) -> bool:
        """检查索引是否存在"""
        filename_idx_key = f"{KEY_PREFIX}filename_idx"
        return self.client.exists(filename_idx_key)

    def _ensure_content_index(self) -> bool:
        """确保内容全文索引存在（基于RediSearch，无需额外依赖）"""
        idx_name = f"{INDEX_NAME}_content"
        try:
            self.client.execute_command('FT.INFO', idx_name)
            return True
        except Exception:
            pass

        try:
            self.client.execute_command(
                'FT.CREATE', idx_name,
                'ON', 'JSON', 'PREFIX', '1', KEY_PREFIX,
                'SCHEMA',
                '$.content', 'AS', 'content', 'TEXT',
                '$.solution', 'AS', 'solution', 'TEXT',
                '$.file_name', 'AS', 'file_name', 'TEXT'
            )
            logger.info(f"全文内容索引 {idx_name} 创建成功，等待索引构建...")

            # 等待索引构建完成（最多10秒）
            for _ in range(20):
                time.sleep(0.5)
                try:
                    info = self.client.execute_command('FT.INFO', idx_name)
                    for i in range(0, len(info), 2):
                        if info[i] == b'percent_indexed':
                            percent = float(info[i + 1])
                            if percent >= 1.0:
                                logger.info(f"全文索引构建完成，已索引全部文档")
                                return True
                            break
                except Exception:
                    pass

            logger.warning("全文索引构建超时，可能部分文档未索引")
            return True
        except Exception as e:
            logger.warning(f"创建全文内容索引失败: {e}")
            return False

    def find_by_content(self, keywords: List[str]) -> List[Dict]:
        """
        按内容关键字精确查找文档（使用RediSearch全文索引加速）

        Args:
            keywords: 关键字列表，多个关键字都需要匹配

        Returns:
            匹配的文档列表
        """
        try:
            logger.info(f"开始按内容查找，关键字: {keywords}")

            if not keywords:
                return []

            keywords_lower = list(set([kw.lower() for kw in keywords if kw]))
            if not keywords_lower:
                return []

            # 直接使用扫描方法进行关键词匹配
            # 跳过 FT.SEARCH：通配符 *keyword* 对中文分词不准确，且前导通配符导致超时
            return self._find_by_content_scan(keywords_lower)

        except Exception as e:
            logger.error(f"按内容查找失败: {str(e)}")
            return []

    def _find_by_content_scan(self, keywords_lower: List[str]) -> List[Dict]:
        """按关键词查找文档：优先 Lua 服务端匹配，fallback 到 Python 扫描"""
        try:
            result = self._find_by_content_lua(keywords_lower)
            if result is not None:
                return result
        except Exception as e:
            logger.warning(f"Lua脚本匹配失败，回退到Python扫描: {e}")

        return self._find_by_content_python_scan(keywords_lower)

    def _find_by_content_lua(self, keywords_lower: List[str]) -> List[Dict]:
        """Lua 脚本在 Redis 服务端匹配关键词，只返回匹配文档的完整数据"""
        script = self.client.register_script(_LUA_CONTENT_SEARCH)
        kw_str = ','.join(keywords_lower)
        matched_keys = script(args=[f"{KEY_PREFIX}*", kw_str])

        if not matched_keys:
            logger.info("Lua内容查找完成，未找到匹配文档")
            return []

        # 只对匹配的 key 获取完整数据
        field_paths = [
            '$.file_name', '$.file_path', '$.problem_id', '$.problem_type',
            '$.content', '$.solution', '$.chunk_index', '$.total_chunks',
            '$.source', '$.created_time'
        ]
        pipe = self.client.pipeline()
        for key in matched_keys:
            pipe.json().get(key, *field_paths)
        docs_data = pipe.execute()

        matched_docs = []
        for doc_data in docs_data:
            if not isinstance(doc_data, dict):
                continue
            d = {}
            for path, value in doc_data.items():
                field = path.replace('$.', '')
                if isinstance(value, list) and value:
                    d[field] = value[0]
                else:
                    d[field] = value if value else ''

            matched_docs.append({
                'file_name': d.get('file_name', ''),
                'file_path': d.get('file_path', ''),
                'problem_id': d.get('problem_id', ''),
                'problem_type': d.get('problem_type', ''),
                'content': d.get('content', ''),
                'solution': d.get('solution', ''),
                'chunk_index': d.get('chunk_index', 0),
                'total_chunks': d.get('total_chunks', 1),
                'embedding_length': 0,
                'source': d.get('source', ''),
                'created_time': d.get('created_time', 0)
            })

        logger.info(f"Lua内容查找完成，找到 {len(matched_docs)} 个匹配的文档")
        return matched_docs

    def _find_by_content_python_scan(self, keywords_lower: List[str]) -> List[Dict]:
        """Python 端扫描 fallback"""
        batch_size = 50
        matched_docs = []
        processed_count = 0
        cursor = '0'

        field_paths = [
            '$.file_name', '$.file_path', '$.problem_id', '$.problem_type',
            '$.content', '$.solution', '$.chunk_index', '$.total_chunks',
            '$.source', '$.created_time'
        ]

        while cursor != 0:
            cursor, doc_keys = self.client.scan(
                cursor=cursor,
                match=f"{KEY_PREFIX}*",
                count=batch_size * 2
            )

            valid_keys = []
            for k in doc_keys:
                k_str = k.decode() if isinstance(k, bytes) else k
                if not k_str.endswith('_idx') and not k_str.endswith('_cache') and not k_str.startswith('workorder_fp:'):
                    valid_keys.append(k)

            if not valid_keys:
                continue

            for i in range(0, len(valid_keys), batch_size):
                batch_keys = valid_keys[i:i + batch_size]
                pipe = self.client.pipeline()
                for key in batch_keys:
                    pipe.json().get(key, *field_paths)
                results = pipe.execute()
                processed_count += len(results)

                for doc_data in results:
                    if not isinstance(doc_data, dict):
                        continue
                    d = {}
                    for path, value in doc_data.items():
                        field = path.replace('$.', '')
                        if isinstance(value, list) and value:
                            d[field] = value[0]
                        else:
                            d[field] = value if value else ''

                    content_fields = [
                        str(d.get('content', '')),
                        str(d.get('solution', '')),
                        str(d.get('file_name', ''))
                    ]
                    all_match = True
                    for keyword in keywords_lower:
                        if not any(keyword in f.lower() for f in content_fields):
                            all_match = False
                            break
                    if all_match:
                        matched_docs.append({
                            'file_name': d.get('file_name', ''),
                            'file_path': d.get('file_path', ''),
                            'problem_id': d.get('problem_id', ''),
                            'problem_type': d.get('problem_type', ''),
                            'content': d.get('content', ''),
                            'solution': d.get('solution', ''),
                            'chunk_index': d.get('chunk_index', 0),
                            'total_chunks': d.get('total_chunks', 1),
                            'embedding_length': 0,
                            'source': d.get('source', ''),
                            'created_time': d.get('created_time', 0)
                        })

                if len(matched_docs) >= 1000:
                    return matched_docs[:1000]

        logger.info(f"Python扫描查找完成，共处理 {processed_count} 个文档，找到 {len(matched_docs)} 个匹配的文档")
        return matched_docs

    def find_by_regex(self, pattern: str, search_fields: List[str] = None, 
                      flags: str = 'i') -> List[Dict]:
        """
        使用正则表达式搜索文档
        
        Args:
            pattern: 正则表达式模式
            search_fields: 要搜索的字段列表，如 ['content', 'solution', 'file_name']
            flags: 正则标志，如 'i' (忽略大小写), 'm' (多行), 's' (点号匹配所有)
            
        Returns:
            匹配的文档列表
        """
        import re
        
        try:
            logger.info(f"开始正则搜索，模式：{pattern}, 字段：{search_fields}, 标志：{flags}")
            
            # 编译正则表达式
            regex_flags = 0
            if 'i' in flags.lower():
                regex_flags |= re.IGNORECASE
            if 'm' in flags.lower():
                regex_flags |= re.MULTILINE
            if 's' in flags.lower():
                regex_flags |= re.DOTALL
            
            compiled_pattern = re.compile(pattern, regex_flags)
            
            # 默认搜索字段
            if search_fields is None or not search_fields:
                search_fields = ['content', 'solution']
            
            # 扫描所有文档
            doc_keys = list(self.client.scan_iter(match=f"{KEY_PREFIX}*", count=100))
            valid_keys = [
                k for k in doc_keys 
                if not k.decode().endswith('_idx') 
                and not k.decode().endswith('_cache')
                and not k.decode().startswith('workorder_fp:')
                and not k.decode().endswith('stats_cache')
            ]
            
            logger.info(f"找到 {len(valid_keys)} 个有效文档")
            
            if not valid_keys:
                return []
            
            # 批量获取文档内容
            pipe = self.client.pipeline()
            for key in valid_keys:
                pipe.json().get(key, '$')
            
            results = pipe.execute()
            logger.info(f"批量获取完成，共 {len(results)} 个结果")
            
            matched_docs = []
            for i, doc in enumerate(results):
                if not doc or not isinstance(doc, list) or not doc:
                    continue
                
                d = doc[0]
                
                # 检查指定字段是否匹配正则
                is_match = False
                matched_field = None
                for field in search_fields:
                    field_value = d.get(field, '')
                    if field_value and compiled_pattern.search(str(field_value)):
                        is_match = True
                        matched_field = field
                        break
                
                if is_match:
                    matched_docs.append({
                        'file_name': d.get('file_name', ''),
                        'file_path': d.get('file_path', ''),
                        'problem_id': d.get('problem_id', ''),
                        'problem_type': d.get('problem_type', ''),
                        'content': d.get('content', ''),
                        'solution': d.get('solution', ''),
                        'chunk_index': d.get('chunk_index', 0),
                        'total_chunks': d.get('total_chunks', 1),
                        'embedding_length': 0,
                        'source': d.get('source', ''),
                        'created_time': d.get('created_time', 0),
                        'matched_field': matched_field
                    })
            
            logger.info(f"正则搜索完成，找到 {len(matched_docs)} 个匹配的文档")
            return matched_docs
            
        except re.error as e:
            logger.error(f"正则表达式错误：{str(e)}")
            raise ValueError(f"无效的正则表达式：{str(e)}")
        except Exception as e:
            logger.error(f"正则搜索失败：{str(e)}")
            return []

    def clear_all(self):
        """清空知识库"""
        try:
            # 清空文档
            doc_keys = list(self.client.scan_iter(match=f"{KEY_PREFIX}*"))
            if doc_keys:
                self.client.delete(*doc_keys)

            # 清空文件指纹
            fp_keys = list(self.client.scan_iter(match=f"{FILE_FINGERPRINT_PREFIX}*"))
            if fp_keys:
                self.client.delete(*fp_keys)

            # 删除全文内容索引（下次查询时自动重建）
            content_idx_name = f"{INDEX_NAME}_content"
            try:
                self.client.execute_command('FT.DROPINDEX', content_idx_name)
            except Exception:
                pass

            logger.info("已清空知识库和文件指纹")
        except Exception as e:
            logger.error(f"清空知识库失败: {str(e)}")

    # Lua 脚本：按 source 字段删除文档（避免将全量数据传到 Python 端）
    _LUA_DELETE_BY_SOURCE = """
local prefix = ARGV[1]
local target_source = ARGV[2]
local deleted = 0
local cursor = '0'
repeat
    local reply = redis.call('SCAN', cursor, 'MATCH', prefix .. '*', 'COUNT', 500)
    cursor = reply[1]
    for _, key in ipairs(reply[2]) do
        local src = redis.call('JSON.GET', key, '$.source')
        if src then
            -- JSON.GET 返回 JSON 数组字符串，如 ["path"]
            local decoded = cjson.decode(src)
            if decoded and decoded[1] and decoded[1] == target_source then
                redis.call('DEL', key)
                deleted = deleted + 1
            end
        end
    end
until cursor == '0'
return deleted
"""

    def delete_by_file_path(self, file_path: str) -> int:
        """按文件路径删除相关文档

        Args:
            file_path: 文件路径（匹配文档的 source 字段）

        Returns:
            删除的文档数量
        """
        try:
            deleted = self.client.eval(
                self._LUA_DELETE_BY_SOURCE, 0,
                KEY_PREFIX, file_path
            )
            # 同时清理该文件的指纹
            fp_pattern = f"{FILE_FINGERPRINT_PREFIX}*"
            fp_keys = list(self.client.scan_iter(match=fp_pattern, count=200))
            for fp_key in fp_keys:
                fp_val = self.client.get(fp_key)
                if fp_val:
                    fp_str = fp_val.decode() if isinstance(fp_val, bytes) else fp_val
                    # 指纹键中包含路径信息，尝试匹配
                    if file_path in fp_str:
                        self.client.delete(fp_key)

            logger.info(f"按路径删除文档: {file_path}, 删除 {deleted} 条")
            return deleted if isinstance(deleted, int) else int(deleted)
        except Exception as e:
            logger.error(f"按路径删除文档失败: {str(e)}")
            return 0
    
    def close(self):
        """关闭连接"""
        if self.client:
            self.client.close()
            logger.info("已关闭Redis连接")
    
    def _generate_fingerprint(self, file_path: str, content: str) -> str:
        """生成文件指纹（路径+文件名+修改时间）"""
        import hashlib
        
        # 获取文件修改时间
        try:
            mtime = os.path.getmtime(file_path)
            mtime_str = str(int(mtime))
        except:
            mtime_str = "0"
        
        # 组合路径、文件名和修改时间
        file_name = os.path.basename(file_path)
        combined_str = f"{file_path}|{file_name}|{mtime_str}"
        
        # 生成MD5
        return hashlib.md5(combined_str.encode()).hexdigest()
    
    def _is_file_changed(self, file_path: str, content: str) -> bool:
        """检查文件是否已修改"""
        import os
        import hashlib
        
        try:
            # 获取当前指纹
            current_fp = self._generate_fingerprint(file_path, content)
            
            # 生成指纹key（使用文件路径+文件名+修改时间的MD5）
            file_name = os.path.basename(file_path)
            try:
                mtime = os.path.getmtime(file_path)
                mtime_str = str(int(mtime))
            except:
                mtime_str = "0"
            key_str = f"{file_path}|{file_name}|{mtime_str}"
            key_hash = hashlib.md5(key_str.encode()).hexdigest()
            fp_key = f"{FILE_FINGERPRINT_PREFIX}{key_hash}"
            
            stored_fp = self.client.get(fp_key)
            
            if stored_fp:
                # 文件已存在，比较指纹
                if stored_fp.decode() == current_fp:
                    return False  # 文件未修改
                else:
                    return True  # 文件已修改
            else:
                return True  # 新文件
        except Exception as e:
            logger.debug(f"检查文件变更失败: {e}")
            return True  # 出错时默认认为已修改
    
    def _update_file_fingerprint(self, file_path: str, content: str):
        """更新文件指纹（30天后自动过期，不管访问未访问）"""
        try:
            fp = self._generate_fingerprint(file_path, content)
            # 生成指纹key（使用文件路径+文件名+修改时间的MD5）
            file_name = os.path.basename(file_path)
            try:
                mtime = os.path.getmtime(file_path)
                mtime_str = str(int(mtime))
            except:
                mtime_str = "0"
            key_str = f"{file_path}|{file_name}|{mtime_str}"
            key_hash = hashlib.md5(key_str.encode()).hexdigest()
            fp_key = f"{FILE_FINGERPRINT_PREFIX}{key_hash}"
            # 设置指纹，30天后过期
            self.client.setex(fp_key, FINGERPRINT_EXPIRE_DAYS * 86400, fp)
            logger.debug(f"更新文件指纹: {file_path}")
        except Exception as e:
            logger.debug(f"更新文件指纹失败: {e}")
    
    def add_documents(self, documents: List[Dict]) -> int:
        """添加文档到知识库（支持增量更新）"""
        success_count = 0
        
        for doc in documents:
            file_path = doc.get('file_path', '')
            file_name = doc.get('file_name', '')
            content = doc.get('content', '')
            
            # 确保文件名使用UTF-8编码
            try:
                if isinstance(file_name, bytes):
                    file_name = file_name.decode('utf-8', errors='replace')
                if isinstance(file_path, bytes):
                    file_path = file_path.decode('utf-8', errors='replace')
            except:
                pass
            
            # 检查文件是否已修改
            is_changed = self._is_file_changed(file_path, content)
            logger.info(f"处理文件: {file_name}, 已修改: {is_changed}")
            
            if not is_changed:
                logger.info(f"文件未修改，跳过: {file_name}")
                continue
            
            # 生成向量
            embedding = self.embedding_model.encode_single(content)
            
            # 生成唯一key（使用文件路径+文件名+修改时间的MD5）
            import os
            file_name = os.path.basename(file_path)
            try:
                mtime = os.path.getmtime(file_path)
                mtime_str = str(int(mtime))
            except:
                mtime_str = "0"
            doc_key_str = f"{file_path}|{file_name}|{mtime_str}"
            doc_key_hash = hashlib.md5(doc_key_str.encode()).hexdigest()
            doc_key = f"{KEY_PREFIX}{doc_key_hash}"
            
            # 构建文档数据（embedding转换为列表）
            doc_data = {
                'problem_id': doc.get('problem_id', ''),
                'problem_type': doc.get('problem_type', ''),
                'file_name': file_name,
                'content': content[:MAX_CONTENT_LENGTH],
                'solution': doc.get('solution', ''),
                'source': file_path,
                'created_time': time.time(),
                'embedding': embedding.tolist()  # 转换为列表
            }
            
            # 存储到Redis
            try:
                self.client.json().set(doc_key, "$", doc_data)
                success_count += 1
                logger.info(f"成功存储文档: {file_name}, 当前计数: {success_count}")
                
                # 更新文件指纹
                self._update_file_fingerprint(file_path, content)
                logger.info(f"更新文件指纹: {file_name}")
                
            except Exception as e:
                logger.error(f"存储文档失败 {file_name}: {str(e)}")
                import traceback
                traceback.print_exc()
        
        logger.info(f"add_documents完成，成功存储 {success_count} 个文档")
        return success_count


if __name__ == "__main__":
    store = RedisVectorStore()
    
    stats = store.get_statistics()
    print(f"知识库统计: {stats}")
    
    test_query = "开户报错"
    results = store.search(test_query)
    print(f"搜索 '{test_query}' 结果: {len(results)} 条")
