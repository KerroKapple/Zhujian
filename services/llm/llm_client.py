"""
========================================
LLM 客户端
========================================

📚 模块说明：
- 统一的 LLM 调用接口
- 支持 OpenAI 兼容 API
- 支持多种模型切换

🎯 核心功能：
1. 同步/异步调用
2. 流式输出
3. 错误重试
4. Token 统计

========================================
"""

import time
import asyncio
from typing import List, Dict, Optional, Generator, AsyncGenerator, Union

from openai import OpenAI, AsyncOpenAI
from openai import APITimeoutError, RateLimitError, APIConnectionError
from loguru import logger

from core.config import settings


class LLMClient:
    """
    LLM 客户端

    🔧 支持的 API：
    - OpenAI API
    - OpenAI 兼容 API（如 vLLM、Ollama、通义千问等）

    💡 特性：
    - 同步/异步调用
    - 流式输出
    - 自动重试
    - 使用统计
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        timeout: int = 60,
        max_retries: int = 3
    ):
        """
        初始化 LLM 客户端

        参数：
            api_key: API 密钥（默认从 settings.LLM_API_KEY 读取）
            api_base: API 基础 URL（默认从 settings.LLM_API_BASE 读取）
            model: 模型名称（默认从 settings.LLM_MODEL_NAME 读取）
            temperature: 生成温度（默认 settings.LLM_TEMPERATURE）
            max_tokens: 最大生成 token 数（默认 settings.LLM_MAX_TOKENS）
            timeout: 请求超时时间（秒）
            max_retries: 最大重试次数
        """
        # API 配置：单一事实源为 settings，缺 key 显式报错而非静默连真实 OpenAI
        self.api_key = api_key or settings.LLM_API_KEY
        if not self.api_key:
            raise ValueError(
                "缺少 LLM API 密钥，请设置 settings.LLM_API_KEY 或传入 api_key"
            )
        self.api_base = api_base or settings.LLM_API_BASE
        self.model = model or settings.LLM_MODEL_NAME

        # 生成参数
        self.temperature = temperature if temperature is not None else settings.LLM_TEMPERATURE
        self.max_tokens = max_tokens if max_tokens is not None else settings.LLM_MAX_TOKENS
        self.timeout = timeout
        # 由 SDK 自身重试交给指数退避循环处理，避免双重重试
        self.max_retries = max_retries

        # 初始化客户端
        self._sync_client = None
        self._async_client = None

        # 使用统计
        self.total_requests = 0
        self.total_tokens = 0
        self.total_errors = 0

        logger.info(
            f"LLM 客户端初始化 | "
            f"模型: {self.model} | "
            f"API: {self.api_base}"
        )

    @property
    def sync_client(self) -> OpenAI:
        """获取同步客户端（懒加载）"""
        if self._sync_client is None:
            # SDK 重试关闭，统一由 _retry_sync 做分类指数退避
            self._sync_client = OpenAI(
                api_key=self.api_key,
                base_url=self.api_base,
                timeout=self.timeout,
                max_retries=0
            )
        return self._sync_client

    @property
    def async_client(self) -> AsyncOpenAI:
        """获取异步客户端（懒加载）"""
        if self._async_client is None:
            self._async_client = AsyncOpenAI(
                api_key=self.api_key,
                base_url=self.api_base,
                timeout=self.timeout,
                max_retries=0
            )
        return self._async_client

    # 可重试错误：超时、限流、连接错误（指数退避）；其余错误立即抛出
    _RETRYABLE = (APITimeoutError, RateLimitError, APIConnectionError)

    def _retry_sync(self, call):
        """同步调用的分类指数退避重试"""
        last_exc = None
        for attempt in range(max(1, self.max_retries)):
            try:
                return call()
            except self._RETRYABLE as e:
                last_exc = e
                delay = 2 ** attempt
                logger.warning(
                    f"LLM 可重试错误 {type(e).__name__}，第 {attempt + 1}/{self.max_retries} 次，{delay}s 后重试"
                )
                time.sleep(delay)
        raise last_exc

    async def _retry_async(self, call):
        """异步调用的分类指数退避重试"""
        last_exc = None
        for attempt in range(max(1, self.max_retries)):
            try:
                return await call()
            except self._RETRYABLE as e:
                last_exc = e
                delay = 2 ** attempt
                logger.warning(
                    f"LLM 可重试错误 {type(e).__name__}，第 {attempt + 1}/{self.max_retries} 次，{delay}s 后重试"
                )
                await asyncio.sleep(delay)
        raise last_exc

    def chat(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> str:
        """
        同步聊天调用

        参数：
            messages: 消息列表
                [
                    {"role": "system", "content": "..."},
                    {"role": "user", "content": "..."}
                ]
            model: 覆盖默认模型
            temperature: 覆盖默认温度
            max_tokens: 覆盖默认最大 token
            **kwargs: 其他参数传递给 API

        返回：
            str: 生成的回复内容
        """
        try:
            self.total_requests += 1

            response = self._retry_sync(lambda: self.sync_client.chat.completions.create(
                model=model or self.model,
                messages=messages,
                temperature=temperature if temperature is not None else self.temperature,
                max_tokens=max_tokens if max_tokens is not None else self.max_tokens,
                **kwargs
            ))

            # 统计 token
            if hasattr(response, 'usage') and response.usage:
                self.total_tokens += response.usage.total_tokens

            content = response.choices[0].message.content

            logger.debug(
                f"LLM 调用成功 | "
                f"模型: {model or self.model} | "
                f"回复长度: {len(content)}"
            )

            return content

        except Exception as e:
            self.total_errors += 1
            logger.error(f"LLM 调用失败: {e}")
            raise

    async def chat_async(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> str:
        """
        异步聊天调用

        参数与 chat() 相同
        """
        try:
            self.total_requests += 1

            response = await self._retry_async(lambda: self.async_client.chat.completions.create(
                model=model or self.model,
                messages=messages,
                temperature=temperature if temperature is not None else self.temperature,
                max_tokens=max_tokens if max_tokens is not None else self.max_tokens,
                **kwargs
            ))

            # 统计 token
            if hasattr(response, 'usage') and response.usage:
                self.total_tokens += response.usage.total_tokens

            content = response.choices[0].message.content

            logger.debug(
                f"LLM 异步调用成功 | "
                f"模型: {model or self.model} | "
                f"回复长度: {len(content)}"
            )

            return content

        except Exception as e:
            self.total_errors += 1
            logger.error(f"LLM 异步调用失败: {e}")
            raise

    def chat_stream(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> Generator[str, None, None]:
        """
        流式聊天调用（同步）

        参数与 chat() 相同

        返回：
            Generator[str]: 逐字符/逐 token 的生成器
        """
        try:
            self.total_requests += 1

            stream = self._retry_sync(lambda: self.sync_client.chat.completions.create(
                model=model or self.model,
                messages=messages,
                temperature=temperature if temperature is not None else self.temperature,
                max_tokens=max_tokens if max_tokens is not None else self.max_tokens,
                stream=True,
                **kwargs
            ))

            for chunk in stream:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content

        except Exception as e:
            self.total_errors += 1
            logger.error(f"LLM 流式调用失败: {e}")
            raise

    async def chat_stream_async(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """
        流式聊天调用（异步）

        参数与 chat() 相同

        返回：
            AsyncGenerator[str]: 逐字符/逐 token 的异步生成器
        """
        try:
            self.total_requests += 1

            stream = await self._retry_async(lambda: self.async_client.chat.completions.create(
                model=model or self.model,
                messages=messages,
                temperature=temperature if temperature is not None else self.temperature,
                max_tokens=max_tokens if max_tokens is not None else self.max_tokens,
                stream=True,
                **kwargs
            ))

            async for chunk in stream:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content

        except Exception as e:
            self.total_errors += 1
            logger.error(f"LLM 异步流式调用失败: {e}")
            raise

    def complete(
        self,
        prompt: str,
        model: Optional[str] = None,
        **kwargs
    ) -> str:
        """
        简单的文本补全（将 prompt 包装为 user message）

        参数：
            prompt: 提示文本
            model: 模型名称
            **kwargs: 其他参数

        返回：
            str: 生成的回复
        """
        messages = [{"role": "user", "content": prompt}]
        return self.chat(messages, model=model, **kwargs)

    async def complete_async(
        self,
        prompt: str,
        model: Optional[str] = None,
        **kwargs
    ) -> str:
        """
        简单的文本补全（异步）

        参数与 complete() 相同
        """
        messages = [{"role": "user", "content": prompt}]
        return await self.chat_async(messages, model=model, **kwargs)

    def get_embedding(
        self,
        text: Union[str, List[str]],
        model: str = "text-embedding-ada-002"
    ) -> Union[List[float], List[List[float]]]:
        """
        获取文本嵌入向量

        参数：
            text: 单个文本或文本列表
            model: 嵌入模型名称

        返回：
            单个向量或向量列表
        """
        try:
            response = self.sync_client.embeddings.create(
                model=model,
                input=text
            )

            if isinstance(text, str):
                return response.data[0].embedding
            else:
                return [item.embedding for item in response.data]

        except Exception as e:
            logger.error(f"获取 Embedding 失败: {e}")
            raise

    def get_stats(self) -> Dict:
        """获取使用统计"""
        return {
            'total_requests': self.total_requests,
            'total_tokens': self.total_tokens,
            'total_errors': self.total_errors,
            'model': self.model,
            'api_base': self.api_base
        }

    def reset_stats(self):
        """重置统计"""
        self.total_requests = 0
        self.total_tokens = 0
        self.total_errors = 0

    async def ping(self) -> bool:
        """
        测试 API 连接

        返回：
            bool: 连接是否正常
        """
        try:
            # 发送一个简单的请求测试连接
            await self.chat_async(
                messages=[{"role": "user", "content": "Hi"}],
                max_tokens=5
            )
            return True
        except Exception as e:
            logger.error(f"API 连接测试失败: {e}")
            return False


# =========================================
# 工厂函数
# =========================================

def create_llm_client(
    provider: str = "openai",
    **kwargs
) -> LLMClient:
    """
    创建 LLM 客户端的工厂函数

    参数：
        provider: 提供商
            - "openai": OpenAI API
            - "qwen": 通义千问
            - "glm": 智谱 GLM
            - "ollama": Ollama 本地部署
            - "vllm": vLLM 部署
        **kwargs: 传递给 LLMClient 的参数

    返回：
        LLMClient: 配置好的客户端实例
    """
    configs = {
        "openai": {
            "api_base": "https://api.openai.com/v1",
            "model": "gpt-3.5-turbo"
        },
        "qwen": {
            "api_base": "https://dashscope.aliyuncs.com/compatible-mode/v1",
            "model": "qwen-plus"
        },
        "glm": {
            "api_base": "https://open.bigmodel.cn/api/paas/v4",
            "model": "glm-4"
        },
        "ollama": {
            "api_base": "http://localhost:11434/v1",
            "model": "llama2"
        },
        "vllm": {
            "api_base": "http://localhost:8000/v1",
            "model": "Qwen/Qwen2-7B-Instruct"
        }
    }

    if provider not in configs:
        logger.warning(f"未知的提供商: {provider}，使用默认配置")
        config = {}
    else:
        config = configs[provider]

    # 合并配置
    config.update(kwargs)

    return LLMClient(**config)


# =========================================
# 💡 使用示例
# =========================================
"""
# 1. 基础使用
from services.llm.llm_client import LLMClient

