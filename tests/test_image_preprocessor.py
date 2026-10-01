"""Tests for deterministic, learner-safe ECG image masking."""

import hashlib
from pathlib import Path

import pytest
from PIL import Image, ImageChops, ImageDraw

from services.case_manager import get_case_by_id
from services.evaluator import EvaluationStatus, evaluate_rate
from services.image_preprocessor import (
    CASE_REDACTION_CONFIGS,
    HEADER_REDACTION_REGION,
    ImagePreprocessingError,
    create_learner_image,
    learner_output_path,
    normalized_region_to_pixels,
)
from services.reasoning import create_reasoning_attempt


def _make_test_image(path):
    image = Image.new("RGB", (200, 100), (255, 238, 240))
    draw = ImageDraw.Draw(image)
    draw.line((0, 50, 199, 50), fill=(20, 20, 20), width=2)
    draw.text((8, 5), "Answer text", fill=(10, 10, 10))
    image.save(path)


def test_creates_same_size_learner_image_without_modifying_source(tmp_path):
    source = tmp_path / "source.png"
    output = tmp_path / "nested" / "learner.png"
    _make_test_image(source)
    original_digest = hashlib.sha256(source.read_bytes()).hexdigest()

    result = create_learner_image(
        source,
        output,
        [{"x": 0.0, "y": 0.0, "width": 0.4, "height": 0.2}],
    )

    assert result == output.resolve()
    assert output.is_file()
    with Image.open(source) as original, Image.open(output) as learner:
        assert learner.size == original.size == (200, 100)
        assert learner.getpixel((15, 10)) == (255, 238, 240)
        assert learner.getpixel((150, 50)) == original.getpixel((150, 50))
    assert hashlib.sha256(source.read_bytes()).hexdigest() == original_digest


def test_normalized_coordinates_convert_with_floor_and_ceil_edges():
    assert normalized_region_to_pixels(
        {"x": 0.1, "y": 0.2, "width": 0.3, "height": 0.4}, (200, 100)
    ) == (20, 20, 80, 60)


def test_decimal_sum_boundary_does_not_expand_by_a_pixel():
    # Binary floating-point addition yields 0.6000000000000001 for 0.2 + 0.4.
    assert normalized_region_to_pixels(
        {"x": 0, "y": 0.2, "width": 0.2, "height": 0.4}, (100, 100)
    ) == (0, 20, 20, 60)


def test_invalid_source_raises_clear_error(tmp_path):
    with pytest.raises(ImagePreprocessingError, match="does not exist"):
        create_learner_image(tmp_path / "missing.png", tmp_path / "out.png", [{"x": 0, "y": 0, "width": 0.1, "height": 0.1}])


def test_unreadable_image_raises_clear_error(tmp_path):
    source = tmp_path / "not-an-image.png"
    source.write_text("not an image", encoding="utf-8")
    with pytest.raises(ImagePreprocessingError, match="not a valid supported image"):
        create_learner_image(source, tmp_path / "out.png", [{"x": 0, "y": 0, "width": 0.1, "height": 0.1}])


@pytest.mark.parametrize(
    "region",
    [
        {"x": -0.1, "y": 0, "width": 0.2, "height": 0.2},
        {"x": 0.8, "y": 0, "width": 0.3, "height": 0.2},
        {"x": 0, "y": 0, "width": 0, "height": 0.2},
        {"x": 0, "y": 0, "width": float("nan"), "height": 0.2},
        {"x": 0, "y": 0, "width": "0.2", "height": 0.2},
    ],
)
def test_invalid_redaction_coordinates_are_rejected(region):
    with pytest.raises(ImagePreprocessingError):
        normalized_region_to_pixels(region, (100, 100))


def test_source_cannot_be_used_as_output(tmp_path):
    source = tmp_path / "source.png"
    _make_test_image(source)
    with pytest.raises(ImagePreprocessingError, match="must differ"):
        create_learner_image(source, source, [{"x": 0, "y": 0, "width": 0.1, "height": 0.1}])


def test_case_configs_share_header_region_and_support_distinct_layouts(tmp_path):
    assert set(CASE_REDACTION_CONFIGS) == {"NSR_001", "SB_001", "ST_001"}
    assert CASE_REDACTION_CONFIGS["NSR_001"] == CASE_REDACTION_CONFIGS["SB_001"] == ()
    assert CASE_REDACTION_CONFIGS["ST_001"] == (HEADER_REDACTION_REGION,)
    source = tmp_path / "multi-region-source.png"
    first_layout_output = tmp_path / "layout-a.png"
    second_layout_output = tmp_path / "layout-b.png"
    _make_test_image(source)
    first_layout = [{"x": 0.1, "y": 0.2, "width": 0.3, "height": 0.1}]
    second_layout = [{"x": 0.7, "y": 0.8, "width": 0.2, "height": 0.1}, {"x": 0.0, "y": 0.0, "width": 0.1, "height": 0.1}]
    create_learner_image(source, first_layout_output, first_layout)
    create_learner_image(source, second_layout_output, second_layout)
    assert first_layout_output.is_file() and second_layout_output.is_file()


def test_empty_redaction_config_preserves_entire_image_without_blank_mask(tmp_path):
    source = tmp_path / "unmasked-source.png"
    output = tmp_path / "unmasked-learner.png"
    _make_test_image(source)

    create_learner_image(source, output, CASE_REDACTION_CONFIGS["NSR_001"])

    with Image.open(source) as original, Image.open(output) as learner:
        assert learner.size == original.size
        assert ImageChops.difference(original.convert("RGB"), learner.convert("RGB")).getbbox() is None


def test_case_view_preparation_resolves_only_learner_asset_paths(tmp_path):
    windows_style = r"assets\ecg\source\NSR_001.jpg"
    learner = learner_output_path(windows_style, project_root=tmp_path)
    assert learner == (tmp_path / "assets/ecg/learner/NSR_001_learner.png").resolve()
    assert learner_output_path(Path(windows_style), project_root=tmp_path) == learner
    assert learner_output_path("assets/ecg/NSR_001.jpg", project_root=tmp_path) is None
    assert learner_output_path(r"assets\ecg\source\..\..\outside.jpg", project_root=tmp_path) is None


def test_existing_evaluator_and_reasoning_contracts_are_unchanged():
    case = get_case_by_id("case_001")
    assert case is not None
    result = evaluate_rate({"answer": "75", "reasoning": "Counted the ventricular complexes"}, case)
    assert result.status == EvaluationStatus.CORRECT
    attempt = create_reasoning_attempt("case_001")
    assert attempt["case_id"] == "case_001"
    assert {"rate", "rhythm", "axis", "p_waves", "pr_interval", "qrs", "st_t"}.issubset(attempt)
