# -*- coding: utf-8 -*-
"""
智能功能模块
包含：智能推荐、智能问答、自动摘要、分类建议、文件对比等
"""

import time
from typing import List, Dict, Optional, Any
from collections import Counter
import re


class SmartRecommender:
    """智能推荐系统"""
    
    def __init__(self, kb, llm=None):
        self.kb = kb
        self.llm = llm
    
    def recommend_by_similarity(self, file_path: str, top_k: int = 5) -> List[Dict]:
        """基于内容相似度推荐"""
        try:
            results = self.kb.find_document_by_filename(file_path)
            
            if not results:
                return []
            
            content = results[0].get('content', '')
            
            if not content:
                return []
            
            if hasattr(self.kb, 'vector_store') and hasattr(self.kb.vector_store, 'search'):
                similar = self.kb.vector_store.search(content, top_k=top_k + 1)
            else:
                query_result = self.kb.query(content, top_k=top_k + 1)
                similar = query_result.get('results', [])
            
            similar = [r for r in similar if r.get('file_path') != file_path]
            
            return similar[:top_k]
            
        except Exception as e:
            print(f"相似度推荐失败: {e}")
            return []
    
    def recommend_by_type(self, problem_type: str, top_k: int = 5) -> List[Dict]:
        """基于问题类型推荐"""
        try:
            stats = self.kb.get_statistics()
            type_dist = stats.get('type_distribution', {})
            
            if problem_type not in type_dist:
                return []
            
            if hasattr(self.kb, 'vector_store') and hasattr(self.kb.vector_store, 'search_by_type'):
                matched = self.kb.vector_store.search_by_type(problem_type, problem_type, top_k=top_k)
            else:
                query_result = self.kb.query(problem_type, problem_type=problem_type, top_k=top_k)
                matched = query_result.get('results', [])
            
            return matched[:top_k]
            
        except Exception as e:
            print(f"类型推荐失败: {e}")
            return []
    
    def recommend_related(self, file_path: str) -> Dict[str, List[Dict]]:
        """综合推荐相关文件"""
        result = {
            'similar': [],
            'same_type': [],
            'related_id': []
        }
        
        try:
            docs = self.kb.find_document_by_filename(file_path)
            
            if not docs:
                return result
            
            doc = docs[0]
            
            result['similar'] = self.recommend_by_similarity(file_path, 5)
            
            problem_type = doc.get('problem_type', '')
            if problem_type:
                result['same_type'] = self.recommend_by_type(problem_type, 5)
            
            problem_id = doc.get('problem_id', '')
            if problem_id and len(problem_id) >= 4:
                id_prefix = problem_id[:4]
                related = self.kb.find_document_by_filename(id_prefix)
                result['related_id'] = [r for r in related if r.get('file_path') != file_path][:5]
            
            return result
            
        except Exception as e:
            print(f"综合推荐失败: {e}")
            return result
    
    def recommend_for_query(self, query: str, top_k: int = 10) -> List[Dict]:
        """为查询推荐相关文件"""
        try:
            if hasattr(self.kb, 'vector_store') and hasattr(self.kb.vector_store, 'search'):
                results = self.kb.vector_store.search(query, top_k=top_k)
            else:
                query_result = self.kb.query(query, top_k=top_k)
                results = query_result.get('results', [])
            
            return results
            
        except Exception as e:
            print(f"查询推荐失败: {e}")
            return []


