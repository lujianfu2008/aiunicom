# -*- coding: utf-8 -*-
"""
知识图谱模块
实现实体识别、关系抽取和知识图谱可视化
"""

import json
import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
import redis
from config import REDIS_CONFIG

logger = logging.getLogger(__name__)


class Entity:
    """实体类"""
    
    def __init__(self, name: str, entity_type: str, properties: Dict[str, Any] = None):
        self.name = name
        self.entity_type = entity_type
        self.properties = properties or {}
        self.created_at = datetime.now().isoformat()
        self.id = self._generate_id()
    
    def _generate_id(self) -> str:
        """生成实体ID"""
        import hashlib
        unique_str = f"{self.entity_type}:{self.name}"
        return hashlib.md5(unique_str.encode('utf-8')).hexdigest()[:16]
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "name": self.name,
            "type": self.entity_type,
            "properties": self.properties,
            "created_at": self.created_at
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Entity':
        """从字典创建实体"""
        entity = cls(
            name=data['name'],
            entity_type=data['type'],
            properties=data.get('properties', {})
        )
        entity.id = data['id']
        entity.created_at = data.get('created_at', datetime.now().isoformat())
        return entity


class Relation:
    """关系类"""
    
    def __init__(self, source_id: str, target_id: str, relation_type: str, properties: Dict[str, Any] = None):
        self.source_id = source_id
        self.target_id = target_id
        self.relation_type = relation_type
        self.properties = properties or {}
        self.created_at = datetime.now().isoformat()
        self.id = self._generate_id()
    
    def _generate_id(self) -> str:
        """生成关系ID"""
        import hashlib
        unique_str = f"{self.source_id}:{self.relation_type}:{self.target_id}"
        return hashlib.md5(unique_str.encode('utf-8')).hexdigest()[:16]
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "source_id": self.source_id,
            "target_id": self.target_id,
            "type": self.relation_type,
            "properties": self.properties,
            "created_at": self.created_at
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Relation':
        """从字典创建关系"""
        relation = cls(
            source_id=data['source_id'],
            target_id=data['target_id'],
            relation_type=data['type'],
            properties=data.get('properties', {})
        )
        relation.id = data['id']
        relation.created_at = data.get('created_at', datetime.now().isoformat())
        return relation


