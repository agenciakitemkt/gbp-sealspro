import unittest

from scoring.items.phone import ITEM
from tests.scoring.helpers import run, referencia


class PhoneTest(unittest.TestCase):
    def test_com_telefone(self):
        self.assertEqual(run(ITEM, referencia()).score, 100)

    def test_sem_telefone(self):
        for empty in ("", "   "):
            p = referencia()
            p["location"]["phone"] = empty
            self.assertEqual(run(ITEM, p).score, 0)


if __name__ == "__main__":
    unittest.main()
