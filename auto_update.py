# -*- coding: utf-8 -*-
"""
文件监听和自动更新模块
支持文件变更监听、后台自动更新、定时任务调度
"""

import os
import time
import threading
import hashlib
from typing import Dict, Set, Callable, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class FileWatcher:
    """文件变更监听器"""
    
    def __init__(self, kb, data_dir: str):
        self.kb = kb
        self.data_dir = data_dir
        self.file_hashes: Dict[str, str] = {}
        self.watching = False
        self.watch_thread: Optional[threading.Thread] = None
        self.interval = 60
        self.callbacks: list = []
        self.file_extensions = {
            '.txt', '.doc', '.docx', '.pdf', '.xlsx', '.xls',
            '.json', '.csv', '.md', '.xml', '.html', '.sql'
        }
    
    def start(self):
        """开始监听"""
        if self.watching:
            return
        
        self.watching = True
        self.watch_thread = threading.Thread(target=self._watch_loop, daemon=True)
        self.watch_thread.start()
        
        logger.info(f"开始监听目录: {self.data_dir}")
    
    def stop(self):
        """停止监听"""
        self.watching = False
        
        if self.watch_thread:
            self.watch_thread.join(timeout=5)
        
        logger.info("停止文件监听")
    
    def _watch_loop(self):
        """监听循环"""
        self._scan_files()
        
        while self.watching:
            try:
                time.sleep(self.interval)
                
                changes = self._detect_changes()
                
                if changes['added'] or changes['modified'] or changes['deleted']:
                    self._handle_changes(changes)
            
            except Exception as e:
                logger.error(f"监听错误: {e}")
    
    def _scan_files(self) -> Dict[str, str]:
        """扫描文件并计算哈希"""
        current_files = {}
        
        if not os.path.exists(self.data_dir):
            return current_files
        
        for root, dirs, files in os.walk(self.data_dir):
            for file in files:
                ext = os.path.splitext(file)[1].lower()
                
                if ext in self.file_extensions:
                    file_path = os.path.join(root, file)
                    
                    try:
                        file_hash = self._calculate_hash(file_path)
                        current_files[file_path] = file_hash
                    except Exception as e:
                        logger.warning(f"计算哈希失败 {file}: {e}")
        
        self.file_hashes = current_files
        return current_files
    
    def _calculate_hash(self, file_path: str) -> str:
        """计算文件哈希"""
        hasher = hashlib.md5()
        
        try:
            with open(file_path, 'rb') as f:
                for chunk in iter(lambda: f.read(8192), b''):
                    hasher.update(chunk)
        except:
            hasher.update(str(os.path.getmtime(file_path)).encode())
        
        return hasher.hexdigest()
    
    def _detect_changes(self) -> Dict:
        """检测变更"""
        current_files = {}
        changes = {
            'added': [],
            'modified': [],
            'deleted': []
        }
        
        if not os.path.exists(self.data_dir):
            return changes
        
        for root, dirs, files in os.walk(self.data_dir):
            for file in files:
                ext = os.path.splitext(file)[1].lower()
                
                if ext in self.file_extensions:
                    file_path = os.path.join(root, file)
                    
                    try:
                        file_hash = self._calculate_hash(file_path)
                        current_files[file_path] = file_hash
                        
                        if file_path not in self.file_hashes:
                            changes['added'].append(file_path)
                        elif self.file_hashes[file_path] != file_hash:
                            changes['modified'].append(file_path)
                    
                    except Exception as e:
                        logger.warning(f"检测变更失败 {file}: {e}")
        
        for file_path in self.file_hashes:
            if file_path not in current_files:
                changes['deleted'].append(file_path)
        
        self.file_hashes = current_files
        
        return changes
    
    def _handle_changes(self, changes: Dict):
        """处理变更"""
        total_changes = len(changes['added']) + len(changes['modified']) + len(changes['deleted'])
        
        if total_changes == 0:
            return
        
        logger.info(f"检测到文件变更: 新增 {len(changes['added'])}, 修改 {len(changes['modified'])}, 删除 {len(changes['deleted'])}")
        
        for callback in self.callbacks:
            try:
                callback(changes)
            except Exception as e:
                logger.error(f"回调执行失败: {e}")
    
    def add_callback(self, callback: Callable):
        """添加变更回调"""
        self.callbacks.append(callback)
    
    def remove_callback(self, callback: Callable):
        """移除变更回调"""
        if callback in self.callbacks:
            self.callbacks.remove(callback)
    
    def get_status(self) -> Dict:
        """获取监听状态"""
        return {
            'watching': self.watching,
            'data_dir': self.data_dir,
            'file_count': len(self.file_hashes),
            'interval': self.interval
        }


