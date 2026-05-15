# -*- coding: utf-8 -*-
"""
沃工单知识库系统主模块
"""

import os
import sys
import json
import logging
import time
from typing import List, Dict, Optional
from datetime import datetime

# 设置环境变量（Windows）
if sys.platform == 'win32':
    os.environ['PYTHONIOENCODING'] = 'utf-8'

from config import DATA_DIR, ZHIPU_CONFIG
from file_parser import FileParser, extract_solution
from vector_store import RedisVectorStore
from zhipu_llm import ZhipuLLM, configure_zhipu

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('knowledge_base.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)




import time
from functools import wraps

def time_logger(func):
    """性能监控装饰器"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        try:
            result = func(*args, **kwargs)
            elapsed = time.time() - start_time
            logger.info(f"{func.__name__} 执行成功，耗时: {elapsed:.3f}秒")
            return result
        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(f"{func.__name__} 执行失败，耗时: {elapsed:.3f}秒，错误: {e}")
            raise

    return wrapper


class KnowledgeBase:
    """沃工单知识库"""
    
    def __init__(self, data_dir: str = DATA_DIR, use_llm: bool = True, use_zhipu_embedding: bool = False):
        self.data_dir = data_dir
        self.parser = FileParser()
        self.vector_store = RedisVectorStore(use_zhipu=use_zhipu_embedding)
        self.use_llm = use_llm
        self.llm = None
        if use_llm and ZHIPU_CONFIG.get('api_key'):
            self.llm = ZhipuLLM(ZHIPU_CONFIG)
        self.initialized = False
    
    def configure_llm(self, api_key: str, model: str = "glm-4"):
        """配置智普大模型"""
        # 使用完整的ZHIPU_CONFIG配置
        config = ZHIPU_CONFIG.copy()
        config['api_key'] = api_key
        config['model'] = model
        self.llm = ZhipuLLM(config)
        logger.info(f"已配置智普大模型: {model}")
    
    @time_logger
    def initialize(self, force_rebuild: bool = False) -> bool:
        """
        初始化知识库（支持增量更新）
        
        Args:
            force_rebuild: 是否强制重建所有文档
            
        Returns:
            是否成功
        """
        try:
            logger.info("开始构建知识库（增量更新模式）...")
            start_time = time.time()
            
            logger.info(f"正在解析目录: {self.data_dir}")
            documents = self.parser.parse_directory(self.data_dir)
            
            if not documents:
                logger.warning("未找到任何文档")
                return False
            
            success_count = 0
            total_docs = len(documents)
            logger.info(f"找到 {total_docs} 个文档，开始处理...")
            
            # 逐个处理文档并立即添加到知识库
            for i, doc in enumerate(documents, 1):
                try:
                    doc_start_time = time.time()
                    problem_desc, solution = extract_solution(doc['content'])
                    doc['solution'] = solution
                    
                    # 立即添加到知识库
                    count = self.vector_store.add_documents([doc])
                    success_count += count
                    
                    doc_elapsed = time.time() - doc_start_time
                    
                    # 处理完每条文档后输出统计信息
                    if count > 0:
                        stats = self.vector_store.get_statistics()
                        file_name = doc.get('file_name', 'unknown')
                        logger.info(f"[{i}/{total_docs}] {file_name} 入库耗时: {doc_elapsed:.3f}秒，成功存储: {success_count} 条，总记录数: {stats['total_documents']}")
                        
                except Exception as e:
                    logger.error(f"处理文档失败 {doc.get('file_name', 'unknown')}: {str(e)}")
                    continue
            
            elapsed = time.time() - start_time
            logger.info(f"知识库构建完成，耗时 {elapsed:.2f} 秒，成功存储 {success_count} 条记录")
            
            # 显示统计信息
            stats = self.vector_store.get_statistics()
            logger.info(f"知识库总记录数: {stats['total_documents']}")
            
            self.initialized = True
            return True
            
        except Exception as e:
            logger.error(f"初始化知识库失败: {str(e)}")
            return False
    
    @time_logger
    def query(self, question: str, problem_type: str = None, top_k: int = 5) -> Dict:
        """
        查询知识库
        
        Args:
            question: 问题文本
            problem_type: 问题类型（可选）
            top_k: 返回结果数量
            
        Returns:
            查询结果字典
        """
        total_start_time = time.time()
        
        # 即使知识库未初始化，也尝试进行搜索
        if not self.initialized:
            logger.warning("知识库未初始化，尝试进行搜索...")
        
        # 执行向量搜索
        vector_search_start = time.time()
        try:
            if problem_type:
                results = self.vector_store.search_by_type(question, problem_type, top_k)
            else:
                results = self.vector_store.search(question, top_k)
        except Exception as e:
            logger.error(f"搜索失败: {e}")
            results = []
        
        vector_search_time = time.time() - vector_search_start
        
        response = {
            'question': question,
            'problem_type': problem_type,
            'results': results,
            'total_results': len(results),
            'vector_search_time': vector_search_time,
            'timestamp': datetime.now().isoformat()
        }
        
        # 如果有搜索结果，生成解决方案
        if results:
            response['best_match'] = results[0]
            response['suggested_solution'] = self._generate_solution(results)
            
            # 调用智普大模型进行AI分析
            llm_analysis_time = 0
            if self.llm:
                try:
                    llm_start = time.time()
                    llm_analysis = self.llm.analyze_problem(question, results)
                    llm_analysis_time = time.time() - llm_start
                    
                    response['llm_analysis'] = llm_analysis
                    response['ai_solution'] = llm_analysis.get('analysis', '')
                    response['llm_analysis_time'] = llm_analysis_time
                    
                    # 添加参考文档信息
                    if llm_analysis.get('reference_docs'):
                        response['reference_docs'] = llm_analysis['reference_docs']
                except Exception as e:
                    logger.warning(f"LLM分析失败: {str(e)}")
        
        # 计算总耗时
        response['query_time'] = time.time() - total_start_time
        
        return response
    
    def _generate_solution(self, results: List[Dict]) -> str:
        """
        根据搜索结果生成解决方案建议
        
        Args:
            results: 搜索结果列表
            
        Returns:
            解决方案文本
        """
        if not results:
            return "未找到相关解决方案"
        
        best = results[0]
        solution_parts = []
        
        solution_parts.append(f"问题类型: {best.get('problem_type', '未知')}")
        solution_parts.append(f"相似度: {best.get('similarity', 0):.2%}")
        solution_parts.append("")
        
        if best.get('solution'):
            solution_parts.append("参考解决方案:")
            solution_parts.append(best['solution'][:500])
        else:
            solution_parts.append("相关问题描述:")
            solution_parts.append(best.get('content', '')[:500])
        
        solution_parts.append("")
        solution_parts.append(f"参考来源: {best.get('source', '未知')}")
        
        if len(results) > 1:
            solution_parts.append("")
            solution_parts.append("其他相关案例:")
            for i, r in enumerate(results[1:3], 1):
                solution_parts.append(f"  {i}. {r.get('problem_type', '')} - 相似度: {r.get('similarity', 0):.2%}")
        
        return '\n'.join(solution_parts)
    
    def get_categories(self) -> List[str]:
        """获取问题分类列表 - 从向量库实时统计"""
        stats = self.vector_store.get_statistics()
        categories = list(stats.get('type_distribution', {}).keys())
        if categories:
            return sorted(categories)
        return []
    
    def get_statistics(self) -> Dict:
        """获取知识库统计信息"""
        return self.vector_store.get_statistics()
    
    def find_document_by_filename(self, filename: str) -> List[Dict]:
        """
        按文件名或完整路径查找文档
        
        Args:
            filename: 文件名或完整路径
            
        Returns:
            匹配的文档列表
        """
        return self.vector_store.find_document_by_filename(filename)

    def find_by_content(self, keywords: List[str]) -> List[Dict]:
        """
        按内容关键字精确查找文档
        
        Args:
            keywords: 关键字列表，多个关键字都需要匹配
            
        Returns:
            匹配的文档列表
        """
        return self.vector_store.find_by_content(keywords)
    
    def create_index(self, force_recreate: bool = False) -> bool:
        """创建索引
        
        Args:
            force_recreate: 是否强制重建索引
        """
        try:
            self.vector_store._create_index(force_recreate=force_recreate)
            return True
        except Exception as e:
            logger.error(f"创建索引失败: {str(e)}")
            return False
    
    def clear_all(self) -> bool:
        """清空知识库"""
        try:
            self.vector_store.clear_all()
            return True
        except Exception as e:
            logger.error(f"清空知识库失败: {str(e)}")
            return False

    def delete_by_file_path(self, file_path: str) -> int:
        """按文件路径删除相关文档

        Args:
            file_path: 文件路径

        Returns:
            删除的文档数量
        """
        try:
            return self.vector_store.delete_by_file_path(file_path)
        except Exception as e:
            logger.error(f"按路径删除文档失败: {str(e)}")
            return 0
    
    @time_logger
    def add_new_document(self, file_path: str) -> bool:
        """
        添加新文档到知识库
        
        Args:
            file_path: 文件路径
            
        Returns:
            是否成功
        """
        try:
            doc = self.parser.parse_file(file_path)
            if not doc:
                return False
            
            problem_desc, solution = extract_solution(doc['content'])
            doc['solution'] = solution
            
            return self.vector_store.add_document(doc)
            
        except Exception as e:
            logger.error(f"添加文档失败: {str(e)}")
            return False
    
    @time_logger
    def rebuild(self) -> bool:
        """重建知识库"""
        logger.info("开始重建知识库...")
        self.vector_store.clear_all()
        return self.initialize(force_rebuild=True)
    
    def close(self):
        """关闭知识库"""
        self.vector_store.close()


def format_response(response: Dict) -> str:
    """格式化查询响应为可读文本"""
    lines = []
    
    lines.append("=" * 60)
    lines.append(f"查询问题: {response['question']}")
    if response.get('problem_type'):
        lines.append(f"问题类型: {response['problem_type']}")
    lines.append(f"查询耗时: {response['query_time']:.3f} 秒")
    lines.append(f"找到结果: {response['total_results']} 条")
    lines.append("=" * 60)
    
    if response.get('suggested_solution'):
        lines.append("")
        lines.append(response['suggested_solution'])
    
    if response.get('ai_solution'):
        lines.append("")
        lines.append("-" * 60)
        lines.append("AI智能分析:")
        lines.append("-" * 60)
        lines.append(response['ai_solution'])
    
    if response.get('results'):
        lines.append("")
        lines.append("-" * 60)
        lines.append("详细搜索结果:")
        lines.append("-" * 60)
        
        for i, result in enumerate(response['results'], 1):
            lines.append(f"\n【结果 {i}】")
            lines.append(f"  问题ID: {result.get('problem_id', '未知')}")
            lines.append(f"  问题类型: {result.get('problem_type', '未知')}")
            lines.append(f"  相似度: {result.get('similarity', 0):.2%}")
            lines.append(f"  来源: {result.get('source', '未知')}")
            lines.append(f"  内容摘要: {result.get('content', '')[:200]}...")
    
    return '\n'.join(lines)


def interactive_mode(kb: KnowledgeBase):
    """交互式查询模式"""
    print("\n" + "=" * 60)
    print("沃工单知识库系统 - 交互式查询")
    print("=" * 60)
    print("输入问题进行查询，输入 'quit' 退出，输入 'stats' 查看统计")
    print("输入 'categories' 查看问题分类，输入 'help' 查看帮助")
    print("=" * 60 + "\n")
    
    while True:
        try:
            user_input = input("\n请输入问题: ").strip()
            
            if not user_input:
                continue
            
            if user_input.lower() == 'quit':
                print("感谢使用，再见！")
                break
            
            if user_input.lower() == 'stats':
                stats = kb.get_statistics()
                print(f"\n知识库统计:")
                print(f"  总文档数: {stats['total_documents']}")
                print(f"  类型分布:")
                for p_type, count in stats['type_distribution'].items():
                    print(f"    - {p_type}: {count}")
                continue
            
            if user_input.lower() == 'categories':
                print("\n问题分类:")
                for cat in kb.get_categories():
                    print(f"  - {cat}")
                continue
            
            if user_input.lower() == 'help':
                print("\n帮助信息:")
                print("  - 直接输入问题进行查询")
                print("  - 输入 'quit' 退出系统")
                print("  - 输入 'stats' 查看知识库统计")
                print("  - 输入 'categories' 查看问题分类")
                print("  - 输入 'type:类型名 问题' 按类型查询")
                continue
            
            problem_type = None
            if user_input.startswith('type:'):
                parts = user_input.split(' ', 1)
                if len(parts) == 2:
                    problem_type = parts[0].replace('type:', '')
                    user_input = parts[1]
            
            response = kb.query(user_input, problem_type)
            print(format_response(response))
            
        except KeyboardInterrupt:
            print("\n\n已取消，再见！")
            break
        except Exception as e:
            print(f"\n发生错误: {str(e)}")


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='沃工单知识库系统')
    parser.add_argument('--init', action='store_true', help='初始化知识库')
    parser.add_argument('--rebuild', action='store_true', help='重建知识库')
    parser.add_argument('--query', type=str, help='查询问题')
    parser.add_argument('--type', type=str, help='问题类型')
    parser.add_argument('--interactive', action='store_true', help='交互式模式')
    parser.add_argument('--stats', action='store_true', help='显示统计信息')
    
    args = parser.parse_args()
    
    kb = KnowledgeBase()
    
    try:
        if args.stats:
            if kb.initialize():
                stats = kb.get_statistics()
                print(f"知识库统计:")
                print(f"  总文档数: {stats['total_documents']}")
                print(f"  类型分布:")
                for p_type, count in stats['type_distribution'].items():
                    print(f"    - {p_type}: {count}")
        
        elif args.rebuild:
            kb.rebuild()
        
        elif args.query:
            if kb.initialize():
                response = kb.query(args.query, args.type)
                print(format_response(response))
        
        elif args.interactive:
            if kb.initialize():
                interactive_mode(kb)
        
        else:
            if kb.initialize():
                interactive_mode(kb)
    
    finally:
        kb.close()


if __name__ == "__main__":
    main()
