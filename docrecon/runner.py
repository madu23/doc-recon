from __future__ import annotations
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import json, os, shutil, time, traceback
from .models import SourceRecord, OCRResult, ValidationResult
from .normalization import normalize_reference
from .ocr import extract_pod, configure_tesseract
from .validation import validate
from .excel_io import read_source_records, write_report


def load_config(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def index_images(folder: Path, extensions: list[str]) -> tuple[dict[str,Path], list[str]]:
    idx={}; duplicates=[]
    extset={x.lower() for x in extensions}
    for p in folder.iterdir():
        if not p.is_file() or p.suffix.lower() not in extset:
            continue
        ref=normalize_reference(p.stem)
        # Accepted files from previous runs may be prefixed with a numeric serial.
        parts=p.stem.split("-",1)
        if len(parts)==2 and parts[0].isdigit(): ref=normalize_reference(parts[1])
        if ref in idx: duplicates.append(ref)
        else: idx[ref]=p
    return idx,duplicates


def _process_one(record: SourceRecord, image_path: Path, cfg: dict) -> ValidationResult:
    started=time.perf_counter()
    configure_tesseract(cfg)
    filename_ref=image_path.stem
    parts=filename_ref.split("-",1)
    if len(parts)==2 and parts[0].isdigit(): filename_ref=parts[1]
    extracted=extract_pod(image_path, record.customer_name, record.phone, record.address, record.pod_number, cfg)
    result=validate(record,extracted,filename_ref,cfg)
    result.original_filename=image_path.name
    result.processing_time_ms=(time.perf_counter()-started)*1000
    return result


def run(input_path: Path, pods_dir: Path, rejected_dir: Path, output_dir: Path, cfg: dict,
        workers: int=1, dry_run: bool=False, copy_files: bool|None=None) -> tuple[list[ValidationResult], Path]:
    records=read_source_records(input_path,cfg)
    image_idx,duplicates=index_images(pods_dir,cfg["files"]["supported_extensions"])
    rejected_dir.mkdir(parents=True,exist_ok=True)
    output_dir.mkdir(parents=True,exist_ok=True)
    accepted_dir=output_dir / "accepted"
    accepted_dir.mkdir(parents=True,exist_ok=True)
    if duplicates:
        print(f"WARNING: duplicate image references detected: {', '.join(duplicates[:10])}")

    results=[]
    tasks=[]
    start=time.time()
    missing=[]
    duplicate_refs=set(duplicates)
    for record in records:
        ref=normalize_reference(record.pod_number)
        if ref in duplicate_refs:
            r=ValidationResult(source=record, original_filename="")
            r.identity_status="NOT CHECKED"; r.completion_status="NOT CHECKED"
            r.final_status="REVIEW"; r.action_required="YES"; r.reason_codes=["DUPLICATE_REFERENCE"]
            r.reason_evidence="Multiple POD files normalize to this reference; assignment requires review."
            results.append(r); continue
        p=image_idx.get(ref)
        if not p:
            r=ValidationResult(source=record, original_filename="")
            r.identity_status="NOT CHECKED"; r.completion_status="NOT CHECKED"
            r.final_status="REJECTED"; r.action_required="YES"; r.reason_codes=["POD_NOT_FOUND"]
            r.reason_evidence="POD image matching the Excel reference was not found."
            results.append(r); missing.append(record)
        else:
            tasks.append((record,p))

    workers=max(1,int(workers))
    if workers == 1:
        iterable=[]
        for i,(rec,p) in enumerate(tasks,1):
            try: r=_process_one(rec,p,cfg)
            except Exception as e:
                r=ValidationResult(source=rec,original_filename=p.name)
                r.final_status="REJECTED"; r.action_required="YES"; r.identity_status="ERROR"; r.completion_status="ERROR"
                r.reason_codes=["PROCESSING_ERROR", "UNREADABLE_DOCUMENT"]; r.reason_evidence=f"OCR/processing failed: {type(e).__name__}"
                r.final_status="REVIEW"
            results.append(r)
            print(f"[{i}/{len(tasks)}] {rec.pod_number}: {r.final_status}")
    else:
        # Thread pool is appropriate because each pytesseract call spends most time in an external Tesseract process.
        with ThreadPoolExecutor(max_workers=workers) as ex:
            futs={ex.submit(_process_one,rec,p,cfg):(rec,p) for rec,p in tasks}
            done=0
            for fut in as_completed(futs):
                rec,p=futs[fut]; done+=1
                try: r=fut.result()
                except Exception as e:
                    r=ValidationResult(source=rec,original_filename=p.name)
                    r.final_status="REJECTED"; r.action_required="YES"; r.identity_status="ERROR"; r.completion_status="ERROR"
                    r.reason_codes=["PROCESSING_ERROR", "UNREADABLE_DOCUMENT"]; r.reason_evidence=f"OCR/processing failed: {type(e).__name__}"
                    r.final_status="REVIEW"
                results.append(r)
                if done == 1 or done % 25 == 0 or done == len(futs):
                    elapsed=max(time.time()-start,0.001)
                    print(f"Processed {done}/{len(futs)} | {done/elapsed:.2f} POD/s")

    # Stable ordering must follow Excel order, never parallel completion order.
    results.sort(key=lambda r:r.source.row_number)

    copy_mode=cfg["files"].get("copy_instead_of_move",False) if copy_files is None else copy_files
    for r in results:
        if not r.original_filename:
            continue
        src=pods_dir / r.original_filename
        if not src.exists():
            # It may have been moved by an earlier resumed attempt; do not crash the full job.
            continue
        if r.final_status == "SUCCESSFUL":
            serial=str(r.source.serial or r.source.row_number)
            target_name=f"{serial}-{normalize_reference(r.source.pod_number)}{src.suffix.lower()}"
            dst=accepted_dir / target_name
            r.final_filename=target_name; r.final_path=str(dst)
        elif r.final_status == "REJECTED":
            dst=rejected_dir / src.name
            r.final_filename=src.name; r.final_path=str(dst)
        else:
            dst=output_dir / "review" / src.name
            dst.parent.mkdir(parents=True, exist_ok=True)
            r.final_filename=src.name; r.final_path=str(dst)
        if dry_run:
            continue
        if dst.exists():
            r.final_status="REVIEW"; r.action_required="YES"
            if "OUTPUT_COLLISION" not in r.reason_codes: r.reason_codes.append("OUTPUT_COLLISION")
            continue
        if copy_mode: shutil.copy2(src,dst)
        else: shutil.move(str(src),str(dst))

    report=output_dir / "POD_Validation_Report.xlsx"
    write_report(results,report)
    return results,report
