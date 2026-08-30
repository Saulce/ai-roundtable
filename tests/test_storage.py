import pytest

from app.storage import Storage


@pytest.fixture
def storage(tmp_path):
    return Storage(str(tmp_path / "test.db"))


def test_roundtrip_discussion(storage):
    personas = [{"name": "A", "stance": "s", "style": "st", "background": None}]
    storage.create_discussion("d1", "话题", personas, max_turns=15)
    storage.append_message("d1", {"kind": "opening", "speaker": "A", "content": "你好"})
    storage.append_message("d1", {"kind": "speech", "speaker": "A", "content": "继续"})
    storage.save_summary("d1", "final", "## 总结")
    storage.update_status("d1", "terminated")

    d = storage.get_discussion("d1")
    assert d["topic"] == "话题"
    assert d["max_turns"] == 15
    assert [m["kind"] for m in d["messages"]] == ["opening", "speech"]
    assert d["summaries"][0]["mode"] == "final"
    assert d["status"] == "terminated"


def test_list_discussions_newest_first(storage):
    storage.create_discussion("d1", "话题1", [], 15)
    storage.create_discussion("d2", "话题2", [], 0)
    items = storage.list_discussions()
    assert [i["id"] for i in items] == ["d2", "d1"]


def test_get_missing_returns_none(storage):
    assert storage.get_discussion("nope") is None
