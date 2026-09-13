import json
from pathlib import Path

import pytest

from docrecon.models import OCRResult, SourceRecord
from docrecon.validation import validate

CFG=json.loads((Path(__file__).parents[1] / "config.json").read_text())

@pytest.fixture
def record():
    return SourceRecord(2, "1", "Ada", "Example", "0803 111 2233", "12 Demo Avenue, Sample City", "Sample City", "DEMO00000001")

def pod(**changes):
    values=dict(extracted_name="Ada Example", extracted_phone="+2348031112233",
                extracted_address="12 Demo Ave Sample City", extracted_reference="DEMO00000001",
                receiver_name_present=True, signature_present=True,
                delivery_date_present=True, ocr_confidence=90)
    values.update(changes)
    return OCRResult(**values)

def test_success(record):
    assert validate(record, pod(), "DEMO00000001", CFG).final_status == "SUCCESSFUL"

def test_name_failure_requires_phone_and_address(record):
    result=validate(record, pod(extracted_name="Different Person", extracted_phone="08000000000"), "DEMO00000001", CFG)
    assert result.final_status == "REJECTED"
    assert {"NAME_MISMATCH", "PHONE_MISMATCH", "IDENTITY_FALLBACK_FAILED"} <= set(result.reason_codes)

def test_name_failure_rescued_only_by_both(record):
    result=validate(record, pod(extracted_name="Different Person", extracted_phone="0803 111 2233"), "DEMO00000001", CFG)
    assert result.identity_status == "MATCH - PHONE+ADDRESS FALLBACK"

@pytest.mark.parametrize(("field", "code"), [
    ("receiver_name_present", "RECEIVER_NAME_MISSING"),
    ("signature_present", "SIGNATURE_MISSING"),
    ("delivery_date_present", "DELIVERY_DATE_MISSING"),
])
def test_missing_completion_evidence(record, field, code):
    result=validate(record, pod(**{field: False}), "DEMO00000001", CFG)
    assert result.final_status == "REJECTED"
    assert code in result.reason_codes

def test_low_confidence_routes_to_review(record):
    result=validate(record, pod(ocr_confidence=10), "DEMO00000001", CFG)
    assert result.final_status == "REVIEW"
    assert "LOW_OCR_CONFIDENCE" in result.reason_codes

def test_reference_is_strict(record):
    result=validate(record, pod(extracted_reference="DEMO00000009"), "DEMO00000001", CFG)
    assert result.final_status == "REJECTED"
    assert "REFERENCE_MISMATCH" in result.reason_codes
