"""
========================================
重建索引脚本
========================================

📚 模块说明：
- 重建 BM25 索引
- 重建向量索引
- 支持增量和全量重建

🚀 使用方式：
    python scripts/rebuild_index.py

========================================
"""

import sys
import os
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime
import argparse

# 添加项目根目录到 Python 路径
ROOT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT_DIR))

from loguru import logger

# 导入核心模块
from core.config import settings
from core.constants import MilvusCollection

# 导入服务模块
from services.retrieval.bm25.bm25_engine import BM25Retriever
from repository.vector_repo import VectorRepository
from repository.document_repo import DocumentRepository
from services.retrieval.vector.milvus_client import milvus_client

# 数据库
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


class IndexRebuilder:
    """
    索引重建器

    🔧 功能：
    1. 重建 BM25 索引
    2. 重建向量索引
    3. 支持指定集合
    4. 支持增量更新
    """

    def __init__(self):
        """初始化索引重建器"""
        logger.info("初始化索引重建器...")

        # 初始化数据库
        self.engine = create_engine(settings.postgres_url)
        Session = sessionmaker(bind=self.engine)
        self.session = Session()
        self.doc_repo = DocumentRepository(self.session)

        # 初始化向量库
        self.vector_repo = VectorRepository()

        # Embedding 懒加载（首次向量化时才构造重型 ML 层）
        self._embedder = None

        # 初始化 BM25
        self.bm25_retriever = BM25Retriever()

        # 统计
        self.stats = {
            'bm25_docs': 0,
            'vector_docs': 0,
            'errors': 0,
            'total_time': 0
        }

        logger.info("索引重建器初始化完成")

    @property
    def embedder(self):
        """懒加载向量化服务，缺失重型依赖时给出清晰提示"""
        if self._embedder is None:
            try:
                from services.embedding.embedding_model import EmbeddingModel
                from services.embedding.embedder import Embedder
            except ImportError as e:
                raise RuntimeError(
                    f"缺少向量化依赖（重型 ML 层）：{e}。请运行 uv add torch sentence-transformers"
                ) from e

            embedding_model = EmbeddingModel(model_name=settings.EMBEDDING_MODEL_NAME)
            self._embedder = Embedder(
                embedding_model=embedding_model,
                batch_size=settings.EMBEDDING_BATCH_SIZE
            )
        return self._embedder

    def rebuild_bm25_index(
        self,
        save_path: Optional[str] = None
    ) -> bool:
        """
        重建 BM25 索引

        参数：
            save_path: 索引保存路径

        返回：
            bool: 是否成功
        """
        logger.info("=" * 60)
        logger.info("开始重建 BM25 索引")
        logger.info("=" * 60)

        start_time = datetime.now()

        try:
            # 1. 从数据库获取所有文档
            logger.info("从数据库加载文档...")
            documents = self.doc_repo.get_all_documents()

            if not documents:
                logger.warning("没有找到文档")
                return False

            logger.info(f"加载了 {len(documents)} 个文档")

            # 2. 准备 BM25 文档格式
            bm25_docs = []
            for doc in documents:
                # 获取文档的所有 chunks
                chunks = self.doc_repo.get_document_chunks(doc.id)

                for chunk in chunks:
                    bm25_docs.append({
                        'id': f"{doc.id}_{chunk.chunk_index}",
                        'text': chunk.text,
                        'metadata': {
                            'doc_id': doc.id,
                            'doc_name': doc.name,
                            'chunk_index': chunk.chunk_index
                        }
                    })

            logger.info(f"准备了 {len(bm25_docs)} 个文档块")

            # 3. 构建索引
            logger.info("构建 BM25 索引...")
            self.bm25_retriever.build_index(bm25_docs)

            # 4. 保存索引
            if save_path is None:
                save_path = str(settings.DATA_DIR / "indexes" / "bm25_index.pkl")

            # 确保目录存在
            Path(save_path).parent.mkdir(parents=True, exist_ok=True)

            self.bm25_retriever.save(save_path)
            logger.info(f"索引已保存: {save_path}")

            # 更新统计
            self.stats['bm25_docs'] = len(bm25_docs)
            process_time = (datetime.now() - start_time).total_seconds()
            self.stats['total_time'] += process_time

            logger.info(f"✓ BM25 索引重建完成 | 文档数: {len(bm25_docs)} | 耗时: {process_time:.2f}s")

            return True

        except Exception as e:
            self.stats['errors'] += 1
            logger.error(f"✗ BM25 索引重建失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False

    def rebuild_vector_index(
        self,
        collection_name: Optional[str] = None,
        drop_existing: bool = False
    ) -> bool:
        """
        重建向量索引

        参数：
            collection_name: 集合名称（None=重建所有）
            drop_existing: 是否删除现有集合

        返回：
            bool: 是否成功
        """
        logger.info("=" * 60)
        logger.info("开始重建向量索引")
        logger.info("=" * 60)

        start_time = datetime.now()

        try:
            # 确定要重建的集合
            if collection_name:
                collections = [collection_name]
            else:
                collections = [
                    MilvusCollection.STANDARDS.value,
                    MilvusCollection.PROJECTS.value,
                    MilvusCollection.CONTRACTS.value
                ]

            total_vectors = 0

            for coll_name in collections:
                logger.info(f"\n处理集合: {coll_name}")

                # 删除现有集合
                if drop_existing:
                    logger.info(f"  删除现有集合...")
                    self.vector_repo.drop_collection(coll_name)

                # 创建集合
                logger.info(f"  创建集合...")
                self.vector_repo.create_collection(
                    collection_name=coll_name,
                    description=f"RAG 向量集合 - {coll_name}"
                )

                # 创建索引
                logger.info(f"  创建索引...")
                self.vector_repo.create_index(coll_name)

                # 获取该集合的文档
                documents = self.doc_repo.get_documents_by_collection(coll_name)

                if not documents:
                    logger.info(f"  集合 {coll_name} 没有文档")
                    continue

                logger.info(f"  找到 {len(documents)} 个文档")

                # 重新向量化并插入
                vectors_data = []
                for doc in documents:
                    chunks = self.doc_repo.get_document_chunks(doc.id)

                    for chunk in chunks:
                        # 向量化
                        embedding = self.embedder.embed_query(chunk.text)

                        vectors_data.append({
                            'doc_id': f"{doc.id}_{chunk.chunk_index}",
                            'text': chunk.text,
                            'embedding': embedding,
                            'metadata': {
                                'doc_id': doc.id,
                                'doc_name': doc.name,
                                'chunk_index': chunk.chunk_index
                            }
                        })

                # 批量插入
                if vectors_data:
                    logger.info(f"  插入 {len(vectors_data)} 个向量...")
                    self.vector_repo.insert_vectors(
                        collection_name=coll_name,
                        vectors=vectors_data
                    )
                    total_vectors += len(vectors_data)

                logger.info(f"  ✓ 集合 {coll_name} 完成")

            # 更新统计
            self.stats['vector_docs'] = total_vectors
            process_time = (datetime.now() - start_time).total_seconds()
            self.stats['total_time'] += process_time

            logger.info(f"\n✓ 向量索引重建完成 | 总向量数: {total_vectors} | 耗时: {process_time:.2f}s")

            return True

        except Exception as e:
            self.stats['errors'] += 1
            logger.error(f"✗ 向量索引重建失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False

    def rebuild_all(
        self,
        drop_existing: bool = False
    ) -> bool:
        """
        重建所有索引

        参数：
            drop_existing: 是否删除现有数据

        返回：
            bool: 是否成功
        """
        logger.info("=" * 60)
        logger.info("🚀 开始重建所有索引")
        logger.info("=" * 60)

        success = True

        # 重建 BM25
        if not self.rebuild_bm25_index():
            success = False

        # 重建向量索引
        if not self.rebuild_vector_index(drop_existing=drop_existing):
            success = False

        return success

    def print_stats(self):
        """打印统计信息"""
        print("\n" + "=" * 60)
        print("📊 索引重建统计")
        print("=" * 60)
        print(f"  BM25 文档数: {self.stats['bm25_docs']}")
        print(f"  向量文档数: {self.stats['vector_docs']}")
        print(f"  错误数: {self.stats['errors']}")
        print(f"  总耗时: {self.stats['total_time']:.2f}s")
        print("=" * 60)

    def close(self):
        """关闭连接"""
        try:
            self.session.close()
            milvus_client.close()
            logger.info("连接已关闭")
        except Exception as e:
            logger.error(f"关闭连接失败: {e}")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="企业级 RAG 系统 - 索引重建工具"
    )

    parser.add_argument(
        '-t', '--type',
        choices=['all', 'bm25', 'vector'],
        default='all',
        help='重建类型（默认: all）'
    )

    parser.add_argument(
        '-c', '--collection',
        default=None,
        help='向量库集合名称（仅 vector 类型有效）'
    )

    parser.add_argument(
        '--drop',
        action='store_true',
        help='删除现有数据后重建'
    )

    parser.add_argument(
        '-y', '--yes',
        action='store_true',
        help='跳过确认'
    )

    args = parser.parse_args()

    # 打印配置
    print("\n" + "=" * 60)
    print("🔧 企业级 RAG 系统 - 索引重建工具")
    print("=" * 60)
    print(f"  重建类型: {args.type}")
    print(f"  集合: {args.collection or '所有'}")
    print(f"  删除现有: {'是' if args.drop else '否'}")
    print("=" * 60)

    # 确认
    if not args.yes:
        if args.drop:
            confirm = input("\n⚠️ 将删除现有数据，确认继续？(y/n): ").strip().lower()
        else:
            confirm = input("\n确认开始重建？(y/n): ").strip().lower()

        if confirm != 'y':
            print("已取消")
            return

    # 初始化重建器
    rebuilder = IndexRebuilder()

    try:
        if args.type == 'all':
            rebuilder.rebuild_all(drop_existing=args.drop)
        elif args.type == 'bm25':
            rebuilder.rebuild_bm25_index()
        elif args.type == 'vector':
            rebuilder.rebuild_vector_index(
                collection_name=args.collection,
                drop_existing=args.drop
            )

        # 打印统计
        rebuilder.print_stats()

    finally:
        rebuilder.close()


if __name__ == "__main__":
    main()


# =========================================
# 💡 使用示例
# =========================================
"""
# 1. 重建所有索引
python scripts/rebuild_index.py

# 2. 只重建 BM25 索引
python scripts/rebuild_index.py -t bm25

# 3. 只重建向量索引
python scripts/rebuild_index.py -t vector

# 4. 重建指定集合的向量索引
python scripts/rebuild_index.py -t vector -c rag_standards

# 5. 删除现有数据后重建
python scripts/rebuild_index.py --drop

# 6. 跳过确认
python scripts/rebuild_index.py -y

# 7. 在代码中使用
from scripts.rebuild_index import IndexRebuilder

rebuilder = IndexRebuilder()
rebuilder.rebuild_all()
rebuilder.print_stats()
rebuilder.close()
"""