class SmartQA:
    """智能问答系统"""
    
    def __init__(self, kb, llm=None):
        self.kb = kb
        self.llm = llm
        self.conversation_history: List[Dict] = []
        self.max_history = 10
        self.context: Dict = {}
    
    def ask(self, question: str, use_history: bool = True) -> Dict:
        """智能问答"""
        result = {
            'question': question,
            'answer': '',
            'sources': [],
            'confidence': 0.0,
            'follow_up_suggestions': []
        }
        
        try:
            if hasattr(self.kb, 'vector_store') and hasattr(self.kb.vector_store, 'search'):
                search_results = self.kb.vector_store.search(question, top_k=5)
            else:
                query_result = self.kb.query(question, top_k=5)
                search_results = query_result.get('results', [])
            
            if not search_results:
                result['answer'] = "抱歉，没有找到相关的信息。请尝试换一种方式提问。"
                return result
            
            result['sources'] = search_results
            
            if self.llm and self.llm.enabled:
                context = self._build_context(search_results)
                
                if use_history and self.conversation_history:
                    history_context = self._build_history_context()
                    context = history_context + "\n\n" + context
                
                prompt = self._build_prompt(question, context)
                
                answer = self.llm.chat(prompt)
                result['answer'] = answer
                result['confidence'] = 0.8
            else:
                result['answer'] = self._generate_simple_answer(search_results)
                result['confidence'] = 0.6
            
            result['follow_up_suggestions'] = self._generate_suggestions(question, search_results)
            
            self._add_to_history(question, result['answer'])
            
            return result
            
        except Exception as e:
            result['answer'] = f"回答生成失败: {str(e)}"
            return result
    
    def _build_context(self, results: List[Dict]) -> str:
        """构建上下文"""
        context_parts = []
        
        for i, r in enumerate(results[:3], 1):
            context_parts.append(f"【相关文档{i}】")
            context_parts.append(f"文件名: {r.get('file_name', '')}")
            context_parts.append(f"问题类型: {r.get('problem_type', '')}")
            context_parts.append(f"内容: {r.get('content', '')[:500]}")
            if r.get('solution'):
                context_parts.append(f"解决方案: {r.get('solution', '')[:300]}")
            context_parts.append("")
        
        return "\n".join(context_parts)
    
    def _build_history_context(self) -> str:
        """构建历史上下文"""
        if not self.conversation_history:
            return ""
        
        history_parts = ["【对话历史】"]
        
        for h in self.conversation_history[-3:]:
            history_parts.append(f"问: {h['question']}")
            history_parts.append(f"答: {h['answer'][:200]}...")
        
        return "\n".join(history_parts)
    
    def _build_prompt(self, question: str, context: str) -> str:
        """构建提示词"""
        return f"""基于以下相关文档回答问题。如果文档中没有相关信息，请说明。

{context}

问题: {question}

请提供准确、简洁的回答，并引用相关文档来源。"""
    
    def _generate_simple_answer(self, results: List[Dict]) -> str:
        """生成简单答案"""
        if not results:
            return "没有找到相关信息。"
        
        answer_parts = ["根据搜索结果，找到以下相关信息:\n"]
        
        for i, r in enumerate(results[:3], 1):
            answer_parts.append(f"{i}. 文件: {r.get('file_name', '')}")
            answer_parts.append(f"   类型: {r.get('problem_type', '')}")
            
            content = r.get('content', '')
            if content:
                answer_parts.append(f"   内容摘要: {content[:200]}...")
            
            if r.get('solution'):
                answer_parts.append(f"   解决方案: {r['solution'][:100]}...")
            
            answer_parts.append("")
        
        return "\n".join(answer_parts)
    
    def _generate_suggestions(self, question: str, results: List[Dict]) -> List[str]:
        """生成后续问题建议"""
        suggestions = []
        
        if results:
            types = set(r.get('problem_type', '') for r in results if r.get('problem_type'))
            for t in list(types)[:2]:
                suggestions.append(f"查看更多关于 '{t}' 的问题")
        
        suggestions.append("查看相关文件的详细内容")
        suggestions.append("搜索类似的解决方案")
        
        return suggestions[:3]
    
    def _add_to_history(self, question: str, answer: str):
        """添加到历史"""
        self.conversation_history.append({
            'question': question,
            'answer': answer,
            'time': time.time()
        })
        
        if len(self.conversation_history) > self.max_history:
            self.conversation_history = self.conversation_history[-self.max_history:]
    
    def clear_history(self):
        """清空历史"""
        self.conversation_history = []
        self.context = {}
    
    def get_history(self) -> List[Dict]:
        """获取历史"""
        return self.conversation_history.copy()


