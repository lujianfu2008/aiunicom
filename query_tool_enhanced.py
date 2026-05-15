# -*- coding: utf-8 -*-
"""
增强版交互式查询工具
集成所有新功能：历史命令、别名、分页、导出、推荐、标签、缓存等
"""

import os
import sys
import re
import time
import logging
import warnings
import redis
import threading
from datetime import datetime
from typing import List, Dict, Optional

if sys.platform == 'win32':
    os.environ['PYTHONIOENCODING'] = 'utf-8'

warnings.filterwarnings('ignore', message='Neither CUDA nor MPS are available')

from config import ZHIPU_CONFIG, update_config, REDIS_CONFIG
from knowledge_base import KnowledgeBase
from enhanced_features import (
    CommandHistory, CommandAliases, ResultPaginator, ResultExporter,
    FavoriteManager, TagManager, SmartCache, BackupManager, 
    ClipboardManager, TrendAnalyzer
)
from smart_features import (
    SmartRecommender, SmartQA, AutoSummarizer, 
    CategorySuggester, FileComparator, BatchOperator
)
from auto_update import AutoUpdater, MaintenanceManager
from plugin_system import PluginManager, UserManager, AuditLogger

logging.basicConfig(
    level=logging.WARNING,
    format='%(asctime)s - %(levelname)s - %(message)s'
)