client = LLMClient(
    api_key="your-api-key",
    api_base="https://api.openai.com/v1",
    model="gpt-3.5-turbo"
)

# 同步调用
response = client.chat([
    {"role": "system", "content": "你是一个有帮助的助手"},
    {"role": "user", "content": "什么是RAG？"}
])
print(response)


# 2. 异步调用
import asyncio

async def main():
    response = await client.chat_async([
        {"role": "user", "content": "解释一下向量检索"}
    ])
    print(response)

asyncio.run(main())


# 3. 流式输出
print("流式输出: ", end="", flush=True)
for chunk in client.chat_stream([
    {"role": "user", "content": "写一首关于AI的诗"}
]):
    print(chunk, end="", flush=True)
print()


# 4. 异步流式输出
async def stream_demo():
    async for chunk in client.chat_stream_async([
        {"role": "user", "content": "讲一个笑话"}
    ]):
        print(chunk, end="", flush=True)

asyncio.run(stream_demo())


# 5. 使用工厂函数
from services.llm.llm_client import create_llm_client

# 创建通义千问客户端
qwen_client = create_llm_client(
    provider="qwen",
    api_key="your-qwen-api-key"
)

# 创建 Ollama 客户端
ollama_client = create_llm_client(
    provider="ollama",
    model="llama2"
)


# 6. 简单补全
answer = client.complete("请解释什么是机器学习？")
print(answer)


# 7. 查看统计
stats = client.get_stats()
print(f"总请求数: {stats['total_requests']}")
print(f"总 Token 数: {stats['total_tokens']}")


# 8. 测试连接
is_connected = await client.ping()
print(f"API 连接: {'正常' if is_connected else '异常'}")
"""
