from __future__ import annotations
import time
from pathlib import Path
import re
import cv2
import numpy as np
import pytesseract
from pytesseract import Output
from rapidfuzz import fuzz
from .models import OCRResult
from .normalization import normalize_reference, normalize_phone, normalize_address, normalize_name

REF_RE = re.compile(r"\b[A-Z][A-Z0-9-]{7,}\b", re.I)
PHONE_RE = re.compile(r"(?:\+?234|0)[\s-]?[789][01]\d(?:[\s-]?\d){7,8}")


def configure_tesseract(cfg: dict) -> None:
    cmd = str(cfg.get("ocr", {}).get("tesseract_cmd", "") or "").strip()
    if cmd:
        pytesseract.pytesseract.tesseract_cmd = cmd


def preprocess(image: np.ndarray, upscale: float = 1.5) -> tuple[np.ndarray, np.ndarray]:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    if upscale and upscale != 1:
        gray = cv2.resize(gray, None, fx=upscale, fy=upscale, interpolation=cv2.INTER_CUBIC)
    # Two representations: grayscale for layout; adaptive binary for OCR.
    binary = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 15)
    return gray, binary


def _ocr_text(binary: np.ndarray, cfg: dict) -> tuple[str, float, dict]:
    lang = cfg.get("ocr", {}).get("language", "eng")
    psms = cfg.get("ocr", {}).get("psm_modes", [3, 11])
    texts = []
    confidences = []
    best_data = None
    best_conf = -1.0
    layout_data = None
    for psm in psms:
        config = f"--oem 3 --psm {int(psm)}"
        data = pytesseract.image_to_data(binary, lang=lang, config=config, output_type=Output.DICT)
        words, confs = [], []
        grouped = {}
        for i, (txt, conf) in enumerate(zip(data["text"], data["conf"])):
            txt = (txt or "").strip()
            try: c = float(conf)
            except: c = -1
            if txt:
                words.append(txt)
                key=(data.get("block_num",[0]*len(data["text"]))[i], data.get("par_num",[0]*len(data["text"]))[i], data.get("line_num",[0]*len(data["text"]))[i])
                grouped.setdefault(key,[]).append(txt)
                if c >= 0: confs.append(c)
        text = "\n".join(" ".join(grouped[k]) for k in grouped)
        mean_conf = sum(confs)/len(confs) if confs else 0.0
        texts.append(text)
        confidences.append(mean_conf)
        layout_data = data  # sparse-text PSM (last configured mode, normally 11) is better for form anchors
        if mean_conf > best_conf:
            best_conf = mean_conf
            best_data = data
    # combine to improve recall; duplicates are harmless for extraction. Layout uses sparse-text data.
    return "\n".join(texts), (sum(confidences)/len(confidences) if confidences else 0.0), layout_data or best_data or {}


def _find_reference(text: str, expected_reference: str) -> str:
    candidates = {normalize_reference(m.group(0)) for m in REF_RE.finditer(text)}
    expected = normalize_reference(expected_reference)
    # OCR sometimes inserts spaces/punctuation. Search compacted text too.
    compact = normalize_reference(text)
    if expected and expected in compact:
        return expected
    if not candidates:
        labelled=re.search(r"(?:REFERENCE|TRACKING|WAYBILL)\s*[:#-]?\s*([A-Z0-9-]{8,})", text, re.I)
        if labelled: candidates.add(normalize_reference(labelled.group(1)))
    if not candidates:
        return ""
    if expected:
        # Bounded OCR-confusion repair: only accept a same-length candidate where
        # every differing character is a documented glyph pair. Return the known
        # expected value; validation remains an exact comparison after this step.
        pairs={frozenset(("0","O")), frozenset(("1","I"))}
        for candidate in candidates:
            if len(candidate)==len(expected) and all(a==b or frozenset((a,b)) in pairs for a,b in zip(candidate,expected)):
                return expected
        return max(candidates, key=lambda c: fuzz.ratio(expected, c))
    return max(candidates, key=len)


def _extract_phone(text: str, expected_phone: str) -> str:
    candidates = []
    for m in PHONE_RE.finditer(text):
        p = normalize_phone(m.group(0))
        if p: candidates.append(p)
    # Fallback: find 10-13 digit runs from OCR punctuation-stripped text
    for raw in re.findall(r"\d{10,13}", re.sub(r"[^0-9+]", "", text)):
        p = normalize_phone(raw)
        if p: candidates.append(p)
    expected = normalize_phone(expected_phone)
    if expected and expected in candidates:
        return expected
    if candidates and expected:
        return max(candidates, key=lambda p: fuzz.ratio(expected, p))
    return candidates[0] if candidates else ""


def _line_candidates(text: str) -> list[str]:
    lines=[]
    for line in text.splitlines():
        line=re.sub(r"\s+", " ", line).strip(" |:-")
        if len(line) >= 3: lines.append(line)
    return lines


