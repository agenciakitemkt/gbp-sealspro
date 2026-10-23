import unittest

from scoring.items.website import ITEM
from tests.scoring.helpers import run, referencia


class WebsiteTest(unittest.TestCase):
    def test_com_site(self):
        self.assertEqual(run(ITEM, referencia()).score, 100)

    def test_sem_site(self):
        p = referencia()
        p["location"]["website"] = ""
        self.assertEqual(run(ITEM, p).score, 0)


if __name__ == "__main__":
    unittest.main()
