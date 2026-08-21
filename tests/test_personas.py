import pytest
from pydantic import ValidationError

from app.personas import Persona, PRESET_PERSONAS, validate_personas, persona_by_name


def test_preset_has_five_in_order():
    names = [p.name for p in PRESET_PERSONAS]
    assert names == ["好为人师者", "杠精", "中立质疑者", "领域专家", "理想主义者"]


def test_preset_required_fields_nonempty():
    for p in PRESET_PERSONAS:
        assert p.stance
        assert p.style


def test_validate_accepts_two_to_six():
    two = PRESET_PERSONAS[:2]
    assert validate_personas(two) == two
    six = PRESET_PERSONAS + [Persona(name="自定义", stance="立场", style="风格")]
    assert len(validate_personas(six)) == 6


def test_validate_rejects_too_few():
    with pytest.raises(ValueError):
        validate_personas(PRESET_PERSONAS[:1])


def test_validate_rejects_too_many():
    many = [Persona(name=f"角色{i}", stance="立场", style="风格") for i in range(7)]
    with pytest.raises(ValueError):
        validate_personas(many)


def test_persona_requires_name_stance_style():
    with pytest.raises(ValidationError):
        Persona(name="", stance="x", style="y")
    with pytest.raises(ValidationError):
        Persona(name="n", stance="", style="y")
    with pytest.raises(ValidationError):
        Persona(name="n", stance="x", style="")


def test_background_optional():
    p = Persona(name="n", stance="x", style="y")
    assert p.background is None


def test_persona_by_name():
    assert persona_by_name(PRESET_PERSONAS, "杠精").name == "杠精"
    with pytest.raises(ValueError):
        persona_by_name(PRESET_PERSONAS, "不存在")
