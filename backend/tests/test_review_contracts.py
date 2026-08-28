from app.core.security import create_one_time_token, hash_one_time_token
from app.models.schemas import CreateReviewRequest
from app.services.review_service import REPORT_HEADINGS, _coerce_node_result, _normalize_report, _validate_node_result
from app.runtime.langgraph_runtime import ReviewState, build_review_graph
from app.routers.reviews import _safe_filename, _validate_file_signature


def test_one_time_token_hash_round_trip():
    raw, hashed = create_one_time_token()
    assert raw
    assert hashed == hash_one_time_token(raw)


def test_review_round_validation_and_report_headings():
    request = CreateReviewRequest(organization_id="org-1", topic="主题", max_round=5)
    assert request.max_round == 5
    report = _normalize_report("## 方案概述\n内容")
    for heading in REPORT_HEADINGS:
        assert heading in report
    assert report.index(REPORT_HEADINGS[0]) < report.index(REPORT_HEADINGS[-1])


def test_invalid_agent_output_is_rejected():
    try:
        _validate_node_result("benefit_argument", {"summary": "x", "claims": []})
    except ValueError:
        pass
    else:
        raise AssertionError("empty argument claims must fail validation")


def test_document_synthesis_output_is_coerced_to_summary():
    result = _coerce_node_result(
        "document_parse",
        {
            "topic": "主题",
            "synthesis": {"benefits": ["提升效率"], "risks": ["实施成本"]},
            "sources": [{"title": "公开资料"}],
        },
    )
    assert "summary" in result
    assert "提升效率" in result["summary"]


def test_langgraph_review_state_and_graph_compile():
    state: ReviewState = {"topic": "主题", "max_round": 1, "current_round": 0, "session_id": "s"}
    assert state["max_round"] == 1
    graph = build_review_graph()
    assert graph is not None


def test_upload_filename_is_confined_to_basename_and_signature_is_checked():
    assert _safe_filename("..\\..\\secret.pdf") == "secret.pdf"
    try:
        _validate_file_signature("document.pdf", b"not a pdf")
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 400
    else:
        raise AssertionError("invalid PDF signature must be rejected")
