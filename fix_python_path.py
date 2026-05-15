#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
修复Python路径和依赖问题
"""

import os
import sys
import subprocess

def create_python_symlink():
    """创建python软链接"""
    try:
        if not os.path.exists('/usr/bin/python'):
            subprocess.run(['ln', '-s', '/usr/bin/python3', '/usr/bin/python'], check=True)
            print("✓ 创建python软链接成功")
        else:
            print("✓ python软链接已存在")
    except Exception as e:
        print(f"✗ 创建python软链接失败: {e}")

def install_missing_dependencies():
    """安装缺失的关键依赖"""
    critical_packages = [
        'sentence-transformers',
        'transformers',
        'torch'
    ]

    for package in critical_packages:
        try:
            __import__(package.replace('-', '_'))
            print(f"✓ {package} 已安装")
        except ImportError:
            print(f"正在安装 {package}...")
            try:
                subprocess.run([sys.executable, '-m', 'pip', 'install', package], check=True)
                print(f"✓ {package} 安装成功")
            except Exception as e:
                print(f"✗ {package} 安装失败: {e}")

if __name__ == '__main__':
    print("开始修复Python环境问题...")
    create_python_symlink()
    install_missing_dependencies()
    print("修复完成！")