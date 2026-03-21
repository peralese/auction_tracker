import hashlib
import json
import re
from datetime import datetime

DATE_PATTERNS = [
    re.compile(r'\bdate\s*[:#-]?\s*(?P<date>\d{1,2}/\d{1,2}/\d{2,4})\b', re.IGNORECASE),
    re.compile(r'\b(?P<date>\d{1,2}/\d{1,2}/\d{2,4})\b'),
]
DATE_FORMATS = ['%m/%d/%Y', '%m/%d/%y']

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
AMOUNT_PATTERN = r'\$?(?:[0-9]{1,3}(?:,[0-9]{3})*|[0-9]{1,6})\.\d{2}'
LINE_ITEM_PATTERNS = [
    re.compile(
        rf'^(?:(?P<lot>\d+)\s+)?(?P<item>.+?)\s+(?P<qty>\d+)\s*(?:[xX]|×)\s*(?P<unit>{AMOUNT_PATTERN})\s+(?P<extended>{AMOUNT_PATTERN})(?:\s+[A-Z]+)?$'
    ),
    re.compile(
        rf'^(?:(?P<lot>\d+)\s+)?(?P<item>.+?)\s+(?P<qty>\d+)\s+(?P<unit>{AMOUNT_PATTERN})\s+(?P<extended>{AMOUNT_PATTERN})(?:\s+[A-Z]+)?$'
    ),
    re.compile(
        rf'^(?:(?P<lot>\d+)\s+)?(?P<item>[A-Za-z].*?)\s+(?P<extended>{AMOUNT_PATTERN})(?:\s+[A-Z]+)?$'
    ),
]
PRICING_ONLY_PATTERNS = [
    re.compile(
        rf'^(?P<qty>\d+)\s*(?:[xX]|×)\s*(?P<unit>{AMOUNT_PATTERN})\s+(?P<extended>{AMOUNT_PATTERN})(?:\s+[A-Z]+)?$'
    ),
    re.compile(
        rf'^(?P<qty>\d+)\s+(?P<unit>{AMOUNT_PATTERN})\s+(?P<extended>{AMOUNT_PATTERN})(?:\s+[A-Z]+)?$'
    ),
    re.compile(rf'^(?P<extended>{AMOUNT_PATTERN})(?:\s+[A-Z]+)?$'),
]
TABLE_END_SUBSTRINGS = [
    'total quantity',
    'total extended price',
    "buyer's premium",
    'remaining invoice balance',
    'premium is',
    'refunds will not be given',
    'all sales are final',
    'double check order',
]
NON_ITEM_SUBSTRINGS = [
    'http://',
    'https://',
    'ship to',
    'sold to',
    'invoice #',
    'invoice#',
    'page:',
    'date:',
    'pickup',
    'questions:',
    'auction sale',
    'upper right corner',
    'unpaid',
    'lot#',
    'unit price',
    'extended price',
]


def preprocess_pil(image):
    gray = ImageOps.grayscale(image)
    enhanced = gray.point(lambda x: 0 if x < 140 else 255, '1')
    return enhanced


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


def normalize_line(line):
    return re.sub(r'\s+', ' ', line.replace('×', 'x')).strip()


def parse_amount(value):
    return float(value.replace('$', '').replace(',', ''))


def format_invoice_date(value):
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(value, fmt).strftime('%Y-%m-%d')
        except ValueError:
            continue
    return None


def extract_invoice_date(text):
    for pattern in DATE_PATTERNS:
        match = pattern.search(text)
        if not match:
            continue
        formatted = format_invoice_date(match.group('date'))
        if formatted:
            return formatted
    return None


def build_item(item, extended, processed_at=None, lot_number=None, invoice_date=None):
    processed_at = processed_at or datetime.today()
    item_date = invoice_date or processed_at.strftime('%Y-%m-%d')
    return {
        'Date': item_date,
        'Lot Number': lot_number,
        'Item': item,
        'Cost': extended,
        'Buyer Premium (20%)': round(extended * 0.20, 2),
        'Total Cost': round(extended * 1.20, 2),
        'Selected for Listing': 'N'
    }


def extract_item_from_line(line, processed_at=None, invoice_date=None):
    for pattern in LINE_ITEM_PATTERNS:
        match = pattern.search(line)
        if not match:
            continue
        item = match.group('item').strip(' -:')
        if not item:
            return None
        lot_number = match.groupdict().get('lot')
        return build_item(
            item,
            parse_amount(match.group('extended')),
            processed_at=processed_at,
            lot_number=lot_number,
            invoice_date=invoice_date,
        )
    return None


def extract_item_from_pending(pending_description, line, processed_at=None, invoice_date=None):
    if not pending_description:
        return None

    combined_line = f"{pending_description} {line}".strip()
    direct_match = extract_item_from_line(combined_line, processed_at=processed_at, invoice_date=invoice_date)
    if direct_match:
        return direct_match

    for pattern in PRICING_ONLY_PATTERNS:
        match = pattern.search(line)
        if not match:
            continue
        lot_match = re.match(r'^(?P<lot>\d+)\s+(?P<item>.+)$', pending_description)
        lot_number = lot_match.group('lot') if lot_match else None
        item_description = lot_match.group('item') if lot_match else pending_description
        return build_item(
            item_description.strip(' -:'),
            parse_amount(match.group('extended')),
            processed_at=processed_at,
            lot_number=lot_number,
            invoice_date=invoice_date,
        )
    return None


