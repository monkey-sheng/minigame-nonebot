import sqlite3
from typing import Optional


class BlackjackDatabase:
    """
    Blackjack game related database operations
    The db has a table `blackjack`, with columns: `qq` TEXT PRIMARY KEY, `money` REAL
    """

    def __init__(self):
        self.conn = sqlite3.connect('blackjack.db')
        self.cursor = self.conn.cursor()

    def get_money(self, qq: str) -> Optional[int]:
        """:returns The amount of money the user with `qq` has, or None if not present in db"""
        query = '''SELECT money FROM blackjack WHERE qq=?'''
        self.cursor.execute(query, (qq,))
        result = self.cursor.fetchone()
        money = None
        if result:
            money = result[0]
        return money

    def set_money(self, qq: str, amount: int):
        """Set the money `amount` for the given `qq`"""
        query = '''UPDATE blackjack SET money=? WHERE qq=?'''
        self.cursor.execute(query, (amount, qq))
        self.conn.commit()

    def insert_new(self, qq: str, money: int):
        """Insert a new record for new user"""
        query = '''INSERT INTO blackjack VALUES (?, ?)'''
        try:
            self.cursor.execute(query, (qq, money))
            self.conn.commit()
        except sqlite3.Error as e:
            # this should never happen
            print(query, e)


DB = BlackjackDatabase()
