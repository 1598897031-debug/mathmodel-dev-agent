"""
LLM 统一调用层
封装 Claude 和 OpenAI API，提供统一接口
支持 prompt caching 优化
"""

from typing import Optional
from dataclasses import dataclass

from ..config import LLMConfig


@dataclass
class Message:
    """消息格式"""
    role: str          # "system" | "user" | "assistant"
    content: str


class LLMClient:
    """
    LLM 统一客户端
    支持 Claude (Anthropic) 和 OpenAI 两种后端
    """

    def __init__(self, config: LLMConfig):
        self.config = config
        self._claude_client = None
        self._openai_client = None

    def _get_claude_client(self):
        """懒加载 Claude 客户端"""
        if self._claude_client is None:
            try:
                import anthropic
                self._claude_client = anthropic.Anthropic(
                    api_key=self.config.claude_api_key
                )
            except ImportError:
                raise ImportError("请安装 anthropic: pip install anthropic")
        return self._claude_client

    def _get_openai_client(self):
        """懒加载 OpenAI 客户端"""
        if self._openai_client is None:
            try:
                import openai
                self._openai_client = openai.OpenAI(
                    api_key=self.config.openai_api_key
                )
            except ImportError:
                raise ImportError("请安装 openai: pip install openai")
        return self._openai_client

    def chat(
        self,
        messages: list[Message],
        model: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: float = 0.7,
    ) -> str:
        """
        统一聊天接口

        Args:
            messages: 消息列表
            model: 模型名称 (可选，默认使用配置中的模型)
            max_tokens: 最大 token 数 (可选)
            temperature: 温度参数

        Returns:
            模型回复文本
        """
        provider = self.config.default_provider

        if provider == "claude":
            return self._chat_claude(messages, model, max_tokens, temperature)
        elif provider == "openai":
            return self._chat_openai(messages, model, max_tokens, temperature)
        else:
            raise ValueError(f"不支持的 LLM 提供商: {provider}")

    def _chat_claude(
        self,
        messages: list[Message],
        model: Optional[str],
        max_tokens: Optional[int],
        temperature: float,
    ) -> str:
        """调用 Claude API"""
        client = self._get_claude_client()
        model = model or self.config.claude_model
        max_tokens = max_tokens or self.config.claude_max_tokens

        # 分离 system 消息和对话消息
        system_msg = ""
        chat_messages = []
        for msg in messages:
            if msg.role == "system":
                system_msg = msg.content
            else:
                chat_messages.append({"role": msg.role, "content": msg.content})

        response = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system_msg,
            messages=chat_messages,
        )
        return response.content[0].text

    def _chat_openai(
        self,
        messages: list[Message],
        model: Optional[str],
        max_tokens: Optional[int],
        temperature: float,
    ) -> str:
        """调用 OpenAI API"""
        client = self._get_openai_client()
        model = model or self.config.openai_model

        formatted = [{"role": m.role, "content": m.content} for m in messages]
        response = client.chat.completions.create(
            model=model,
            messages=formatted,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        return response.choices[0].message.content
