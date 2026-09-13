"""Evaluate an actual DocRecon Excel report against synthetic expected labels."""
import argparse, json, statistics
from pathlib import Path
from openpyxl import load_workbook

def main():
    p=argparse.ArgumentParser(description="Compute decision metrics from a DocRecon report and labelled JSON")
    p.add_argument("--report", required=True); p.add_argument("--expected", required=True)
    args=p.parse_args(); expected=json.loads(Path(args.expected).read_text())
    ws=load_workbook(args.report, data_only=True, read_only=True)["FULL RECORDS"]
    rows=list(ws.values); header={name:i for i,name in enumerate(rows[0])}
    actual={str(r[header["Excel Original POD"]]):str(r[header["Final Status"]]) for r in rows[1:]}
    labels={str(x["reference"]):x["status"] for x in expected}
    compared=[(labels[k],actual.get(k,"MISSING")) for k in labels]
    correct=sum(e==a for e,a in compared); n=len(compared)
    false_accept=sum(a=="SUCCESSFUL" and e!="SUCCESSFUL" for e,a in compared)
    false_reject=sum(a=="REJECTED" and e=="SUCCESSFUL" for e,a in compared)
    review=sum(a=="REVIEW" for _,a in compared)
    print("Synthetic demonstration benchmark")
    print(json.dumps({"labelled":n,"decision_accuracy":correct/n if n else 0,
        "review_rate":review/n if n else 0,"false_acceptance_rate":false_accept/n if n else 0,
        "false_rejection_rate":false_reject/n if n else 0},indent=2))

if __name__ == "__main__": main()
