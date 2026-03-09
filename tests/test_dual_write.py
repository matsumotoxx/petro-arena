import unittest
from unittest.mock import patch, MagicMock
import database as db

class TestDualWrite(unittest.TestCase):
    @patch("database.sync_user_created")
    @patch("database.get_connection")
    def test_create_user_sync(self, mock_conn, mock_sync):
        conn = MagicMock()
        c = MagicMock()
        mock_conn.return_value = conn
        conn.cursor.return_value = c
        c.lastrowid = 1
        c.fetchone.return_value = (1, "alice", "a@x.com", "Jogador", 0, "2025-01-01 00:00:00")
        res = db.create_user("alice","a@x.com","pwd")
        self.assertTrue(res)
        self.assertTrue(mock_sync.called)

    @patch("database.check_promotion", return_value=None)
    @patch("database.sync_transaction")
    @patch("database.sync_user_balance")
    @patch("database.get_connection")
    def test_update_points_sync(self, mock_conn, mock_balance, mock_tx, _):
        conn = MagicMock()
        c = MagicMock()
        mock_conn.return_value = conn
        conn.cursor.return_value = c
        c.fetchone.side_effect = [
            (10,),           # current balance
            ("alice","a@x.com"),  # user info
            (1,1,"EARN",5,"bonus","2025-01-01 00:00:00"), # tx row
        ]
        c.lastrowid = 1
        db.update_points(1,5,"bonus","EARN",None)
        self.assertTrue(mock_balance.called)
        self.assertTrue(mock_tx.called)

if __name__ == "__main__":
    unittest.main()
