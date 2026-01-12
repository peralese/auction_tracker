import pytesseract
from PIL import Image
import re
from datetime import datetime
from pathlib import Path
import pandas as pd
from PIL import ImageOps
from pdf2image import convert_from_path
import hashlib
import json

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

# === Step 3: Parse item lines ===
def parse_items(text):
    exclude_keywords = [
        "Total Quantity", "Total Extended Price", "20% Buyer's Premium",
        "Tax1 Default", "Invoice Total", "Remaining Invoice Balance"
    ]

    lines = text.split('\n')
    parsed_items = []
    for line in lines:
        line = line.strip()
        # Skip empty lines or summary rows
        if not line or any(keyword.lower() in line.lower() for keyword in exclude_keywords):
            continue
        
        # Match invoice line items that include lot/description and unit/extended prices.
        # Example: "363 Description ... 1 x 12.00 12.00 T"
        match = re.search(
            r'^(?:\d+\s+)?(.+?)\s+\d+\s*x\s*([0-9]{1,3}(?:,[0-9]{3})*|[0-9]{1,6})\.(\d{2})\s+([0-9]{1,3}(?:,[0-9]{3})*|[0-9]{1,6})\.(\d{2})\b',
            line,
        )
        if match:
            item = match.group(1).strip()
            extended = float(f"{match.group(4).replace(',', '')}.{match.group(5)}")
            parsed_items.append({
                'Date': datetime.today().strftime('%Y-%m-%d'),
                'Item': item,
                'Cost': extended,
                'Buyer Premium (20%)': round(extended * 0.20, 2),
                'Total Cost': round(extended * 1.20, 2),
                'Selected for Listing': 'N'
            })
    return parsed_items


# === Step 4: Save to Excel ===
def save_to_excel(parsed_items, output_path='All_Items.xlsx'):
    df = pd.DataFrame(parsed_items)
    try:
        existing = pd.read_excel(output_path)
        df = pd.concat([existing, df], ignore_index=True)
    except FileNotFoundError:
        pass  # file doesn't exist yet
    except Exception as exc:
        raise RuntimeError(f"Failed to read existing Excel file: {output_path}") from exc

    df.to_excel(output_path, index=False)

# === Example Usage ===
if __name__ == '__main__':
    input_dir = Path('input')
    tracker_path = Path('.processed_files.json')
    processed_hashes = load_processed_hashes(tracker_path)
    image_paths = sorted(input_dir.glob('*.jpg'))
    pdf_paths = sorted(input_dir.glob('*.pdf'))
    if not image_paths and not pdf_paths:
        print(f"No .jpg or .pdf files found in: {input_dir}")
        raise SystemExit(1)

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

        try:
            text = extract_text_from_image(str(image_path))
        except FileNotFoundError:
            print(f"Receipt image not found: {image_path}")
            raise SystemExit(1)
        except Exception as exc:
            print(f"Failed to OCR receipt image '{image_path}': {exc}")
            raise SystemExit(1)

        items = parse_items(text)
        all_items.extend(items)
        if items:
            print(f"Extracted {len(items)} items from {image_path}")
        else:
            print(f"No items found in {image_path}")
        processed_hashes[file_hash] = {
            'path': str(image_path),
            'processed_at': datetime.now().isoformat(timespec='seconds'),
        }

    for pdf_path in pdf_paths:
        try:
            file_hash = sha256_file(pdf_path)
        except Exception as exc:
            print(f"Failed to hash file '{pdf_path}': {exc}")
            raise SystemExit(1)

        if file_hash in processed_hashes:
            print(f"Skipping already processed file: {pdf_path}")
            continue

        try:
            pages = convert_from_path(str(pdf_path))
        except Exception as exc:
            print(f"Failed to convert PDF '{pdf_path}': {exc}")
            raise SystemExit(1)

        if not pages:
            print(f"No pages found in {pdf_path}")
            continue

        for page_index, page in enumerate(pages, start=1):
            try:
                text = extract_text_from_pil(page)
            except Exception as exc:
                print(f"Failed to OCR '{pdf_path}' page {page_index}: {exc}")
                raise SystemExit(1)

            items = parse_items(text)
            all_items.extend(items)
            if items:
                print(f"Extracted {len(items)} items from {pdf_path} page {page_index}")
            else:
                print(f"No items found in {pdf_path} page {page_index}")
        processed_hashes[file_hash] = {
            'path': str(pdf_path),
            'processed_at': datetime.now().isoformat(timespec='seconds'),
        }

    if all_items:
        print("\nExtracted Items:")
        for item in all_items:
            print(f"- {item['Item']} : ${item['Cost']}")
        try:
            save_to_excel(all_items)
        except Exception as exc:
            print(f"Failed to save Excel output: {exc}")
            raise SystemExit(1)
        print("\nSaved to 'All_Items.xlsx'")
        try:
            save_processed_hashes(tracker_path, processed_hashes)
        except Exception as exc:
            print(f"Failed to update processed file tracker: {exc}")
            raise SystemExit(1)
    else:
        print("No items found.")
