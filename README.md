# DocRecon

DocRecon is a Python document-intelligence pipeline that reconciles Proof-of-Delivery (POD) images with structured business records. It combines image preprocessing, Tesseract OCR, template-aware evidence extraction, fuzzy identity reconciliation, deterministic business rules, confidence-based review routing, safe file handling, and auditable Excel reporting. All public samples are synthetic.

## Problem and outcome

POD validation is more than reading text. A defensible decision must link a document to the correct record, check identity, independently detect completion evidence, preserve uncertainty, and explain the outcome. DocRecon produces `SUCCESSFUL`, `REJECTED`, or `REVIEW`.

> Extraction proposes evidence. Deterministic validation decides whether that evidence satisfies business rules.

The pipeline never fills in missing values or uses a weak name match to override conflicting evidence.

## Demo

Prerequisites: Python 3.10+ and [Tesseract OCR](https://tesseract-ocr.github.io/). On Windows, install Tesseract and set `ocr.tesseract_cmd` in a local config if it is not on `PATH`.

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
python -m pip install -e .[dev]
python scripts/generate_synthetic_samples.py
docrecon --input samples/input/sample_input.xlsx --pods samples/pods --output output --dry-run
pytest
```

`--dry-run` is the default. Use `--copy` to preserve originals or explicitly opt into destructive routing with `--move`. Existing destinations are never overwritten.

## Pipeline

Structured records → indexed image lookup → preprocessing → multi-pass Tesseract OCR → template-aware extraction → reconciliation → deterministic validation → safe routing and Excel audit report.

See [architecture](docs/architecture.md) and [validation rules](docs/validation-rules.md).

## Validation strategy

- References are strictly compared after case/punctuation normalization; they are not fuzzily reassigned.
- Names use RapidFuzz with a configurable default threshold of 88.
- If the name fails, identity is rescued only when both normalized phone and address similarity (default 72) pass.
- Receiver name, signature-like mark presence, and delivery date presence are independent requirements.
- Low-confidence or unreadable evidence routes to `REVIEW` unless a deterministic rejection rule already fails.
- Thresholds are starting points and require calibration on representative, permitted data.

Signature handling is **presence detection**, not biometric signature verification.

## CLI

```text
docrecon --input WORKBOOK --pods POD_FOLDER [--output OUTPUT]
         [--rejected REJECTED] [--config CONFIG] [--workers N]
         [--dry-run | --copy | --move]
```

The CLI writes `POD_Validation_Report.xlsx` with summary, full audit records, challenges, corrections, and location summary sheets.

## Evaluation and benchmark

Generate the labelled synthetic fixtures, then inspect `python scripts/evaluate.py --help` and `python scripts/benchmark.py --help`. These tools compute current-run results; no numbers are hard-coded. See [evaluation](docs/evaluation.md).

## Technology

Python, OpenCV, NumPy, Pillow, Tesseract/pytesseract, RapidFuzz, openpyxl, and pytest. No cloud OCR, LLM, VLM, or production deployment is claimed.

## Security and privacy

Tracked demonstration data is generated and synthetic. Full OCR text, phone numbers, addresses, reports, `.env` files, local configs, and output folders are excluded.

## Current limitations

- Extraction targets the demonstrated POD layout and needs a template classifier for heterogeneous forms.
- Signature detection identifies a signature-like mark only.
- Tesseract is installed separately.
- Synthetic fixtures demonstrate behavior; they do not establish production accuracy.
- Thresholds have not been calibrated on a representative production corpus.

## Repository layout

`docrecon/` contains the pipeline, `tests/` tests, `samples/` generated synthetic fixtures, `scripts/` generation/evaluation/benchmark tools, and `docs/` design documentation.

## License

MIT. See [LICENSE](LICENSE).
