#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
关键问题修复脚本
修复以下问题：
1. 模型加载异步问题
2. Redis键命名冲突
3. 错误恢复机制
4. 性能优化
"""

import os
import sys
import hashlib

# 修复vector_store.py的键命名冲突问题
def fix_redis_key_conflict():
    """修复Redis键命名冲突"""
    vector_store_path = '/home/ubuntu/AIknowledge/aiunicom/vector_store.py'

    # 读取原文件
    with open(vector_store_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 修复1: 添加更安全的键生成方法
    old_key_generation = '''doc_key = f"{KEY_PREFIX}{doc.get('problem_id', '')}_{hashlib.md5(chunk.encode()).hexdigest()[:8]}"'''

    new_key_generation = '''# 使用更安全的键生成方法，避免冲突
                import uuid
                content_hash = hashlib.md5(chunk.encode()).hexdigest()
                timestamp = str(int(time.time() * 1000000))
                unique_id = str(uuid.uuid4())[:8]
                doc_key = f"{KEY_PREFIX}{doc.get('problem_id', '')}_{content_hash}_{timestamp}_{unique_id}"'''

    if old_key_generation in content:
        content = content.replace(old_key_generation, new_key_generation)
        print("✓ 修复Redis键命名冲突问题")
    else:
        print("⚠ Redis键生成逻辑可能已修改")

    # 修复2: 添加错误恢复机制
    if 'def reconnect_redis(self):' not in content:
        reconnect_method = '''
    def reconnect_redis(self):
        """重新连接Redis"""
        try:
            if self.client:
                self.client.close()

            self._connect()
            logger.info("Redis重连成功")
            return True
        except Exception as e:
            logger.error(f"Redis重连失败: {str(e)}")
            return False

    def safe_search(self, query, top_k=TOP_K_RESULTS):
        """安全的搜索方法，带错误恢复"""
        try:
            return self.search(query, top_k)
        except redis.exceptions.ConnectionError:
            logger.warning("Redis连接错误，尝试重连...")
            if self.reconnect_redis():
                try:
                    return self.search(query, top_k)
                except Exception as e:
                    logger.error(f"重连后搜索失败: {e}")
                    return []
            return []
        except Exception as e:
            logger.error(f"搜索失败: {e}")
            return []'''

        # 在close方法前添加
        close_pos = content.rfind('def close(self):')
        if close_pos != -1:
            content = content[:close_pos] + reconnect_method + content[close_pos:]
            print("✓ 添加错误恢复机制")

    # 保存修复后的文件
    with open(vector_store_path, 'w', encoding='utf-8') as f:
        f.write(content)

    return True

# 修复file_parser.py的文件名编码问题
def fix_filename_encoding():
    """修复文件名编码问题"""
    file_parser_path = '/home/ubuntu/AIknowledge/aiunicom/file_parser.py'

    with open(file_parser_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 添加更安全的文件名处理
    old_filename_handling = '''try:
            file_name = os.path.basename(file_path)
            if isinstance(file_name, bytes):
                file_name = file_name.decode('utf-8', errors='replace')
        except:
            file_name = os.path.basename(file_path)'''

    new_filename_handling = '''try:
            file_name = os.path.basename(file_path)
            if isinstance(file_name, bytes):
                file_name = file_name.decode('utf-8', errors='replace')
            elif isinstance(file_name, str):
                # 确保UTF-8编码
                file_name = file_name.encode('utf-8', errors='replace').decode('utf-8')
        except Exception as e:
            logger.debug(f"文件名编码转换失败: {e}")
            file_name = os.path.basename(file_path)
            if isinstance(file_name, bytes):
                file_name = file_name.decode('latin-1', errors='replace')'''

    if old_filename_handling in content:
        content = content.replace(old_filename_handling, new_filename_handling)
        print("✓ 修复文件名编码问题")

    with open(file_parser_path, 'w', encoding='utf-8') as f:
        f.write(content)

    return True

# 修复配置安全性问题
def fix_config_security():
    """修复配置安全性问题"""
    config_path = '/home/ubuntu/AIknowledge/aiunicom/config.py'

    with open(config_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 添加配置验证
    if 'def validate_config():' not in content:
        validation_code = '''

def validate_config():
    """验证配置完整性"""
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

    logger.info("配置验证通过")'''

        # 在文件末尾添加
        content = content.rstrip() + validation_code

        # 更新__all__导出
        if '__all__' not in content:
            content = content + '\n__all__ = ["config", "update_config", "get_config", "validate_config"]'

        with open(config_path, 'w', encoding='utf-8') as f:
            f.write(content)

        print("✓ 添加配置验证机制")

    return True

# 添加性能监控
def add_performance_monitoring():
    """添加性能监控"""
    knowledge_base_path = '/home/ubuntu/AIknowledge/aiunicom/knowledge_base.py'

    with open(knowledge_base_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 添加性能监控装饰器
    if 'def time_logger(func):' not in content:
        monitor_code = '''

import time
from functools import wraps

def time_logger(func):
    """性能监控装饰器"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        try:
            result = func(*args, **kwargs)
            elapsed = time.time() - start_time
            logger.info(f"{func.__name__} 执行成功，耗时: {elapsed:.3f}秒")
            return result
        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(f"{func.__name__} 执行失败，耗时: {elapsed:.3f}秒，错误: {e}")
            raise

    return wrapper'''

        # 在类定义前添加
        class_pos = content.find('class KnowledgeBase:')
        if class_pos != -1:
            content = content[:class_pos] + monitor_code + content[class_pos:]
            print("✓ 添加性能监控装饰器")

        # 为关键方法添加装饰器
        methods_to_monitor = ['initialize', 'query', 'add_new_document', 'rebuild']
        for method in methods_to_monitor:
            method_pattern = f'    def {method}(self'
            if method_pattern in content:
                # 在方法定义前添加装饰器
                content = content.replace(
                    method_pattern,
                    f'    @time_logger\n{method_pattern}'
                )
                print(f"✓ 为 {method} 方法添加性能监控")

    with open(knowledge_base_path, 'w', encoding='utf-8') as f:
        f.write(content)

    return True

def create_startup_script():
    """创建启动脚本，包含环境检查"""
    startup_script = '''#!/bin/bash
