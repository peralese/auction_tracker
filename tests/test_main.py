import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pandas as pd

import main


class ParseItemsTests(unittest.TestCase):
    def test_parses_invoice_line_with_lot_number(self):
        processed_at = datetime(2026, 3, 20, 14, 30)
        items = main.parse_items(
            '363 Description of Item 1 x 12.00 12.00 T',
            processed_at=processed_at,
        )

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]['Date'], '2026-03-20')
        self.assertEqual(items[0]['Lot Number'], '363')
        self.assertEqual(items[0]['Item'], 'Description of Item')
        self.assertEqual(items[0]['Cost'], 12.0)
        self.assertEqual(items[0]['Buyer Premium (20%)'], 2.4)
        self.assertEqual(items[0]['Total Cost'], 14.4)

    def test_excludes_summary_lines(self):
        items = main.parse_items('Invoice Total 78.00\nTax1 Default 13.00')
        self.assertEqual(items, [])

    def test_handles_ocr_spacing_and_commas(self):
        items = main.parse_items('363   Vintage Lamp    1 x 1,200.00   1,200.00 T')
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]['Lot Number'], '363')
        self.assertEqual(items[0]['Item'], 'Vintage Lamp')
        self.assertEqual(items[0]['Cost'], 1200.0)

    def test_handles_simple_item_price_format(self):
        items = main.parse_items('WWII German Helmet $25.00')
        self.assertEqual(len(items), 1)
        self.assertIsNone(items[0]['Lot Number'])
        self.assertEqual(items[0]['Item'], 'WWII German Helmet')
        self.assertEqual(items[0]['Cost'], 25.0)

    def test_handles_missing_x_between_qty_and_prices(self):
        items = main.parse_items('364 Uniform Jacket 2 20.00 40.00 T')
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]['Lot Number'], '364')
        self.assertEqual(items[0]['Item'], 'Uniform Jacket')
        self.assertEqual(items[0]['Cost'], 40.0)

    def test_handles_split_description_and_pricing_lines(self):
        items = main.parse_items('284 World War II Coffee Table Books\nJones and Summerville authors.\n1 x 10.00 10.00 T')
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]['Lot Number'], '284')
        self.assertEqual(items[0]['Item'], 'World War II Coffee Table Books Jones and Summerville authors.')
        self.assertEqual(items[0]['Cost'], 10.0)

    def test_appends_continuation_line_to_previous_priced_row(self):
        items = main.parse_items(
            '17 Vases & Candle Holders 1 x 65.00 65.00 T\n'
            '284 World War II Coffee Table Books 1 x 10.00 10.00 T\n'
            'Jones and Summerville authors.\n'
            '287 Coffee Table Books Militaria 1 x 5.00 5.00 T'
        )
        self.assertEqual(
            [(item['Lot Number'], item['Item'], item['Cost']) for item in items],
            [
                ('17', 'Vases & Candle Holders', 65.0),
                ('284', 'World War II Coffee Table Books Jones and Summerville authors.', 10.0),
                ('287', 'Coffee Table Books Militaria', 5.0),
            ],
        )

    def test_uses_invoice_date_when_present(self):
        items = main.parse_items(
            'Invoice #: 91302\nDate: 3/20/2026\nLot# DESCRIPTION\n404 Socket Bayonet 1 x 50.00 50.00 T',
            processed_at=datetime(2026, 3, 21, 8, 0, 0),
            invoice_date='2026-03-20',
        )
        self.assertEqual(items[0]['Date'], '2026-03-20')

    def test_stops_before_footer_text(self):
        sample_text = """Date: 3/20/2026
Lot# DESCRIPTION QUANTITY UNIT PRICE EXTENDED PRICE
663 Scarce 1967 Snoopy and His Friends: The Royal
Guardsmen LP RECORD 1 x 6.00 6.00 T
PREMIUM IS 20% USING CURRENCY PAY 16% CASH ALL SALES ARE FINAL
"""
        items = main.parse_items(sample_text, invoice_date='2026-03-20')
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]['Date'], '2026-03-20')
        self.assertEqual(items[0]['Lot Number'], '663')
        self.assertEqual(items[0]['Item'], 'Scarce 1967 Snoopy and His Friends: The Royal Guardsmen LP RECORD')

    def test_parses_table_section_without_header_noise(self):
        sample_text = """On Site Pickup by scheduled appointment time Only. Scheduling through the link on your invoice:
https://visibook.com/example
On Site Pickup Location:
6307 Tremont St.
Dallas, TX, 75214
Invoice #: 179542
Date: 3/17/2026
# 7222
SHIP TO:
Erick Perales
Lot# DESCRIPTION QUANTITY UNIT PRICE EXTENDED PRICE
17 Vases & Candle Holders 1 x 65.00 65.00 T
284 World War II Coffee Table Books
Jones and Summerville authors.
1 x 10.00 10.00 T
287 Coffee Table Books Militaria 1 x 5.00 5.00 T
Total Quantity: 3.00
"""
        items = main.parse_items(sample_text)

        self.assertEqual(
            [(item['Lot Number'], item['Item'], item['Cost']) for item in items],
            [
                ('17', 'Vases & Candle Holders', 65.0),
                ('284', 'World War II Coffee Table Books Jones and Summerville authors.', 10.0),
                ('287', 'Coffee Table Books Militaria', 5.0),
            ],
        )