class KnowledgeGraph:
    """知识图谱类"""
    
    def __init__(self, redis_client=None):
        """初始化知识图谱"""
        if redis_client is None:
            self.redis_client = redis.Redis(
                host=REDIS_CONFIG['host'],
                port=REDIS_CONFIG['port'],
                db=REDIS_CONFIG['db'],
                password=REDIS_CONFIG['password'],
                decode_responses=True
            )
        else:
            self.redis_client = redis_client
        
        self.entity_prefix = "kg:entity:"
        self.relation_prefix = "kg:relation:"
        self.entity_index_prefix = "kg:entity_index:"
        self.relation_index_prefix = "kg:relation_index:"
    
    def add_entity(self, entity: Entity) -> bool:
        """添加实体"""
        try:
            entity_key = f"{self.entity_prefix}{entity.id}"
            entity_data = json.dumps(entity.to_dict(), ensure_ascii=False)
            
            self.redis_client.set(entity_key, entity_data)
            
            type_index_key = f"{self.entity_index_prefix}type:{entity.entity_type}"
            self.redis_client.sadd(type_index_key, entity.id)
            
            name_index_key = f"{self.entity_index_prefix}name:{entity.name}"
            self.redis_client.sadd(name_index_key, entity.id)
            
            logger.info(f"添加实体成功: {entity.name} ({entity.entity_type})")
            return True
        except Exception as e:
            logger.error(f"添加实体失败: {e}")
            return False
    
    def get_entity(self, entity_id: str) -> Optional[Entity]:
        """获取实体"""
        try:
            entity_key = f"{self.entity_prefix}{entity_id}"
            entity_data = self.redis_client.get(entity_key)
            
            if entity_data:
                return Entity.from_dict(json.loads(entity_data))
            return None
        except Exception as e:
            logger.error(f"获取实体失败: {e}")
            return None
    
    def get_entities_by_type(self, entity_type: str) -> List[Entity]:
        """按类型获取实体"""
        try:
            type_index_key = f"{self.entity_index_prefix}type:{entity_type}"
            entity_ids = self.redis_client.smembers(type_index_key)
            
            entities = []
            for entity_id in entity_ids:
                entity = self.get_entity(entity_id)
                if entity:
                    entities.append(entity)
            
            return entities
        except Exception as e:
            logger.error(f"按类型获取实体失败: {e}")
            return []
    
    def search_entities(self, keyword: str, limit: int = 20) -> List[Entity]:
        """搜索实体"""
        try:
            entities = []
            entity_keys = self.redis_client.keys(f"{self.entity_prefix}*")
            
            for entity_key in entity_keys[:limit * 2]:
                entity_data = self.redis_client.get(entity_key)
                if entity_data:
                    entity_dict = json.loads(entity_data)
                    if keyword.lower() in entity_dict['name'].lower():
                        entities.append(Entity.from_dict(entity_dict))
                        if len(entities) >= limit:
                            break
            
            return entities
        except Exception as e:
            logger.error(f"搜索实体失败: {e}")
            return []
    
    def add_relation(self, relation: Relation) -> bool:
        """添加关系"""
        try:
            relation_key = f"{self.relation_prefix}{relation.id}"
            relation_data = json.dumps(relation.to_dict(), ensure_ascii=False)
            
            self.redis_client.set(relation_key, relation_data)
            
            type_index_key = f"{self.relation_index_prefix}type:{relation.relation_type}"
            self.redis_client.sadd(type_index_key, relation.id)
            
            source_index_key = f"{self.relation_index_prefix}source:{relation.source_id}"
            self.redis_client.sadd(source_index_key, relation.id)
            
            target_index_key = f"{self.relation_index_prefix}target:{relation.target_id}"
            self.redis_client.sadd(target_index_key, relation.id)
            
            logger.info(f"添加关系成功: {relation.source_id} -> {relation.relation_type} -> {relation.target_id}")
            return True
        except Exception as e:
            logger.error(f"添加关系失败: {e}")
            return False
    
    def get_relation(self, relation_id: str) -> Optional[Relation]:
        """获取关系"""
        try:
            relation_key = f"{self.relation_prefix}{relation_id}"
            relation_data = self.redis_client.get(relation_key)
            
            if relation_data:
                return Relation.from_dict(json.loads(relation_data))
            return None
        except Exception as e:
            logger.error(f"获取关系失败: {e}")
            return None
    
    def get_relations_by_entity(self, entity_id: str) -> List[Relation]:
        """获取实体的所有关系"""
        try:
            relations = []
            
            source_index_key = f"{self.relation_index_prefix}source:{entity_id}"
            relation_ids = self.redis_client.smembers(source_index_key)
            
            for relation_id in relation_ids:
                relation = self.get_relation(relation_id)
                if relation:
                    relations.append(relation)
            
            target_index_key = f"{self.relation_index_prefix}target:{entity_id}"
            relation_ids = self.redis_client.smembers(target_index_key)
            
            for relation_id in relation_ids:
                relation = self.get_relation(relation_id)
                if relation and relation not in relations:
                    relations.append(relation)
            
            return relations
        except Exception as e:
            logger.error(f"获取实体关系失败: {e}")
            return []
    
    def get_graph_data(self, entity_id: str = None, depth: int = 2) -> Dict[str, Any]:
        """获取图谱数据（用于可视化）"""
        try:
            nodes = []
            edges = []
            visited_entities = set()
            visited_relations = set()
            
            if entity_id:
                self._build_graph_recursive(entity_id, depth, visited_entities, visited_relations, nodes, edges)
            else:
                entity_keys = self.redis_client.keys(f"{self.entity_prefix}*")
                for entity_key in entity_keys[:50]:
                    entity_data = self.redis_client.get(entity_key)
                    if entity_data:
                        entity_dict = json.loads(entity_data)
                        nodes.append({
                            "id": entity_dict['id'],
                            "label": entity_dict['name'],
                            "group": entity_dict['type'],
                            "title": f"{entity_dict['type']}: {entity_dict['name']}"
                        })
                
                relation_keys = self.redis_client.keys(f"{self.relation_prefix}*")
                for relation_key in relation_keys[:50]:
                    relation_data = self.redis_client.get(relation_key)
                    if relation_data:
                        relation_dict = json.loads(relation_data)
                        edges.append({
                            "id": relation_dict['id'],
                            "from": relation_dict['source_id'],
                            "to": relation_dict['target_id'],
                            "label": relation_dict['type'],
                            "title": relation_dict['type']
                        })
            
            return {
                "nodes": nodes,
                "edges": edges
            }
        except Exception as e:
            logger.error(f"获取图谱数据失败: {e}")
            return {"nodes": [], "edges": []}
    
    def _build_graph_recursive(self, entity_id: str, depth: int, visited_entities: set, 
                               visited_relations: set, nodes: list, edges: list):
        """递归构建图谱"""
        if depth <= 0 or entity_id in visited_entities:
            return
        
        visited_entities.add(entity_id)
        
        entity = self.get_entity(entity_id)
        if not entity:
            return
        
        nodes.append({
            "id": entity.id,
            "label": entity.name,
            "group": entity.entity_type,
            "title": f"{entity.entity_type}: {entity.name}"
        })
        
        relations = self.get_relations_by_entity(entity_id)
        
        for relation in relations:
            if relation.id in visited_relations:
                continue
            
            visited_relations.add(relation.id)
            
            edges.append({
                "id": relation.id,
                "from": relation.source_id,
                "to": relation.target_id,
                "label": relation.relation_type,
                "title": relation.relation_type
            })
            
            if relation.source_id not in visited_entities:
                self._build_graph_recursive(relation.source_id, depth - 1, 
                                           visited_entities, visited_relations, nodes, edges)
            
            if relation.target_id not in visited_entities:
                self._build_graph_recursive(relation.target_id, depth - 1, 
                                           visited_entities, visited_relations, nodes, edges)
    
    def get_stats(self) -> Dict[str, int]:
        """获取统计信息"""
        try:
            entity_count = len(self.redis_client.keys(f"{self.entity_prefix}*"))
            relation_count = len(self.redis_client.keys(f"{self.relation_prefix}*"))
            
            return {
                "entity_count": entity_count,
                "relation_count": relation_count
            }
        except Exception as e:
            logger.error(f"获取统计信息失败: {e}")
            return {"entity_count": 0, "relation_count": 0}
    
    def clear_all(self) -> bool:
        """清空所有数据"""
        try:
            entity_keys = self.redis_client.keys(f"{self.entity_prefix}*")
            relation_keys = self.redis_client.keys(f"{self.relation_prefix}*")
            entity_index_keys = self.redis_client.keys(f"{self.entity_index_prefix}*")
            relation_index_keys = self.redis_client.keys(f"{self.relation_index_prefix}*")
            
            all_keys = entity_keys + relation_keys + entity_index_keys + relation_index_keys
            
            if all_keys:
                self.redis_client.delete(*all_keys)
            
            logger.info("清空知识图谱数据成功")
            return True
        except Exception as e:
            logger.error(f"清空知识图谱数据失败: {e}")
            return False
