"""核心质量回归测试：覆盖本次修复/补全的关键逻辑（不依赖外部服务与重型 ML 依赖）"""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from core.constants import (
    DocumentType, DocumentStatus, RetrievalMode,
    QueryType, AnswerQuality, MilvusCollection,
)
from core.config import settings


# =========================================
# 1. 重建的常量枚举
# =========================================

def test_document_type_covers_all_used_members():
    for name in ["STANDARD", "PROJECT", "CONTRACT", "PDF", "WORD",
                 "IMAGE", "TEXT", "OTHER", "UNKNOWN"]:
        assert hasattr(DocumentType, name)


def test_milvus_collection_values_match_settings():
    assert MilvusCollection.STANDARDS.value == settings.MILVUS_COLLECTION_STANDARD
    assert MilvusCollection.PROJECTS.value == settings.MILVUS_COLLECTION_PROJECT
    assert MilvusCollection.CONTRACTS.value == settings.MILVUS_COLLECTION_CONTRACT


def test_other_enums_have_expected_members():
    assert DocumentStatus.COMPLETED.value == "completed"
    assert RetrievalMode.HYBRID.value == "hybrid"
    assert QueryType.STANDARD_QUERY.value == "standard_query"
    assert AnswerQuality.HIGH.value == "high"


# =========================================
# 2. LLM JSON 解析（施工图实体抽取）
# =========================================

def _extractor():
    from services.document.construction_drawing.entity_extractor import EntityExtractor
    return EntityExtractor(use_llm=False)


def test_parse_llm_json_plain():
    ext = _extractor()
    assert ext._parse_llm_json('{"components": [{"code": "KL-1"}]}') == {
        "components": [{"code": "KL-1"}]
    }


def test_parse_llm_json_fenced():
    ext = _extractor()
    content = "好的：\n```json\n{\"materials\": [{\"grade\": \"C30\"}]}\n```\n"
    assert ext._parse_llm_json(content) == {"materials": [{"grade": "C30"}]}


def test_parse_llm_json_embedded_braces():
    ext = _extractor()
    content = "前缀文字 {\"specifications\": [{\"code\": \"GB50010\"}]} 后缀"
    assert ext._parse_llm_json(content) == {
        "specifications": [{"code": "GB50010"}]
    }


def test_parse_llm_json_invalid_returns_none():
    ext = _extractor()
    assert ext._parse_llm_json("not json at all") is None
    assert ext._parse_llm_json("") is None


# =========================================
# 3. 权限：细粒度资源权限
# =========================================

def _checker():
    from services.permission.permission_checker import PermissionChecker
    return PermissionChecker()


def _patch_session(monkeypatch, records):
    """让 SessionLocal() 返回一个吐出 records 的假会话"""
    class _Query:
        def filter(self, *a, **k):
            return self

        def all(self):
            return records

    class _Session:
        def query(self, *a, **k):
            return _Query()

        def close(self):
            pass

    monkeypatch.setattr("core.database.SessionLocal", lambda: _Session())


def test_fine_grained_none_when_no_record(monkeypatch):
    from core.constants import UserRole  # noqa: F401
    from services.permission.permission_checker import ResourceType, ActionType
    chk = _checker()
    _patch_session(monkeypatch, [])
    assert chk._check_fine_grained_permission(
        "u1", ResourceType.DOCUMENT, "doc1", ActionType.READ
    ) is None


def test_fine_grained_explicit_deny(monkeypatch):
    from services.permission.permission_checker import ResourceType, ActionType
    chk = _checker()
    rec = SimpleNamespace(
        resource_id="doc1", can_read=False, can_write=False,
        can_delete=False, can_share=False, valid_from=None, valid_until=None,
    )
    _patch_session(monkeypatch, [rec])
    assert chk._check_fine_grained_permission(
        "u1", ResourceType.DOCUMENT, "doc1", ActionType.READ
    ) is False


def test_fine_grained_specific_beats_wildcard(monkeypatch):
    from services.permission.permission_checker import ResourceType, ActionType
    chk = _checker()
    wildcard = SimpleNamespace(
        resource_id=None, can_read=False, can_write=False,
        can_delete=False, can_share=False, valid_from=None, valid_until=None,
    )
    specific = SimpleNamespace(
        resource_id="doc1", can_read=True, can_write=False,
        can_delete=False, can_share=False, valid_from=None, valid_until=None,
    )
    _patch_session(monkeypatch, [wildcard, specific])
    assert chk._check_fine_grained_permission(
        "u1", ResourceType.DOCUMENT, "doc1", ActionType.READ
    ) is True


def test_fine_grained_expired_record_skipped(monkeypatch):
    from services.permission.permission_checker import ResourceType, ActionType
    chk = _checker()
    expired = SimpleNamespace(
        resource_id="doc1", can_read=True, can_write=False,
        can_delete=False, can_share=False,
        valid_from=None, valid_until=datetime.now(timezone.utc) - timedelta(days=1),
    )
    _patch_session(monkeypatch, [expired])
    # 过期记录被跳过，且无其它记录 -> None
    assert chk._check_fine_grained_permission(
        "u1", ResourceType.DOCUMENT, "doc1", ActionType.READ
    ) is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
