# -*- coding: utf-8 -*-
"""
沃工单知识库交互式查询工具 V3
支持动态输入问题并获取解决方案
- 关键词精确搜索（订单号、手机号）
- 向量语义搜索
- 自动识别查询类型
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
from typing import List, Dict

# 设置环境变量（Windows）
if sys.platform == 'win32':
    os.environ['PYTHONIOENCODING'] = 'utf-8'

# 禁用GPU警告
warnings.filterwarnings('ignore', message='Neither CUDA nor MPS are available')

from config import ZHIPU_CONFIG, update_config, REDIS_CONFIG
from knowledge_base import KnowledgeBase

logging.basicConfig(
    level=logging.WARNING,
    format='%(asctime)s - %(levelname)s - %(message)s'
)


class InteractiveQuery:
    """交互式查询工具 - 支持关键词和向量混合搜索"""
    
    def __init__(self):
        self.kb = None
        self.llm_enabled = False
        self.redis_client = None
        self._connect_redis()
        self.init_thread = None
        self.is_initializing = False
        self.current_mode = 'main'  # 当前模式: main, find_file, find_content, find_vec, find_vec_ai, open_file
        self.mode_stack = []  # 模式栈，用于cd命令
    
    def _highlight_text(self, text: str, keywords: List[str], color_code: str = '93') -> str:
        """
        高亮显示文本中的关键字
        
        Args:
            text: 原始文本
            keywords: 需要高亮的关键字列表
            color_code: ANSI颜色代码（默认黄色）
            
        Returns:
            高亮后的文本
        """
        if not text or not keywords:
            return text
        
        highlighted = text
        for keyword in keywords:
            if keyword:
                # 使用ANSI颜色代码高亮
                highlighted = highlighted.replace(
                    keyword, 
                    f'\033[{color_code}m{keyword}\033[0m'
                )
        
        return highlighted
    
    def _change_mode(self, new_mode: str):
        """切换模式"""
        if new_mode != self.current_mode:
            self.mode_stack.append(self.current_mode)
            self.current_mode = new_mode
    
    def _go_back_mode(self):
        """返回上一级模式"""
        if self.mode_stack:
            self.current_mode = self.mode_stack.pop()
            return True
        return False
    
    def _connect_redis(self):
        """连接Redis"""
        try:
            self.redis_client = redis.Redis(**REDIS_CONFIG)
            self.redis_client.ping()
        except Exception as e:
            print(f"Redis连接失败: {e}")
            sys.exit(1)
    
    def start(self):
        """启动交互式查询"""
        self._print_welcome()
        self._init_knowledge_base()
        self._check_llm_config()
        self._run_loop()
    
    def _print_welcome(self):
        """打印欢迎信息"""
        print("\n" + "=" * 70)
        print(" " * 20 + "沃工单知识库查询系统 V3")
        print("=" * 70)
        print("\n功能说明:")
        print("  - 支持状态切换，无需重复输入命令")
        print("  - 输入问题进行智能查询，系统将返回相关解决方案")
        print("  - 支持订单号、手机号精确查询")
        print("  - 支持按问题类型筛选查询结果")
        print("  - 可配置智普大模型增强分析能力")
        print("\n命令列表:")
        print("  help        - 显示帮助信息")
        print("  categories  - 显示问题分类列表")
        print("  stats       - 显示知识库统计信息")
        print("  config      - 配置智普大模型API Key")
        print("  init        - 初始化知识库（全量重建）")
        print("  rebuild     - 重建知识库（增量更新）")
        print("  find_file   - 按文件名查找文件")
        print("  find_content - 按内容关键字精确查找")
        print("  find_vec    - 向量查找（不调用大模型）")
        print("  find_vec_ai - 向量+大模型智能查询")
        print("  open_file   - 打开指定文件")
        print("  su <模式>   - 切换到指定模式")
        print("  cd          - 返回上一级模式")
        print("  quit/exit   - 退出系统")
        print("=" * 70 + "\n")
    
    def _get_prompt(self) -> str:
        """根据当前模式获取提示符"""
        if self.current_mode == 'main':
            return "请输入问题 > "
        elif self.current_mode == 'find_file':
            return "find_file > "
        elif self.current_mode == 'find_content':
            return "find_content > "
        elif self.current_mode == 'find_vec':
            return "find_vec > "
        elif self.current_mode == 'find_vec_ai':
            return "find_vec_ai > "
        elif self.current_mode == 'open_file':
            return "open_file > "
        else:
            return "请输入问题 > "
    
    def _show_mode_info(self):
        """显示当前模式信息"""
        if self.current_mode == 'main':
            print("\n当前模式: 主模式")
            print("使用 su 命令切换到其他模式:")
            print("  su find_file   - 切换到文件查找模式")
            print("  su find_content - 切换到内容查找模式")
            print("  su find_vec    - 切换到向量查找模式")
            print("  su find_vec_ai - 切换到智能查询模式")
            print("  su open_file   - 切换到文件打开模式")
        elif self.current_mode == 'find_file':
            print("\n当前模式: 文件查找模式")
            print("使用 cd 命令返回主模式")
            print("直接输入文件名或路径进行查找")
        elif self.current_mode == 'find_content':
            print("\n当前模式: 内容查找模式")
            print("使用 cd 命令返回主模式")
            print("直接输入关键字进行查找")
        elif self.current_mode == 'find_vec':
            print("\n当前模式: 向量查找模式")
            print("使用 cd 命令返回主模式")
            print("直接输入问题进行向量搜索")
        elif self.current_mode == 'find_vec_ai':
            print("\n当前模式: 智能查询模式")
            print("使用 cd 命令返回主模式")
            print("直接输入问题进行智能查询")
        elif self.current_mode == 'open_file':
            print("\n当前模式: 文件打开模式")
            print("使用 cd 命令返回主模式")
            print("直接输入文件名打开文件")
        print("-" * 40)
    
    def _init_knowledge_base(self):
        """初始化知识库（不自动构建数据）"""
        print("正在初始化知识库...")
        try:
            print("  - 检查Redis连接...")
            import redis
            r = redis.Redis(
                host='127.0.0.1',
                password='RedUssTest',
                port=6380,
                db=0
            )
            r.ping()
            print("  - Redis连接成功")
            
            print("  - 创建知识库对象...")
            self.kb = KnowledgeBase(use_llm=False)
            print("  - 知识库对象创建成功")
            
            # 检查索引是否存在
            stats = self.kb.get_statistics()
            total_docs = stats.get('total_documents', 0)
            
            if total_docs > 0:
                print(f"  - 检测到已有索引，共 {total_docs} 条记录")
                print("  - 提示: 使用 'rebuild' 命令进行增量更新")
                print("  - 提示: 使用 'init' 命令进行全量重建\n")
            else:
                print("  - 检测到无索引，请使用 'init' 命令初始化数据\n")
                
        except redis.exceptions.ConnectionError as e:
            print(f"\nRedis连接失败: {str(e)}")
            print("请确保Redis Stack服务已启动，配置如下:")
            print("  host: 127.0.0.1")
            print("  port: 6380")
            print("  password: RedUssTest")
            sys.exit(1)
        except Exception as e:
            print(f"知识库初始化出错: {str(e)}")
            import traceback
            traceback.print_exc()
            print("\n提示: 模型加载可能需要较长时间，请耐心等待")
            print("  - 如果长时间无响应，请使用 'init' 命令重新初始化\n")
    
    def _check_llm_config(self):
        """检查智普大模型配置"""
        if ZHIPU_CONFIG.get('api_key'):
            self._enable_llm(ZHIPU_CONFIG['api_key'])
    
    def _enable_llm(self, api_key: str):
        """启用智普大模型"""
        try:
            self.kb.configure_llm(api_key, ZHIPU_CONFIG.get('model', 'glm-4'))
            self.llm_enabled = True
            print("智普大模型已启用，将提供AI增强分析\n")
        except Exception as e:
            print(f"智普大模型配置失败: {str(e)}\n")
    
    def _run_loop(self):
        """运行交互循环"""
        while True:
            try:
                prompt = self._get_prompt()
                user_input = input(prompt).strip()
                
                if not user_input:
                    continue
                
                if user_input.lower() in ['quit', 'exit', 'q']:
                    self._quit()
                    break
                
                if user_input.lower() == 'help':
                    self._show_help()
                    continue
                
                if user_input.lower() == 'categories':
                    self._show_categories()
                    continue
                
                if user_input.lower() == 'stats':
                    self._show_stats()
                    continue
                
                if user_input.lower() == 'config':
                    self._config_llm()
                    continue
                
                if user_input.lower() == 'rebuild':
                    self._rebuild()
                    continue
                
                if user_input.lower() == 'init':
                    if self.is_initializing:
                        print("\n初始化过程正在执行中，请稍后再试...")
                    else:
                        self._init()
                    continue
                
                # 模式切换命令
                if user_input.lower().startswith('su ') or user_input.lower().startswith('cd '):
                    parts = user_input.lower().split(' ', 1)
                    if len(parts) > 1:
                        mode = parts[1].strip()
                        if mode == '..':
                            # su .. 或 cd .. 返回上一级
                            if self._go_back_mode():
                                print(f"\n已返回 {self.current_mode} 模式")
                                self._show_mode_info()
                            else:
                                print("\n已在最顶层模式")
                        elif mode in ['find_file', 'find_content', 'find_vec', 'find_vec_ai', 'open_file']:
                            self._change_mode(mode)
                            self._show_mode_info()
                        else:
                            print(f"\n错误: 不支持的模式 '{mode}'")
                            print("可用模式: find_file, find_content, find_vec, find_vec_ai, open_file")
                    else:
                        # cd 或 su 返回上一级
                        if user_input.lower() == 'cd' or user_input.lower() == 'su':
                            if self._go_back_mode():
                                print(f"\n已返回 {self.current_mode} 模式")
                                self._show_mode_info()
                            else:
                                print("\n已在最顶层模式")
                        else:
                            print("\n错误: 请指定模式")
                            print("用法: su <模式> 或 cd <模式>")
                    continue
                
                # 根据当前模式处理输入
                if self.current_mode == 'find_file':
                    self._find_by_filename(user_input)
                    continue
                    
                if self.current_mode == 'find_content':
                    self._find_by_content(user_input)
                    continue
                    
                if self.current_mode == 'find_vec':
                    self._find_vec(user_input)
                    continue
                    
                if self.current_mode == 'find_vec_ai':
                    self._find_vec_ai(user_input)
                    continue
                    
                if self.current_mode == 'open_file':
                    self._open_file(user_input)
                    continue
                
                # 主模式下的传统命令
                if user_input.lower() == 'find_file':
                    self._change_mode('find_file')
                    self._show_mode_info()
                    continue
                
                if user_input.lower() == 'find_content':
                    self._change_mode('find_content')
                    self._show_mode_info()
                    continue
                
                if user_input.lower() == 'find_vec':
                    self._change_mode('find_vec')
                    self._show_mode_info()
                    continue
                
                if user_input.lower() == 'find_vec_ai':
                    self._change_mode('find_vec_ai')
                    self._show_mode_info()
                    continue
                
                if user_input.lower() == 'open_file':
                    self._change_mode('open_file')
                    self._show_mode_info()
                    continue
                
                if user_input.lower() == 'test':
                    """测试实时统计功能"""
                    print("\n  测试实时统计功能")
                    print(" ---------------------------------------- ")
                    
                    # 清空现有数据
                    print("  - 清空现有数据...")
                    self.kb.clear_all()
                    
                    # 检查初始统计
                    stats = self.kb.get_statistics()
                    print(f"  - 初始统计: {stats['total_documents']} 条")
                    
                    # 创建测试文档
                    test_docs = [
                        {
                            'file_path': 'test1.txt',
                            'file_name': 'test1.txt',
                            'content': '测试文档1，这是一个测试文档',
                            'problem_id': 'test1',
                            'problem_type': '测试类型'
                        },
                        {
                            'file_path': 'test2.txt',
                            'file_name': 'test2.txt',
                            'content': '测试文档2，这是另一个测试文档',
                            'problem_id': 'test2',
                            'problem_type': '测试类型'
                        },
                        {
                            'file_path': 'test3.txt',
                            'file_name': 'test3.txt',
                            'content': '测试文档3，这是第三个测试文档',
                            'problem_id': 'test3',
                            'problem_type': '测试类型'
                        }
                    ]
                    
                    # 逐个添加文档并检查统计
                    for i, doc in enumerate(test_docs, 1):
                        print(f"  - 添加文档 {i}: {doc['file_name']}")
                        count = self.kb.vector_store.add_documents([doc])
                        print(f"  - 成功添加 {count} 个文档")
                        
                        # 检查统计
                        stats = self.kb.get_statistics()
                        print(f"  - 当前统计: {stats['total_documents']} 条")
                        
                    print("\n  测试完成！")
                    print()
                    continue
                
                # 主模式下的智能查询
                self._query(user_input)
                
            except KeyboardInterrupt:
                print("\n")
                self._quit()
                break
            except Exception as e:
                print(f"\n发生错误: {str(e)}")
    
    def _search_by_keyword(self, keyword: str, top_k: int = 10) -> List[Dict]:
        """
        基于关键词的精确搜索
        适用于订单号、号码等精确查询
        """
        results = []
        
        # 1. 直接搜索包含关键词的文档
        try:
            from redis.commands.search.query import Query
            
            # 转义特殊字符
            escaped_keyword = keyword.replace('"', '\\"')
            query_str = f'@content:"{escaped_keyword}"'
            
            query_obj = Query(query_str) \
                .return_fields("problem_id", "problem_type", "file_name", "content", "solution") \
                .paging(0, top_k)
            
            search_results = self.redis_client.ft("workorder_knowledge_idx").search(query_obj)
            
            for doc in search_results.docs:
                results.append({
                    'problem_id': getattr(doc, 'problem_id', ''),
                    'problem_type': getattr(doc, 'problem_type', '未知'),
                    'file_name': getattr(doc, 'file_name', ''),
                    'content': getattr(doc, 'content', '')[:500],
                    'solution': getattr(doc, 'solution', ''),
                    'match_type': '精确匹配',
                    'similarity': 1.0
                })
        except Exception as e:
            pass
        
        # 2. 如果精确匹配没找到，尝试模糊匹配
        if not results:
            try:
                # 扫描所有key进行模糊匹配
                pattern = keyword[:6] if len(keyword) > 6 else keyword
                for key in self.redis_client.scan_iter(match=f"workorder:*"):
                    try:
                        doc = self.redis_client.json().get(key)
                        if doc and pattern in str(doc.get('content', '')):
                            results.append({
                                'problem_id': doc.get('problem_id', ''),
                                'problem_type': doc.get('problem_type', '未知'),
                                'file_name': doc.get('file_name', ''),
                                'content': doc.get('content', '')[:500],
                                'solution': doc.get('solution', ''),
                                'match_type': '模糊匹配',
                                'similarity': 0.8
                            })
                            if len(results) >= top_k:
                                break
                    except:
                        continue
            except Exception as e:
                pass
        
        return results
    
    def _search_by_vector(self, query: str, top_k: int = 5) -> List[Dict]:
        """向量语义搜索"""
        response = self.kb.query(query, top_k=top_k)
        # 检查是否有错误
        if response.get('error'):
            return response  # 返回包含错误的字典
        return response.get('results', [])
    
    def _query(self, question: str):
        """执行查询 - 智能选择搜索策略"""
        problem_type = None
        
        # 检查是否按类型筛选
        if question.startswith('type:'):
            parts = question.split(' ', 1)
            if len(parts) == 2:
                problem_type = parts[0].replace('type:', '')
                question = parts[1]
                print(f"\n按类型筛选: {problem_type}")
        
        print(f"\n正在查询: {question}")
        print("-" * 70)
        
        start_time = datetime.now()
        results = []
        
        # 判断查询类型
        # 1. 订单号/数字ID查询
        order_pattern = r'\b\d{10,20}\b'
        orders = re.findall(order_pattern, question)
        
        # 2. 手机号查询
        phone_pattern = r'1[3-9]\d{9}'
        phones = re.findall(phone_pattern, question)
        
        # 3. 问题ID查询
        problem_pattern = r'问题[：:]?\s*(\d+)'
        problem_ids = re.findall(problem_pattern, question)
        
        search_keywords = orders + phones + problem_ids
        
        # 首先调用knowledge_base.query()获取智普大模型的分析结果
        query_start_time = time.time()
        print("正在进行AI智能分析...")
        response = self.kb.query(question, problem_type, top_k=5)
        query_elapsed = time.time() - query_start_time
        
        # 打印总耗时
        print(f"\n查询总耗时: {query_elapsed:.2f}秒")
        
        # 打印各项耗时
        if response.get('vector_search_time'):
            print(f"  - 向量搜索耗时: {response.get('vector_search_time'):.3f}秒")
        if response.get('llm_analysis_time'):
            print(f"  - 大模型分析耗时: {response.get('llm_analysis_time'):.3f}秒")
        
        # 检查是否有错误
        if response.get('error'):
            print(f"\n{response['error']}")
            return
        
        # 获取查询结果
        results = response.get('results', [])
        
        # 显示智普大模型的AI分析结果
        if response.get('ai_solution'):
            print("\n" + "=" * 70)
            print("AI智能分析")
            print("=" * 70)
            ai_solution = response['ai_solution']
            print(ai_solution)
            print("=" * 70)
            
            # 显示参考文档信息
            if response.get('reference_docs'):
                print("\n" + "=" * 70)
                print("参考文档")
                print("=" * 70)
                for doc in response['reference_docs']:
                    print(f"\n【参考文档{doc['index']}】")
                    print(f"  文件名: {doc['file_name']}")
                    print(f"  来源: {doc['source']}")
                    print(f"  相似度: {doc['similarity']:.2%}")
                    print(f"  内容摘要: {doc['content']}")
                print("=" * 70)
        
        # 如果没有找到结果，尝试关键词搜索
        if not results and search_keywords:
            print(f"\n未找到语义匹配结果，尝试关键词搜索: {search_keywords}")
            for keyword in search_keywords:
                keyword_results = self._search_by_keyword(keyword)
                results.extend(keyword_results)
            
            # 去重
            seen = set()
            unique_results = []
            for r in results:
                key = r.get('file_name', '')
                if key not in seen:
                    seen.add(key)
                    unique_results.append(r)
            results = unique_results
        
        elapsed = (datetime.now() - start_time).total_seconds()
        
        print(f"\n查询完成，耗时 {elapsed:.3f} 秒，找到 {len(results)} 条相关记录")
        
        if results:
            self._print_results_v2(results)
        else:
            print("\n未找到相关解决方案")
            print("建议:")
            print("  1. 检查订单号/手机号是否输入正确")
            print("  2. 尝试使用不同的关键词")
            print("  3. 使用更具体的问题描述")
            print("  4. 查看问题分类后按类型查询")
    
    def _print_results_v2(self, results: List[Dict]):
        """打印查询结果（增强版）"""
        print("\n" + "=" * 70)
        print("查询结果")
        print("=" * 70)
        
        for i, result in enumerate(results[:5], 1):
            print(f"\n【结果 {i}】{result.get('match_type', '语义匹配')}")
            print(f"  问题类型: {result.get('problem_type', '未知')}")
            if result.get('problem_id'):
                print(f"  问题ID: {result.get('problem_id')}")
            print(f"  文件名: {result.get('file_name', '未知')}")
            
            if result.get('solution'):
                print(f"\n  解决方案:")
                solution = result['solution']
                if len(solution) > 300:
                    print(f"    {solution[:300]}...")
                else:
                    print(f"    {solution}")
            else:
                print(f"\n  问题内容:")
                content = result.get('content', '')
                if len(content) > 300:
                    print(f"    {content[:300]}...")
                else:
                    print(f"    {content}")
            print("-" * 70)
    
    def _show_help(self):
        """显示帮助信息"""
        print("\n" + "=" * 70)
        print("帮助信息")
        print("=" * 70)
        print("\n查询方式:")
        print("  1. 直接输入问题，如: 开户报错如何处理")
        print("  2. 按类型查询，如: type:开户报错 用户办理失败")
        
        # 从向量库实时获取问题分类
        categories = self.kb.get_categories()
        print("\n问题分类 (从向量库实时统计):")
        for i, cat in enumerate(categories, 1):
            print(f"  {i:2d}. {cat}")
        
        print("\n命令说明:")
        print("  help        - 显示本帮助信息")
        print("  categories  - 显示问题分类列表")
        print("  stats       - 显示知识库统计信息")
        print("  config      - 配置智普大模型API Key")
        print("  rebuild     - 重建知识库索引")
        print("  quit/exit   - 退出系统")
        print("=" * 70)
    
    def _show_categories(self):
        """显示问题分类"""
        # 从向量库实时获取问题分类
        categories = self.kb.get_categories()
        
        print("\n问题分类列表 (从向量库实时统计):")
        print("-" * 40)
        for i, cat in enumerate(categories, 1):
            print(f"  {i:2d}. {cat}")
        print("-" * 40)
        print("使用方式: type:分类名 问题内容")
        print("示例: type:开户报错 用户开户失败")
    
    def _show_stats(self):
        """显示统计信息"""
        stats = self.kb.get_statistics()
        print("\n知识库统计信息:")
        print("-" * 40)
        print(f"  总文档数: {stats['total_documents']}")
        print("-" * 40)
    
    def _find_by_filename(self, filename: str = None):
        """按文件名或完整路径查找文件"""
        if filename is None:
            print("\n" + "=" * 70)
            print("按文件名或完整路径查找文件")
            print("=" * 70)
            print("支持的格式:")
            print("  1. 文件名: 6925120-产品结束服务没有结束的问题.txt")
            print("  2. 完整路径: e:\\AIknowledge\\aiunicom\\data\\6925120-产品结束服务没有结束的问题.txt")
            print("  3. 正斜杠路径: e:/AIknowledge/aiunicom/data/6925120-产品结束服务没有结束的问题.txt")
            print("=" * 70)
            
            filename = input("请输入文件名或完整路径: ").strip()
            
            if not filename:
                print("\n错误: 文件名不能为空")
                print("=" * 70)
                return
        
        print("\n正在查找...")
        results = self.kb.find_document_by_filename(filename)
        
        # 提取文件名中的关键字用于高亮
        import os
        filename_only = os.path.basename(filename)
        keywords = [filename_only] if filename_only else []
        
        # 显示搜索结果
        if results:
            print(f"\n找到 {len(results)} 个匹配的文档:")
            for i, result in enumerate(results, 1):
                print("\n" + "-" * 50)
                print(f"【结果{i}】")
                # 高亮显示文件名
                file_name = result.get('file_name', '未知')
                highlighted_filename = self._highlight_text(file_name, keywords, '96') if keywords else file_name
                print(f"  文件名: {highlighted_filename}")
                print(f"  文件路径: {result.get('file_path', '未知')}")
                print(f"  问题ID: {result.get('problem_id', '未知')}")
                print(f"  问题类型: {result.get('problem_type', '未知')}")
                print(f"  块索引: {result.get('chunk_index', '未知')}/{result.get('total_chunks', '未知')}")
                print(f"  向量维度: {result.get('embedding_length', 0)}")
                print(f"  来源: {result.get('source', '未知')}")
                
                if result.get('content'):
                    content = result['content']
                    content_preview = content[:3000] + '...' if len(content) > 3000 else content
                    print(f"  内容预览: {content_preview}")
                
                if result.get('solution'):
                    solution = result['solution']
                    solution_preview = solution[:50] + '...' if len(solution) > 50 else solution
                    print(f"  解决方案: {solution_preview}")
            
            print("\n" + "=" * 70)
        else:
            print("\n未找到匹配的文件")
        print("=" * 70)
    
    def _open_file(self, filename: str = None):
        """打开指定文件"""
        if filename is None:
            print("\n" + "=" * 70)
            print("打开文件")
            print("=" * 70)
            print("使用说明:")
            print("  - 输入文件名或完整路径")
            print("  - 如果找到多个匹配文件，将让您选择")
            print("  - 如果只有一个匹配文件，将直接打开")
            print("  - 示例: 6925120-产品结束服务没有结束的问题.txt")
            print("=" * 70)
            
            filename = input("请输入文件名或完整路径: ").strip()
            
            if not filename:
                print("\n错误: 文件名不能为空")
                print("=" * 70)
                return
        
        print("\n正在查找文件...")
        results = self.kb.find_document_by_filename(filename)
        
        if not results:
            print("\n未找到匹配的文件")
            print("=" * 70)
            return
        
        # 如果只有一个文件，直接打开
        if len(results) == 1:
            file_path = results[0].get('file_path', '')
            file_name = results[0].get('file_name', '')
            
            # 如果路径为空，提示用户
            if not file_path:
                print(f"\n找到文件: {file_name}")
                print("但文件路径为空，无法打开。")
                print("这可能是因为文件在导入时没有记录完整路径。")
                print("=" * 70)
                return
            
            self._open_file_with_system(file_path)
            return
        
        # 多个文件，让用户选择
        print(f"\n找到 {len(results)} 个匹配的文件:")
        print("-" * 50)
        valid_results = []
        for i, result in enumerate(results, 1):
            file_path = result.get('file_path', '')
            file_name = result.get('file_name', '未知')
            
            # 只显示有路径的文件
            if file_path:
                valid_results.append(result)
                print(f"  {len(valid_results)}. {file_name}")
                print(f"     路径: {file_path}")
                print(f"     类型: {result.get('problem_type', '未知')}")
                print()
            else:
                print(f"  [跳过] {file_name} (路径为空)")
                print()
        
        if not valid_results:
            print("\n所有找到的文件路径都为空，无法打开。")
            print("这可能是因为文件在导入时没有记录完整路径。")
            print("=" * 70)
            return
        
        print("-" * 50)
        choice = input("请选择要打开的文件序号 (1-{}), 或按回车取消: ".format(len(valid_results))).strip()
        
        if not choice:
            print("已取消")
            print("=" * 70)
            return
        
        try:
            index = int(choice) - 1
            if 0 <= index < len(valid_results):
                file_path = valid_results[index].get('file_path', '')
                self._open_file_with_system(file_path)
            else:
                print(f"\n错误: 无效的序号 '{choice}'")
                print("=" * 70)
        except ValueError:
            print(f"\n错误: 请输入有效的数字")
            print("=" * 70)
    
    def _open_file_with_system(self, file_path: str):
        """使用系统默认程序打开文件"""
        import os
        import platform
        
        if not file_path or not os.path.exists(file_path):
            print(f"\n错误: 文件不存在: {file_path}")
            print("=" * 70)
            return
        
        try:
            system = platform.system()
            if system == 'Windows':
                os.startfile(file_path)
            elif system == 'Darwin':  # macOS
                os.system(f'open "{file_path}"')
            else:  # Linux
                os.system(f'xdg-open "{file_path}"')
            
            print(f"\n已打开文件: {file_path}")
            print("=" * 70)
        except Exception as e:
            print(f"\n打开文件失败: {str(e)}")
            print(f"文件路径: {file_path}")
            print("=" * 70)
    
    def _find_vec_ai(self, question: str = None):
        """向量+大模型智能查询"""
        if question is None:
            print("\n" + "=" * 70)
            print("向量+大模型智能查询")
            print("=" * 70)
            print("使用说明:")
            print("  - 输入自然语言问题，系统将进行语义理解")
            print("  - 结合向量相似度搜索和AI分析")
            print("  - 示例: 用户开户失败怎么办")
            print("  - 示例: 套餐变更后费用异常如何处理")
            print("=" * 70)
            
            question = input("请输入问题: ").strip()
            
            if not question:
                print("\n错误: 问题不能为空")
                print("=" * 70)
                return
        
        print("\n正在分析...")
        self._query(question)
    
    def _find_vec(self, question: str = None):
        """向量查找（不调用大模型）"""
        if question is None:
            print("\n" + "=" * 70)
            print("向量查找")
            print("=" * 70)
            print("使用说明:")
            print("  - 输入自然语言问题，系统将进行语义向量搜索")
            print("  - 仅执行向量相似度匹配，不调用大模型分析")
            print("  - 适合需要快速向量搜索的场景")
            print("  - 示例: 用户开户失败怎么办")
            print("  - 示例: 套餐变更后费用异常如何处理")
            print("=" * 70)
            
            question = input("请输入问题: ").strip()
            
            if not question:
                print("\n错误: 问题不能为空")
                print("=" * 70)
                return
        
        print("\n正在执行向量搜索...")
        
        # 只执行向量搜索，不调用大模型
        start_time = datetime.now()
        
        # 检查是否按类型筛选
        problem_type = None
        if question.startswith('type:'):
            parts = question.split(' ', 1)
            if len(parts) == 2:
                problem_type = parts[0].replace('type:', '')
                question = parts[1]
                print(f"\n按类型筛选: {problem_type}")
        
        print(f"查询: {question}")
        print("-" * 70)
        
        # 执行向量搜索
        vector_search_start = time.time()
        try:
            if problem_type:
                results = self.kb.vector_store.search_by_type(question, problem_type, top_k=5)
            else:
                results = self.kb.vector_store.search(question, top_k=5)
        except Exception as e:
            print(f"向量搜索失败: {str(e)}")
            results = []
        
        vector_search_time = time.time() - vector_search_start
        
        # 显示搜索结果
        if results:
            print(f"\n找到 {len(results)} 个相关文档:")
            for i, result in enumerate(results, 1):
                print("\n" + "-" * 50)
                print(f"【结果{i}】")
                print(f"  文件名: {result.get('file_name', '未知')}")
                print(f"  问题类型: {result.get('problem_type', '未知')}")
                print(f"  相似度: {result.get('similarity', 0):.2%}")
                print(f"  来源: {result.get('source', '未知')}")
                
                if result.get('content'):
                    content_preview = result['content'][:300] + '...' if len(result['content']) > 300 else result['content']
                    print(f"  内容摘要: {content_preview}")
                
                if result.get('solution'):
                    solution_preview = result['solution'][:100] + '...' if len(result['solution']) > 100 else result['solution']
                    print(f"  解决方案: {solution_preview}")
            
            print("\n" + "=" * 70)
            print(f"向量搜索耗时: {vector_search_time:.3f}秒")
        else:
            print("\n未找到相关文档")
        
        total_elapsed = (datetime.now() - start_time).total_seconds()
        print(f"总耗时: {total_elapsed:.3f}秒")
        print("=" * 70)
    
    def _find_by_content(self, keywords_input: str = None):
        """按内容关键字精确查找"""
        if keywords_input is None:
            print("\n" + "=" * 70)
            print("按内容关键字精确查找")
            print("=" * 70)
            print("使用说明:")
            print("  - 多个关键字用空格分隔")
            print("  - 带空格的关键字用双引号括起来")
            print("  - 示例1: 开户 失败")
            print("  - 示例2: \"产品结束服务\" 没有结束")
            print("=" * 70)
            
            keywords_input = input("请输入关键字: ").strip()
            
            if not keywords_input:
                print("\n错误: 关键字不能为空")
                print("=" * 70)
                return
        
        # 解析关键字（支持双引号）
        keywords = []
        current_keyword = []
        in_quotes = False
        
        for char in keywords_input:
            if char == '"':
                in_quotes = not in_quotes
                if not in_quotes:
                    keywords.append(''.join(current_keyword).strip())
                    current_keyword = []
            elif char == ' ' and not in_quotes:
                if current_keyword:
                    keywords.append(''.join(current_keyword).strip())
                    current_keyword = []
            else:
                current_keyword.append(char)
        
        if current_keyword:
            keywords.append(''.join(current_keyword).strip())
        
        # 过滤空关键字
        keywords = [k for k in keywords if k]
        
        if not keywords:
            print("\n错误: 关键字不能为空")
            print("=" * 70)
            return
        
        print("\n正在查找...")
        results = self.kb.find_by_content(keywords)
        
        if results:
            print(f"\n找到 {len(results)} 个匹配的文档:")
            for i, result in enumerate(results, 1):
                print("\n" + "-" * 50)
                print(f"【结果{i}】")
                print(f"  文件名: {result.get('file_name', '未知')}")
                print(f"  文件路径: {result.get('file_path', '未知')}")
                print(f"  问题ID: {result.get('problem_id', '未知')}")
                print(f"  问题类型: {result.get('problem_type', '未知')}")
                print(f"  块索引: {result.get('chunk_index', '未知')}/{result.get('total_chunks', '未知')}")
                print(f"  向量维度: {result.get('embedding_length', 0)}")
                print(f"  来源: {result.get('source', '未知')}")
                
                if result.get('content'):
                    content = result['content']
                    content_preview = content[:3000] + '...' if len(content) > 3000 else content
                    # 高亮显示关键字
                    highlighted_content = self._highlight_text(content_preview, keywords)
                    print(f"  内容预览: {highlighted_content}")
                
                if result.get('solution'):
                    solution = result['solution']
                    solution_preview = solution[:50] + '...' if len(solution) > 50 else solution
                    # 高亮显示关键字
                    highlighted_solution = self._highlight_text(solution_preview, keywords)
                    print(f"  解决方案: {highlighted_solution}")
            
            print("\n" + "=" * 70)
        else:
            print("\n未找到匹配的文件")
        print("=" * 70)
    
    def _config_llm(self):
        """配置智普大模型"""
        print("\n配置智普大模型")
        print("-" * 40)
        print("智普大模型可以提供更智能的问题分析和解决方案")
        print("请访问 https://open.bigmodel.cn 获取API Key")
        print("-" * 40)
        
        api_key = input("请输入API Key (直接回车跳过): ").strip()
        if api_key:
            update_config('zhipu', 'api_key', api_key)
            self._enable_llm(api_key)
        else:
            print("已跳过配置")
    
    def _rebuild(self):
        """重建知识库 - 增量更新模式"""
        print("\n" + "=" * 70)
        print("重建知识库（增量更新模式）")
        print("=" * 70)
        print("\n说明:")
        print("  - 系统会自动检测新增或修改的文件")
        print("  - 基于文件路径+文件名+修改时间判断文件是否变更")
        print("  - 只处理变更的文件，未修改的文件自动跳过")
        print("  - 文件指纹30天后自动过期")
        print("=" * 70)
        
        confirm = input("\n确认要开始增量更新吗？(y/n): ").strip().lower()
        if confirm == 'y':
            print("\n开始增量更新...")
            if self.kb.initialize():
                stats = self.kb.get_statistics()
                print(f"\n增量更新完成，当前知识库共 {stats['total_documents']} 条记录")
            else:
                print("\n增量更新失败")
        else:
            print("\n已取消")
    
    def _init(self):
        """初始化知识库 - 全量重建模式（后台执行）"""
        def init_worker():
            try:
                print("\n开始全量重建...")
                print("  - 清空现有数据...")
                self.kb.clear_all()
                
                print("  - 重建索引...")
                self.kb.create_index(force_recreate=True)
                
                print("  - 全量导入数据...")
                success = self.kb.initialize()
                
                self.is_initializing = False
                if success:
                    stats = self.kb.get_statistics()
                    print(f"\n全量重建完成，当前知识库共 {stats['total_documents']} 条记录")
                else:
                    print("\n全量重建失败")
            except Exception as e:
                self.is_initializing = False
                print(f"\n初始化过程出错: {str(e)}")
        
        print("\n" + "=" * 70)
        print("初始化知识库（全量重建模式）")
        print("=" * 70)
        print("\n说明:")
        print("  - 清空所有现有数据和索引")
        print("  - 重建索引结构")
        print("  - 全量导入所有文件")
        print("  - 此操作会在后台执行，您可以使用stats命令查看进度")
        print("=" * 70)
        
        confirm = input("\n确认要清空数据并全量重建吗？(yes/no): ").strip().lower()
        if confirm == 'yes':
            self.is_initializing = True
            self.init_thread = threading.Thread(target=init_worker)
            self.init_thread.daemon = True
            self.init_thread.start()
            print("\n初始化已在后台开始执行...")
            print("可以使用 'stats' 命令查看实时进度")
        else:
            print("\n已取消")
    
    def _quit(self):
        """退出系统"""
        if self.kb:
            self.kb.close()
        print("\n感谢使用沃工单知识库系统，再见！\n")


def main():
    """主函数"""
    query_tool = InteractiveQuery()
    query_tool.start()


if __name__ == "__main__":
    main()
