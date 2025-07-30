import pytesseract
from PIL import Image
import re
from datetime import datetime
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
        
        # Match lines like: Some Item Name        $12.00
        # match = re.search(r'(.+?)\s+\$?(\d+\.\d{2})$', line)
        match = re.search(r'(.+?)\s+\$?\s?(\d{1,4}\.\d{2})', line)
        if match:
            item = match.group(1).strip()
            cost = float(match.group(2))
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

    df.to_excel(output_path, index=False)

# === Example Usage ===
if __name__ == '__main__':
    image_path = 'data/temp_receipts/sample_receipt.jpg'  # Update path as needed
    text = extract_text_from_image(image_path)
    items = parse_items(text)
    
    if items:
        print("Extracted Items:")
        for item in items:
            print(f"- {item['Item']} : ${item['Cost']}")
        save_to_excel(items)
        print("\nSaved to 'All_Items.xlsx'")
    else:
        print("No items found.")
