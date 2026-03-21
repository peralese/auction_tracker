import hashlib
import json
import re
from datetime import datetime
from pathlib import Path

import pandas as pd
import pytesseract
from pdf2image import convert_from_path
from PIL import Image, ImageOps

EXCLUDE_KEYWORDS = [
    "Total Quantity",
    "Total Extended Price",
    "20% Buyer's Premium",
    "Tax1 Default",
    "Invoice Total",
    "Remaining Invoice Balance",
]
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png"}
PDF_SUFFIXES = {".pdf"}


# === Step 1: Preprocess the image ===
def preprocess_pil(image):
    gray = ImageOps.grayscale(image)
    enhanced = gray.point(lambda x: 0 if x < 140 else 255, '1')  # Simple threshold
    return enhanced


# === Step 2: Load and OCR the image ===
def preprocess_image(image_path):
    image = Image.open(image_path)
    return preprocess_pil(image)


def extract_text_from_image(image_path):
    image = preprocess_image(image_path)
    text = pytesseract.image_to_string(image)
    return text


def extract_text_from_pil(image):
    processed = preprocess_pil(image)
    text = pytesseract.image_to_string(processed)
    return text


def sha256_file(path, chunk_size=1024 * 1024):
    hasher = hashlib.sha256()
    with open(path, 'rb') as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b''):
            hasher.update(chunk)
    return hasher.hexdigest()


def load_processed_hashes(tracker_path):
    if not tracker_path.exists():
        return {}
    try:
        with tracker_path.open('r', encoding='utf-8') as handle:
            data = json.load(handle)
        if isinstance(data, dict):
            return data
    except Exception:
        return {}
    return {}


def save_processed_hashes(tracker_path, processed_hashes):
    with tracker_path.open('w', encoding='utf-8') as handle:
        json.dump(processed_hashes, handle, indent=2, sort_keys=True)


def build_item(item, extended, processed_at=None):
    processed_at = processed_at or datetime.today()
    return {
        'Date': processed_at.strftime('%Y-%m-%d'),
        'Item': item,
        'Cost': extended,
        'Buyer Premium (20%)': round(extended * 0.20, 2),
        'Total Cost': round(extended * 1.20, 2),
        'Selected for Listing': 'N'
    }


# === Step 3: Parse item lines ===
def parse_items(text, processed_at=None):
    lines = text.split('\n')
    parsed_items = []
    for line in lines:
        line = line.strip()
        if not line or any(keyword.lower() in line.lower() for keyword in EXCLUDE_KEYWORDS):
            continue

        match = re.search(
            r'^(?:\d+\s+)?(.+?)\s+\d+\s*x\s*([0-9]{1,3}(?:,[0-9]{3})*|[0-9]{1,6})\.(\d{2})\s+([0-9]{1,3}(?:,[0-9]{3})*|[0-9]{1,6})\.(\d{2})\b',
            line,
        )
        if match:
            item = match.group(1).strip()
            extended = float(f"{match.group(4).replace(',', '')}.{match.group(5)}")
            parsed_items.append(build_item(item, extended, processed_at=processed_at))
    return parsed_items


# === Step 4: Save to Excel ===
def save_to_excel(parsed_items, output_path=Path('output') / 'All_Items.xlsx'):
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(parsed_items)
    try:
        existing = pd.read_excel(output_path)
        df = pd.concat([existing, df], ignore_index=True)
    except FileNotFoundError:
        pass
    except Exception as exc:
        raise RuntimeError(f"Failed to read existing Excel file: {output_path}") from exc

    df.to_excel(output_path, index=False)


def discover_input_files(input_dir):
    image_paths = []
    pdf_paths = []
    for path in sorted(input_dir.iterdir()):
        if not path.is_file():
            continue
        suffix = path.suffix.lower()
        if suffix in IMAGE_SUFFIXES:
            image_paths.append(path)
        elif suffix in PDF_SUFFIXES:
            pdf_paths.append(path)
    return image_paths, pdf_paths


