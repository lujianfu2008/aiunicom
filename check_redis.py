# -*- coding: utf-8 -*-
"""
检查Redis连接
"""

import sys
import redis

try:
    r = redis.Redis(
        host='127.0.0.1',
        port=6380,
        password='RedUssTest',
        db=0
    )
    r.ping()
    print("Redis连接成功")
    sys.exit(0)
except Exception as e:
    print(f"Redis连接失败: {e}")
    sys.exit(1)
