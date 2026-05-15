# -*- coding: utf-8 -*-
"""
插件系统和用户权限管理模块
"""

import os
import json
import time
import hashlib
from typing import Dict, List, Optional, Callable, Any
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class PluginBase:
    """插件基类"""
    
    name = "base_plugin"
    version = "1.0.0"
    description = "基础插件"
    
    def on_load(self):
        """插件加载时调用"""
        pass
    
    def on_unload(self):
        """插件卸载时调用"""
        pass
    
    def on_file_parsed(self, file_info: Dict) -> Dict:
        """文件解析后调用"""
        return file_info
    
    def on_query(self, query: str) -> str:
        """查询时调用"""
        return query
    
    def on_result(self, result: Dict) -> Dict:
        """返回结果时调用"""
        return result
    
    def on_command(self, command: str, args: List[str]) -> Optional[str]:
        """自定义命令处理"""
        return None


class PluginManager:
    """插件管理器"""
    
    def __init__(self):
        self.plugins: Dict[str, PluginBase] = {}
        self.plugin_dir = 'plugins'
        
        if not os.path.exists(self.plugin_dir):
            os.makedirs(self.plugin_dir)
    
    def load_plugin(self, plugin: PluginBase) -> bool:
        """加载插件"""
        try:
            plugin.on_load()
            self.plugins[plugin.name] = plugin
            
            logger.info(f"加载插件: {plugin.name} v{plugin.version}")
            return True
        
        except Exception as e:
            logger.error(f"加载插件失败: {e}")
            return False
    
    def unload_plugin(self, name: str) -> bool:
        """卸载插件"""
        if name in self.plugins:
            try:
                self.plugins[name].on_unload()
                del self.plugins[name]
                
                logger.info(f"卸载插件: {name}")
                return True
            
            except Exception as e:
                logger.error(f"卸载插件失败: {e}")
                return False
        
        return False
    
    def get_plugin(self, name: str) -> Optional[PluginBase]:
        """获取插件"""
        return self.plugins.get(name)
    
    def list_plugins(self) -> List[Dict]:
        """列出所有插件"""
        return [
            {
                'name': p.name,
                'version': p.version,
                'description': p.description
            }
            for p in self.plugins.values()
        ]
    
    def on_file_parsed(self, file_info: Dict) -> Dict:
        """文件解析后调用所有插件"""
        result = file_info
        
        for plugin in self.plugins.values():
            try:
                result = plugin.on_file_parsed(result)
            except Exception as e:
                logger.error(f"插件 {plugin.name} 处理失败: {e}")
        
        return result
    
    def on_query(self, query: str) -> str:
        """查询时调用所有插件"""
        result = query
        
        for plugin in self.plugins.values():
            try:
                result = plugin.on_query(result)
            except Exception as e:
                logger.error(f"插件 {plugin.name} 处理失败: {e}")
        
        return result
    
    def on_result(self, result: Dict) -> Dict:
        """返回结果时调用所有插件"""
        processed = result
        
        for plugin in self.plugins.values():
            try:
                processed = plugin.on_result(processed)
            except Exception as e:
                logger.error(f"插件 {plugin.name} 处理失败: {e}")
        
        return processed
    
    def on_command(self, command: str, args: List[str]) -> Optional[str]:
        """处理自定义命令"""
        for plugin in self.plugins.values():
            try:
                result = plugin.on_command(command, args)
                if result is not None:
                    return result
            except Exception as e:
                logger.error(f"插件 {plugin.name} 命令处理失败: {e}")
        
        return None


class User:
    """用户类"""
    
    def __init__(self, username: str, password_hash: str, role: str = 'user'):
        self.username = username
        self.password_hash = password_hash
        self.role = role
        self.created_time = time.time()
        self.last_login = None
        self.login_count = 0
        self.preferences: Dict = {}
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            'username': self.username,
            'password_hash': self.password_hash,
            'role': self.role,
            'created_time': self.created_time,
            'last_login': self.last_login,
            'login_count': self.login_count,
            'preferences': self.preferences
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'User':
        """从字典创建"""
        user = cls(data['username'], data['password_hash'], data.get('role', 'user'))
        user.created_time = data.get('created_time', time.time())
        user.last_login = data.get('last_login')
        user.login_count = data.get('login_count', 0)
        user.preferences = data.get('preferences', {})
        return user