class AutoSummarizer:
    """自动摘要生成器"""
    
    def __init__(self, kb, llm=None):
        self.kb = kb
        self.llm = llm
    
    def summarize_file(self, file_path: str) -> Dict:
        """生成文件摘要"""
        result = {
            'file_path': file_path,
            'summary': '',
            'key_points': [],
            'problem_type': '',
            'confidence': 0.0
        }
        
        try:
            docs = self.kb.find_document_by_filename(file_path)
            
            if not docs:
                result['summary'] = "文件未找到"
                return result
            
            doc = docs[0]
            content = doc.get('content', '')
            
            if not content:
                result['summary'] = "文件内容为空"
                return result
            
            result['problem_type'] = doc.get('problem_type', '')
            
            if self.llm and self.llm.enabled:
                summary = self._summarize_with_llm(content)
                result['summary'] = summary
                result['key_points'] = self._extract_key_points_with_llm(content)
                result['confidence'] = 0.9
            else:
                result['summary'] = self._summarize_simple(content)
                result['key_points'] = self._extract_key_points_simple(content)
                result['confidence'] = 0.6
            
            return result
            
        except Exception as e:
            result['summary'] = f"摘要生成失败: {str(e)}"
            return result
    
    def _summarize_with_llm(self, content: str) -> str:
        """使用LLM生成摘要"""
        try:
            prompt = f"""请对以下内容进行摘要，要求：
1. 提取核心问题和关键信息
2. 概述解决方案（如果有）
3. 控制在200字以内

内容:
{content[:2000]}

摘要:"""
            
            return self.llm.chat(prompt)
            
        except Exception as e:
            return self._summarize_simple(content)
    
    def _summarize_simple(self, content: str) -> str:
        """简单摘要"""
        sentences = re.split(r'[。！？\n]', content)
        
        sentences = [s.strip() for s in sentences if s.strip() and len(s.strip()) > 10]
        
        if not sentences:
            return content[:200]
        
        summary = sentences[0]
        
        if len(sentences) > 1:
            summary += " " + sentences[1]
        
        if len(summary) > 300:
            summary = summary[:300] + "..."
        
        return summary
    
    def _extract_key_points_with_llm(self, content: str) -> List[str]:
        """使用LLM提取关键点"""
        try:
            prompt = f"""请从以下内容中提取3-5个关键点，每点一行:

内容:
{content[:1500]}

关键点:"""
            
            response = self.llm.chat(prompt)
            
            points = [p.strip() for p in response.split('\n') if p.strip()]
            
            return points[:5]
            
        except:
            return self._extract_key_points_simple(content)
    
    def _extract_key_points_simple(self, content: str) -> List[str]:
        """简单提取关键点"""
        keywords = []
        
        patterns = [
            r'问题[：:]\s*([^\n。]+)',
            r'原因[：:]\s*([^\n。]+)',
            r'解决[：:]\s*([^\n。]+)',
            r'建议[：:]\s*([^\n。]+)',
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, content)
            keywords.extend(matches[:2])
        
        return keywords[:5]
    
    def batch_summarize(self, file_paths: List[str]) -> List[Dict]:
        """批量生成摘要"""
        results = []
        
        for path in file_paths:
            result = self.summarize_file(path)
            results.append(result)
        
        return results


class CategorySuggester:
    """智能分类建议器"""
    
    def __init__(self, kb, llm=None):
        self.kb = kb
        self.llm = llm
        self.category_keywords = self._build_category_keywords()
    
    def _build_category_keywords(self) -> Dict[str, List[str]]:
        """构建分类关键词"""
        return {
            '开户问题': ['开户', '新装', '入网', '新用户'],
            '套餐问题': ['套餐', '资费', '包月', '流量包'],
            '计费问题': ['计费', '扣费', '账单', '费用'],
            '网络问题': ['网络', '信号', '上网', '连接'],
            '业务办理': ['办理', '变更', '取消', '退订'],
            '充值缴费': ['充值', '缴费', '话费', '余额'],
            '客服问题': ['客服', '投诉', '咨询', '建议'],
            '系统问题': ['系统', '报错', '异常', '故障'],
        }
    
    def suggest_category(self, content: str) -> Dict:
        """建议分类"""
        result = {
            'suggested_category': '',
            'confidence': 0.0,
            'all_suggestions': []
        }
        
        try:
            scores = {}
            
            for category, keywords in self.category_keywords.items():
                score = sum(1 for kw in keywords if kw in content)
                if score > 0:
                    scores[category] = score
            
            if scores:
                sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
                
                result['suggested_category'] = sorted_scores[0][0]
                result['all_suggestions'] = [
                    {'category': cat, 'score': score}
                    for cat, score in sorted_scores[:5]
                ]
                
                total_score = sum(scores.values())
                result['confidence'] = sorted_scores[0][1] / total_score if total_score > 0 else 0
            
            if self.llm and self.llm.enabled:
                llm_suggestion = self._suggest_with_llm(content)
                if llm_suggestion:
                    result['llm_suggestion'] = llm_suggestion
            
            return result
            
        except Exception as e:
            print(f"分类建议失败: {e}")
            return result
    
    def _suggest_with_llm(self, content: str) -> str:
        """使用LLM建议分类"""
        try:
            categories = list(self.category_keywords.keys())
            
            prompt = f"""请从以下分类中选择最适合的分类，或提供新的分类建议。

可选分类: {', '.join(categories)}

内容:
{content[:500]}

分类:"""
            
            return self.llm.chat(prompt)
            
        except:
            return ""
    
    def learn_from_feedback(self, content: str, correct_category: str):
        """从反馈中学习"""
        words = re.findall(r'[\u4e00-\u9fa5]{2,}', content)
        
        word_freq = Counter(words)
        
        top_words = [w for w, _ in word_freq.most_common(5)]
        
        if correct_category not in self.category_keywords:
            self.category_keywords[correct_category] = []
        
        for word in top_words:
            if word not in self.category_keywords[correct_category]:
                self.category_keywords[correct_category].append(word)


