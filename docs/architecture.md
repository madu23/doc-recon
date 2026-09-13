# Architecture

```mermaid
flowchart TD
  A[Excel source of truth] --> B[Record loader and normalization]
  B --> C[Reference-indexed POD lookup]
  C --> D[Image preprocessing]
  D --> E[Replaceable OCR boundary<br/>Tesseract implementation]
  E --> F[Template-aware field and completion extraction]
  F --> G[Normalization and identity reconciliation]
  G --> H[Deterministic validation engine]
  H --> I[SUCCESSFUL]
  H --> J[REJECTED]
  H --> K[REVIEW]
  I --> L[Audit report and safe routing]
  J --> L
  K --> L
```

The spreadsheet and POD directory are each scanned once. OCR is isolated in `docrecon/ocr.py`; validation accepts structured models and can be tested without Tesseract. The current extractor combines document-wide OCR with a known completion-section layout. This is template-aware V1, not general document understanding. Errors are contained per document.