class EnhancedInteractiveQuery:
    """增强版交互式查询工具"""
    
    def __init__(self):
        self.kb = None
        self.llm_enabled = False
        self.redis_client = None
        self._connect_redis()
        
        self.current_mode = 'main'
        self.mode_stack = []
        
        self.history = CommandHistory()
        self.aliases = CommandAliases()
        self.paginator = ResultPaginator(page_size=10)
        self.favorites = FavoriteManager()
        self.tags = TagManager()
        self.cache = SmartCache()
        self.backup_mgr = BackupManager()
        self.clipboard = ClipboardManager()
        self.plugins = PluginManager()
        self.users = UserManager()
        self.audit = AuditLogger()
        
        self.recommender = None
        self.smart_qa = None
        self.summarizer = None
        self.category_suggester = None
        self.file_comparator = None
        self.batch_operator = None
        self.auto_updater = None
        self.maintenance = None
        
        self.last_results: List[Dict] = []
        self.init_thread = None
        self.is_initializing = False
    
    def _connect_redis(self):
        """连接Redis"""
        try:
            self.redis_client = redis.Redis(**REDIS_CONFIG)
            self.redis_client.ping()
        except Exception as e:
            print(f"Redis连接失败: {e}")
            sys.exit(1)
    
    def _init_smart_features(self):
        """初始化智能功能"""
        self.recommender = SmartRecommender(self.kb)
        self.smart_qa = SmartQA(self.kb)
        self.summarizer = AutoSummarizer(self.kb)
        self.category_suggester = CategorySuggester(self.kb)
        self.file_comparator = FileComparator(self.kb)
        self.batch_operator = BatchOperator(self.kb)
    
    def start(self):
        """启动交互式查询"""
        self._print_welcome()
        self._init_knowledge_base()
        self._check_llm_config()
        self._init_smart_features()
        self._run_loop()
    
    def _print_welcome(self):
        """打印欢迎信息"""
        print("\n" + "=" * 70)
        print(" " * 15 + "沃工单知识库查询系统 V4 (增强版)")
        print("=" * 70)
        print("\n新增功能:")
        print("  ✓ 历史命令记录 (history)")
        print("  ✓ 命令别名支持 (alias)")
        print("  ✓ 结果分页显示 (page)")
        print("  ✓ 导出功能 (export)")
        print("  ✓ 收藏系统 (favorite)")
        print("  ✓ 标签系统 (tag)")
        print("  ✓ 智能推荐 (recommend)")
        print("  ✓ 自动摘要 (summary)")
        print("  ✓ 文件对比 (compare)")
        print("  ✓ 批量操作 (batch)")
        print("  ✓ 备份恢复 (backup)")
        print("  ✓ 趋势分析 (trend)")
        print("  ✓ 用户管理 (user)")
        print("  ✓ API服务 (api)")
        
        print("\n基础命令:")
        print("  help        - 显示帮助信息")
        print("  stats       - 显示知识库统计")
        print("  categories  - 显示问题分类")
        print("  history     - 显示历史命令")
        print("  alias       - 显示命令别名")
        
        print("\n查询命令:")
        print("  find_file   - 按文件名查找")
        print("  find_content - 按内容查找")
        print("  find_vec    - 向量查找")
        print("  find_vec_ai - 智能查询")
        print("  open_file   - 打开文件")
        
        print("\n增强命令:")
        print("  recommend   - 推荐相关文件")
        print("  summary     - 生成摘要")
        print("  favorite    - 收藏管理")
        print("  tag         - 标签管理")
        print("  export      - 导出结果")
        print("  backup      - 备份管理")
        print("  trend       - 趋势分析")
        print("  user        - 用户管理")
        print("  api         - 启动API服务")
        
        print("\n模式切换:")
        print("  su <模式>   - 切换模式")
        print("  cd          - 返回上级")
        print("  quit/exit   - 退出系统")
        print("=" * 70 + "\n")
    
    def _get_prompt(self) -> str:
        """获取提示符"""
        prompts = {
            'main': "主模式 > ",
            'find_file': "find_file > ",
            'find_content': "find_content > ",
            'find_vec': "find_vec > ",
            'find_vec_ai': "find_vec_ai > ",
            'open_file': "open_file > ",
            'recommend': "recommend > ",
            'summary': "summary > ",
            'favorite': "favorite > ",
            'tag': "tag > "
        }
        return prompts.get(self.current_mode, "请输入 > ")
    
    def _show_mode_info(self):
        """显示模式信息"""
        mode_info = {
            'main': ("主模式", "使用 su 命令切换模式"),
            'find_file': ("文件查找模式", "输入文件名查找"),
            'find_content': ("内容查找模式", "输入关键字查找"),
            'find_vec': ("向量查找模式", "输入问题搜索"),
            'find_vec_ai': ("智能查询模式", "输入问题查询"),
            'open_file': ("文件打开模式", "输入文件名打开"),
            'recommend': ("推荐模式", "输入文件路径获取推荐"),
            'summary': ("摘要模式", "输入文件路径生成摘要"),
            'favorite': ("收藏模式", "管理收藏文件"),
            'tag': ("标签模式", "管理文件标签")
        }
        
        info = mode_info.get(self.current_mode, ("未知模式", ""))
        print(f"\n当前模式: {info[0]}")
        print(info[1])
        print("使用 cd 返回上级")
        print("-" * 40)
    
    def _change_mode(self, new_mode: str):
        """切换模式"""
        if new_mode != self.current_mode:
            self.mode_stack.append(self.current_mode)
            self.current_mode = new_mode
    
    def _go_back_mode(self):
        """返回上级模式"""
        if self.mode_stack:
            self.current_mode = self.mode_stack.pop()
            return True
        return False
    
    def _init_knowledge_base(self):
        """初始化知识库"""
        print("正在初始化知识库...")
        try:
            self.kb = KnowledgeBase(use_llm=False)
            print("知识库初始化成功")
        except Exception as e:
            print(f"知识库初始化失败: {e}")
    
    def _check_llm_config(self):
        """检查LLM配置"""
        if ZHIPU_CONFIG.get('api_key'):
            self.llm_enabled = True
    
    def _run_loop(self):
        """主循环"""
        while True:
            try:
                prompt = self._get_prompt()
                user_input = input(prompt).strip()
                
                if not user_input:
                    continue
                
                self.history.add(user_input)
                
                user_input = self.aliases.get(user_input.split()[0]) + ' ' + ' '.join(user_input.split()[1:]) if ' ' in user_input else self.aliases.get(user_input)
                
                if self._handle_command(user_input):
                    continue
                
                if self.current_mode != 'main':
                    self._handle_mode_input(user_input)
                    continue
                
                self._handle_main_input(user_input)
                
            except KeyboardInterrupt:
                print("\n\n正在退出...")
                break
            except EOFError:
                break
    
    def _handle_command(self, user_input: str) -> bool:
        """处理命令"""
        cmd = user_input.lower().split()[0] if user_input else ''
        args = user_input.split()[1:] if len(user_input.split()) > 1 else []
        
        if cmd in ['quit', 'exit', 'q']:
            print("\n感谢使用，再见！")
            sys.exit(0)
        
        if cmd == 'help':
            self._show_help()
            return True
        
        if cmd == 'history':
            self.history.show(20)
            return True
        
        if cmd == 'alias':
            self.aliases.show()
            return True
        
        if cmd in ['su', 'cd']:
            self._handle_mode_switch(cmd, args)
            return True
        
        if cmd == 'stats':
            self._show_stats()
            return True
        
        if cmd == 'categories':
            self._show_categories()
            return True
        
        if cmd == 'export':
            self._handle_export(args)
            return True
        
        if cmd == 'favorite':
            self._handle_favorite(args)
            return True
        
        if cmd == 'tag':
            self._handle_tag(args)
            return True
        
        if cmd == 'recommend':
            self._handle_recommend(args)
            return True
        
        if cmd == 'summary':
            self._handle_summary(args)
            return True
        
        if cmd == 'backup':
            self._handle_backup(args)
            return True
        
        if cmd == 'trend':
            self._handle_trend()
            return True
        
        if cmd == 'user':
            self._handle_user(args)
            return True
        
        if cmd == 'api':
            self._start_api_server()
            return True
        
        if cmd == 'page':
            self._handle_page(args)
            return True
        
        if cmd == 'copy':
            self._handle_copy(args)
            return True
        
        if cmd == 'compare':
            self._handle_compare(args)
            return True
        
        if cmd == 'clear':
            os.system('cls' if os.name == 'nt' else 'clear')
            return True
        
        return False
    
    def _handle_mode_switch(self, cmd: str, args: List[str]):
        """处理模式切换"""
        if not args:
            if cmd == 'cd':
                if self._go_back_mode():
                    self._show_mode_info()
                else:
                    print("\n已在最顶层模式")
            return
        
        mode = args[0]
        
        if mode == '..':
            if self._go_back_mode():
                self._show_mode_info()
            else:
                print("\n已在最顶层模式")
        elif mode in ['find_file', 'find_content', 'find_vec', 'find_vec_ai', 'open_file', 'recommend', 'summary', 'favorite', 'tag']:
            self._change_mode(mode)
            self._show_mode_info()
        else:
            print(f"\n不支持的模式: {mode}")
    
    def _handle_mode_input(self, user_input: str):
        """处理模式输入"""
        mode_handlers = {
            'find_file': self._find_by_filename,
            'find_content': self._find_by_content,
            'find_vec': self._find_vec,
            'find_vec_ai': self._find_vec_ai,
            'open_file': self._open_file,
            'recommend': self._mode_recommend,
            'summary': self._mode_summary,
            'favorite': self._mode_favorite,
            'tag': self._mode_tag
        }
        
        handler = mode_handlers.get(self.current_mode)
        if handler:
            handler(user_input)
    
    def _handle_main_input(self, user_input: str):
        """处理主模式输入"""
        if self.kb is None:
            print("知识库未初始化")
            return
        
        print("\n正在查询...")
        start_time = time.time()
        
        if hasattr(self.kb, 'vector_store') and hasattr(self.kb.vector_store, 'search'):
            results = self.kb.vector_store.search(user_input, top_k=5)
        else:
            query_result = self.kb.query(user_input, top_k=5)
            results = query_result.get('results', [])
        
        elapsed = time.time() - start_time
        
        if results:
            self.last_results = results
            print(f"\n找到 {len(results)} 条相关结果 (耗时: {elapsed:.2f}秒)")
            
            for i, result in enumerate(results, 1):
                print(f"\n【结果{i}】")
                print(f"  文件: {result.get('file_name', '未知')}")
                print(f"  类型: {result.get('problem_type', '未知')}")
                print(f"  相似度: {result.get('score', 0):.4f}")
                
                content = result.get('content', '')
                print(f"  内容: {content[:200]}...")
        else:
            print("\n未找到相关结果")
    
    def _show_help(self):
        """显示帮助"""
        print("\n" + "=" * 70)
        print("帮助信息")
        print("=" * 70)
        print("\n基础命令:")
        print("  help        - 显示此帮助")
        print("  history     - 显示历史命令")
        print("  alias       - 显示命令别名")
        print("  stats       - 显示统计信息")
        print("  clear       - 清屏")
        print("  quit        - 退出系统")
        
        print("\n查询命令:")
        print("  find_file <文件名>     - 按文件名查找")
        print("  find_content <关键字>  - 按内容查找")
        print("  find_vec <问题>        - 向量查找")
        print("  find_vec_ai <问题>     - 智能查询")
        print("  open_file <文件名>     - 打开文件")
        
        print("\n增强功能:")
        print("  recommend <文件路径>   - 推荐相关文件")
        print("  summary <文件路径>     - 生成摘要")
        print("  compare <文件1> <文件2> - 对比文件")
        print("  export [csv|excel|json] - 导出结果")
        print("  page [next|prev|<页号>] - 分页浏览")
        print("  copy [n]               - 复制第n条结果路径")
        
        print("\n收藏和标签:")
        print("  favorite add <文件路径> - 添加收藏")
        print("  favorite list          - 列出收藏")
        print("  tag add <文件> <标签>  - 添加标签")
        print("  tag list               - 列出标签")
        
        print("\n系统管理:")
        print("  backup create          - 创建备份")
        print("  backup list            - 列出备份")
        print("  trend                  - 趋势分析")
        print("  user login <用户名>    - 登录")
        print("  api                    - 启动API服务")
        print("=" * 70)
    
    def _show_stats(self):
        """显示统计"""
        if self.kb is None:
            print("知识库未初始化")
            return
        
        stats = self.kb.get_statistics()
        
        print("\n" + "=" * 70)
        print("知识库统计信息")
        print("=" * 70)
        print(f"文档总数: {stats.get('total_documents', 0)}")
        print(f"问题类型数: {len(stats.get('type_distribution', {}))}")
        
        cache_stats = self.cache.get_stats()
        print(f"\n缓存统计:")
        print(f"  内存缓存: {cache_stats['memory_items']} 项")
        print(f"  磁盘缓存: {cache_stats['disk_items']} 项")
        print(f"  磁盘大小: {cache_stats['disk_size_mb']:.2f} MB")
        
        print(f"\n收藏数: {len(self.favorites.list_all())}")
        print(f"标签数: {len(self.tags.list_all_tags())}")
        print("=" * 70)
    
    def _show_categories(self):
        """显示分类"""
        if self.kb is None:
            print("知识库未初始化")
            return
        
        stats = self.kb.get_statistics()
        type_dist = stats.get('type_distribution', {})
        
        print("\n问题分类列表:")
        print("-" * 40)
        
        sorted_types = sorted(type_dist.items(), key=lambda x: x[1], reverse=True)
        for i, (type_name, count) in enumerate(sorted_types, 1):
            print(f"  {i:3d}. {type_name}: {count}")
        
        print("-" * 40)
    
    def _handle_export(self, args: List[str]):
        """处理导出"""
        if not self.last_results:
            print("没有可导出的结果")
            return
        
        format = args[0] if args else 'json'
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"export_{timestamp}.{format}"
        
        if format == 'csv':
            ResultExporter.to_csv(self.last_results, filename)
        elif format == 'excel':
            ResultExporter.to_excel(self.last_results, filename)
        elif format == 'json':
            ResultExporter.to_json(self.last_results, filename)
        else:
            print(f"不支持的格式: {format}")
    
    def _handle_favorite(self, args: List[str]):
        """处理收藏"""
        if not args:
            self.favorites.show()
            return
        
        action = args[0]
        
        if action == 'add' and len(args) > 1:
            file_path = ' '.join(args[1:])
            self.favorites.add(file_path, os.path.basename(file_path))
        elif action == 'remove' and len(args) > 1:
            file_path = ' '.join(args[1:])
            self.favorites.remove(file_path)
        elif action == 'list':
            self.favorites.show()
        else:
            print("用法: favorite add/remove/list")
    
    def _handle_tag(self, args: List[str]):
        """处理标签"""
        if not args:
            self.tags.show()
            return
        
        action = args[0]
        
        if action == 'add' and len(args) >= 3:
            file_path = args[1]
            tag = args[2]
            self.tags.add_tag(file_path, tag)
        elif action == 'remove' and len(args) >= 3:
            file_path = args[1]
            tag = args[2]
            self.tags.remove_tag(file_path, tag)
        elif action == 'list':
            self.tags.show()
        else:
            print("用法: tag add/remove/list")
    
    def _handle_recommend(self, args: List[str]):
        """处理推荐"""
        if not args:
            print("用法: recommend <文件路径>")
            return
        
        file_path = ' '.join(args)
        
        if self.recommender is None:
            print("推荐系统未初始化")
            return
        
        print("\n正在分析...")
        results = self.recommender.recommend_related(file_path)
        
        if results.get('similar'):
            print("\n相似文件:")
            for i, r in enumerate(results['similar'][:5], 1):
                print(f"  {i}. {r.get('file_name', '未知')}")
        
        if results.get('same_type'):
            print("\n同类型文件:")
            for i, r in enumerate(results['same_type'][:5], 1):
                print(f"  {i}. {r.get('file_name', '未知')}")
    
    def _handle_summary(self, args: List[str]):
        """处理摘要"""
        if not args:
            print("用法: summary <文件路径>")
            return
        
        file_path = ' '.join(args)
        
        if self.summarizer is None:
            print("摘要系统未初始化")
            return
        
        print("\n正在生成摘要...")
        result = self.summarizer.summarize_file(file_path)
        
        print(f"\n文件: {result.get('file_path', '未知')}")
        print(f"类型: {result.get('problem_type', '未知')}")
        print(f"\n摘要:\n{result.get('summary', '无')}")
        
        if result.get('key_points'):
            print("\n关键点:")
            for i, point in enumerate(result['key_points'], 1):
                print(f"  {i}. {point}")
    
    def _handle_backup(self, args: List[str]):
        """处理备份"""
        if not args:
            print("用法: backup create/list/restore/delete")
            return
        
        action = args[0]
        
        if action == 'create':
            print("\n正在创建备份...")
            path = self.backup_mgr.create_backup(self.redis_client)
            if path:
                print(f"备份成功: {path}")
        
        elif action == 'list':
            backups = self.backup_mgr.list_backups()
            print(f"\n备份列表 ({len(backups)} 个):")
            for b in backups:
                print(f"  - {b['name']}: {b['document_count']} 个文档")
        
        elif action == 'restore' and len(args) > 1:
            name = args[1]
            print(f"\n正在恢复备份: {name}")
            self.backup_mgr.restore_backup(self.redis_client, name)
        
        elif action == 'delete' and len(args) > 1:
            name = args[1]
            self.backup_mgr.delete_backup(name)
        
        else:
            print("用法: backup create/list/restore/delete <名称>")
    
    def _handle_trend(self):
        """处理趋势分析"""
        if self.kb is None:
            print("知识库未初始化")
            return
        
        analyzer = TrendAnalyzer(self.kb)
        report = analyzer.generate_report()
        print(report)
    
    def _handle_user(self, args: List[str]):
        """处理用户管理"""
        if not args:
            user_info = self.users.get_current_user_info()
            if user_info:
                print(f"\n当前用户: {user_info['username']}")
                print(f"角色: {user_info['role']}")
                print(f"登录次数: {user_info['login_count']}")
            else:
                print("\n未登录")
            return
        
        action = args[0]
        
        if action == 'login' and len(args) >= 3:
            username = args[1]
            password = args[2]
            if self.users.login(username, password):
                print(f"登录成功: {username}")
            else:
                print("登录失败")
        
        elif action == 'logout':
            self.users.logout()
            print("已登出")
        
        elif action == 'list':
            users = self.users.list_users()
            print(f"\n用户列表 ({len(users)} 个):")
            for u in users:
                print(f"  - {u['username']} ({u['role']})")
        
        else:
            print("用法: user login/logout/list")
    
    def _handle_page(self, args: List[str]):
        """处理分页"""
        if not self.last_results:
            print("没有结果")
            return
        
        self.paginator.set_results(self.last_results)
        
        if not args:
            page_results = self.paginator.get_current_page()
            print(f"\n{self.paginator.get_page_info()}")
            for i, r in enumerate(page_results, 1):
                print(f"  {i}. {r.get('file_name', '未知')}")
        
        elif args[0] == 'next':
            results = self.paginator.next_page()
            if results:
                print(f"\n{self.paginator.get_page_info()}")
                for i, r in enumerate(results, 1):
                    print(f"  {i}. {r.get('file_name', '未知')}")
        
        elif args[0] == 'prev':
            results = self.paginator.prev_page()
            if results:
                print(f"\n{self.paginator.get_page_info()}")
                for i, r in enumerate(results, 1):
                    print(f"  {i}. {r.get('file_name', '未知')}")
        
        elif args[0].isdigit():
            page = int(args[0]) - 1
            results = self.paginator.go_to_page(page)
            if results:
                print(f"\n{self.paginator.get_page_info()}")
                for i, r in enumerate(results, 1):
                    print(f"  {i}. {r.get('file_name', '未知')}")
    
    def _handle_copy(self, args: List[str]):
        """处理复制"""
        if not self.last_results:
            print("没有结果")
            return
        
        index = int(args[0]) - 1 if args and args[0].isdigit() else 0
        
        if 0 <= index < len(self.last_results):
            file_path = self.last_results[index].get('file_path', '')
            if file_path:
                self.clipboard.copy(file_path)
            else:
                print("文件路径为空")
    
    def _handle_compare(self, args: List[str]):
        """处理对比"""
        if len(args) < 2:
            print("用法: compare <文件1> <文件2>")
            return
        
        file1 = args[0]
        file2 = args[1]
        
        if self.file_comparator is None:
            print("对比系统未初始化")
            return
        
        print("\n正在对比...")
        result = self.file_comparator.compare(file1, file2)
        
        print(f"\n相似度: {result.get('similarity', 0):.2%}")
        
        if result.get('common_points'):
            print("\n共同点:")
            for point in result['common_points'][:5]:
                print(f"  - {point[:50]}...")
    
    def _start_api_server(self):
        """启动API服务"""
        try:
            from api_server import init_app, run_server
            
            init_app(self.kb, None, self)
            
            print("\n正在启动API服务...")
            print("访问地址: http://localhost:5000")
            print("按 Ctrl+C 停止服务")
            
            run_server(port=5000, debug=False)
        
        except ImportError as e:
            print(f"无法启动API服务: {e}")
            print("请确保已安装: pip install flask flask-cors")
    
    def _find_by_filename(self, filename: str):
        """按文件名查找"""
        if self.kb is None:
            print("知识库未初始化")
            return
        
        results = self.kb.find_document_by_filename(filename)
        
        if results:
            self.last_results = results
            print(f"\n找到 {len(results)} 个文件")
            for i, r in enumerate(results, 1):
                print(f"  {i}. {r.get('file_name', '未知')}")
        else:
            print("\n未找到文件")
    
    def _find_by_content(self, keywords: str):
        """按内容查找"""
        if self.kb is None:
            print("知识库未初始化")
            return
        
        keyword_list = keywords.split()
        results = self.kb.find_by_content(keyword_list)
        
        if results:
            self.last_results = results
            print(f"\n找到 {len(results)} 个结果")
            for i, r in enumerate(results, 1):
                print(f"  {i}. {r.get('file_name', '未知')}")
        else:
            print("\n未找到结果")
    
    def _find_vec(self, query: str):
        """向量查找"""
        self._handle_main_input(query)
    
    def _find_vec_ai(self, query: str):
        """智能查询"""
        if self.smart_qa is None:
            self._handle_main_input(query)
            return
        
        print("\n正在分析...")
        result = self.smart_qa.ask(query)
        
        print(f"\n回答:\n{result.get('answer', '无')}")
        
        if result.get('sources'):
            self.last_results = result['sources']
            print(f"\n参考来源: {len(result['sources'])} 个")
    
    def _open_file(self, filename: str):
        """打开文件"""
        if self.kb is None:
            print("知识库未初始化")
            return
        
        results = self.kb.find_document_by_filename(filename)
        
        if not results:
            print("\n未找到文件")
            return
        
        if len(results) == 1:
            file_path = results[0].get('file_path', '')
            if file_path:
                self._open_file_with_system(file_path)
            else:
                print("文件路径为空")
            return
        
        print(f"\n找到 {len(results)} 个文件:")
        for i, r in enumerate(results, 1):
            print(f"  {i}. {r.get('file_name', '未知')}")
        
        choice = input("\n选择文件序号: ").strip()
        try:
            index = int(choice) - 1
            if 0 <= index < len(results):
                file_path = results[index].get('file_path', '')
                self._open_file_with_system(file_path)
        except:
            print("无效选择")
    
    def _open_file_with_system(self, file_path: str):
        """使用系统打开文件"""
        import platform
        
        if not os.path.exists(file_path):
            print(f"文件不存在: {file_path}")
            return
        
        try:
            if platform.system() == 'Windows':
                os.startfile(file_path)
            elif platform.system() == 'Darwin':
                os.system(f'open "{file_path}"')
            else:
                os.system(f'xdg-open "{file_path}"')
            
            print(f"已打开: {os.path.basename(file_path)}")
        except Exception as e:
            print(f"打开失败: {e}")
    
    def _mode_recommend(self, user_input: str):
        """推荐模式"""
        self._handle_recommend(user_input.split())
    
    def _mode_summary(self, user_input: str):
        """摘要模式"""
        self._handle_summary(user_input.split())
    
    def _mode_favorite(self, user_input: str):
        """收藏模式"""
        self._handle_favorite(user_input.split())
    
    def _mode_tag(self, user_input: str):
        """标签模式"""
        self._handle_tag(user_input.split())


def main():
    """主函数"""
    query = EnhancedInteractiveQuery()
    query.start()


if __name__ == '__main__':
    main()
