import unittest

from scoring.items.services import ITEM
from tests.scoring.helpers import run, referencia


class ServicesTest(unittest.TestCase):
    def test_com_servicos(self):
        self.assertEqual(run(ITEM, referencia()).score, 100)

    def test_sem_servicos(self):
        p = referencia()
        p["location"]["services"] = []
        self.assertEqual(run(ITEM, p).score, 0)


if __name__ == "__main__":
    unittest.main()
