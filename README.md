# Auction Tracker

This tool extracts purchased items from auction invoices using Tesseract OCR and exports them into a structured Excel workbook. The parser is tuned to the invoice item table so header, shipping, and pickup text are less likely to leak into item descriptions.

## Features

- Tesseract OCR for printed auction invoices and receipts
- PDF support via Poppler and `pdf2image`
- Regex-based parsing for invoice table rows and multiline descriptions
- Lot number extraction from invoice rows
- Filters for totals, taxes, header text, shipping blocks, and summary rows
- Structured Excel output in `output/All_Items.xlsx`
- Automatic buyer-premium and total-cost calculation
- Processed-file tracking in `.processed_files.json`

## Supported Input Format

The parser currently supports invoice table rows such as:

```text
Lot# DESCRIPTION QUANTITY UNIT PRICE EXTENDED PRICE
17 Vases & Candle Holders 1 x 65.00 65.00 T
284 World War II Coffee Table Books
Jones and Summerville authors.
1 x 10.00 10.00 T
287 Coffee Table Books Militaria 1 x 5.00 5.00 T
```

That produces rows like:

| Date | Lot Number | Item | Cost | Buyer Premium (20%) | Total Cost | Selected for Listing |
| --- | --- | --- | --- | --- | --- | --- |
| 2026-03-20 | 17 | Vases & Candle Holders | 65.0 | 13.0 | 78.0 | N |
| 2026-03-20 | 284 | World War II Coffee Table Books Jones and Summerville authors. | 10.0 | 2.0 | 12.0 | N |

Notes:
- `Date` is the processing date.
- `Lot Number` is extracted from the leading table value when present.
- Supported file types are `.jpg`, `.jpeg`, `.png`, and `.pdf`, case-insensitive.
- Files are marked as processed even when OCR succeeds but no item rows match.
- Supported line formats include `qty x unit extended`, `qty unit extended`, simple `item price`, and multiline descriptions followed by pricing on the next line.

## How to Use

1. Place invoice files in `input/`.
2. Run `python3 main.py`.
3. Review `output/All_Items.xlsx`.

If you need to reprocess files, delete `.processed_files.json`.

## Requirements

- Python 3.8+
- Tesseract OCR installed and available on `PATH`
- Poppler installed for PDF support
- Python packages from `requirements.txt`

Install Python dependencies with:

```bash
pip install -r requirements.txt
```

## Install Notes

### Ubuntu / Debian

Install Tesseract:

```bash
sudo apt update
sudo apt install tesseract-ocr
```

Install Poppler:

```bash
sudo apt update
sudo apt install poppler-utils
```

Verify both tools:

```bash
tesseract --version
pdftoppm -h
```

### Windows

Install Tesseract from:
https://github.com/UB-Mannheim/tesseract/wiki

Install Poppler from:
https://github.com/oschwartz10612/poppler-windows/releases

Then verify both executables are on `PATH`.

## Filters Applied

The parser excludes lines containing:

- `Total Quantity`
- `Total Extended Price`
- `20% Buyer's Premium`
- `Tax1 Default`
- `Invoice Total`
- `Remaining Invoice Balance`

## Roadmap

- Add end-to-end validation with real sample invoices and expected outputs
- Improve output structure with per-run files, timestamps, or additional workbook tabs
- Add setup and runtime diagnostics for missing Tesseract and Poppler dependencies
- Google Sheets integration
- Upload UI
- eBay API integration

## License

MIT License. Use freely, modify, and share!

Author
Erick Perales — IT Architect, Cloud Migration Specialist