class FileComparator:
    """文件对比器"""
    
    def __init__(self, kb):
        self.kb = kb
    
    def compare(self, file1: str, file2: str) -> Dict:
        """对比两个文件"""
        result = {
            'file1': file1,
            'file2': file2,
            'similarity': 0.0,
            'differences': [],
            'common_points': [],
            'unique_to_file1': [],
            'unique_to_file2': []
        }
        
        try:
            docs1 = self.kb.find_document_by_filename(file1)
            docs2 = self.kb.find_document_by_filename(file2)
            
            if not docs1 or not docs2:
                result['error'] = "文件未找到"
                return result
            
            content1 = docs1[0].get('content', '')
            content2 = docs2[0].get('content', '')
            
            result['similarity'] = self._calculate_similarity(content1, content2)
            
            result['common_points'] = self._find_common(content1, content2)
            
            result['unique_to_file1'] = self._find_unique(content1, content2)
            result['unique_to_file2'] = self._find_unique(content2, content1)
            
            result['differences'] = self._find_differences(content1, content2)
            
            return result
            
        except Exception as e:
            result['error'] = str(e)
            return result
    
    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """计算相似度"""
        words1 = set(re.findall(r'[\u4e00-\u9fa5]+', text1))
        words2 = set(re.findall(r'[\u4e00-\u9fa5]+', text2))
        
        if not words1 or not words2:
            return 0.0
        
        intersection = words1 & words2
        union = words1 | words2
        
        return len(intersection) / len(union) if union else 0.0
    
    def _find_common(self, text1: str, text2: str) -> List[str]:
        """找出共同点"""
        sentences1 = set(re.split(r'[。！？\n]', text1))
        sentences2 = set(re.split(r'[。！？\n]', text2))
        
        common = sentences1 & sentences2
        
        return [s.strip() for s in common if s.strip() and len(s.strip()) > 10][:10]
    
    def _find_unique(self, text1: str, text2: str) -> List[str]:
        """找出text1独有的内容"""
        sentences1 = set(re.split(r'[。！？\n]', text1))
        sentences2 = set(re.split(r'[。！？\n]', text2))
        
        unique = sentences1 - sentences2
        
        return [s.strip() for s in unique if s.strip() and len(s.strip()) > 10][:10]
    
    def _find_differences(self, text1: str, text2: str) -> List[Dict]:
        """找出差异"""
        differences = []
        
        lines1 = text1.split('\n')
        lines2 = text2.split('\n')
        
        for i, (l1, l2) in enumerate(zip(lines1, lines2)):
            if l1.strip() != l2.strip():
                differences.append({
                    'line': i + 1,
                    'file1': l1.strip()[:100],
                    'file2': l2.strip()[:100]
                })
        
        return differences[:20]


class BatchOperator:
    """批量操作器"""
    
    def __init__(self, kb):
        self.kb = kb
    
    def batch_open(self, file_paths: List[str]) -> Dict:
        """批量打开文件"""
        result = {
            'success': [],
            'failed': []
        }
        
        import os
        import platform
        
        for path in file_paths:
            try:
                if os.path.exists(path):
                    if platform.system() == 'Windows':
                        os.startfile(path)
                    elif platform.system() == 'Darwin':
                        os.system(f'open "{path}"')
                    else:
                        os.system(f'xdg-open "{path}"')
                    
                    result['success'].append(path)
                else:
                    result['failed'].append({'path': path, 'error': '文件不存在'})
            except Exception as e:
                result['failed'].append({'path': path, 'error': str(e)})
        
        return result
    
    def batch_export(self, results: List[Dict], format: str = 'csv', filename: str = None) -> str:
        """批量导出"""
        from enhanced_features import ResultExporter
        
        if filename is None:
            from datetime import datetime
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"export_{timestamp}.{format}"
        
        if format == 'csv':
            ResultExporter.to_csv(results, filename)
        elif format == 'excel':
            ResultExporter.to_excel(results, filename)
        elif format == 'json':
            ResultExporter.to_json(results, filename)
        else:
            print(f"不支持的格式: {format}")
            return ""
        
        return filename
    
    def batch_tag(self, file_paths: List[str], tag: str, tag_manager) -> Dict:
        """批量打标签"""
        result = {
            'success': 0,
            'failed': 0
        }
        
        for path in file_paths:
            try:
                tag_manager.add_tag(path, tag)
                result['success'] += 1
            except:
                result['failed'] += 1
        
        return result
    
    def batch_favorite(self, file_paths: List[str], favorite_manager) -> Dict:
        """批量收藏"""
        result = {
            'success': 0,
            'failed': 0
        }
        
        for path in file_paths:
            try:
                import os
                file_name = os.path.basename(path)
                favorite_manager.add(path, file_name)
                result['success'] += 1
            except:
                result['failed'] += 1
        
        return result
