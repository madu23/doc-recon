# Validation rules

References are normalized to uppercase alphanumerics and compared exactly against the filename and extracted reference. DocRecon does not fuzzily assign documents.

The extractor has one bounded OCR-confusion repair: a same-length candidate may be aligned to the already assigned expected reference only when every differing glyph is `O/0` or `I/1`. It cannot change length, search another record, or repair unrelated characters.

Names are normalized for case, punctuation, whitespace, and token order. A score at or above `name_match_threshold` passes. Below it, the only fallback is:

```text
normalized phone matches AND address score >= address_match_threshold
```

Completion requires independent receiver-name, signature-presence, and delivery-date signals. Missing evidence produces specific reason codes. Low OCR confidence without a deterministic failure produces `REVIEW`; deterministic rule failures produce `REJECTED`. Missing values remain missing.

Defaults (name 88, address 72, OCR confidence 35) require calibration and versioning for each permitted production dataset.
