import pytesseract
from PIL import Image
import re
from datetime import datetime
from pathlib import Path
import pandas as pd
from PIL import ImageOps

# === Step 1: Preprocess the image ===

def preprocess_image(image_path):
    image = Image.open(image_path)
    gray = ImageOps.grayscale(image)
    enhanced = gray.point(lambda x: 0 if x < 140 else 255, '1')  # Simple threshold
    return enhanced


# === Step 2: Load and OCR the image ===
def extract_text_from_image(image_path):
    image = preprocess_image(image_path)
    text = pytesseract.image_to_string(image)
    return text

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
        
        # Match lines like: Some Item Name        $12.00 (price anchored at end)
        match = re.search(r'^(.+?)\s+\$?\s*([0-9]{1,3}(?:,[0-9]{3})*|[0-9]{1,6})\.(\d{2})\s*$', line)
        if match:
            item = match.group(1).strip()
            cost = float(f"{match.group(2).replace(',', '')}.{match.group(3)}")
            parsed_items.append({
                'Date': datetime.today().strftime('%Y-%m-%d'),
                'Item': item,
                'Cost': cost,
                'Buyer Premium (20%)': round(cost * 0.20, 2),
                'Total Cost': round(cost * 1.20, 2),
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
    image_paths = sorted(input_dir.glob('*.jpg'))
    if not image_paths:
        print(f"No .jpg files found in: {input_dir}")
        raise SystemExit(1)

    all_items = []
    for image_path in image_paths:
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
    else:
        print("No items found.")
