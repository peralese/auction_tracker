# Auction Tracker

This tool extracts purchased items from auction invoices using Tesseract OCR and exports them into a structured Excel workbook. The current parser is tuned for invoice-style line items that include quantity, unit price, and extended price.

## Features

- Tesseract OCR for printed auction invoices and receipts
- PDF support via Poppler and `pdf2image`
- Regex-based parsing for auction invoice lines
- Filters for totals, taxes, and summary rows
- Structured Excel output in `output/All_Items.xlsx`
- Automatic buyer-premium and total-cost calculation
- Processed-file tracking in `.processed_files.json`

## Supported Input Format

The parser currently expects invoice lines similar to this OCR output:

```text
363 WWII German Helmet 1 x 25.00 25.00 T
364 WWII Uniform Jacket 1 x 40.00 40.00 T
Tax1 Default 13.00
Invoice Total 78.00
```

That produces rows like:

| Date | Item | Cost | Buyer Premium (20%) | Total Cost | Selected for Listing |
| --- | --- | --- | --- | --- | --- |
| 2026-03-20 | WWII German Helmet | 25.0 | 5.0 | 30.0 | N |
| 2026-03-20 | WWII Uniform Jacket | 40.0 | 8.0 | 48.0 | N |

Notes:
- The `Date` column is the processing date, not the invoice date.
- Supported file types are `.jpg`, `.jpeg`, `.png`, and `.pdf`, case-insensitive.
- Files are marked as processed even when OCR succeeds but no item rows match.

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

- Improve parser coverage for more OCR and invoice layout variations
- Extract richer invoice metadata such as invoice date, invoice number, and auction details
- Add end-to-end validation with real sample invoices and expected outputs
- Improve output structure with per-run files, timestamps, or additional workbook tabs
- Add setup and runtime diagnostics for missing Tesseract and Poppler dependencies
- Google Sheets integration
- Upload UI
- eBay API integration

## License

MIT