class UserManager:
    """用户管理器"""
    
    USERS_FILE = '.users.json'
    
    ROLE_PERMISSIONS = {
        'admin': ['all'],
        'user': ['search', 'find_file', 'find_content', 'stats', 'help'],
        'guest': ['search', 'help']
    }
    
    def __init__(self):
        self.users: Dict[str, User] = {}
        self.current_user: Optional[User] = None
        self.load()
        
        if 'admin' not in self.users:
            self.create_user('admin', 'admin123', 'admin')
    
    def create_user(self, username: str, password: str, role: str = 'user') -> bool:
        """创建用户"""
        if username in self.users:
            return False
        
        password_hash = self._hash_password(password)
        user = User(username, password_hash, role)
        self.users[username] = user
        
        self.save()
        logger.info(f"创建用户: {username}")
        return True
    
    def delete_user(self, username: str) -> bool:
        """删除用户"""
        if username == 'admin':
            return False
        
        if username in self.users:
            del self.users[username]
            self.save()
            logger.info(f"删除用户: {username}")
            return True
        
        return False
    
    def login(self, username: str, password: str) -> bool:
        """登录"""
        if username not in self.users:
            return False
        
        user = self.users[username]
        
        if user.password_hash != self._hash_password(password):
            return False
        
        user.last_login = time.time()
        user.login_count += 1
        self.current_user = user
        
        self.save()
        logger.info(f"用户登录: {username}")
        return True
    
    def logout(self):
        """登出"""
        if self.current_user:
            logger.info(f"用户登出: {self.current_user.username}")
        self.current_user = None
    
    def change_password(self, username: str, old_password: str, new_password: str) -> bool:
        """修改密码"""
        if username not in self.users:
            return False
        
        user = self.users[username]
        
        if user.password_hash != self._hash_password(old_password):
            return False
        
        user.password_hash = self._hash_password(new_password)
        self.save()
        
        logger.info(f"修改密码: {username}")
        return True
    
    def has_permission(self, permission: str) -> bool:
        """检查权限"""
        if not self.current_user:
            return permission in self.ROLE_PERMISSIONS.get('guest', [])
        
        role = self.current_user.role
        permissions = self.ROLE_PERMISSIONS.get(role, [])
        
        return 'all' in permissions or permission in permissions
    
    def get_current_user_info(self) -> Optional[Dict]:
        """获取当前用户信息"""
        if not self.current_user:
            return None
        
        return {
            'username': self.current_user.username,
            'role': self.current_user.role,
            'last_login': datetime.fromtimestamp(self.current_user.last_login).strftime('%Y-%m-%d %H:%M:%S') if self.current_user.last_login else '从未登录',
            'login_count': self.current_user.login_count
        }
    
    def list_users(self) -> List[Dict]:
        """列出所有用户"""
        return [
            {
                'username': u.username,
                'role': u.role,
                'created_time': datetime.fromtimestamp(u.created_time).strftime('%Y-%m-%d %H:%M'),
                'last_login': datetime.fromtimestamp(u.last_login).strftime('%Y-%m-%d %H:%M') if u.last_login else '从未登录',
                'login_count': u.login_count
            }
            for u in self.users.values()
        ]
    
    def _hash_password(self, password: str) -> str:
        """哈希密码"""
        return hashlib.sha256(password.encode()).hexdigest()
    
    def save(self):
        """保存用户数据"""
        try:
            data = {
                username: user.to_dict()
                for username, user in self.users.items()
            }
            
            with open(self.USERS_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        
        except Exception as e:
            logger.error(f"保存用户数据失败: {e}")
    
    def load(self):
        """加载用户数据"""
        try:
            if os.path.exists(self.USERS_FILE):
                with open(self.USERS_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                self.users = {
                    username: User.from_dict(user_data)
                    for username, user_data in data.items()
                }
        
        except Exception as e:
            logger.error(f"加载用户数据失败: {e}")
            self.users = {}


class AuditLogger:
    """审计日志"""
    
    LOG_FILE = '.audit.log'
    
    def __init__(self):
        self.log_file = self.LOG_FILE
    
    def log(self, action: str, username: str = None, details: Dict = None):
        """记录日志"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        log_entry = {
            'timestamp': timestamp,
            'action': action,
            'username': username or 'anonymous',
            'details': details or {}
        }
        
        try:
            with open(self.log_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')
        
        except Exception as e:
            logger.error(f"写入审计日志失败: {e}")
    
    def get_logs(self, limit: int = 100) -> List[Dict]:
        """获取日志"""
        logs = []
        
        try:
            if os.path.exists(self.log_file):
                with open(self.log_file, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                
                for line in lines[-limit:]:
                    try:
                        logs.append(json.loads(line.strip()))
                    except:
                        pass
        
        except Exception as e:
            logger.error(f"读取审计日志失败: {e}")
        
        return logs
    
    def clear_logs(self):
        """清空日志"""
        try:
            if os.path.exists(self.log_file):
                os.remove(self.log_file)
        except Exception as e:
            logger.error(f"清空审计日志失败: {e}")


class ExamplePlugin(PluginBase):
    """示例插件"""
    
    name = "example_plugin"
    version = "1.0.0"
    description = "示例插件，展示插件功能"
    
    def on_query(self, query: str) -> str:
        """处理查询"""
        return query.strip()
    
    def on_result(self, result: Dict) -> Dict:
        """处理结果"""
        if 'content' in result and len(result['content']) > 500:
            result['content_preview'] = result['content'][:500] + '...'
        
        return result
    
    def on_command(self, command: str, args: List[str]) -> Optional[str]:
        """处理自定义命令"""
        if command == 'hello':
            return f"Hello! 插件已加载，参数: {args}"
        
        return None
