"""角色（persona）模型与预设套件。

决议来源：Wayfinder Map #1 决策票 #5（角色模型）。
"""

from pydantic import BaseModel, Field


class Persona(BaseModel):
    """一名讨论角色的设定。

    - name / stance / style 必填（非空）
    - stance 是开场陈述轮的锚点 + 立场漂移的基线，允许被说服而改变
    - background 可选
    """

    name: str = Field(min_length=1, description="角色名字")
    stance: str = Field(min_length=1, description="立场（开场基线锚点，允许漂移）")
    style: str = Field(min_length=1, description="说话风格")
    background: str | None = Field(default=None, description="专业背景（可选）")


PRESET_PERSONAS: list[Persona] = [
    Persona(
        name="好为人师者",
        stance="坚信并力挺本次话题的主张，愿意给出扎实的论据支撑。",
        style="热情，爱引经据典，习惯给人提建议。",
    ),
    Persona(
        name="杠精",
        stance="持怀疑态度，专找话题主张的毛病，总想反过来驳一驳。",
        style="尖锐但逻辑在线，喜欢挑刺、唱反调。",
    ),
    Persona(
        name="中立质疑者",
        stance="不站队，立场保持中立，只关心论证是否站得住脚。",
        style="连环追问，专挑各方论证里的漏洞。",
    ),
    Persona(
        name="领域专家",
        stance="从专业与实务角度审视话题，以数据和案例说话。",
        style="冷静克制，引用数据与案例，避免空谈。",
    ),
    Persona(
        name="理想主义者",
        stance="从价值观、伦理与长期影响的角度看待话题。",
        style="富有理想色彩，谈原则、谈长远，不太计较眼前得失。",
    ),
]


def validate_personas(personas: list[Persona]) -> list[Persona]:
    """校验角色数量在 2–6 之间，通过则原样返回。"""
    if not 2 <= len(personas) <= 6:
        raise ValueError(f"角色数量必须为 2–6 个，当前 {len(personas)} 个")
    return personas


def persona_by_name(personas: list[Persona], name: str) -> Persona:
    """按名字查找角色；未找到抛 ValueError。"""
    for persona in personas:
        if persona.name == name:
            return persona
    raise ValueError(f"未找到角色：{name}")