class DiscoveryTests(unittest.TestCase):
    def test_discovers_supported_extensions_case_insensitively(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            for name in ['invoice.JPG', 'scan.jpeg', 'photo.PnG', 'statement.PDF', 'notes.txt']:
                (root / name).write_text('x', encoding='utf-8')

            image_paths, pdf_paths = main.discover_input_files(root)

            self.assertEqual([path.name for path in image_paths], ['invoice.JPG', 'photo.PnG', 'scan.jpeg'])
            self.assertEqual([path.name for path in pdf_paths], ['statement.PDF'])


class WorkflowTests(unittest.TestCase):
    def test_process_pending_files_marks_unmatched_image_as_processed(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            image_path = Path(tmpdir) / 'invoice.jpg'
            image_path.write_bytes(b'image-bytes')
            processed_hashes = {}

            with patch('main.sha256_file', return_value='hash-1'), patch('main.process_image_file', return_value=[]):
                items = main.process_pending_files([image_path], [], processed_hashes)

            self.assertEqual(items, [])
            self.assertIn('hash-1', processed_hashes)
            self.assertEqual(processed_hashes['hash-1']['path'], str(image_path))

    def test_process_pdf_file_combines_pages(self):
        processed_at = datetime(2026, 3, 20, 14, 30)
        with patch('main.convert_from_path', return_value=['page-1', 'page-2']), patch(
            'main.extract_text_from_pil',
            side_effect=[
                'Lot# DESCRIPTION\n17 First Item 1 x 12.00 12.00 T',
                '284 Second Item\n1 x 15.00 15.00 T',
            ],
        ):
            items = main.process_pdf_file(Path('input/Invoice_179542.pdf'), processed_at=processed_at)

        self.assertEqual(
            [(item['Lot Number'], item['Item']) for item in items],
            [('17', 'First Item'), ('284', 'Second Item')],
        )

    def test_save_to_excel_creates_master_and_run_workbooks(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / 'output'
            run_timestamp = datetime(2026, 3, 21, 9, 45, 30)
            items = [
                {
                    'Date': '2026-03-21',
                    'Lot Number': '17',
                    'Item': 'Vases & Candle Holders',
                    'Cost': 65.0,
                    'Buyer Premium (20%)': 13.0,
                    'Total Cost': 78.0,
                    'Selected for Listing': 'N',
                }
            ]

            paths = main.save_to_excel(items, output_dir=output_dir, run_timestamp=run_timestamp)

            self.assertTrue(paths['master_path'].exists())
            self.assertTrue(paths['run_path'].exists())

            master_book = pd.ExcelFile(paths['master_path'])
            run_book = pd.ExcelFile(paths['run_path'])
            self.assertEqual(master_book.sheet_names, ['All Items'])
            self.assertEqual(run_book.sheet_names, ['Items', 'Run Summary'])

            master_df = pd.read_excel(paths['master_path'], sheet_name='All Items')
            run_df = pd.read_excel(paths['run_path'], sheet_name='Items')
            summary_df = pd.read_excel(paths['run_path'], sheet_name='Run Summary')

            self.assertEqual(len(master_df), 1)
            self.assertEqual(len(run_df), 1)
            self.assertEqual(summary_df.loc[0, 'Items Extracted'], 1)
            self.assertEqual(summary_df.loc[0, 'Grand Total'], 78.0)

    def test_save_and_load_processed_hashes_round_trip(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker_path = Path(tmpdir) / '.processed_files.json'
            payload = {'hash-1': {'path': 'input/invoice.pdf', 'processed_at': '2026-03-20T10:00:00'}}

            main.save_processed_hashes(tracker_path, payload)
            loaded = main.load_processed_hashes(tracker_path)

            self.assertEqual(loaded, payload)
            self.assertEqual(json.loads(tracker_path.read_text(encoding='utf-8')), payload)


if __name__ == '__main__':
    unittest.main()
