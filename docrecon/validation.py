from __future__ import annotations
from .models import SourceRecord, OCRResult, ValidationResult
from .normalization import name_similarity, address_similarity, normalize_phone, normalize_reference


def validate(record: SourceRecord, extracted: OCRResult, filename_ref: str, cfg: dict) -> ValidationResult:
    vcfg=cfg["validation"]
    result=ValidationResult(source=record, extracted=extracted)
    expected_name=record.customer_name
    result.name_score=name_similarity(expected_name, extracted.extracted_name)
    result.address_score=address_similarity(record.address, extracted.extracted_address)
    result.phone_match=bool(normalize_phone(record.phone)) and normalize_phone(record.phone)==normalize_phone(extracted.extracted_phone)
    expected_ref=normalize_reference(record.pod_number)
    ocr_ref=normalize_reference(extracted.extracted_reference)
    filename_match=expected_ref==normalize_reference(filename_ref)
    result.reference_match=filename_match and bool(ocr_ref) and ocr_ref==expected_ref

    # Reference is always strict.
    if not filename_match or (vcfg.get("require_reference_inside_pod",True) and not result.reference_match):
        result.reason_codes.append("REFERENCE_MISMATCH")

    name_ok=result.name_score >= float(vcfg.get("name_match_threshold",88))
    if name_ok:
        result.identity_status="MATCH"
    else:
        # Business rule: if a name does not confidently match,
        # second-layer validation only succeeds when BOTH phone and address match.
        fallback_ok = result.phone_match and result.address_score >= float(vcfg.get("address_match_threshold",72))
        if fallback_ok:
            result.identity_status="MATCH - PHONE+ADDRESS FALLBACK"
        else:
            result.identity_status="MISMATCH"
            result.reason_codes.extend(["NAME_MISMATCH", "IDENTITY_FALLBACK_FAILED"])
            if not result.phone_match:
                result.reason_codes.append("PHONE_MISMATCH")
            if result.address_score < float(vcfg.get("address_match_threshold",72)):
                result.reason_codes.append("ADDRESS_MISMATCH")

    missing=[]
    if not extracted.receiver_name_present:
        missing.append("RECEIVER_NAME_MISSING")
    if not extracted.signature_present:
        missing.append("SIGNATURE_MISSING")
    if not extracted.delivery_date_present:
        missing.append("DELIVERY_DATE_MISSING")
    result.reason_codes.extend(missing)
    result.completion_status="PASS" if not missing else "FAIL"

    minimum_confidence=float(vcfg.get("minimum_ocr_confidence", 35))
    if extracted.ocr_confidence < minimum_confidence:
        result.reason_codes.append("LOW_OCR_CONFIDENCE")

    hard_rejections={
        "REFERENCE_MISMATCH", "NAME_MISMATCH", "IDENTITY_FALLBACK_FAILED",
        "RECEIVER_NAME_MISSING", "SIGNATURE_MISSING", "DELIVERY_DATE_MISSING",
    }
    unreadable=extracted.ocr_confidence < minimum_confidence and not extracted.full_text.strip()
    if unreadable:
        if "UNREADABLE_DOCUMENT" not in result.reason_codes: result.reason_codes.append("UNREADABLE_DOCUMENT")
        result.final_status="REVIEW"
        result.action_required="YES"
    elif any(code in hard_rejections for code in result.reason_codes):
        result.final_status="REJECTED"
        result.action_required="YES"
    elif result.reason_codes:
        result.final_status="REVIEW"
        result.action_required="YES"
    else:
        result.final_status="SUCCESSFUL"
        result.action_required="NO"

    evidence=[]
    evidence.append(f"Name score={result.name_score:.1f}%")
    if not name_ok:
        evidence.append(f"name fallback: phone={'match' if result.phone_match else 'mismatch'}, address score={result.address_score:.1f}%")
    else:
        evidence.append(f"phone={'match' if result.phone_match else 'not required after name match'}; address score={result.address_score:.1f}%")
    evidence.append(f"reference={'match' if result.reference_match else 'mismatch/unreadable'}")
    evidence.append(f"receiver={'present' if extracted.receiver_name_present else 'missing'}")
    evidence.append(f"signature={'present' if extracted.signature_present else 'missing'}")
    evidence.append(f"delivery date={'present' if extracted.delivery_date_present else 'missing'}")
    if result.reason_codes:
        evidence.append("reasons=" + ", ".join(result.reason_codes))
    else:
        evidence.append("Identity, reference and completion checks passed.")
    result.reason_evidence="; ".join(evidence)
    return result