def processed_metadata(path, processed_at=None):
    processed_at = processed_at or datetime.now()
    return {
        'path': str(path),
        'processed_at': processed_at.isoformat(timespec='seconds'),
    }


def process_image_file(image_path, processed_at=None):
    text = extract_text_from_image(str(image_path))
    return parse_items(text, processed_at=processed_at)


def process_pdf_file(pdf_path, processed_at=None):
    pages = convert_from_path(str(pdf_path))
    if not pages:
        return []

    all_items = []
    for page in pages:
        text = extract_text_from_pil(page)
        all_items.extend(parse_items(text, processed_at=processed_at))
    return all_items


def process_pending_files(image_paths, pdf_paths, processed_hashes):
    all_items = []

    for image_path in image_paths:
        try:
            file_hash = sha256_file(image_path)
        except Exception as exc:
            print(f"Failed to hash file '{image_path}': {exc}")
            raise SystemExit(1)

        if file_hash in processed_hashes:
            print(f"Skipping already processed file: {image_path}")
            continue

        processed_at = datetime.now()
        try:
            items = process_image_file(image_path, processed_at=processed_at)
        except FileNotFoundError:
            print(f"Receipt image not found: {image_path}")
            raise SystemExit(1)
        except Exception as exc:
            print(f"Failed to OCR receipt image '{image_path}': {exc}")
            raise SystemExit(1)

        all_items.extend(items)
        if items:
            print(f"Extracted {len(items)} items from {image_path}")
        else:
            print(f"No items found in {image_path}")
        processed_hashes[file_hash] = processed_metadata(image_path, processed_at=processed_at)

    for pdf_path in pdf_paths:
        try:
            file_hash = sha256_file(pdf_path)
        except Exception as exc:
            print(f"Failed to hash file '{pdf_path}': {exc}")
            raise SystemExit(1)

        if file_hash in processed_hashes:
            print(f"Skipping already processed file: {pdf_path}")
            continue

        processed_at = datetime.now()
        try:
            pages = convert_from_path(str(pdf_path))
        except Exception as exc:
            print(f"Failed to convert PDF '{pdf_path}': {exc}")
            raise SystemExit(1)

        if not pages:
            print(f"No pages found in {pdf_path}")
            processed_hashes[file_hash] = processed_metadata(pdf_path, processed_at=processed_at)
            continue

        file_items = []
        for page_index, page in enumerate(pages, start=1):
            try:
                text = extract_text_from_pil(page)
            except Exception as exc:
                print(f"Failed to OCR '{pdf_path}' page {page_index}: {exc}")
                raise SystemExit(1)

            items = parse_items(text, processed_at=processed_at)
            file_items.extend(items)
            if items:
                print(f"Extracted {len(items)} items from {pdf_path} page {page_index}")
            else:
                print(f"No items found in {pdf_path} page {page_index}")
        all_items.extend(file_items)
        processed_hashes[file_hash] = processed_metadata(pdf_path, processed_at=processed_at)

    return all_items


def main():
    input_dir = Path('input')
    tracker_path = Path('.processed_files.json')
    processed_hashes = load_processed_hashes(tracker_path)
    image_paths, pdf_paths = discover_input_files(input_dir)
    if not image_paths and not pdf_paths:
        print(f"No supported image or PDF files found in: {input_dir}")
        raise SystemExit(1)

    all_items = process_pending_files(image_paths, pdf_paths, processed_hashes)

    try:
        save_processed_hashes(tracker_path, processed_hashes)
    except Exception as exc:
        print(f"Failed to update processed file tracker: {exc}")
        raise SystemExit(1)

    if all_items:
        print("\nExtracted Items:")
        for item in all_items:
            print(f"- {item['Item']} : ${item['Cost']}")
        try:
            save_to_excel(all_items)
        except Exception as exc:
            print(f"Failed to save Excel output: {exc}")
            raise SystemExit(1)
        print("\nSaved to 'output/All_Items.xlsx'")
    else:
        print('No items found.')


if __name__ == '__main__':
    main()
