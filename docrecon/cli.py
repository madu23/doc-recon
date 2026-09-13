from __future__ import annotations
import argparse, os, sys, shutil
from pathlib import Path
from .runner import load_config, run


def build_parser():
    p=argparse.ArgumentParser(prog="docrecon", description="Validate POD images against an Excel master file using OCR.")
    p.add_argument("--input", required=True, help="Path to source .xlsx file")
    p.add_argument("--pods", required=True, help="Folder containing POD images")
    p.add_argument("--rejected", default="./output/rejected", help="Folder to receive rejected POD images")
    p.add_argument("--output", default="./output", help="Output folder for accepted PODs and report")
    p.add_argument("--config", default=str(Path(__file__).resolve().parents[1]/"config.json"), help="JSON configuration file")
    p.add_argument("--workers", type=int, default=max(1,min(4,(os.cpu_count() or 2)-1)), help="Parallel OCR workers")
    mode=p.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="Validate and report without routing images (safe default)")
    mode.add_argument("--copy", action="store_true", help="Copy routed images while preserving originals")
    mode.add_argument("--move", action="store_true", help="Move routed images (destructive production mode)")
    return p


def main():
    args=build_parser().parse_args()
    input_path=Path(args.input).expanduser().resolve()
    pods=Path(args.pods).expanduser().resolve()
    rejected=Path(args.rejected).expanduser().resolve()
    output=Path(args.output).expanduser().resolve()
    cfg_path=Path(args.config).expanduser().resolve()
    for p,label in [(input_path,"input workbook"),(pods,"POD folder"),(cfg_path,"config")]:
        if not p.exists():
            raise SystemExit(f"ERROR: {label} not found: {p}")
    print("DocRecon POD Validator")
    print(f"Input:    {input_path}")
    print(f"PODs:     {pods}")
    print(f"Rejected: {rejected}")
    print(f"Output:   {output}")
    print(f"Workers:  {args.workers}")
    cfg=load_config(cfg_path)
    dry_run=not (args.copy or args.move) or args.dry_run
    results,report=run(input_path,pods,rejected,output,cfg,args.workers,dry_run,not args.move)
    ok=sum(r.final_status=="SUCCESSFUL" for r in results)
    rej=sum(r.final_status=="REJECTED" for r in results)
    rev=sum(r.final_status=="REVIEW" for r in results)
    print("\nCompleted")
    print(f"Total:      {len(results)}")
    print(f"Successful: {ok}")
    print(f"Rejected:   {rej}")
    print(f"Review:     {rev}")
    print(f"Report:     {report}")

if __name__ == "__main__":
    main()
