from __future__ import annotations
from dataclasses import dataclass, field, asdict
from enum import Enum

class Status(str, Enum):
    SUCCESSFUL = "SUCCESSFUL"
    REJECTED = "REJECTED"
    REVIEW = "REVIEW"

@dataclass
class SourceRecord:
    row_number: int
    serial: str
    first_name: str
    last_name: str
    phone: str
    address: str
    location: str
    pod_number: str

    @property
    def customer_name(self) -> str:
        return " ".join(x for x in [self.first_name, self.last_name] if x).strip()

@dataclass
class OCRResult:
    full_text: str = ""
    extracted_name: str = ""
    extracted_phone: str = ""
    extracted_address: str = ""
    extracted_reference: str = ""
    receiver_name_present: bool = False
    signature_present: bool = False
    delivery_date_present: bool = False
    delivery_date_text: str = ""
    delivery_section_found: bool = False
    ocr_confidence: float = 0.0
    engine: str = "tesseract"
    engine_version: str = ""
    processing_time_ms: float = 0.0
    diagnostics: dict = field(default_factory=dict)

@dataclass
class ValidationResult:
    source: SourceRecord
    original_filename: str = ""
    final_filename: str = ""
    final_path: str = ""
    extracted: OCRResult = field(default_factory=OCRResult)
    name_score: float = 0.0
    address_score: float = 0.0
    phone_match: bool = False
    reference_match: bool = False
    identity_status: str = ""
    completion_status: str = ""
    final_status: str = ""
    action_required: str = ""
    reason_codes: list[str] = field(default_factory=list)
    reason_evidence: str = ""
    processing_time_ms: float = 0.0

    def to_dict(self) -> dict:
        d = asdict(self)
        d["customer"] = self.source.customer_name
        return d
