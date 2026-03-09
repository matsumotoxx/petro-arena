import unittest
from unittest.mock import patch, MagicMock
from components.google_sheets_client import read_rows

class TestGoogleSheetsHeaders(unittest.TestCase):
    @patch("components.google_sheets_client.get_client")
    def test_duplicate_headers_fallback(self, mock_cli):
        ws = MagicMock()
        # Simulate get_all_records raising due to duplicate headers
        ws.get_all_records.side_effect = Exception("duplicate headers")
        ws.get_all_values.return_value = [
            ["username", "username", "id"],
            ["alice", "ALICE", "1"],
            ["bob", "BOB", "2"],
        ]
        sh = MagicMock()
        sh.worksheet.return_value = ws
        cli = MagicMock()
        cli.open_by_key.return_value = sh
        mock_cli.return_value = cli
        rows = read_rows("sheet", "users", header=True)
        self.assertEqual(rows[0]["username"], "alice")
        self.assertEqual(rows[0]["username_2"], "ALICE")
        self.assertEqual(rows[0]["id"], "1")

if __name__ == "__main__":
    unittest.main()