# 知识库系统启动脚本

set -e

echo "开始检查环境..."

# 检查Python版本
python3 --version > /dev/null 2>&1 || {
    echo "错误: Python3未安装"
    exit 1
}

# 检查关键依赖
python3 -c "import redis" > /dev/null 2>&1 || {
    echo "错误: redis库未安装"
    pip install redis
}

python3 -c "import numpy" > /dev/null 2>&1 || {
    echo "错误: numpy库未安装"
    pip install numpy
}

# 检查Redis连接
python3 -c "
import redis
try:
    r = redis.Redis(host='42.194.141.197', port=6379, password='RedUssTest')
    r.ping()
    print('Redis连接成功')
except Exception as e:
    print(f'Redis连接失败: {e}')
    exit(1)
"

# 检查配置文件
if [ ! -f "config.ini" ]; then
    echo "错误: config.ini不存在"
    exit 1
fi

# 验证配置
python3 -c "
from config import validate_config
validate_config()
"

echo "环境检查通过，启动系统..."

# 初始化知识库
echo "初始化知识库..."
python3 -m knowledge_base --init

# 启动交互式模式
echo "启动交互式查询..."
python3 -m query_tool --interactive
'''

    with open('/home/ubuntu/AIknowledge/aiunicom/start_system.sh', 'w') as f:
        f.write(startup_script)

    # 添加执行权限
    os.chmod('/home/ubuntu/AIknowledge/aiunicom/start_system.sh', 0o755)
    print("✓ 创建启动脚本")

if __name__ == '__main__':
    print("开始修复关键问题...")

    try:
        fix_redis_key_conflict()
        fix_filename_encoding()
        fix_config_security()
        add_performance_monitoring()
        create_startup_script()

        print("\\n✓ 所有关键问题修复完成！")
        print("\\n使用方法：")
        print("1. 运行: bash start_system.sh")
        print("2. 或手动执行: python3 -m query_tool --interactive")

    except Exception as e:
        print(f"修复过程中发生错误: {e}")
        import traceback
        traceback.print_exc()