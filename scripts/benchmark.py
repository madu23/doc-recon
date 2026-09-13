"""Measure deterministic validation throughput; repeated synthetic load is not an accuracy benchmark."""
import argparse, json, platform, statistics, sys, time
from pathlib import Path
from docrecon.models import OCRResult, SourceRecord
from docrecon.validation import validate

def main():
    p=argparse.ArgumentParser(description="Run a repeated synthetic validation load test")
    p.add_argument("--samples",type=int,default=1000); args=p.parse_args()
    cfg=json.loads((Path(__file__).parents[1]/"config.json").read_text())
    record=SourceRecord(2,"1","Ada","Example","08031112233","12 Demo Avenue","Sample City","DEMO00000001")
    pod=OCRResult(extracted_name="Ada Example",extracted_phone="08031112233",extracted_address="12 Demo Avenue",
        extracted_reference="DEMO00000001",receiver_name_present=True,signature_present=True,
        delivery_date_present=True,ocr_confidence=95)
    lat=[]; start=time.perf_counter()
    for _ in range(args.samples):
        one=time.perf_counter(); validate(record,pod,"DEMO00000001",cfg); lat.append((time.perf_counter()-one)*1000)
    elapsed=time.perf_counter()-start
    ordered=sorted(lat); p95=ordered[min(len(ordered)-1,int(len(ordered)*.95))] if len(ordered)>=20 else None
    print("Synthetic repeated-load benchmark (validation only; excludes OCR)")
    print(json.dumps({"samples":args.samples,"os":platform.platform(),"python":sys.version.split()[0],
        "elapsed_seconds":elapsed,"throughput_per_second":args.samples/elapsed,
        "mean_ms":statistics.mean(lat),"median_ms":statistics.median(lat),"p95_ms":p95},indent=2))

if __name__ == "__main__": main()
