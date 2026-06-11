"""
========================================
Embedding模型管理器
========================================

📚 模块说明：
- 加载和管理向量化模型
- 支持多种Embedding模型
- 统一的向量化接口

🎯 核心功能：
1. 模型加载和缓存
2. 批量向量化
3. 相似度计算
4. 模型切换

========================================
"""

import os
from typing import List, Union, Optional, Dict
from pathlib import Path

import numpy as np
from loguru import logger

from core.config import settings

# 重型依赖懒加载守卫：缺失 torch/sentence_transformers 时模块仍可 import
try:
    import sentence_transformers  # noqa: F401
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False
    logger.warning("sentence_transformers 未安装，Embedding 功能不可用。请运行: uv add sentence-transformers")


class EmbeddingModel:
    """
    Embedding模型管理器

    🔧 支持的模型：
    - BAAI/bge-large-zh-v1.5 (推荐中文)
    - BAAI/bge-base-zh-v1.5
    - shibing624/text2vec-base-chinese
    - 其他SentenceTransformer兼容模型

    💡 特性：
    - 自动设备选择（GPU/CPU）
    - 批量处理优化
    - 模型缓存
    """

    def __init__(
            self,
            model_name: Optional[str] = None,
            device: Optional[str] = None,
            cache_dir: Optional[str] = None,
            normalize_embeddings: bool = True
    ):
        """
        初始化Embedding模型

        参数：
            model_name: 模型名称或路径（默认从 settings.EMBEDDING_MODEL_NAME 读取）
            device: 设备 ('cuda', 'cpu', 'mps' 或 None自动选择)
            cache_dir: 模型缓存目录
            normalize_embeddings: 是否归一化向量（推荐True）
        """
        self.model_name = model_name or settings.EMBEDDING_MODEL_NAME
        self.normalize_embeddings = normalize_embeddings
        self.device = device  # None 时在 _load_model 内根据 torch 可用性确定
        self.cache_dir = cache_dir or os.path.join(
            Path.home(),
            '.cache',
            'huggingface',
            'hub'
        )

        logger.info(
            f"初始化Embedding模型 | "
            f"模型: {self.model_name} | "
            f"归一化: {normalize_embeddings}"
        )

        # 加载模型
        self.model = self._load_model()
        self.dimension = self.model.get_sentence_embedding_dimension()

        # 维度单一事实源校验
        if self.dimension != settings.VECTOR_DIM:
            logger.warning(
                f"模型维度({self.dimension})与 settings.VECTOR_DIM({settings.VECTOR_DIM}) 不一致"
            )

        logger.info(f"模型加载完成 | 设备: {self.device} | 向量维度: {self.dimension}")

    def _resolve_device(self) -> str:
        """根据 torch 可用性确定设备"""
        import torch

        if self.device is not None:
            return self.device

        if torch.cuda.is_available():
            return 'cuda'
        # mps 用 getattr 守卫，旧版 torch 无 mps 后端
        mps = getattr(torch.backends, 'mps', None)
        if mps is not None and mps.is_available():
            return 'mps'
        return 'cpu'

    def _load_model(self):
        """加载SentenceTransformer模型（懒加载重型依赖）"""
        if not SENTENCE_TRANSFORMERS_AVAILABLE:
            raise RuntimeError(
                "sentence_transformers 未安装，无法加载 Embedding 模型。请运行: uv add sentence-transformers"
            )

        from sentence_transformers import SentenceTransformer

        try:
            self.device = self._resolve_device()
            model = SentenceTransformer(
                self.model_name,
                device=self.device,
                cache_folder=self.cache_dir
            )
            model.eval()
            return model

        except Exception as e:
            logger.error(f"模型加载失败: {e}")
            raise

    def encode(
            self,
            texts: Union[str, List[str]],
            batch_size: int = 32,
            show_progress: bool = False,
            convert_to_numpy: bool = True
    ) -> np.ndarray:
        """
        将文本编码为向量

        参数：
            texts: 单个文本或文本列表
            batch_size: 批处理大小
            show_progress: 是否显示进度条
            convert_to_numpy: 是否转为numpy数组

        返回：
            向量数组 shape=(n, dimension)；单文本返回 (dimension,)

        契约：输入输出一一对应，空文本填零向量保持顺序与长度，不丢弃
        """
        # 统一处理为列表
        if isinstance(texts, str):
            texts = [texts]
            single_text = True
        else:
            single_text = False

        # 区分有效文本与空文本，记录位置以保持顺序一一对应
        valid_indices = [i for i, t in enumerate(texts) if t and t.strip()]
        valid_texts = [texts[i] for i in valid_indices]

        # 全空：返回与输入等长的零向量矩阵
        if not valid_texts:
            logger.warning("输入全部为空文本，返回零向量")
            result = np.zeros((len(texts), self.dimension), dtype=np.float32)
            return result[0] if single_text else result

        logger.debug(f"编码文本 | 有效: {len(valid_texts)}/{len(texts)} | batch_size: {batch_size}")

        try:
            valid_embeddings = self.model.encode(
                valid_texts,
                batch_size=batch_size,
                show_progress_bar=show_progress,
                convert_to_numpy=True,
                normalize_embeddings=self.normalize_embeddings
            )

            # 回填到与输入等长的矩阵，空文本位置保持零向量
            result = np.zeros((len(texts), self.dimension), dtype=valid_embeddings.dtype)
            for slot, orig_idx in enumerate(valid_indices):
                result[orig_idx] = valid_embeddings[slot]

            return result[0] if single_text else result

        except Exception as e:
            logger.error(f"文本编码失败: {e}")
            raise

    def encode_queries(
            self,
            queries: Union[str, List[str]],
            **kwargs
    ) -> np.ndarray:
        """
        编码查询文本（为查询优化）

        注意：某些模型对查询和文档使用不同的编码
        """
        # BGE模型需要添加查询指令
        if 'bge' in self.model_name.lower():
            if isinstance(queries, str):
                queries = f"为这个句子生成表示以用于检索相关文章：{queries}"
            else:
                queries = [
                    f"为这个句子生成表示以用于检索相关文章：{q}"
                    for q in queries
                ]

        return self.encode(queries, **kwargs)

    def similarity(
            self,
            embeddings1: np.ndarray,
            embeddings2: np.ndarray,
            metric: str = 'cosine'
    ) -> Union[float, np.ndarray]:
        """
        计算向量相似度

        参数：
            embeddings1: 向量1或向量矩阵1
            embeddings2: 向量2或向量矩阵2
            metric: 相似度度量 ('cosine', 'dot', 'euclidean')

        返回：
            相似度分数
        """
        if metric == 'cosine':
            if self.normalize_embeddings:
                return np.dot(embeddings1, embeddings2.T)
            else:
                norm1 = np.linalg.norm(embeddings1, axis=-1, keepdims=True)
                norm2 = np.linalg.norm(embeddings2, axis=-1, keepdims=True)
                return np.dot(embeddings1, embeddings2.T) / (norm1 * norm2.T)

        elif metric == 'dot':
            return np.dot(embeddings1, embeddings2.T)

        elif metric == 'euclidean':
            return -np.linalg.norm(
                embeddings1[:, None] - embeddings2,
                axis=-1
            )

        else:
            raise ValueError(f"不支持的相似度度量: {metric}")

    def get_model_info(self) -> Dict:
        """获取模型信息"""
        return {
            'model_name': self.model_name,
            'dimension': self.dimension,
            'device': self.device,
            'normalize_embeddings': self.normalize_embeddings,
            'max_seq_length': self.model.max_seq_length
        }

    def __repr__(self) -> str:
        return (
            f"EmbeddingModel("
            f"model='{self.model_name}', "
            f"dim={getattr(self, 'dimension', '?')}, "
            f"device='{self.device}')"
        )
