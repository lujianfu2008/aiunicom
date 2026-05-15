# -*- coding: utf-8 -*-
"""
检查依赖包
"""

import sys

try:
    import redis
    import numpy
    import requests
    print("依赖包检查通过")
    sys.exit(0)
except ImportError as e:
    print(f"依赖包检查失败: {e}")
    sys.exit(1)
