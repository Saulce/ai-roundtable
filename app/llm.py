from langchain_openai import ChatOpenAI

from app.config import Config


def get_llm(config: Config) -> ChatOpenAI:
    """按 config 构造 OpenAI 兼容的 ChatOpenAI 客户端。"""
    return ChatOpenAI(
        base_url=config.base_url,
        api_key=config.api_key,
        model=config.model,
    )
