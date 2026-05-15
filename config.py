# -*- coding: utf-8 -*-
"""
沃工单知识库系统配置文件
"""

import os
import configparser

config = configparser.ConfigParser()
config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.ini')
config.read(config_path, encoding='utf-8')

REDIS_CONFIG = {
    "host": config.get('redis', 'host', fallback='127.0.0.1'),
    "password": config.get('redis', 'password', fallback=''),
    "port": config.getint('redis', 'port', fallback=6379),
    "db": config.getint('redis', 'db', fallback=0)
}

LOCAL_MODEL_PATH = config.get('model', 'local_model_path', fallback=r'D:\models\text2vec-base-chinese')
VECTOR_DIMENSION = config.getint('model', 'vector_dimension', fallback=768)
# 向量模型提供商：local(本地模型) 或 zhipu(智谱 AI)
VECTOR_MODEL_PROVIDER = config.get('model', 'vector_model_provider', fallback='local')

ZHIPU_CONFIG = {
    "api_key": config.get('zhipu', 'api_key', fallback=''),
    "api_base": config.get('zhipu', 'api_base', fallback='https://open.bigmodel.cn/api/paas/v4'),
    "model": config.get('zhipu', 'model', fallback='glm-4'),
    "embedding_model": config.get('zhipu', 'embedding_model', fallback='embedding-2'),
    "max_tokens": config.getint('zhipu', 'max_tokens', fallback=2000),
    "temperature": config.getfloat('zhipu', 'temperature', fallback=0.7)
}

LOCAL_MODEL_CONFIG = {
    "api_base": config.get('local_model', 'api_base', fallback='http://192.168.1.189:11434/api/chat'),
    "model": config.get('local_model', 'model', fallback='deepseek-r1:1.5b'),
    "temperature": config.getfloat('local_model', 'temperature', fallback=0.7)
}

DEFAULT_MODEL_PROVIDER = config.get('model', 'default_provider', fallback='zhipu')

DATA_DIR = config.get('data', 'data_dir', fallback=r"D:\工作文档\cbss2.0体验版\沃工单问题定位")
CHUNK_SIZE = config.getint('data', 'chunk_size', fallback=500)
CHUNK_OVERLAP = config.getint('data', 'chunk_overlap', fallback=50)
MAX_CONTENT_LENGTH = config.getint('data', 'max_content_length', fallback=10000)

SIMILARITY_THRESHOLD = config.getfloat('search', 'similarity_threshold', fallback=0.7)
TOP_K_RESULTS = config.getint('search', 'top_k_results', fallback=5)

# 认证配置
AUTH_CONFIG = {
    "username": config.get('auth', 'username', fallback=''),
    "password": config.get('auth', 'password', fallback='')
}

INDEX_NAME = "workorder_knowledge_idx"
KEY_PREFIX = "workorder:"
FILE_FINGERPRINT_PREFIX = "workorder_fp:"  # 文件指纹前缀
FINGERPRINT_EXPIRE_DAYS = 30  # 指纹过期天数

# 支持的文件扩展名
SUPPORTED_EXTENSIONS = [
    # 文本文件
    '.txt', '.md', '.markdown',
    # Word文档
    '.doc', '.docx',
    # Excel表格
    '.xlsx', '.xls', '.csv',
    # PDF文档
    '.pdf',
    # 图片文件
    '.png', '.jpg', '.jpeg', '.bmp', '.tiff', '.gif',
    # 网页/XML
    '.html', '.htm', '.xml',
    # SQL文件
    '.sql',
    # 数据文件
    '.json',
    # 压缩包
    '.zip',
    # 演示文稿
    '.pptx',
    # 思维导图
    '.xmind'
]


def update_config(section: str, key: str, value: str):
    """更新配置文件"""
    config.set(section, key, value)
    with open(config_path, 'w', encoding='utf-8') as f:
        config.write(f)


def get_config(section: str, key: str, fallback: str = '') -> str:
    """获取配置项"""
    return config.get(section, key, fallback=fallback)

def validate_config():
    """验证配置完整性"""
    import logging
    logger = logging.getLogger(__name__)

    required_sections = ['redis', 'model', 'data']
    required_redis_keys = ['host', 'port', 'password']
    required_model_keys = ['vector_dimension']

    for section in required_sections:
        if not config.has_section(section):
            raise ValueError(f"缺少配置节: {section}")

    # 验证Redis配置
    for key in required_redis_keys:
        if not config.get('redis', key, fallback=''):
            raise ValueError(f"缺少Redis配置: {key}")

    # 验证模型配置
    for key in required_model_keys:
        if not config.get('model', key, fallback=''):
            raise ValueError(f"缺少模型配置: {key}")

    # 验证数据目录
    data_dir = config.get('data', 'data_dir', fallback='')
    if data_dir and not os.path.exists(data_dir):
        logger.warning(f"数据目录不存在: {data_dir}")

    logger.info("配置验证通过")

    # 验证Redis配置
    for key in required_redis_keys:
        if not config.get('redis', key, fallback=''):
            raise ValueError(f"缺少Redis配置: {key}")

    # 验证模型配置
    for key in required_model_keys:
        if not config.get('model', key, fallback=''):
            raise ValueError(f"缺少模型配置: {key}")

    # 验证数据目录
    data_dir = config.get('data', 'data_dir', fallback='')
    if data_dir and not os.path.exists(data_dir):
        logger.warning(f"数据目录不存在: {data_dir}")

    logger.info("配置验证通过")
__all__ = ["config", "update_config", "get_config", "validate_config"]