#!/usr/bin/env python3
"""
自定义 DeepSeek 嵌入客户端
"""

import logging
from typing import List
from graphiti_core.embedder.client import EmbedderClient

logger = logging.getLogger(__name__)

class DeepSeekEmbedder(EmbedderClient):
    """简化的嵌入客户端，避免调用OpenAI API"""
    
    def __init__(self):
        logger.info("✅ 初始化 DeepSeek 嵌入客户端（简化版）")
        # 设置固定的嵌入维度
        self.embedding_dim = 384
    
    async def create(self, input_data) -> List[float]:
        """实现抽象方法：生成文本的嵌入向量"""
        if isinstance(input_data, str):
            return await self.embed_text(input_data)
        elif isinstance(input_data, list) and all(isinstance(item, str) for item in input_data):
            # 如果是字符串列表，返回第一个的嵌入
            if input_data:
                return await self.embed_text(input_data[0])
            else:
                return [0.0] * self.embedding_dim
        else:
            # 对于其他类型，转换为字符串
            return await self.embed_text(str(input_data))
    
    async def embed_text(self, text: str) -> List[float]:
        """生成文本的嵌入向量（简化实现）"""
        # 使用简单的哈希方法生成固定长度的向量
        # 这是一个占位符实现，避免调用外部API
        import hashlib
        import struct
        
        # 使用文本的哈希值生成伪嵌入向量
        hash_obj = hashlib.sha256(text.encode('utf-8'))
        hash_bytes = hash_obj.digest()
        
        # 将哈希字节转换为浮点数向量
        embedding = []
        for i in range(0, min(len(hash_bytes), self.embedding_dim * 4), 4):
            if i + 4 <= len(hash_bytes):
                float_val = struct.unpack('f', hash_bytes[i:i+4])[0]
                # 标准化到 [-1, 1] 范围
                float_val = max(-1.0, min(1.0, float_val / 1e10))
                embedding.append(float_val)
        
        # 填充到目标维度
        while len(embedding) < self.embedding_dim:
            embedding.append(0.0)
        
        # 截断到目标维度
        embedding = embedding[:self.embedding_dim]
        
        logger.debug(f"生成嵌入向量，文本长度: {len(text)}, 向量维度: {len(embedding)}")
        return embedding
    
    async def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """批量生成文本的嵌入向量"""
        embeddings = []
        for text in texts:
            embedding = await self.embed_text(text)
            embeddings.append(embedding)
        
        logger.debug(f"批量生成嵌入向量，文本数量: {len(texts)}")
        return embeddings
    
    def get_embedding_dim(self) -> int:
        """返回嵌入向量的维度"""
        return self.embedding_dim 