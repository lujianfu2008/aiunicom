# -*- coding: utf-8 -*-
"""
知识图谱抽取模块
使用 LLM 进行实体识别和关系抽取
"""

import json
import logging
import re
from typing import List, Dict, Any, Optional, Tuple
from knowledge_graph import Entity, Relation, KnowledgeGraph

logger = logging.getLogger(__name__)


class KnowledgeExtractor:
    """知识抽取器"""
    
    def __init__(self, llm_instance=None, knowledge_graph: KnowledgeGraph = None):
        """初始化知识抽取器"""
        self.llm = llm_instance
        self.kg = knowledge_graph or KnowledgeGraph()
        
        self.entity_types = {
            "问题": "描述的问题现象",
            "解决方案": "解决问题的方法或步骤",
            "系统": "涉及的系统或平台",
            "组件": "涉及的组件或模块",
            "错误代码": "错误代码或错误信息",
            "配置项": "配置参数或设置",
            "命令": "操作命令或指令",
            "文件": "涉及的文件或路径",
            "人员": "涉及的人员或角色",
            "时间": "时间点或时间段"
        }
        
        self.relation_types = {
            "导致": "问题导致的结果",
            "解决": "解决方案解决的问题",
            "属于": "实体所属的分类",
            "包含": "实体包含的子项",
            "依赖": "实体之间的依赖关系",
            "配置": "配置项与系统的关系",
            "执行": "命令与操作的关系",
            "生成": "错误代码的生成来源",
            "涉及": "问题涉及的系统或组件",
            "关联": "实体之间的关联关系"
        }
    
    def extract_from_text(self, text: str, doc_id: str = None) -> Tuple[List[Entity], List[Relation]]:
        """从文本中抽取实体和关系"""
        try:
            if not self.llm:
                logger.warning("LLM 未初始化，无法进行知识抽取")
                return [], []
            
            prompt = self._build_extraction_prompt(text)
            
            # 修复：使用消息列表格式
            messages = [{"role": "user", "content": prompt}]
            response = self.llm.chat(messages)
            
            if not response:
                logger.warning("LLM 响应为空")
                return [], []
            
            entities, relations = self._parse_extraction_response(response, doc_id)
            
            return entities, relations
        except Exception as e:
            logger.error(f"知识抽取失败: {e}")
            return [], []
    
    def _build_extraction_prompt(self, text: str) -> str:
        """构建知识抽取提示词"""
        entity_types_desc = "\n".join([f"- {k}: {v}" for k, v in self.entity_types.items()])
        relation_types_desc = "\n".join([f"- {k}: {v}" for k, v in self.relation_types.items()])
        
        prompt = f"""请从以下文本中识别实体和关系，并按照指定格式输出。

文本内容：
{text[:2000]}

实体类型：
{entity_types_desc}

关系类型：
{relation_types_desc}

请严格按照以下 JSON 格式输出，不要添加任何其他内容：

{{
  "entities": [
    {{
      "name": "实体名称",
      "type": "实体类型",
      "properties": {{
        "key": "value"
      }}
    }}
  ],
  "relations": [
    {{
      "source": "源实体名称",
      "target": "目标实体名称",
      "type": "关系类型",
      "properties": {{
        "key": "value"
      }}
    }}
  ]
}}

注意事项：
1. 实体名称要准确，不要添加多余的解释
2. 实体类型必须是上述列出的类型之一
3. 关系类型必须是上述列出的类型之一
4. 只抽取明确提到的实体和关系，不要推测
5. 如果文本中没有实体或关系，返回空数组
6. 确保输出的 JSON 格式正确，可以被解析

请开始抽取："""
        
        return prompt
    
    def _parse_extraction_response(self, response: str, doc_id: str = None) -> Tuple[List[Entity], List[Relation]]:
        """解析抽取结果"""
        try:
            json_match = re.search(r'\{[\s\S]*\}', response)
            if not json_match:
                logger.warning("未找到 JSON 格式的抽取结果")
                return [], []
            
            json_str = json_match.group(0)
            data = json.loads(json_str)
            
            entities = []
            entity_map = {}
            
            for entity_data in data.get('entities', []):
                name = entity_data.get('name', '').strip()
                entity_type = entity_data.get('type', '').strip()
                
                if not name or not entity_type:
                    continue
                
                if entity_type not in self.entity_types:
                    logger.warning(f"未知的实体类型: {entity_type}")
                    continue
                
                properties = entity_data.get('properties', {})
                if doc_id:
                    properties['doc_id'] = doc_id
                
                entity = Entity(name=name, entity_type=entity_type, properties=properties)
                entities.append(entity)
                entity_map[name] = entity
            
            relations = []
            
            for relation_data in data.get('relations', []):
                source_name = relation_data.get('source', '').strip()
                target_name = relation_data.get('target', '').strip()
                relation_type = relation_data.get('type', '').strip()
                
                if not source_name or not target_name or not relation_type:
                    continue
                
                if relation_type not in self.relation_types:
                    logger.warning(f"未知的关系类型: {relation_type}")
                    continue
                
                source_entity = entity_map.get(source_name)
                target_entity = entity_map.get(target_name)
                
                if not source_entity:
                    source_entity = Entity(name=source_name, entity_type="未知")
                    entities.append(source_entity)
                    entity_map[source_name] = source_entity
                
                if not target_entity:
                    target_entity = Entity(name=target_name, entity_type="未知")
                    entities.append(target_entity)
                    entity_map[target_name] = target_entity
                
                properties = relation_data.get('properties', {})
                if doc_id:
                    properties['doc_id'] = doc_id
                
                relation = Relation(
                    source_id=source_entity.id,
                    target_id=target_entity.id,
                    relation_type=relation_type,
                    properties=properties
                )
                relations.append(relation)
            
            return entities, relations
        except json.JSONDecodeError as e:
            logger.error(f"解析 JSON 失败: {e}")
            return [], []
        except Exception as e:
            logger.error(f"解析抽取结果失败: {e}")
            return [], []
    
    def extract_and_save(self, text: str, doc_id: str = None) -> Dict[str, Any]:
        """抽取并保存实体和关系"""
        try:
            entities, relations = self.extract_from_text(text, doc_id)
            
            saved_entities = 0
            saved_relations = 0
            
            entity_id_map = {}
            
            for entity in entities:
                existing_entity = self._find_entity_by_name_and_type(entity.name, entity.entity_type)
                if existing_entity:
                    entity_id_map[entity.name] = existing_entity.id
                else:
                    if self.kg.add_entity(entity):
                        saved_entities += 1
                        entity_id_map[entity.name] = entity.id
            
            for relation in relations:
                source_name = None
                target_name = None
                
                for name, entity in entity_id_map.items():
                    if entity == relation.source_id:
                        source_name = name
                    if entity == relation.target_id:
                        target_name = name
                
                if not source_name or not target_name:
                    continue
                
                if self._relation_exists(relation.source_id, relation.target_id, relation.relation_type):
                    continue
                
                if self.kg.add_relation(relation):
                    saved_relations += 1
            
            return {
                "success": True,
                "entities_count": len(entities),
                "relations_count": len(relations),
                "saved_entities": saved_entities,
                "saved_relations": saved_relations
            }
        except Exception as e:
            logger.error(f"抽取并保存失败: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def _find_entity_by_name_and_type(self, name: str, entity_type: str) -> Optional[Entity]:
        """根据名称和类型查找实体"""
        try:
            entities = self.kg.get_entities_by_type(entity_type)
            for entity in entities:
                if entity.name == name:
                    return entity
            return None
        except Exception as e:
            logger.error(f"查找实体失败: {e}")
            return None
    
    def _relation_exists(self, source_id: str, target_id: str, relation_type: str) -> bool:
        """检查关系是否已存在"""
        try:
            relations = self.kg.get_relations_by_entity(source_id)
            for relation in relations:
                if (relation.target_id == target_id and 
                    relation.relation_type == relation_type):
                    return True
            return False
        except Exception as e:
            logger.error(f"检查关系是否存在失败: {e}")
            return False
    
    def batch_extract_from_documents(self, documents: List[Dict[str, Any]]) -> Dict[str, Any]:
        """批量从文档中抽取知识"""
        try:
            total_entities = 0
            total_relations = 0
            saved_entities = 0
            saved_relations = 0
            failed_docs = []
            
            for i, doc in enumerate(documents):
                doc_id = doc.get('id', f'doc_{i}')
                content = doc.get('content', '')
                
                if not content:
                    continue
                
                logger.info(f"正在处理文档 {i+1}/{len(documents)}: {doc_id}")
                
                result = self.extract_and_save(content, doc_id)
                
                if result['success']:
                    total_entities += result['entities_count']
                    total_relations += result['relations_count']
                    saved_entities += result['saved_entities']
                    saved_relations += result['saved_relations']
                else:
                    failed_docs.append({
                        "doc_id": doc_id,
                        "error": result.get('error', '未知错误')
                    })
            
            return {
                "success": True,
                "total_documents": len(documents),
                "processed_documents": len(documents) - len(failed_docs),
                "total_entities": total_entities,
                "total_relations": total_relations,
                "saved_entities": saved_entities,
                "saved_relations": saved_relations,
                "failed_documents": failed_docs
            }
        except Exception as e:
            logger.error(f"批量抽取失败: {e}")
            return {
                "success": False,
                "error": str(e)
            }
