# -*- coding: utf-8 -*-
"""
智普大模型集成模块 - 用于增强问题理解和答案生成
"""

import json
import logging
from typing import List, Dict, Optional
import requests

from config import LOCAL_MODEL_PATH, ZHIPU_CONFIG

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class ZhipuLLM:
    """智普大模型接口"""
    
    def __init__(self, config: Dict = None):
        self.config = config or ZHIPU_CONFIG
        self.api_key = self.config.get('api_key', '')
        self.api_base = self.config.get('api_base', 'https://open.bigmodel.cn/api/paas/v4')
        self.model = self.config.get('model', 'glm-4')
        
    def set_api_key(self, api_key: str):
        """设置API Key"""
        self.api_key = api_key
        self.config['api_key'] = api_key
    
    def chat(self, messages: List[Dict], temperature: float = None) -> str:
        """
        调用智普对话模型
        
        Args:
            messages: 消息列表，格式为 [{"role": "user", "content": "..."}]
            temperature: 温度参数
            
        Returns:
            模型回复文本
        """
        if not self.api_key:
            logger.warning("未配置智普API Key")
            return ""
        
        url = f"{self.api_base}/chat/completions"
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": self.model,
            "messages": messages,
            "max_tokens": self.config.get('max_tokens', 4000),
            "temperature": temperature or self.config.get('temperature', 0.7)
        }
        
        try:
            response = requests.post(url, headers=headers, json=data, timeout=60)
            response.raise_for_status()
            
            result = response.json()
            return result['choices'][0]['message']['content']
            
        except Exception as e:
            logger.error(f"调用智普模型失败: {str(e)}")
            return ""
    
    def get_embedding(self, text: str) -> List[float]:
        """
        获取文本的向量表示
        
        Args:
            text: 输入文本
            
        Returns:
            向量列表
        """
        if not self.api_key:
            logger.warning("未配置智普API Key")
            return []
        
        url = f"{self.api_base}/embeddings"
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": self.config.get('embedding_model', 'embedding-2'),
            "input": text
        }
        
        try:
            response = requests.post(url, headers=headers, json=data, timeout=30)
            response.raise_for_status()
            
            result = response.json()
            return result['data'][0]['embedding']
            
        except Exception as e:
            logger.error(f"获取向量失败: {str(e)}")
            return []
    
    def analyze_problem(self, question: str, search_results: List[Dict]) -> Dict:
        """
        分析问题并生成解决方案
        
        Args:
            question: 用户问题
            search_results: 知识库搜索结果
            
        Returns:
            分析结果字典
        """
        if not self.api_key:
            return self._simple_analysis(question, search_results)
        
        context = self._build_context(search_results)
        
        prompt = f"""你是一个专业的联通客服问题分析专家。请根据以下知识库内容，深入分析用户问题并提供完整的解决方案。

用户问题：{question}

相关知识库内容：
{context}

请按以下格式详细回答：

## 1. 问题类型
[根据知识库内容，判断问题所属的具体分类，如：开户报错、套餐变更、移机改号、销户问题、合约问题、费用问题、服务状态、终端问题、跨域业务、实名认证等]

## 2. 问题描述
[详细描述用户遇到的问题，包括问题的具体表现、影响范围等]

## 3. 问题原因分析
[深入分析问题产生的根本原因，可能包括：
- 系统层面的原因
- 业务流程的原因
- 数据配置的原因
- 用户操作的原因
- 其他可能的原因]

## 4. 解决方案
[提供详细、可操作的解决步骤，包括：
### 4.1 立即处理措施
[能够快速解决问题的临时措施]

### 4.2 根本解决方案
[彻底解决问题的完整步骤，按序号列出]
1. 第一步：...
2. 第二步：...
3. 第三步：...
...

### 4.3 验证方法
[如何验证问题是否已经解决]

## 5. 预防措施
[如何避免类似问题再次发生]

## 6. 注意事项
[处理过程中需要特别注意的事项，包括：
- 操作风险
- 数据备份要求
- 权限要求
- 时间窗口要求
- 其他重要提示]

## 7. 相关案例参考
[简要总结知识库中相关案例的关键信息，包括案例编号、相似度和来源文件]

## 8. 参考文档
[列出所有参考的文档，格式为：
1. 文档名称：[文件名]，相似度：[相似度]%
2. 文档名称：[文件名]，相似度：[相似度]%
...
]

请确保回答内容详实、专业、可操作性强，帮助客服人员快速理解和解决问题。"""
        
        messages = [{"role": "user", "content": prompt}]
        response = self.chat(messages)
        
        # 提取参考文档信息
        reference_docs = []
        for i, result in enumerate(search_results[:5], 1):
            reference_docs.append({
                'index': i,
                'file_name': result.get('file_name', '未知'),
                'source': result.get('source', '未知'),
                'similarity': result.get('similarity', 0),
                'content': result.get('content', '')[:100] + '...' if result.get('content') else '无'
            })
        
        return {
            'question': question,
            'analysis': response,
            'problem_type': self._extract_type(response),
            'confidence': 0.9,
            'reference_docs': reference_docs
        }
    
    def _build_context(self, search_results: List[Dict], max_length: int = 8000) -> str:
        """构建上下文"""
        context_parts = []
        total_length = 0
        
        for i, result in enumerate(search_results[:5], 1):
            content = result.get('content', '')
            source = result.get('source', '未知')
            similarity = result.get('similarity', 0)
            
            part = f"\n【案例{i}】(相似度: {similarity:.2%}, 来源: {source})\n{content}\n"
            
            if total_length + len(part) > max_length:
                break
            
            context_parts.append(part)
            total_length += len(part)
        
        return ''.join(context_parts)
    
    def _extract_type(self, analysis: str) -> str:
        """从分析结果中提取问题类型"""
        import re
        match = re.search(r'问题类型[：:]\s*(.+?)(?:\n|$)', analysis)
        if match:
            return match.group(1).strip()
        return "其他问题"
    
    def _simple_analysis(self, question: str, search_results: List[Dict]) -> Dict:
        """简单分析（无API Key时使用）"""
        if not search_results:
            return {
                'question': question,
                'analysis': '未找到相关案例',
                'problem_type': '其他问题',
                'confidence': 0
            }
        
        best = search_results[0]
        return {
            'question': question,
            'analysis': f"根据知识库匹配，该问题属于{best.get('problem_type', '未知')}类型。",
            'problem_type': best.get('problem_type', '其他问题'),
            'confidence': best.get('similarity', 0)
        }
    
    def classify(self, question: str) -> str:
        """
        对问题进行分类
        
        Args:
            question: 问题文本
            
        Returns:
            问题类型
        """
        if not self.api_key:
            return self._simple_classify(question)
        
        # 从知识库获取实际的类别列表
        from vector_store import RedisVectorStore
        vs = RedisVectorStore()
        stats = vs.get_statistics()
        categories = list(stats.get('type_distribution', {}).keys())
        vs.close()
        
        # 如果没有类别，使用默认类别
        if not categories:
            categories = ['系统报错', '套餐变更', '副卡问题', '其他问题', '开户报错', '产品受理', '合约问题', '销户问题', '终端问题', '服务状态', '费用问题', '亲情业务', '跨域业务', '实名认证', '移机改号']
        
        prompt = f"""请将以下问题归类到最合适的类别中。

问题：{question}

可选类别：
{', '.join(categories)}

请只返回类别名称，不要其他内容。"""
        
        messages = [{"role": "user", "content": prompt}]
        response = self.chat(messages, temperature=0.1)
        
        for category in categories:
            if category in response:
                return category
        
        return "其他问题"
    
    def _simple_classify(self, question: str) -> str:
        """简单分类（基于关键词）"""
        type_keywords = {
            '开户报错': ['开户', '新装', '新开'],
            '套餐变更': ['套餐', '变更', '改套餐', '转套餐'],
            '移机改号': ['移机', '改号', '迁移'],
            '销户问题': ['销户', '销号', '注销', '拆机'],
            '合约问题': ['合约', '解约', '违约金', '协议'],
            '费用问题': ['费用', '扣费', '账单', '收费'],
            '服务状态': ['停机', '复机', '状态'],
            '终端问题': ['终端', '设备', '光猫'],
            '跨域业务': ['跨域', '异地'],
            '实名认证': ['实名', '认证', '身份'],
            '副卡问题': ['副卡', '附属卡'],
            '亲情业务': ['亲情', '亲情网', '亲情付'],
            '产品受理': ['产品', '受理', '办理'],
            '系统报错': ['报错', '错误', '失败', '异常']
        }
        
        for category, keywords in type_keywords.items():
            for keyword in keywords:
                if keyword in question:
                    return category
        
        return '其他问题'


zhipu_llm = ZhipuLLM()


def configure_zhipu(api_key: str, model: str = "glm-4"):
    """配置智普大模型"""
    zhipu_llm.set_api_key(api_key)
    zhipu_llm.model = model
    logger.info(f"已配置智普大模型: {model}")


if __name__ == "__main__":
    llm = ZhipuLLM()
    
    test_question = "用户开户时提示报错，如何处理？"
    category = llm.classify_problem(test_question)
    print(f"问题分类: {category}")