def _best_name_line(text: str, expected_name: str) -> str:
    expected = normalize_name(expected_name)
    candidates = _line_candidates(text)
    # Also inspect local phrases after common labels.
    chunks = re.split(r"(?:NAME OF RECEIVER|RECEIVER NAME|RECIPIENTS NAME|RECIPIENT NAME)", text, flags=re.I)
    if len(chunks) > 1:
        candidates.extend(_line_candidates(chunks[-1][:180]))
    def quality(line):
        norm=normalize_name(line)
        if not norm: return 0
        if len(norm.replace(" ", "")) < max(4, int(len(expected.replace(" ", ""))*0.45)):
            return 0
        # Penalise very long lines containing unrelated document text.
        base=max(fuzz.ratio(expected,norm), fuzz.token_set_ratio(expected,norm), fuzz.partial_ratio(expected,norm))
        if len(norm.split()) > 8: base -= 20
        # Prefer plausible name lines over lines that include long numeric identifiers.
        if sum(ch.isdigit() for ch in line) >= 5: base -= 8
        return base
    return max(candidates, key=quality, default="")


def _best_address_line(text: str, expected_address: str) -> str:
    expected = normalize_address(expected_address)
    candidates = _line_candidates(text)
    def quality(line):
        norm=normalize_address(line)
        if len(norm) < 8: return 0
        return max(fuzz.token_set_ratio(expected,norm), fuzz.partial_ratio(expected,norm))
    # Combine adjacent lines as addresses commonly wrap.
    combined = candidates + [candidates[i] + " " + candidates[i+1] for i in range(len(candidates)-1)]
    return max(combined, key=quality, default="")


def _locate_delivery_section(image: np.ndarray, binary: np.ndarray, data: dict) -> tuple[int,int,int,int] | None:
    # Coordinates in OCR data belong to the upscaled binary image.
    words = data.get("text", []) if data else []
    xs=data.get("left", []); ys=data.get("top", []); ws=data.get("width", []); hs=data.get("height", [])
    H,W=binary.shape[:2]
    hits=[]
    refs=[]
    for i,w in enumerate(words):
        raw=str(w or "")
        norm_alpha=re.sub(r"[^A-Z]", "", raw.upper())
        norm_ref=re.sub(r"[^A-Z0-9]", "", raw.upper())
        if norm_alpha in {"DELIVERY","INFORMATION","RECIPIENTS","RECIPIENT"}:
            hits.append((norm_alpha, int(xs[i]), int(ys[i]), int(ws[i]), int(hs[i])))
        if len(norm_ref) >= 12 and any(ch.isdigit() for ch in norm_ref):
            refs.append((norm_ref, int(xs[i]), int(ys[i]), int(ws[i]), int(hs[i])))

    delivery=[h for h in hits if h[0]=="DELIVERY"]
    recipients=[h for h in hits if h[0] in {"RECIPIENTS","RECIPIENT"}]
    if delivery:
        h=max(delivery, key=lambda t: (t[1] > W*0.45, t[2], t[1]))
        x=max(0, h[1]-30); y=max(0, h[2]-15)
        return x, y, W-5, min(H, y + int(H*0.25))
    if recipients:
        # Recipient label is inside Section 9, just below its heading.
        h=max(recipients, key=lambda t: (t[1] > W*0.45, t[2], t[1]))
        x=max(0, h[1]-35); y=max(0, h[2]-70)
        return x, y, W-5, min(H, y + int(H*0.27))
    if refs:
        # Demonstration-template fallback: a lower reference box sits immediately left of
        # Section 9. Its OCR bounding box gives both position and document scale, even for
        # perspective photographs with large background margins.
        lower=max(refs, key=lambda t:t[2])
        _, rx, ry, rw, rh=lower
        if ry > H*0.45:
            x=max(0, int(rx + 1.22*rw))
            y=max(0, int(ry - 1.12*rw))
            right=min(W, int(x + 1.55*rw))
            bottom=min(H, int(y + 1.02*rw))
            return x,y,right,bottom
    return None

def _colored_ink_ratio(crop_bgr: np.ndarray) -> float:
    if crop_bgr.size == 0: return 0.0
    hsv=cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2HSV)
    # Handwriting in samples is blue/purple; saturation filter suppresses black printed form lines.
    mask=(hsv[:,:,1] > 55) & (hsv[:,:,2] < 245)
    return float(mask.mean())


def _dark_ink_ratio(gray_crop: np.ndarray) -> float:
    if gray_crop.size == 0: return 0.0
    # Conservative fallback. Printed boxes/labels contribute dark pixels, so only use as secondary signal.
    return float((gray_crop < 100).mean())


