import unittest

from scoring.items.hours import ITEM
from tests.scoring.helpers import run, referencia


class HoursTest(unittest.TestCase):
    def test_com_horario(self):
        self.assertEqual(run(ITEM, referencia()).score, 100)

    def test_sem_horario(self):
        p = referencia()
        p["location"]["hours"] = {}
        self.assertEqual(run(ITEM, p).score, 0)


if __name__ == "__main__":
    unittest.main()
