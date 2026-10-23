import unittest

from scoring.items.founding_date import ITEM
from tests.scoring.helpers import run, referencia


class FoundingDateTest(unittest.TestCase):
    def test_com_data(self):
        self.assertEqual(run(ITEM, referencia()).score, 100)

    def test_sem_data(self):
        p = referencia()
        p["location"]["openingDate"] = None
        self.assertEqual(run(ITEM, p).score, 0)


if __name__ == "__main__":
    unittest.main()
