"""Tests for structured case loading and learner-safe retrieval."""

from services.case_manager import (
    REFERENCE_DOMAINS,
    REQUIRED_CASE_FIELDS,
    get_available_difficulties,
    get_case_by_id,
    get_case_for_student,
    get_cases_by_difficulty,
    load_cases,
    resolve_ecg_image_path,
    validate_case,
)
import services.case_manager as case_manager
from services.evaluator import EvaluationStatus, evaluate_interpretation, evaluate_rate


EXPECTED_CASES = {
    "case_001": "Normal Sinus Rhythm",
    "case_002": "Sinus Bradycardia",
    "case_003": "Sinus Tachycardia",
}


def test_all_three_cases_load_with_valid_schema():
    cases = load_cases()
    assert len(cases) == 3
    assert {case["case_id"]: case["title"] for case in cases} == EXPECTED_CASES
    for case in cases:
        assert validate_case(case)
        assert REQUIRED_CASE_FIELDS.issubset(case)
        assert set(case["reference_findings"]) == set(REFERENCE_DOMAINS)
        assert all(isinstance(case["reference_findings"][domain], dict) for domain in REFERENCE_DOMAINS)
        if case["case_id"] in {"case_001", "case_002"}:
            assert case["image_path"] == f"assets/ecg/learner/{'NSR' if case['case_id'] == 'case_001' else 'SB'}_001_learner.png"
            assert case["source_name"].startswith("GenECG")
            assert case["source_url"].startswith("https://huggingface.co/datasets/edcci/GenECG/")
            assert case["license"] == "CC BY 4.0"
            assert "PTB-XL record" in case["source_record"]
        else:
            assert case["image_path"] is None
            assert all(case[field] is None for field in ("source_name", "source_url", "license", "source_record"))


def test_difficulty_filters_match_new_case_set():
    assert get_available_difficulties() == ["Beginner", "Intermediate"]
    assert len(get_cases_by_difficulty("Beginner")) == 1
    assert len(get_cases_by_difficulty("Intermediate")) == 2
    assert get_cases_by_difficulty(" beginner ") == get_cases_by_difficulty("Beginner")
    assert get_cases_by_difficulty("") == []
    assert get_cases_by_difficulty(None) == []


def test_retrieving_existing_and_missing_cases():
    case = get_case_by_id("case_001")
    assert case is not None
    assert case["title"] == "Normal Sinus Rhythm"
    assert case["id"] == case["case_id"]
    assert get_case_by_id("missing_case") is None
    assert get_case_by_id("") is None
    assert get_case_by_id(None) is None


def test_invalid_schema_is_rejected():
    case = get_case_by_id("case_001")
    assert case is not None
    case["reference_findings"] = {"rate": {"answer": "75"}}
    assert not validate_case(case)


def test_student_projection_excludes_all_reference_material():
    case = get_case_for_student("case_001")
    assert case is not None
    assert set(case) == {
        "id",
        "case_id",
        "title",
        "difficulty",
        "description",
        "learning_objectives",
        "image_path",
        "source_name",
        "source_url",
        "license",
        "source_record",
    }
    assert case["title"] != "Normal Sinus Rhythm"
    assert "reference_findings" not in case
    assert "reference_interpretation" not in case
    assert "teaching_notes" not in case
    assert get_case_for_student("missing_case") is None


def test_image_metadata_schema_and_learner_safe_source_attribution(monkeypatch):
    case = get_case_by_id("case_001")
    assert case is not None
    case.update(
        {
            "image_path": "assets/ecg/case_001.png",
            "source_name": "Educational ECG Archive",
            "source_url": "https://example.org/ecg/case_001",
            "license": "CC BY 4.0",
            "source_record": "record-001",
        }
    )
    assert validate_case(case)
    monkeypatch.setattr(case_manager, "load_cases", lambda: [case])
    student_case = get_case_for_student("case_001")
    assert student_case is not None
    assert student_case["image_path"] == "assets/ecg/case_001.png"
    assert student_case["source_name"] == "Educational ECG Archive"
    assert student_case["source_url"] == "https://example.org/ecg/case_001"
    assert student_case["license"] == "CC BY 4.0"
    assert student_case["source_record"] == "record-001"
    assert not {"reference_findings", "reference_interpretation", "teaching_notes"}.intersection(student_case)


def test_image_path_must_be_local_and_resolve_under_ecg_assets(tmp_path, monkeypatch):
    case = get_case_by_id("case_001")
    assert case is not None
    case.update(
        {
            "image_path": "assets/ecg/sample.png",
            "source_name": "Archive",
            "source_url": "https://example.org/record",
            "license": "CC BY 4.0",
            "source_record": "sample",
        }
    )
    monkeypatch.setattr(case_manager, "CASES_FILE", tmp_path / "data" / "cases.json")
    asset = tmp_path / "assets" / "ecg" / "sample.png"
    asset.parent.mkdir(parents=True)
    asset.write_bytes(b"local test asset")
    assert validate_case(case)
    assert resolve_ecg_image_path(case["image_path"]) == asset.resolve()
    assert resolve_ecg_image_path("https://example.org/image.png") is None
    assert resolve_ecg_image_path("assets/ecg/../../outside.png") is None
    assert resolve_ecg_image_path("assets/ecg/missing.png") is None
    case["image_path"] = "assets/other/sample.png"
    assert not validate_case(case)


def test_reference_data_remains_available_to_evaluator_only_internally():
    case = get_case_by_id("case_001")
    learner_case = get_case_for_student("case_001")
    assert case is not None and learner_case is not None
    assert evaluate_rate({"answer": "75", "reasoning": "Counted ventricular complexes"}, case).status == EvaluationStatus.CORRECT
    assert evaluate_interpretation("Normal sinus rhythm", case).status == EvaluationStatus.CORRECT
    assert evaluate_rate({"answer": "75", "reasoning": "Counted ventricular complexes"}, learner_case).status == EvaluationStatus.NOT_EVALUATED
    assert evaluate_interpretation("Normal sinus rhythm", learner_case).status == EvaluationStatus.NOT_EVALUATED