class AutoUpdater:
    """自动更新器"""
    
    def __init__(self, kb, data_dir: str):
        self.kb = kb
        self.data_dir = data_dir
        self.watcher = FileWatcher(kb, data_dir)
        self.update_thread: Optional[threading.Thread] = None
        self.updating = False
        self.update_queue: list = []
        self.last_update_time: Optional[float] = None
        
        self.watcher.add_callback(self._on_file_change)
    
    def start(self):
        """启动自动更新"""
        self.watcher.start()
        logger.info("自动更新器已启动")
    
    def stop(self):
        """停止自动更新"""
        self.watcher.stop()
        self.updating = False
        logger.info("自动更新器已停止")
    
    def _on_file_change(self, changes: Dict):
        """文件变更回调"""
        files_to_update = []
        
        files_to_update.extend(changes['added'])
        files_to_update.extend(changes['modified'])
        
        if files_to_update:
            logger.info(f"添加 {len(files_to_update)} 个文件到更新队列")
            self.update_queue.extend(files_to_update)
            
            if not self.updating:
                self._start_update()
        
        if changes['deleted']:
            self._handle_deletions(changes['deleted'])
    
    def _start_update(self):
        """开始更新"""
        if self.updating:
            return
        
        self.updating = True
        self.update_thread = threading.Thread(target=self._update_loop, daemon=True)
        self.update_thread.start()
    
    def _update_loop(self):
        """更新循环"""
        while self.updating and self.update_queue:
            try:
                file_path = self.update_queue.pop(0)
                
                logger.info(f"更新文件: {os.path.basename(file_path)}")
                
                self._update_file(file_path)
                
                time.sleep(0.1)
            
            except Exception as e:
                logger.error(f"更新失败: {e}")
        
        self.updating = False
        self.last_update_time = time.time()
    
    def _update_file(self, file_path: str):
        """更新单个文件"""
        try:
            if self.kb.add_new_document(file_path):
                logger.info(f"成功更新: {os.path.basename(file_path)}")
            else:
                logger.warning(f"文件解析无结果: {os.path.basename(file_path)}")
        except Exception as e:
            logger.error(f"更新文件失败 {file_path}: {e}")
    
    def _handle_deletions(self, deleted_files: list):
        """处理删除的文件"""
        for file_path in deleted_files:
            try:
                self.kb.delete_by_file_path(file_path)
                logger.info(f"已删除: {os.path.basename(file_path)}")
            except Exception as e:
                logger.error(f"删除失败 {file_path}: {e}")
    
    def force_update_all(self):
        """强制更新所有文件"""
        logger.info("开始强制更新所有文件...")
        
        self.kb.rebuild()
        
        self.last_update_time = time.time()
        
        logger.info("强制更新完成")
    
    def get_status(self) -> Dict:
        """获取状态"""
        return {
            'updating': self.updating,
            'queue_size': len(self.update_queue),
            'last_update': datetime.fromtimestamp(self.last_update_time).strftime('%Y-%m-%d %H:%M:%S') if self.last_update_time else '从未更新',
            'watcher': self.watcher.get_status()
        }


