import unittest

from scoring.items.cover import ITEM
from tests.scoring.helpers import run, referencia


class CoverTest(unittest.TestCase):
    def test_com_capa(self):
        self.assertEqual(run(ITEM, referencia()).score, 100)

    def test_sem_capa(self):
        p = referencia()
        p["media"] = [m for m in p["media"] if m["category"] != "COVER"]
        self.assertEqual(run(ITEM, p).score, 0)


if __name__ == "__main__":
    unittest.main()
