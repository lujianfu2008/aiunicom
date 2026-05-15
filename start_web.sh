#!/bin/bash
# 知识库Web系统启动脚本

set -e

echo "=== 开始启动知识库Web系统 ==="

# 检查Python版本
python3 --version > /dev/null 2>&1 || {
    echo "错误: Python3未安装"
    exit 1
}
echo "✓ Python3已安装"

# 安装Python依赖库
echo "安装Python依赖库..."
pip3 install --break-system-packages olefile textract 2>&1 | tail -5

# 尝试安装antiword（用于解析旧版Word文档）
echo "尝试安装antiword..."
if command -v antiword &> /dev/null; then
    echo "✓ antiword已安装"
else
    echo "⚠ antiword未安装，部分Word文档可能无法解析"
    echo "  如需安装，请运行: sudo apt-get install antiword"
fi

# 检查Redis连接
echo "检查Redis连接..."
python3 -c "
import redis
try:
    r = redis.Redis(host='42.194.141.197', port=6379, password='RedUssTest')
    r.ping()
    print('✓ Redis连接成功')
except Exception as e:
    print(f'✗ Redis连接失败: {e}')
    exit(1)
"

# 检查配置文件
if [ ! -f "config.ini" ]; then
    echo "错误: config.ini不存在"
    exit 1
fi
echo "✓ 配置文件存在"

# 验证配置
python3 -c "
from config import validate_config
validate_config()
print('✓ 配置验证通过')
"

# 启动Web服务器
echo "启动Web服务器..."
echo "访问地址: http://0.0.0.0:5000"
echo "按 Ctrl+C 停止服务"
echo "=================================="

# 启动api_server.py
python3 api_server.py