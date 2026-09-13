"""Generate obviously synthetic workbook, labelled cases, and POD-like images."""
import json
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from openpyxl import Workbook

ROOT=Path(__file__).parents[1]; INPUT=ROOT/"samples"/"input"; PODS=ROOT/"samples"/"pods"; EXPECTED=ROOT/"samples"/"expected"
CASES=[
 (1,"Ada","Example","DEMO00000001","SUCCESSFUL","complete"),
 (2,"Tunde","Sample","DEMO00000002","SUCCESSFUL","complete"),
 (3,"Chika","Demo","DEMO00000003","SUCCESSFUL","complete"),
 (4,"Mina","Fixture","DEMO00000004","REJECTED","complete"),
 (5,"Ola","Synthetic","DEMO00000005","REJECTED","wrong reference"),
 (6,"Ife","Example","DEMO00000006","REJECTED","missing receiver"),
 (7,"Kemi","Sample","DEMO00000007","REJECTED","missing signature"),
 (8,"Nia","Demo","DEMO00000008","REJECTED","missing date"),
 (9,"Femi","Fixture","DEMO00000009","REJECTED","missing all"),
 (10,"Zara","Synthetic","DEMO00000010","REVIEW","unreadable"),
 (11,"Noah","Example","DEMO00000011","REJECTED","missing file"),
 (12,"Lina","Sample","DEMO00000012","REVIEW","duplicate file"),
]

def main():
    for d in (INPUT,PODS,EXPECTED): d.mkdir(parents=True,exist_ok=True)
    wb=Workbook(); ws=wb.active; ws.title="Synthetic Records"; ws.append(["SYNTHETIC DATA - NOT A REAL CLIENT"])
    ws.append(["S/N","FIRST_NAME","LAST_NAME","MOBILE","STREET","CITY","POD number"])
    labels=[]
    for serial,first,last,ref,status,case in CASES:
        ws.append([serial,first,last,f"0803000{serial:04d}",f"{serial} Demo Avenue","Sample City",ref])
        labels.append({"reference":ref,"status":status,"case":case})
        if case=="missing file": continue
        image=Image.new("RGB",(1200,800),"white"); draw=ImageDraw.Draw(image)
        try: font=ImageFont.truetype("DejaVuSans.ttf",30)
        except OSError: font=ImageFont.load_default()
        actual_ref="DEMO00000999" if case=="wrong reference" else ref
        shown_name=(f"{last} {first}" if serial==2 else "Unknown Person" if serial in (3,4) else f"{first} {last}")
        shown_phone=("08039999999" if serial==4 else f"0803000{serial:04d}")
        lines=["SYNTHETIC PROOF OF DELIVERY",f"Reference: {actual_ref}",f"Customer: {shown_name}",
            f"Phone: {shown_phone}",f"Address: {serial} Demo Avenue, Sample City"]
        y=50
        for line in lines: draw.text((60,y),line,fill="black",font=font); y+=55
        draw.rectangle((50,380,1150,750),outline="black",width=3)
        draw.text((600,385),"DELIVERY INFORMATION",fill="black",font=font)
        if case not in ("missing receiver","missing all"): draw.text((620,450),f"Receiver: Demo {serial}",fill="black",font=font)
        if case not in ("missing signature","missing all"): draw.line((650,510,760,475,900,525),fill="black",width=7)
        if case not in ("missing date","missing all"): draw.text((620,545),"2026-01-15",fill="black",font=font)
        if case=="unreadable": image=image.filter(ImageFilter.GaussianBlur(12))
        image.save(PODS/f"{ref}.png")
        if case=="duplicate file": image.save(PODS/"DEMO-00000012.png")
    wb.save(INPUT/"sample_input.xlsx"); (EXPECTED/"labels.json").write_text(json.dumps(labels,indent=2))
    print(f"Generated {len(CASES)} synthetic records in {ROOT/'samples'}")

if __name__ == "__main__": main()
