# -*- coding: utf-8 -*-
"""
沃工单知识库系统使用示例
"""

from knowledge_base import KnowledgeBase
from config import ZHIPU_CONFIG


def example_basic_query():
    """基本查询示例"""
    print("\n=== 基本查询示例 ===\n")
    
    kb = KnowledgeBase(use_llm=False)
    
    if kb.initialize():
        question = "开户报错如何处理"
        response = kb.query(question)
        
        if response['results']:
            best = response['results'][0]
            print(f"问题类型: {best.get('problem_type')}")
            print(f"相似度: {best.get('similarity'):.1%}")
            print(f"解决方案: {best.get('solution', best.get('content', ''))[:300]}...")
        else:
            print("未找到相关结果")
    
    kb.close()


def example_query_with_type():
    """按类型查询示例"""
    print("\n=== 按类型查询示例 ===\n")
    
    kb = KnowledgeBase(use_llm=False)
    
    if kb.initialize():
        question = "用户无法办理业务"
        problem_type = "系统报错"
        response = kb.query(question, problem_type=problem_type)
        
        print(f"查询: {question}")
        print(f"类型: {problem_type}")
        print(f"结果数: {response['total_results']}")
    
    kb.close()


def example_with_llm():
    """使用智普大模型增强查询"""
    print("\n=== 智普大模型增强示例 ===\n")
    
    if not ZHIPU_CONFIG.get('api_key'):
        print("请先在config.ini中配置智普API Key")
        return
    
    kb = KnowledgeBase(use_llm=True)
    
    if kb.initialize():
        question = "用户开户时提示系统错误，应该如何排查和解决？"
        response = kb.query(question)
        
        if response.get('ai_solution'):
            print("AI分析结果:")
            print(response['ai_solution'])
    
    kb.close()


if __name__ == "__main__":
    print("\n沃工单知识库系统 - 使用示例")
    print("=" * 50)
    
    example_basic_query()
    
    print("\n" + "=" * 50)
    print("更多功能请运行: python query_tool.py")
    print("=" * 50)
