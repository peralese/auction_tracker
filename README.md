# 🧾 Auction Tracker — OCR to Google Sheets MVP

This tool automates the process of extracting item purchases from auction receipts using Tesseract OCR and exports them into a structured Excel file (or Google Sheet, in future versions). It is designed to help you manage auction spending and prepare listings for resale platforms like eBay.

---

## 🚀 Features

- 🧠 Tesseract OCR for reading printed auction receipts
- 🔎 Regex-based parsing for extracting item names and prices
- ❌ Filters out totals, taxes, and non-item summary lines
- 💾 Outputs structured data to Excel file (`All_Items.xlsx`)
- 🧮 Auto-calculates 20% buyer premium and total cost
- 📅 Automatically timestamps the purchase date
- ✅ Ready for future Google Sheets & eBay API integration

---

## 🖼️ Example Receipt Format (OCR Input)

```
WWII German Helmet     $25.00  
WWII Uniform Jacket    $40.00  
Tax1 Default:          $5.00  
Invoice Total:         $75.00  
```

➡️ Output:

| Date       | Item                | Cost | Buyer Premium (20%) | Total Cost | Selected for Listing |
|------------|---------------------|------|----------------------|------------|-----------------------|
| 2025-07-29 | WWII German Helmet  | 25.0 | 5.0                  | 30.0       | N                     |
| 2025-07-29 | WWII Uniform Jacket | 40.0 | 8.0                  | 48.0       | N                     |

---

## 🧪 How to Use

1. **Place receipt image(s)** in:
   ```
   input/
   ```

2. **Run the script**:
   ```bash
   python main.py
   ```

3. **Check the output**:
   ```
   All_Items.xlsx
   ```

Notes:
- All `.jpg` files in `input/` are processed each run.

---

## 🛠️ Requirements

- Python 3.8+
- Tesseract-OCR (installed and added to PATH)
- Python packages:
  ```bash
  pip install pytesseract pillow pandas openpyxl
  ```

---

## 🧩 Install Notes (Tesseract OCR)

### Linux (Pop!_OS / Ubuntu)

```bash
sudo apt update
sudo apt install tesseract-ocr
```

Verify:

```bash
tesseract --version
```

### Windows

1. Download the installer from the official repo:  
   https://github.com/UB-Mannheim/tesseract/wiki
2. Install and add Tesseract to your PATH (the installer offers this option).
3. Verify in PowerShell:

```powershell
tesseract --version
```

---

## 🔧 Configuration

If Tesseract is not in your system `PATH`, set the path manually in `main.py`:

```python
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
```

---

## 🧼 Filters Applied

To ensure clean data extraction, the parser **excludes lines containing**:

- `Total Quantity`
- `Total Extended Price`
- `20% Buyer's Premium`
- `Tax1 Default`
- `Invoice Total`
- `Remaining Invoice Balance`

---

## 📌 Roadmap

- [ ] Google Sheets integration using `gspread`
- [ ] Flask UI for uploading receipts and managing listings
- [ ] eBay API integration to push listings
- [ ] Tagging support: category, condition, auction name
- [ ] PDF receipt support with `pdf2image`

---

## 📜 License

MIT License. Use freely, modify, and share!

## Author

Erick Perales  — IT Architect, Cloud Migration Specialist