def looks_like_description_fragment(line):
    if re.search(AMOUNT_PATTERN, line):
        return False
    return bool(re.search(r'[A-Za-z]', line))


def starts_with_lot_number(line):
    return bool(re.match(r'^\d+\s+', line))


def is_non_item_line(line):
    lowered = line.lower()
    if any(keyword.lower() in lowered for keyword in EXCLUDE_KEYWORDS):
        return True
    if any(fragment in lowered for fragment in NON_ITEM_SUBSTRINGS):
        return True
    if re.search(r'https?://|\S+@\S+', line):
        return True
    if lowered.startswith('invoice ') or lowered.startswith('page ') or lowered.startswith('date '):
        return True
    return False


def relevant_text_lines(text):
    normalized_lines = [normalize_line(line) for line in text.splitlines()]

    table_start = None
    for index, line in enumerate(normalized_lines):
        lowered = line.lower()
        if 'lot#' in lowered and 'description' in lowered:
            table_start = index + 1
            break

    if table_start is not None:
        table_lines = []
        for line in normalized_lines[table_start:]:
            lowered = line.lower()
            if any(fragment in lowered for fragment in TABLE_END_SUBSTRINGS):
                break
            table_lines.append(line)
        return table_lines
    return normalized_lines


def parse_items(text, processed_at=None, invoice_date=None):
    parsed_items = []
    pending_description = None

    for line in relevant_text_lines(text):
        if not line or is_non_item_line(line):
            pending_description = None
            continue

        item = extract_item_from_pending(pending_description, line, processed_at=processed_at, invoice_date=invoice_date)
        if item:
            parsed_items.append(item)
            pending_description = None
            continue

        item = extract_item_from_line(line, processed_at=processed_at, invoice_date=invoice_date)
        if item:
            parsed_items.append(item)
            pending_description = None
            continue

        if looks_like_description_fragment(line):
            if pending_description:
                pending_description = f"{pending_description} {line}".strip()
            elif parsed_items and not starts_with_lot_number(line):
                parsed_items[-1]['Item'] = f"{parsed_items[-1]['Item']} {line}".strip()
            else:
                pending_description = line
        else:
            pending_description = None

    return parsed_items


def build_output_paths(output_dir, run_timestamp=None):
    output_dir = Path(output_dir)
    run_timestamp = run_timestamp or datetime.now()
    timestamp_label = run_timestamp.strftime('%Y%m%d_%H%M%S')
    runs_dir = output_dir / 'runs'
    return {
        'output_dir': output_dir,
        'runs_dir': runs_dir,
        'master_path': output_dir / 'All_Items.xlsx',
        'run_path': runs_dir / f'Auction_Items_{timestamp_label}.xlsx',
        'timestamp_label': timestamp_label,
    }


def build_run_summary(parsed_items, run_timestamp):
    subtotal = round(sum(item['Cost'] for item in parsed_items), 2)
    premium_total = round(sum(item['Buyer Premium (20%)'] for item in parsed_items), 2)
    grand_total = round(sum(item['Total Cost'] for item in parsed_items), 2)
    distinct_lots = len({item['Lot Number'] for item in parsed_items if item.get('Lot Number')})
    return pd.DataFrame([
        {
            'Run Timestamp': run_timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            'Items Extracted': len(parsed_items),
            'Distinct Lots': distinct_lots,
            'Subtotal Cost': subtotal,
            'Buyer Premium Total': premium_total,
            'Grand Total': grand_total,
        }
    ])


def save_to_excel(parsed_items, output_dir=Path('output'), run_timestamp=None):
    paths = build_output_paths(output_dir, run_timestamp=run_timestamp)
    paths['output_dir'].mkdir(parents=True, exist_ok=True)
    paths['runs_dir'].mkdir(parents=True, exist_ok=True)

    run_timestamp = run_timestamp or datetime.now()
    run_df = pd.DataFrame(parsed_items)
    summary_df = build_run_summary(parsed_items, run_timestamp)

    try:
        existing = pd.read_excel(paths['master_path'])
        master_df = pd.concat([existing, run_df], ignore_index=True)
    except FileNotFoundError:
        master_df = run_df
    except Exception as exc:
        raise RuntimeError(f"Failed to read existing Excel file: {paths['master_path']}") from exc

    with pd.ExcelWriter(paths['master_path'], engine='openpyxl') as writer:
        master_df.to_excel(writer, sheet_name='All Items', index=False)

    with pd.ExcelWriter(paths['run_path'], engine='openpyxl') as writer:
        run_df.to_excel(writer, sheet_name='Items', index=False)
        summary_df.to_excel(writer, sheet_name='Run Summary', index=False)

    return paths


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
    invoice_date = extract_invoice_date(text)
    return parse_items(text, processed_at=processed_at, invoice_date=invoice_date)


def process_pdf_file(pdf_path, processed_at=None):
    pages = convert_from_path(str(pdf_path))
    if not pages:
        return []

    page_texts = [extract_text_from_pil(page) for page in pages]
    invoice_date = extract_invoice_date('\n'.join(page_texts))

    all_items = []
    for text in page_texts:
        all_items.extend(parse_items(text, processed_at=processed_at, invoice_date=invoice_date))
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

            invoice_date = extract_invoice_date(text)
            items = parse_items(text, processed_at=processed_at, invoice_date=invoice_date)
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
