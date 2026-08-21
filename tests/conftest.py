from types import SimpleNamespace
import pytest


class FakeLLM:
    """按 handler 分发响应：handler(prompt) -> str 或 list[str]。
    ainvoke 返回带 .content 的对象；astream 若 handler 返回 list 则逐 token yield，否则按字符 yield。"""

    def __init__(self, handler):
        self.handler = handler
        self.invoke_calls = []

    async def ainvoke(self, prompt):
        self.invoke_calls.append(prompt)
        content = self.handler(prompt)
        if isinstance(content, list):
            content = "".join(content)
        return SimpleNamespace(content=content)

    async def astream(self, prompt):
        out = self.handler(prompt)
        tokens = out if isinstance(out, list) else list(out)
        for token in tokens:
            yield SimpleNamespace(content=token)


@pytest.fixture
def fake_llm():
    def make(handler):
        return FakeLLM(handler)
    return make
