"""
========================================
配置管理模块
========================================

📚 模块说明：
- 使用 Pydantic Settings 管理所有配置项
- 配置来源：环境变量 > .env文件 > 默认值
- 自动验证配置的有效性

🎯 使用方法：
    from core.config import settings

    # 获取配置
    db_url = settings.postgres_url
    log_level = settings.LOG_LEVEL

    # 修改配置（仅在初始化时）
    settings.DEBUG = True

========================================
"""
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator
from typing import Optional, List
from pathlib import Path


class Settings(BaseSettings):
    """
    应用配置类

    设计理念：
    1. 所有配置集中管理，避免硬编码
    2. 使用类型注解，IDE有智能提示
    3. 自动验证配置，避免运行时错误
    """

    # =========================================
    # 应用基础配置
    # =========================================
    APP_NAME: str = "Enterprise RAG System"
    APP_VERSION: str = "1.0.0"
    API_PREFIX: str = "/api/v1"  # API路由前缀

    # 调试模式：开发时设为True，生产环境必须为False
    DEBUG: bool = Field(default=False, description="调试模式")

    # 运行环境：development(开发) / production(生产)
    ENVIRONMENT: str = Field(default="production", description="运行环境")

    # =========================================
    # 服务器配置
    # =========================================
    HOST: str = Field(default="0.0.0.0", description="服务绑定地址")
    PORT: int = Field(default=8000, description="服务端口")
    WORKERS: int = Field(default=4, description="Worker进程数")

    # =========================================
    # PostgreSQL 关系数据库配置
    # =========================================
    # 用途：存储文档元数据、用户信息、查询日志等

    POSTGRES_HOST: str = Field(default="localhost", description="PostgreSQL主机地址")
    POSTGRES_PORT: int = Field(default=5432, description="PostgreSQL端口")
    POSTGRES_USER: str = Field(default="rag_user", description="数据库用户名")
    POSTGRES_PASSWORD: str = Field(default="", description="数据库密码")
    POSTGRES_DB: str = Field(default="enterprise_rag", description="数据库名称")

    @property
    def postgres_url(self) -> str:
        """
        构建PostgreSQL连接URL

        返回格式：postgresql://用户名:密码@主机:端口/数据库名
        示例：postgresql://rag_user:password@localhost:5432/enterprise_rag
        """
        return (
            f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    # =========================================
    # Milvus 向量数据库配置
    # =========================================
    # 用途：存储文档向量，支持高效的相似度搜索

    MILVUS_HOST: str = Field(default="localhost", description="Milvus主机地址")
    MILVUS_PORT: int = Field(default=19530, description="Milvus端口")
    MILVUS_USER: str = Field(default="", description="Milvus用户名（可选）")
    MILVUS_PASSWORD: str = Field(default="", description="Milvus密码（可选）")

    # --- 分层向量库设计 ---
    # 📌 核心设计理念：将不同类型的文档分层存储，实现：
    #    1. 权限隔离：不同层级有不同的访问权限
    #    2. 检索优先级：优先搜索权威规范，再搜索项目资料
    #    3. 更新效率：新规范只需更新对应层级，不影响其他层

    MILVUS_COLLECTION_STANDARD: str = "rag_standards"  # 第一层：权威规范库（优先级最高）
    MILVUS_COLLECTION_PROJECT: str = "rag_projects"  # 第二层：项目资料库
    MILVUS_COLLECTION_CONTRACT: str = "rag_contracts"  # 第三层：合同库（权限要求最高）

    # --- 向量配置 ---
    VECTOR_DIM: int = Field(default=1024, description="向量维度（取决于Embedding模型）")

    # 索引类型说明：
    # - IVF_FLAT：平衡性能和准确率，适合中等规模（推荐）
    # - IVF_SQ8：更省内存，略降精度
    # - HNSW：最高精度，但内存占用大
    MILVUS_INDEX_TYPE: str = Field(default="IVF_FLAT", description="向量索引类型")

    # 相似度度量方式：
    # - IP (Inner Product)：内积，适合归一化向量（推荐）
    # - L2：欧式距离
    # - COSINE：余弦相似度
    MILVUS_METRIC_TYPE: str = Field(default="IP", description="相似度度量方式")

    # =========================================
    # Redis 缓存配置
    # =========================================
    # 用途：
    # 1. 缓存热门查询结果，避免重复计算
    # 2. 存储用户搜索历史
    # 3. 缓存用户权限信息

    REDIS_HOST: str = Field(default="localhost", description="Redis主机地址")
    REDIS_PORT: int = Field(default=6379, description="Redis端口")
    REDIS_PASSWORD: str = Field(default="", description="Redis密码（可选）")
    REDIS_DB: int = Field(default=0, description="Redis数据库索引")

    # 缓存过期时间：6小时 = 21600秒
    # 💡 为什么是6小时？平衡缓存命中率和数据新鲜度
    REDIS_CACHE_TTL: int = Field(default=21600, description="缓存过期时间(秒)")

    @property
    def redis_url(self) -> str:
        """
        构建Redis连接URL

        返回格式：redis://[:密码@]主机:端口/数据库索引
        """
        auth = f":{self.REDIS_PASSWORD}@" if self.REDIS_PASSWORD else ""
        return f"redis://{auth}{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

    # =========================================
    # Neo4j 图数据库配置
    # =========================================
    # 用途：
    # 1. 存储施工图知识图谱
    # 2. 管理实体和关系（构件、材料、规范等）
    # 3. 支持图谱增强的RAG检索

    NEO4J_URI: str = Field(default="bolt://localhost:7687", description="Neo4j连接URI")
    NEO4J_USER: str = Field(default="neo4j", description="Neo4j用户名")
    NEO4J_PASSWORD: str = Field(default="", description="Neo4j密码")
    NEO4J_DATABASE: str = Field(default="neo4j", description="Neo4j数据库名")

    # --- 连接池配置 ---
    NEO4J_MAX_CONNECTION_POOL_SIZE: int = Field(default=50, description="最大连接池大小")
    NEO4J_CONNECTION_TIMEOUT: int = Field(default=30, description="连接超时时间(秒)")
    NEO4J_MAX_TRANSACTION_RETRY_TIME: int = Field(default=30, description="事务最大重试时间(秒)")

    @property
    def neo4j_url(self) -> str:
        """
        获取Neo4j连接URI

        返回格式：bolt://主机:端口
        """
        return self.NEO4J_URI

    # =========================================
    # 文件路径配置
    # =========================================
    # 📁 项目目录结构：
    # Enterprise_RAG/
    # ├── data/
    # │   ├── raw_docs/     <- 原始文档存放处
    # │   └── processed/    <- 处理后的文档
    # └── logs/             <- 日志文件

    BASE_DIR: Path = Field(default_factory=lambda: Path(__file__).parent.parent)
    DATA_DIR: Path = Field(default_factory=lambda: Path(__file__).parent.parent / "data")
    RAW_DOCS_DIR: Path = Field(default_factory=lambda: Path(__file__).parent.parent / "data" / "raw_docs")
    PROCESSED_DIR: Path = Field(default_factory=lambda: Path(__file__).parent.parent / "data" / "processed")
    LOG_DIR: Path = Field(default_factory=lambda: Path(__file__).parent.parent / "logs")

    # =========================================
    # Embedding 向量化模型配置
    # =========================================
    # 🎯 Embedding的作用：将文本转换为数字向量，用于相似度计算

    # 推荐的中文模型：
    # - hfl/chinese-roberta-wwm-ext：通用中文（推荐）
    # - BAAI/bge-large-zh：更大更强，但更慢
    # - shibing624/text2vec-base-chinese：轻量级
    EMBEDDING_MODEL_NAME: str = Field(
        default="BAAI/bge-large-zh-v1.5",
        description="中文Embedding模型名称"
    )

    # 如果有本地下载的模型，可以指定路径，避免每次从网上下载
    EMBEDDING_MODEL_PATH: Optional[str] = Field(
        default=None,
        description="本地模型路径（可选）"
    )

    # 批处理配置：一次处理多少条文本（越大越快，但占用内存越多）
    EMBEDDING_BATCH_SIZE: int = Field(default=32, description="向量化批处理大小")

    # 最大文本长度：超过会被截断（BERT类模型一般是512）
    EMBEDDING_MAX_LENGTH: int = Field(default=512, description="文本最大长度")

    # =========================================
    # 文档处理配置
    # =========================================

    # --- 文本分块策略 ---
    # 🔍 为什么要分块？
    #    长文档无法直接输入模型，需要切成小块
    #    每个块既要足够小（适合模型），又要足够大（保留上下文）

    CHUNK_SIZE: int = Field(default=512, description="每个文本块的大小(tokens)")

    # 重叠大小：相邻两个块之间的重叠部分
    # 💡 为什么要重叠？避免重要信息被切断
    CHUNK_OVERLAP: int = Field(default=50, description="文本块之间的重叠大小")

    # --- OCR光学字符识别配置 ---
    OCR_ENABLED: bool = Field(default=True, description="是否启用OCR识别扫描件")
    OCR_LANGUAGE: str = Field(default="ch", description="OCR语言：ch(中文)/en(英文)")

    # --- 支持的文件格式 ---
    SUPPORTED_FILE_TYPES: List[str] = Field(
        default=[".pdf", ".docx", ".doc", ".txt"],
        description="支持上传的文件类型"
    )

    # =========================================
    # 混合检索配置
    # =========================================
    # 🎯 核心理念：结合BM25关键词检索和向量语义检索，互补优势

    # --- 权重配置 ---
    # 📊 权重含义：
    #    BM25权重 = 0.3  -> 关键词匹配占30%
    #    向量权重 = 0.4  -> 语义相似度占40%
    #    Rerank权重 = 0.3 -> 精排模型占30%
    #    三者之和 = 1.0

    BM25_WEIGHT: float = Field(default=0.3, description="BM25关键词检索权重")
    VECTOR_WEIGHT: float = Field(default=0.4, description="向量语义检索权重")
    RERANK_WEIGHT: float = Field(default=0.3, description="Rerank重排序权重")

    # --- 召回配置 ---
    # 🔄 检索流程：
    #    1. 初始召回：BM25和向量检索各返回100条
    #    2. 合并去重：得到约150-200条候选
    #    3. Rerank重排序：从候选中选出最相关的5条

    RETRIEVAL_TOP_K: int = Field(default=100, description="初始召回文档数量")
    RERANK_TOP_K: int = Field(default=5, description="重排序后返回的Top-K数量")

    # --- Rerank重排序模型 ---
    # 🎯 作用：对初步检索结果进行精准排序，提高Top-5的准确率
    RERANK_MODEL_NAME: str = Field(
        default="BAAI/bge-reranker-base",
        description="重排序模型名称"
    )

    # =========================================
    # LLM 大语言模型配置
    # =========================================
    # 🤖 LLM的作用：基于检索到的文档，生成最终答案

    LLM_MODEL_NAME: str = Field(default="Qwen/Qwen-7B-Chat", description="LLM模型名称")

    # API配置（如果使用在线API）
    LLM_API_BASE: Optional[str] = Field(default=None, description="LLM API地址")
    LLM_API_KEY: Optional[str] = Field(default=None, description="LLM API密钥")

    # 生成参数
    LLM_MAX_TOKENS: int = Field(default=2048, description="最大生成长度")

    # Temperature：控制生成的随机性
    # - 0.0：完全确定性（每次生成相同）
    # - 1.0：更有创造性（但可能不稳定）
    # - 0.7：平衡点（推荐）
    LLM_TEMPERATURE: float = Field(default=0.7, description="生成温度参数")

    # --- LoRA微调配置 ---
    # 🎓 LoRA：一种参数高效的微调方法
    # 用途：让模型更懂工程专业术语，减少"胡说八道"
    LORA_ENABLED: bool = Field(default=False, description="是否使用LoRA微调模型")
    LORA_MODEL_PATH: Optional[str] = Field(default=None, description="LoRA模型文件路径")

    # =========================================
    # 权限控制配置
    # =========================================
    # 🔒 重要性：防止用户访问无权限的敏感文档

    ENABLE_PERMISSION_CHECK: bool = Field(
        default=True,
        description="是否启用权限检查（生产环境必须开启）"
    )

    # --- 跨域配置 ---
    CORS_ORIGINS: List[str] = Field(
        default=["http://localhost:5173", "http://localhost:3000"],
        description="允许的跨域来源"
    )

    # --- JWT令牌配置 ---
    # JWT：用于用户认证的令牌机制
    JWT_SECRET_KEY: str = Field(
        default="your-secret-key-change-in-production",
        description="JWT密钥（⚠️ 生产环境必须修改为强密码）"
    )
    JWT_ALGORITHM: str = Field(default="HS256", description="JWT加密算法")
    JWT_EXPIRE_MINUTES: int = Field(default=1440, description="JWT过期时间(分钟)，默认24小时")

    # =========================================
    # 日志配置
    # =========================================
    # 📝 日志系统：记录系统运行状态，方便调试和监控

    LOG_LEVEL: str = Field(default="INFO", description="日志级别：DEBUG/INFO/WARNING/ERROR")
    LOG_FILE_MAX_SIZE: str = Field(default="100 MB", description="单个日志文件最大大小")
    LOG_FILE_ROTATION: str = Field(default="1 day", description="日志轮转周期")
    LOG_FILE_RETENTION: str = Field(default="30 days", description="日志保留时间")

    # =========================================
    # 性能配置
    # =========================================
    MAX_CONCURRENT_REQUESTS: int = Field(default=100, description="最大并发请求数")
    REQUEST_TIMEOUT: int = Field(default=60, description="请求超时时间(秒)")

    # =========================================
    # 监控配置
    # =========================================
    ENABLE_METRICS: bool = Field(default=True, description="是否启用性能指标收集")
    ENABLE_QUERY_LOG: bool = Field(default=True, description="是否记录查询日志")

    # =========================================
    # 配置验证器
    # =========================================
    # 🛡️ 作用：在应用启动前检查配置是否合法

    @field_validator("CHUNK_SIZE")
    @classmethod
    def validate_chunk_size(cls, v):
        """验证chunk_size必须大于0"""
        if v <= 0:
            raise ValueError("CHUNK_SIZE必须大于0")
        return v

    @field_validator("CHUNK_OVERLAP")
    @classmethod
    def validate_chunk_overlap(cls, v, info):
        """验证overlap不能大于chunk_size"""
        chunk_size = info.data.get("CHUNK_SIZE", 512)
        if v >= chunk_size:
            raise ValueError("CHUNK_OVERLAP必须小于CHUNK_SIZE")
        return v

    @field_validator("BM25_WEIGHT", "VECTOR_WEIGHT", "RERANK_WEIGHT")
    @classmethod
    def validate_weights(cls, v):
        """验证权重在0-1之间"""
        if not 0 <= v <= 1:
            raise ValueError("权重必须在0-1之间")
        return v

    def ensure_dirs(self) -> None:
        """显式创建运行所需目录（原始文档、处理结果、日志）"""
        self.DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.RAW_DOCS_DIR.mkdir(parents=True, exist_ok=True)
        self.PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
        self.LOG_DIR.mkdir(parents=True, exist_ok=True)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


# =========================================
# 创建全局配置实例
# =========================================
# 💡 单例模式：整个应用共享一个配置实例
settings = Settings()


# =========================================
# 便捷函数
# =========================================
def get_settings() -> Settings:
    """
    获取配置实例

    用法：
        from core.config import get_settings

        settings = get_settings()
        print(settings.APP_NAME)

    返回：
        Settings: 配置实例
    """
    return settings


# =========================================
# 💡 使用示例
# =========================================
"""
# 1. 导入配置
from core.config import settings

# 2. 使用配置
print(f"应用名称: {settings.APP_NAME}")
print(f"数据库URL: {settings.postgres_url}")
print(f"向量维度: {settings.VECTOR_DIM}")

# 3. 在其他模块中使用
def connect_database():
    db_url = settings.postgres_url
    # 连接数据库...
"""