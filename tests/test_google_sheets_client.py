import unittest
from unittest.mock import patch, MagicMock
from components.google_sheets_client import update_row_by_key, delete_row_by_key

class TestGoogleSheetsClient(unittest.TestCase):
    @patch("components.google_sheets_client.get_client")
    def test_update_row_by_key(self, mock_cli):
        ws = MagicMock()
        ws.get_all_records.return_value = [
            {"id": 1, "username": "A"},
            {"id": 2, "username": "B"},
        ]
        sh = MagicMock()
        sh.worksheet.return_value = ws
        cli = MagicMock()
        cli.open_by_key.return_value = sh
        mock_cli.return_value = cli
        ok = update_row_by_key("sheet", "users", "id", 2, {"username": "BB"})
        self.assertTrue(ok)
        ws.update_cell.assert_called()

    @patch("components.google_sheets_client.get_client")
    def test_delete_row_by_key(self, mock_cli):
        ws = MagicMock()
        ws.get_all_records.return_value = [
            {"id": 10, "username": "X"},
            {"id": 11, "username": "Y"},
        ]
        sh = MagicMock()
        sh.worksheet.return_value = ws
        cli = MagicMock()
        cli.open_by_key.return_value = sh
        mock_cli.return_value = cli
        ok = delete_row_by_key("sheet", "users", "id", 11)
        self.assertTrue(ok)
        ws.delete_rows.assert_called()

if __name__ == "__main__":
    unittest.main()