def _handwriting_metrics(crop_bgr: np.ndarray) -> tuple[float, int, int]:
    if crop_bgr.size == 0:
        return 0.0, 0, 0
    gray=cv2.cvtColor(crop_bgr,cv2.COLOR_BGR2GRAY)
    blur=cv2.GaussianBlur(gray,(3,3),0)
    _,bw=cv2.threshold(blur,0,255,cv2.THRESH_BINARY_INV+cv2.THRESH_OTSU)
    h,w=bw.shape
    # Remove long printed form lines. Remaining connected strokes are mostly handwriting.
    horiz=cv2.morphologyEx(bw,cv2.MORPH_OPEN,cv2.getStructuringElement(cv2.MORPH_RECT,(max(15,w//8),1)))
    vert=cv2.morphologyEx(bw,cv2.MORPH_OPEN,cv2.getStructuringElement(cv2.MORPH_RECT,(1,max(10,h//3))))
    ink=cv2.subtract(bw,horiz)
    ink=cv2.subtract(ink,vert)
    ratio=float((ink>0).mean())
    n,labels,stats,centroids=cv2.connectedComponentsWithStats((ink>0).astype(np.uint8),8)
    areas=[int(st[4]) for st in stats[1:] if int(st[4])>=10]
    return ratio, len(areas), max(areas,default=0)

def _delivery_presence(image: np.ndarray, binary: np.ndarray, data: dict, scale: float) -> tuple[bool,bool,bool,str,dict]:
    box=_locate_delivery_section(image,binary,data)
    diag={"delivery_box": box}
    if not box:
        return False, False, False, "", diag
    x1,y1,x2,y2=box
    ox1,oy1,ox2,oy2=[int(v/scale) for v in (x1,y1,x2,y2)]
    section=image[max(0,oy1):min(image.shape[0],oy2), max(0,ox1):min(image.shape[1],ox2)]
    if section.size==0:
        return False,False,False,"",diag
    h,w=section.shape[:2]
    # Crop only the writable bands, deliberately excluding printed labels and border lines.
    rec=section[int(h*0.23):int(h*0.40), int(w*0.02):int(w*0.98)]
    sig=section[int(h*0.49):int(h*0.68), int(w*0.02):int(w*0.98)]
    date=section[int(h*0.78):int(h*0.95), int(w*0.02):int(w*0.98)]
    rr,rc,rl=_handwriting_metrics(rec)
    sr,sc,sl=_handwriting_metrics(sig)
    dr,dc,dl=_handwriting_metrics(date)
    diag.update({
        "recipient_ink_ratio":rr,"recipient_components":rc,"recipient_largest":rl,
        "signature_ink_ratio":sr,"signature_components":sc,"signature_largest":sl,
        "date_ink_ratio":dr,"date_components":dc,"date_largest":dl
    })
    # Calibrated conservatively against the supplied completed and blank Kxpress examples.
    rec_present = rr > 0.045 and (rc >= 3 or rl >= 80)
    sig_present = sr > 0.025 and (sc >= 3 or sl >= 100)
    date_present = dr > 0.018 and (dc >= 2 or dl >= 60)
    date_gray=cv2.cvtColor(date,cv2.COLOR_BGR2GRAY) if date.size else np.zeros((1,1),dtype=np.uint8)
    date_text=pytesseract.image_to_string(date_gray, config="--oem 3 --psm 7").strip() if date_gray.size>1 else ""
    # OCR digits may rescue a very light handwritten/printed date, but not a blank form line.
    digit_count=len(re.findall(r"\d",date_text))
    if digit_count >= 4 and dr > 0.008:
        date_present=True
    return rec_present,sig_present,date_present,date_text,diag

def extract_pod(image_path: Path, expected_name: str, expected_phone: str, expected_address: str, expected_reference: str, cfg: dict) -> OCRResult:
    started=time.perf_counter()
    image=cv2.imread(str(image_path))
    if image is None:
        raise ValueError(f"Unable to read image: {image_path}")
    scale=float(cfg.get("ocr",{}).get("upscale",1.5) or 1.0)
    gray,binary=preprocess(image,scale)
    text, conf, data=_ocr_text(binary,cfg)
    ref=_find_reference(text, expected_reference)
    phone=_extract_phone(text, expected_phone)
    name=_best_name_line(text, expected_name)
    address=_best_address_line(text, expected_address)
    rec,sig,date,date_text,diag=_delivery_presence(image,binary,data,scale)
    receiver_match=re.search(r"RECEIVER\s*[:#.-]\s*([A-Z][A-Z0-9 .'-]{2,})", text, re.I)
    if receiver_match and normalize_name(receiver_match.group(1)): rec=True
    date_match=re.search(r"\b(?:20\d{2}[-/]\d{1,2}[-/]\d{1,2}|\d{1,2}[-/]\d{1,2}[-/]20\d{2})\b", text)
    if date_match:
        date=True
        if not date_text: date_text=date_match.group(0)
    result=OCRResult(
        full_text=text,
        extracted_name=name,
        extracted_phone=phone,
        extracted_address=address,
        extracted_reference=ref,
        receiver_name_present=rec,
        signature_present=sig,
        delivery_date_present=date,
        delivery_date_text=date_text,
        delivery_section_found=bool(diag.get("delivery_box")),
        ocr_confidence=conf,
        diagnostics=diag,
    )
    result.processing_time_ms=(time.perf_counter()-started)*1000
    try:
        result.engine_version=str(pytesseract.get_tesseract_version())
    except Exception:
        result.engine_version="unavailable"
    return result
