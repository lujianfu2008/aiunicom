#!/bin/bash
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
