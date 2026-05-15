# -*- coding: utf-8 -*-
"""
知识库增强功能模块
包含：历史命令、别名、分页、导出、推荐、标签、缓存等
"""

import os
import json
import time
import hashlib
import pickle
from typing import List, Dict, Optional, Any
from datetime import datetime
from collections import OrderedDict
import threading
import shutil

HISTORY_FILE = '.query_history'
ALIASES_FILE = '.query_aliases'
FAVORITES_FILE = '.query_favorites'
TAGS_FILE = '.query_tags'
CACHE_DIR = '.query_cache'
BACKUP_DIR = 'backups'


class CommandHistory:
    """命令历史管理器"""
    
    def __init__(self, max_size: int = 500):
        self.max_size = max_size
        self.history: List[str] = []
        self.current_index = -1
        self.history_file = HISTORY_FILE
        self.load()
    
    def add(self, command: str):
        """添加命令到历史"""
        if not command.strip():
            return
        
        command = command.strip()
        
        if self.history and self.history[-1] == command:
            return
        
        if command in self.history:
            self.history.remove(command)
        
        self.history.append(command)
        
        if len(self.history) > self.max_size:
            self.history = self.history[-self.max_size:]
        
        self.current_index = len(self.history)
        self.save()
    
    def get_previous(self) -> Optional[str]:
        """获取上一条命令"""
        if not self.history:
            return None
        
        if self.current_index > 0:
            self.current_index -= 1
            return self.history[self.current_index]
        
        return self.history[0] if self.history else None
    
    def get_next(self) -> Optional[str]:
        """获取下一条命令"""
        if not self.history:
            return None
        
        if self.current_index < len(self.history) - 1:
            self.current_index += 1
            return self.history[self.current_index]
        
        self.current_index = len(self.history)
        return ""
    
    def search(self, keyword: str) -> List[str]:
        """搜索历史命令"""
        return [cmd for cmd in self.history if keyword.lower() in cmd.lower()]
    
    def clear(self):
        """清空历史"""
        self.history = []
        self.current_index = -1
        self.save()
    
    def save(self):
        """保存历史到文件"""
        try:
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(self.history, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存历史失败: {e}")
    
    def load(self):
        """从文件加载历史"""
        try:
            if os.path.exists(self.history_file):
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    self.history = json.load(f)
                self.current_index = len(self.history)
        except Exception as e:
            print(f"加载历史失败: {e}")
            self.history = []
    
    def show(self, count: int = 20):
        """显示历史命令"""
        if not self.history:
            print("没有历史命令")
            return
        
        print(f"\n最近 {min(count, len(self.history))} 条命令:")
        print("-" * 60)
        for i, cmd in enumerate(self.history[-count:], 1):
            print(f"  {i:3d}. {cmd}")
        print("-" * 60)


class CommandAliases:
    """命令别名管理器"""
    
    DEFAULT_ALIASES = {
        'ff': 'find_file',
        'fc': 'find_content',
        'fv': 'find_vec',
        'fva': 'find_vec_ai',
        'of': 'open_file',
        's': 'stats',
        'h': 'help',
        'q': 'quit',
        'ex': 'export',
        'fav': 'favorite',
        'tag': 'tags',
        'rec': 'recommend',
        'sum': 'summary',
        'his': 'history',
    }
    
    def __init__(self):
        self.aliases: Dict[str, str] = {}
        self.aliases_file = ALIASES_FILE
        self.load()
    
    def get(self, alias: str) -> str:
        """获取别名对应的命令"""
        return self.aliases.get(alias, alias)
    
    def set(self, alias: str, command: str):
        """设置别名"""
        self.aliases[alias] = command
        self.save()
    
    def remove(self, alias: str) -> bool:
        """删除别名"""
        if alias in self.aliases:
            del self.aliases[alias]
            self.save()
            return True
        return False
    
    def list_all(self) -> Dict[str, str]:
        """列出所有别名"""
        return self.aliases.copy()
    
    def save(self):
        """保存别名到文件"""
        try:
            with open(self.aliases_file, 'w', encoding='utf-8') as f:
                json.dump(self.aliases, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存别名失败: {e}")
    
    def load(self):
        """从文件加载别名"""
        self.aliases = self.DEFAULT_ALIASES.copy()
        try:
            if os.path.exists(self.aliases_file):
                with open(self.aliases_file, 'r', encoding='utf-8') as f:
                    loaded = json.load(f)
                    self.aliases.update(loaded)
        except Exception as e:
            print(f"加载别名失败: {e}")
    
    def show(self):
        """显示所有别名"""
        print("\n命令别名列表:")
        print("-" * 40)
        for alias, cmd in sorted(self.aliases.items()):
            print(f"  {alias:6s} -> {cmd}")
        print("-" * 40)


class ResultPaginator:
    """结果分页器"""
    
    def __init__(self, page_size: int = 10):
        self.page_size = page_size
        self.results: List[Dict] = []
        self.current_page = 0
        self.total_pages = 0
    
    def set_results(self, results: List[Dict]):
        """设置结果"""
        self.results = results
        self.current_page = 0
        self.total_pages = (len(results) + self.page_size - 1) // self.page_size
    
    def get_current_page(self) -> List[Dict]:
        """获取当前页结果"""
        start = self.current_page * self.page_size
        end = start + self.page_size
        return self.results[start:end]
    
    def next_page(self) -> Optional[List[Dict]]:
        """下一页"""
        if self.current_page < self.total_pages - 1:
            self.current_page += 1
            return self.get_current_page()
        return None
    
    def prev_page(self) -> Optional[List[Dict]]:
        """上一页"""
        if self.current_page > 0:
            self.current_page -= 1
            return self.get_current_page()
        return None
    
    def go_to_page(self, page: int) -> Optional[List[Dict]]:
        """跳转到指定页"""
        if 0 <= page < self.total_pages:
            self.current_page = page
            return self.get_current_page()
        return None
    
    def get_page_info(self) -> str:
        """获取分页信息"""
        return f"第 {self.current_page + 1}/{self.total_pages} 页 (共 {len(self.results)} 条结果)"
    
    def has_next(self) -> bool:
        """是否有下一页"""
        return self.current_page < self.total_pages - 1
    
    def has_prev(self) -> bool:
        """是否有上一页"""
        return self.current_page > 0


class ResultExporter:
    """结果导出器"""
    
    @staticmethod
    def to_csv(results: List[Dict], filename: str) -> bool:
        """导出到CSV"""
        try:
            import csv
            
            if not results:
                print("没有结果可导出")
                return False
            
            with open(filename, 'w', encoding='utf-8-sig', newline='') as f:
                writer = csv.writer(f)
                
                headers = ['文件名', '文件路径', '问题ID', '问题类型', '内容预览', '解决方案']
                writer.writerow(headers)
                
                for result in results:
                    content = result.get('content', '')
                    content_preview = content[:100] + '...' if len(content) > 100 else content
                    
                    row = [
                        result.get('file_name', ''),
                        result.get('file_path', ''),
                        result.get('problem_id', ''),
                        result.get('problem_type', ''),
                        content_preview,
                        result.get('solution', '')
                    ]
                    writer.writerow(row)
            
            print(f"成功导出到: {filename}")
            return True
            
        except Exception as e:
            print(f"导出CSV失败: {e}")
            return False
    
    @staticmethod
    def to_excel(results: List[Dict], filename: str) -> bool:
        """导出到Excel"""
        try:
            import pandas as pd
            
            if not results:
                print("没有结果可导出")
                return False
            
            data = []
            for result in results:
                content = result.get('content', '')
                content_preview = content[:200] + '...' if len(content) > 200 else content
                
                data.append({
                    '文件名': result.get('file_name', ''),
                    '文件路径': result.get('file_path', ''),
                    '问题ID': result.get('problem_id', ''),
                    '问题类型': result.get('problem_type', ''),
                    '内容预览': content_preview,
                    '解决方案': result.get('solution', ''),
                    '创建时间': datetime.fromtimestamp(result.get('created_time', 0)).strftime('%Y-%m-%d %H:%M:%S') if result.get('created_time') else ''
                })
            
            df = pd.DataFrame(data)
            df.to_excel(filename, index=False, engine='openpyxl')
            
            print(f"成功导出到: {filename}")
            return True
            
        except ImportError:
            print("需要安装 pandas 和 openpyxl: pip install pandas openpyxl")
            return False
        except Exception as e:
            print(f"导出Excel失败: {e}")
            return False
    
    @staticmethod
    def to_json(results: List[Dict], filename: str) -> bool:
        """导出到JSON"""
        try:
            if not results:
                print("没有结果可导出")
                return False
            
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(results, f, ensure_ascii=False, indent=2)
            
            print(f"成功导出到: {filename}")
            return True
            
        except Exception as e:
            print(f"导出JSON失败: {e}")
            return False


class FavoriteManager:
    """收藏管理器"""
    
    def __init__(self):
        self.favorites: Dict[str, Dict] = {}
        self.favorites_file = FAVORITES_FILE
        self.load()
    
    def add(self, file_path: str, file_name: str, note: str = ""):
        """添加收藏"""
        self.favorites[file_path] = {
            'file_name': file_name,
            'file_path': file_path,
            'note': note,
            'added_time': time.time()
        }
        self.save()
        print(f"已收藏: {file_name}")
    
    def remove(self, file_path: str) -> bool:
        """移除收藏"""
        if file_path in self.favorites:
            file_name = self.favorites[file_path]['file_name']
            del self.favorites[file_path]
            self.save()
            print(f"已取消收藏: {file_name}")
            return True
        return False
    
    def is_favorite(self, file_path: str) -> bool:
        """检查是否已收藏"""
        return file_path in self.favorites
    
    def list_all(self) -> List[Dict]:
        """列出所有收藏"""
        return list(self.favorites.values())
    
    def search(self, keyword: str) -> List[Dict]:
        """搜索收藏"""
        results = []
        for fav in self.favorites.values():
            if keyword.lower() in fav['file_name'].lower() or keyword.lower() in fav.get('note', '').lower():
                results.append(fav)
        return results
    
    def save(self):
        """保存收藏到文件"""
        try:
            with open(self.favorites_file, 'w', encoding='utf-8') as f:
                json.dump(self.favorites, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存收藏失败: {e}")
    
    def load(self):
        """从文件加载收藏"""
        try:
            if os.path.exists(self.favorites_file):
                with open(self.favorites_file, 'r', encoding='utf-8') as f:
                    self.favorites = json.load(f)
        except Exception as e:
            print(f"加载收藏失败: {e}")
            self.favorites = {}
    
    def show(self):
        """显示所有收藏"""
        if not self.favorites:
            print("\n没有收藏的文件")
            return
        
        print(f"\n收藏列表 ({len(self.favorites)} 个):")
        print("-" * 60)
        for i, fav in enumerate(self.favorites.values(), 1):
            added_time = datetime.fromtimestamp(fav['added_time']).strftime('%Y-%m-%d %H:%M')
            print(f"  {i}. {fav['file_name']}")
            print(f"     路径: {fav['file_path']}")
            if fav.get('note'):
                print(f"     备注: {fav['note']}")
            print(f"     添加时间: {added_time}")
            print()
        print("-" * 60)


class TagManager:
    """标签管理器"""
    
    def __init__(self):
        self.tags: Dict[str, Dict[str, List[str]]] = {}
        self.tags_file = TAGS_FILE
        self.load()
    
    def add_tag(self, file_path: str, tag: str):
        """添加标签"""
        if tag not in self.tags:
            self.tags[tag] = {'files': [], 'created_time': time.time()}
        
        if file_path not in self.tags[tag]['files']:
            self.tags[tag]['files'].append(file_path)
            self.save()
            print(f"已添加标签 '{tag}'")
    
    def remove_tag(self, file_path: str, tag: str):
        """移除标签"""
        if tag in self.tags and file_path in self.tags[tag]['files']:
            self.tags[tag]['files'].remove(file_path)
            if not self.tags[tag]['files']:
                del self.tags[tag]
            self.save()
            print(f"已移除标签 '{tag}'")
    
    def get_file_tags(self, file_path: str) -> List[str]:
        """获取文件的所有标签"""
        result = []
        for tag, data in self.tags.items():
            if file_path in data['files']:
                result.append(tag)
        return result
    
    def get_files_by_tag(self, tag: str) -> List[str]:
        """获取标签下的所有文件"""
        return self.tags.get(tag, {}).get('files', [])
    
    def list_all_tags(self) -> List[str]:
        """列出所有标签"""
        return list(self.tags.keys())
    
    def get_tag_stats(self) -> Dict[str, int]:
        """获取标签统计"""
        return {tag: len(data['files']) for tag, data in self.tags.items()}
    
    def save(self):
        """保存标签到文件"""
        try:
            with open(self.tags_file, 'w', encoding='utf-8') as f:
                json.dump(self.tags, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存标签失败: {e}")
    
    def load(self):
        """从文件加载标签"""
        try:
            if os.path.exists(self.tags_file):
                with open(self.tags_file, 'r', encoding='utf-8') as f:
                    self.tags = json.load(f)
        except Exception as e:
            print(f"加载标签失败: {e}")
            self.tags = {}
    
    def show(self):
        """显示所有标签"""
        if not self.tags:
            print("\n没有标签")
            return
        
        print(f"\n标签列表 ({len(self.tags)} 个):")
        print("-" * 40)
        stats = self.get_tag_stats()
        for tag, count in sorted(stats.items(), key=lambda x: -x[1]):
            print(f"  {tag}: {count} 个文件")
        print("-" * 40)


class SmartCache:
    """智能缓存管理器"""
    
    def __init__(self, max_memory_items: int = 1000, max_disk_size_mb: int = 100):
        self.max_memory_items = max_memory_items
        self.max_disk_size_mb = max_disk_size_mb
        self.memory_cache: OrderedDict = OrderedDict()
        self.cache_dir = CACHE_DIR
        self.lock = threading.Lock()
        
        if not os.path.exists(self.cache_dir):
            os.makedirs(self.cache_dir)
    
    def get(self, key: str) -> Optional[Any]:
        """获取缓存"""
        cache_key = self._make_key(key)
        
        with self.lock:
            if cache_key in self.memory_cache:
                self.memory_cache.move_to_end(cache_key)
                return self.memory_cache[cache_key]
        
        disk_cache = self._get_from_disk(cache_key)
        if disk_cache is not None:
            with self.lock:
                self._add_to_memory(cache_key, disk_cache)
            return disk_cache
        
        return None
    
    def set(self, key: str, value: Any, ttl: int = 3600):
        """设置缓存"""
        cache_key = self._make_key(key)
        
        with self.lock:
            self._add_to_memory(cache_key, value)
        
        self._save_to_disk(cache_key, value, ttl)
    
    def delete(self, key: str):
        """删除缓存"""
        cache_key = self._make_key(key)
        
        with self.lock:
            if cache_key in self.memory_cache:
                del self.memory_cache[cache_key]
        
        self._delete_from_disk(cache_key)
    
    def clear(self):
        """清空缓存"""
        with self.lock:
            self.memory_cache.clear()
        
        if os.path.exists(self.cache_dir):
            shutil.rmtree(self.cache_dir)
            os.makedirs(self.cache_dir)
    
    def _make_key(self, key: str) -> str:
        """生成缓存键"""
        return hashlib.md5(key.encode()).hexdigest()
    
    def _add_to_memory(self, key: str, value: Any):
        """添加到内存缓存"""
        if len(self.memory_cache) >= self.max_memory_items:
            self.memory_cache.popitem(last=False)
        self.memory_cache[key] = value
    
    def _get_from_disk(self, key: str) -> Optional[Any]:
        """从磁盘获取缓存"""
        cache_file = os.path.join(self.cache_dir, f"{key}.cache")
        
        try:
            if os.path.exists(cache_file):
                with open(cache_file, 'rb') as f:
                    data = pickle.load(f)
                
                if data.get('expire_time', float('inf')) > time.time():
                    return data.get('value')
                else:
                    os.remove(cache_file)
        except:
            pass
        
        return None
    
    def _save_to_disk(self, key: str, value: Any, ttl: int):
        """保存到磁盘"""
        cache_file = os.path.join(self.cache_dir, f"{key}.cache")
        
        try:
            data = {
                'value': value,
                'expire_time': time.time() + ttl
            }
            
            with open(cache_file, 'wb') as f:
                pickle.dump(data, f)
        except:
            pass
    
    def _delete_from_disk(self, key: str):
        """从磁盘删除缓存"""
        cache_file = os.path.join(self.cache_dir, f"{key}.cache")
        
        try:
            if os.path.exists(cache_file):
                os.remove(cache_file)
        except:
            pass
    
    def get_stats(self) -> Dict:
        """获取缓存统计"""
        disk_size = 0
        disk_count = 0
        
        if os.path.exists(self.cache_dir):
            for f in os.listdir(self.cache_dir):
                if f.endswith('.cache'):
                    disk_count += 1
                    disk_size += os.path.getsize(os.path.join(self.cache_dir, f))
        
        return {
            'memory_items': len(self.memory_cache),
            'disk_items': disk_count,
            'disk_size_mb': disk_size / (1024 * 1024)
        }


class BackupManager:
    """备份管理器"""
    
    def __init__(self):
        self.backup_dir = BACKUP_DIR
        
        if not os.path.exists(self.backup_dir):
            os.makedirs(self.backup_dir)
    
    def create_backup(self, redis_client, name: str = None) -> str:
        """创建备份"""
        if name is None:
            name = datetime.now().strftime('backup_%Y%m%d_%H%M%S')
        
        backup_path = os.path.join(self.backup_dir, name)
        
        if not os.path.exists(backup_path):
            os.makedirs(backup_path)
        
        try:
            from config import KEY_PREFIX
            
            doc_keys = list(redis_client.scan_iter(match=f"{KEY_PREFIX}*", count=100))
            valid_keys = [k for k in doc_keys if not k.decode().endswith(('_idx', '_cache', '_fp'))]
            
            print(f"正在备份 {len(valid_keys)} 个文档...")
            
            count = 0
            for key in valid_keys:
                try:
                    data = redis_client.json().get(key)
                    if data:
                        key_str = key.decode() if isinstance(key, bytes) else key
                        key_hash = hashlib.md5(key_str.encode()).hexdigest()
                        backup_file = os.path.join(backup_path, f"{key_hash}.json")
                        
                        with open(backup_file, 'w', encoding='utf-8') as f:
                            json.dump({
                                'key': key_str,
                                'data': data
                            }, f, ensure_ascii=False)
                        
                        count += 1
                except Exception as e:
                    print(f"备份失败 {key}: {e}")
            
            meta = {
                'created_time': time.time(),
                'document_count': count,
                'version': '1.0'
            }
            
            with open(os.path.join(backup_path, 'meta.json'), 'w', encoding='utf-8') as f:
                json.dump(meta, f, ensure_ascii=False, indent=2)
            
            print(f"备份完成: {backup_path}")
            print(f"共备份 {count} 个文档")
            
            return backup_path
            
        except Exception as e:
            print(f"备份失败: {e}")
            return ""
    
    def list_backups(self) -> List[Dict]:
        """列出所有备份"""
        backups = []
        
        if not os.path.exists(self.backup_dir):
            return backups
        
        for name in os.listdir(self.backup_dir):
            backup_path = os.path.join(self.backup_dir, name)
            meta_file = os.path.join(backup_path, 'meta.json')
            
            if os.path.isdir(backup_path) and os.path.exists(meta_file):
                try:
                    with open(meta_file, 'r', encoding='utf-8') as f:
                        meta = json.load(f)
                    
                    backups.append({
                        'name': name,
                        'path': backup_path,
                        'created_time': meta.get('created_time', 0),
                        'document_count': meta.get('document_count', 0)
                    })
                except:
                    pass
        
        return sorted(backups, key=lambda x: x['created_time'], reverse=True)
    
    def restore_backup(self, redis_client, backup_name: str) -> bool:
        """恢复备份"""
        backup_path = os.path.join(self.backup_dir, backup_name)
        
        if not os.path.exists(backup_path):
            print(f"备份不存在: {backup_name}")
            return False
        
        try:
            meta_file = os.path.join(backup_path, 'meta.json')
            with open(meta_file, 'r', encoding='utf-8') as f:
                meta = json.load(f)
            
            print(f"正在恢复备份: {backup_name}")
            print(f"文档数量: {meta.get('document_count', 0)}")
            
            count = 0
            for filename in os.listdir(backup_path):
                if filename.endswith('.json') and filename != 'meta.json':
                    try:
                        with open(os.path.join(backup_path, filename), 'r', encoding='utf-8') as f:
                            item = json.load(f)
                        
                        key = item['key']
                        data = item['data']
                        
                        redis_client.json().set(key, '$', data)
                        count += 1
                    except Exception as e:
                        print(f"恢复失败 {filename}: {e}")
            
            print(f"恢复完成，共恢复 {count} 个文档")
            return True
            
        except Exception as e:
            print(f"恢复失败: {e}")
            return False
    
    def delete_backup(self, backup_name: str) -> bool:
        """删除备份"""
        backup_path = os.path.join(self.backup_dir, backup_name)
        
        if os.path.exists(backup_path):
            shutil.rmtree(backup_path)
            print(f"已删除备份: {backup_name}")
            return True
        
        return False


class ClipboardManager:
    """剪贴板管理器"""
    
    @staticmethod
    def copy(text: str) -> bool:
        """复制文本到剪贴板"""
        try:
            import pyperclip
            pyperclip.copy(text)
            print(f"已复制到剪贴板: {text[:50]}...")
            return True
        except ImportError:
            try:
                import subprocess
                
                subprocess.run(['clip'], input=text.encode('utf-16'), check=True)
                print(f"已复制到剪贴板: {text[:50]}...")
                return True
            except:
                print("复制失败，请安装 pyperclip: pip install pyperclip")
                return False
        except Exception as e:
            print(f"复制失败: {e}")
            return False
    
    @staticmethod
    def paste() -> str:
        """从剪贴板粘贴"""
        try:
            import pyperclip
            return pyperclip.paste()
        except ImportError:
            try:
                import subprocess
                result = subprocess.run(['powershell', '-command', 'Get-Clipboard'], capture_output=True, text=True)
                return result.stdout.strip()
            except:
                return ""
        except:
            return ""


class TrendAnalyzer:
    """趋势分析器"""
    
    def __init__(self, kb):
        self.kb = kb
    
    def analyze_by_time(self, days: int = 30) -> Dict:
        """按时间分析趋势"""
        try:
            stats = self.kb.get_statistics()
            
            result = {
                'period_days': days,
                'total_documents': stats.get('total_documents', 0),
                'type_distribution': stats.get('type_distribution', {}),
                'analysis_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
            return result
            
        except Exception as e:
            print(f"趋势分析失败: {e}")
            return {}
    
    def get_hot_types(self, top_n: int = 10) -> List[Dict]:
        """获取热门问题类型"""
        try:
            stats = self.kb.get_statistics()
            type_dist = stats.get('type_distribution', {})
            
            sorted_types = sorted(type_dist.items(), key=lambda x: x[1], reverse=True)
            
            return [{'type': t, 'count': c} for t, c in sorted_types[:top_n]]
            
        except Exception as e:
            print(f"获取热门类型失败: {e}")
            return []
    
    def generate_report(self) -> str:
        """生成分析报告"""
        try:
            stats = self.kb.get_statistics()
            hot_types = self.get_hot_types(10)
            
            report = []
            report.append("=" * 60)
            report.append("知识库趋势分析报告")
            report.append(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            report.append("=" * 60)
            report.append("")
            report.append(f"文档总数: {stats.get('total_documents', 0)}")
            report.append(f"问题类型数: {len(stats.get('type_distribution', {}))}")
            report.append("")
            report.append("热门问题类型 Top 10:")
            report.append("-" * 40)
            
            for i, item in enumerate(hot_types, 1):
                report.append(f"  {i:2d}. {item['type']}: {item['count']} 个")
            
            report.append("-" * 40)
            
            return "\n".join(report)
            
        except Exception as e:
            return f"生成报告失败: {e}"
