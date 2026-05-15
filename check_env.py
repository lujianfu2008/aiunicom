# -*- coding: utf-8 -*-
"""
环境检查脚本 - 检查系统环境是否满足运行要求
"""

import sys
import subprocess

def check_python_version():
    """检查Python版本"""
    print("[1/5] 检查Python版本...")
    version = sys.version_info
    if version.major >= 3 and version.minor >= 8:
        print(f"   ✓ Python版本: {version.major}.{version.minor}.{version.micro}")
        return True
    else:
        print(f"   ✗ Python版本过低: {version.major}.{version.minor}.{version.micro}")
        print("   请安装Python 3.8或更高版本")
        return False

def check_redis():
    """检查Redis连接"""
    print("[2/5] 检查Redis服务...")
    try:
        import redis
        r = redis.Redis(
            host='127.0.0.1',
            port=6380,
            password='RedUssTest',
            db=0
        )
        r.ping()
        print("   ✓ Redis连接成功")
        print("   配置: 127.0.0.1:6380")
        return True
    except ImportError:
        print("   ✗ 未安装redis-py包")
        return False
    except Exception as e:
        print(f"   ✗ Redis连接失败: {e}")
        print("   请确保Redis Stack服务已启动")
        return False

def check_dependencies():
    """检查依赖包"""
    print("[3/5] 检查依赖包...")
    required = [
        'redis',
        'numpy',
        'requests',
        'PIL',
        'docx',
        'openpyxl',
        'pdfplumber',
        'pytesseract'
    ]
    
    missing = []
    for package in required:
        try:
            if package == 'PIL':
                __import__('PIL')
            elif package == 'docx':
                __import__('docx')
            else:
                __import__(package)
        except ImportError:
            missing.append(package)
    
    if missing:
        print(f"   ✗ 缺少依赖包: {', '.join(missing)}")
        print("   请运行: pip install -r requirements.txt")
        return False
    else:
        print("   ✓ 所有依赖包已安装")
        return True

def check_model():
    """检查本地模型"""
    print("[4/5] 检查本地模型...")
    import os
    model_path = r"D:\models\text2vec-base-chinese"
    if os.path.exists(model_path):
        print(f"   ✓ 模型路径存在: {model_path}")
        return True
    else:
        print(f"   ✗ 模型路径不存在: {model_path}")
        print("   请确保模型文件已下载并放置在正确位置")
        return False

def check_data_dir():
    """检查数据目录"""
    print("[5/5] 检查数据目录...")
    import os
    data_dir = r"D:\工作文档\cbss2.0体验版\沃工单问题定位"
    if os.path.exists(data_dir):
        print(f"   ✓ 数据目录存在: {data_dir}")
        # 统计文件数量
        file_count = 0
        for root, dirs, files in os.walk(data_dir):
            file_count += len(files)
        print(f"   发现 {file_count} 个文件")
        return True
    else:
        print(f"   ✗ 数据目录不存在: {data_dir}")
        print("   请确保数据目录存在或修改config.ini中的配置")
        return False

def main():
    """主函数"""
    print("=" * 70)
    print("           沃工单知识库系统 - 环境检查")
    print("=" * 70)
    print()
    
    checks = [
        check_python_version(),
        check_redis(),
        check_dependencies(),
        check_model(),
        check_data_dir()
    ]
    
    print()
    print("=" * 70)
    if all(checks):
        print("           ✓ 环境检查通过，系统可以正常运行")
    else:
        print("           ✗ 环境检查未通过，请修复上述问题")
    print("=" * 70)
    print()
    
    input("按回车键退出...")

if __name__ == "__main__":
    main()