class ScheduledTask:
    """定时任务"""
    
    def __init__(self, name: str, func: Callable, interval: int):
        self.name = name
        self.func = func
        self.interval = interval
        self.last_run: Optional[float] = None
        self.running = False
        self.thread: Optional[threading.Thread] = None
    
    def start(self):
        """启动任务"""
        self.running = True
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()
    
    def stop(self):
        """停止任务"""
        self.running = False
    
    def _run_loop(self):
        """运行循环"""
        while self.running:
            try:
                time.sleep(self.interval)
                
                if self.running:
                    self.func()
                    self.last_run = time.time()
            
            except Exception as e:
                logger.error(f"定时任务 {self.name} 执行失败: {e}")
    
    def get_status(self) -> Dict:
        """获取状态"""
        return {
            'name': self.name,
            'interval': self.interval,
            'running': self.running,
            'last_run': datetime.fromtimestamp(self.last_run).strftime('%Y-%m-%d %H:%M:%S') if self.last_run else '从未运行'
        }


class TaskScheduler:
    """任务调度器"""
    
    def __init__(self):
        self.tasks: Dict[str, ScheduledTask] = {}
    
    def add_task(self, name: str, func: Callable, interval: int):
        """添加定时任务"""
        if name in self.tasks:
            self.tasks[name].stop()
        
        task = ScheduledTask(name, func, interval)
        self.tasks[name] = task
        
        logger.info(f"添加定时任务: {name}, 间隔: {interval}秒")
    
    def remove_task(self, name: str):
        """移除定时任务"""
        if name in self.tasks:
            self.tasks[name].stop()
            del self.tasks[name]
            
            logger.info(f"移除定时任务: {name}")
    
    def start_task(self, name: str):
        """启动任务"""
        if name in self.tasks:
            self.tasks[name].start()
            logger.info(f"启动任务: {name}")
    
    def stop_task(self, name: str):
        """停止任务"""
        if name in self.tasks:
            self.tasks[name].stop()
            logger.info(f"停止任务: {name}")
    
    def start_all(self):
        """启动所有任务"""
        for task in self.tasks.values():
            task.start()
        
        logger.info("启动所有定时任务")
    
    def stop_all(self):
        """停止所有任务"""
        for task in self.tasks.values():
            task.stop()
        
        logger.info("停止所有定时任务")
    
    def get_status(self) -> Dict:
        """获取所有任务状态"""
        return {
            name: task.get_status()
            for name, task in self.tasks.items()
        }


class MaintenanceManager:
    """维护管理器"""
    
    def __init__(self, kb):
        self.kb = kb
        self.scheduler = TaskScheduler()
    
    def setup_scheduled_tasks(self):
        """设置定时任务"""
        self.scheduler.add_task(
            'cleanup_cache',
            self._cleanup_cache,
            3600
        )
        
        self.scheduler.add_task(
            'update_stats',
            self._update_stats,
            300
        )
        
        self.scheduler.add_task(
            'check_health',
            self._check_health,
            600
        )
    
    def start(self):
        """启动维护"""
        self.setup_scheduled_tasks()
        self.scheduler.start_all()
        logger.info("维护管理器已启动")
    
    def stop(self):
        """停止维护"""
        self.scheduler.stop_all()
        logger.info("维护管理器已停止")
    
    def _cleanup_cache(self):
        """清理缓存"""
        try:
            stats = self.kb.get_statistics()
            logger.debug(f"缓存清理完成, 当前文档数: {stats.get('total_documents', 0)}")
        except Exception as e:
            logger.error(f"缓存清理失败: {e}")
    
    def _update_stats(self):
        """更新统计"""
        try:
            stats = self.kb.get_statistics()
            logger.debug(f"统计更新完成: {stats.get('total_documents', 0)} 个文档")
        except Exception as e:
            logger.error(f"统计更新失败: {e}")
    
    def _check_health(self):
        """健康检查"""
        try:
            stats = self.kb.get_statistics()
            
            if stats.get('total_documents', 0) == 0:
                logger.warning("知识库为空")
            
            logger.debug("健康检查完成")
        except Exception as e:
            logger.error(f"健康检查失败: {e}")
    
    def get_status(self) -> Dict:
        """获取状态"""
        return {
            'scheduler': self.scheduler.get_status()
        }
