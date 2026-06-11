"""
========================================
Milvus 向量数据库初始化脚本
========================================

📚 功能说明：
- 创建三层向量库集合
- 为每个集合创建索引
- 验证初始化结果

🎯 使用场景：
- 首次部署系统时运行
- 重置向量库时运行

运行方式：
    python scripts/init_milvus.py

========================================
"""
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from repository.vector_repo import VectorRepository
from services.retrieval.vector.milvus_client import milvus_client
from core.logger import logger
from core.constants import MilvusCollection, MilvusIndexParams


def init_milvus():
    """
    初始化Milvus向量数据库

    🏗️ 创建三层向量库：
    1. rag_standards - 权威规范库（第一层）
    2. rag_projects - 项目资料库（第二层）
    3. rag_contracts - 合同库（第三层）
    """

    logger.info("=" * 60)
    logger.info("开始初始化Milvus向量数据库")
    logger.info("=" * 60)

    try:
        # 创建VectorRepository实例
        vector_repo = VectorRepository()

        # 定义三层向量库配置
        collections_config = [
            {
                "name": MilvusCollection.STANDARDS.value,
                "description": "权威规范库 - 存储国标、行标、企业标准等权威文档"
            },
            {
                "name": MilvusCollection.PROJECTS.value,
                "description": "项目资料库 - 存储项目总结、施工记录、经验文档"
            },
            {
                "name": MilvusCollection.CONTRACTS.value,
                "description": "合同库 - 存储采购合同、施工合同、技术协议"
            }
        ]

        # 创建集合
        logger.info("\n步骤 1/3: 创建向量库集合")
        logger.info("-" * 60)

        for config in collections_config:
            collection_name = config["name"]
            description = config["description"]

            logger.info(f"\n创建集合: {collection_name}")
            logger.info(f"描述: {description}")

            # 创建集合
            collection = vector_repo.create_collection(
                collection_name=collection_name,
                description=description
            )

            logger.info(f"✓ 集合 {collection_name} 创建成功")

        # 创建索引
        logger.info("\n步骤 2/3: 为集合创建索引")
        logger.info("-" * 60)

        for config in collections_config:
            collection_name = config["name"]

            logger.info(f"\n为集合 {collection_name} 创建索引...")

            # 使用IVF_FLAT索引（平衡性能和准确率）
            vector_repo.create_index(
                collection_name=collection_name,
                index_params=MilvusIndexParams.IVF_FLAT
            )

            logger.info(f"✓ 集合 {collection_name} 索引创建成功")

        # 验证初始化结果
        logger.info("\n步骤 3/3: 验证初始化结果")
        logger.info("-" * 60)

        for config in collections_config:
            collection_name = config["name"]

            # 获取集合统计信息
            stats = vector_repo.get_collection_stats(collection_name)

            logger.info(f"\n集合: {stats['name']}")
            logger.info(f"  - 向量数量: {stats['num_entities']}")
            logger.info(f"  - 描述: {stats['description']}")

        # 关闭连接（单例统一管理）
        milvus_client.close()

        logger.info("\n" + "=" * 60)
        logger.info("✓ Milvus向量数据库初始化完成！")
        logger.info("=" * 60)

        logger.info("\n📊 已创建的集合：")
        for config in collections_config:
            logger.info(f"  - {config['name']}: {config['description']}")

        return True

    except Exception as e:
        logger.error(f"\n✗ Milvus初始化失败: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return False


def reset_milvus():
    """
    重置Milvus向量数据库（删除所有集合后重新创建）

    ⚠️ 危险操作！会删除所有向量数据
    """

    logger.warning("=" * 60)
    logger.warning("⚠️  警告：即将重置Milvus向量数据库")
    logger.warning("这将删除所有现有的向量数据！")
    logger.warning("=" * 60)

    # 二次确认
    confirm = input("\n请输入 'YES' 确认重置（其他任何输入将取消）: ")

    if confirm != "YES":
        logger.info("已取消重置操作")
        return False

    try:
        vector_repo = VectorRepository()

        # 删除所有集合
        collections = [
            MilvusCollection.STANDARDS.value,
            MilvusCollection.PROJECTS.value,
            MilvusCollection.CONTRACTS.value
        ]

        logger.info("\n删除现有集合...")
        for collection_name in collections:
            vector_repo.drop_collection(collection_name)
            logger.info(f"✓ 已删除集合: {collection_name}")

        # 重新初始化
        logger.info("\n重新创建集合...")
        result = init_milvus()

        return result

    except Exception as e:
        logger.error(f"\n✗ 重置失败: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return False


def check_milvus_status():
    """
    检查Milvus向量数据库状态
    """

    logger.info("=" * 60)
    logger.info("检查Milvus向量数据库状态")
    logger.info("=" * 60)

    try:
        vector_repo = VectorRepository()

        collections = [
            MilvusCollection.STANDARDS.value,
            MilvusCollection.PROJECTS.value,
            MilvusCollection.CONTRACTS.value
        ]

        logger.info("\n📊 集合状态：\n")

        total_vectors = 0
        for collection_name in collections:
            stats = vector_repo.get_collection_stats(collection_name)

            if "error" in stats:
                logger.warning(f"✗ {collection_name}: 不存在")
            else:
                num_entities = stats['num_entities']
                total_vectors += num_entities

                logger.info(f"✓ {collection_name}")
                logger.info(f"  - 向量数量: {num_entities:,}")
                logger.info(f"  - 描述: {stats['description']}\n")

        logger.info("-" * 60)
        logger.info(f"总向量数: {total_vectors:,}")
        logger.info("=" * 60)

        milvus_client.close()

        return True

    except Exception as e:
        logger.error(f"\n✗ 检查失败: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return False


def main():
    """
    主函数：提供交互式菜单
    """

    print("\n" + "=" * 60)
    print("Milvus 向量数据库管理工具")
    print("=" * 60)

    print("\n请选择操作：")
    print("1. 初始化Milvus（首次部署使用）")
    print("2. 检查Milvus状态")
    print("3. 重置Milvus（⚠️ 删除所有数据）")
    print("0. 退出")

    choice = input("\n请输入选项（0-3）: ").strip()

    if choice == "1":
        init_milvus()
    elif choice == "2":
        check_milvus_status()
    elif choice == "3":
        reset_milvus()
    elif choice == "0":
        print("退出")
    else:
        print("无效的选项")


if __name__ == "__main__":
    main()

# =========================================
# 💡 使用示例
# =========================================
"""
# 1. 首次初始化
python scripts/init_milvus.py
# 选择选项 1

# 2. 检查状态
python scripts/init_milvus.py
# 选择选项 2

# 3. 在代码中直接调用
from scripts.init_milvus import init_milvus

success = init_milvus()
if success:
    print("初始化成功")
"""