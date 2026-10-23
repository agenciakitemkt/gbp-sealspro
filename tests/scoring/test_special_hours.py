import unittest

from scoring.items.special_hours import ITEM
from tests.scoring.helpers import run, referencia


def period(start, end):
    return {"start": start, "end": end, "closed": True}


class SpecialHoursTest(unittest.TestCase):
    def test_periodo_no_ano_corrente(self):
        self.assertEqual(run(ITEM, referencia()).score, 100)

    def test_so_outros_anos(self):
        p = referencia()
        p["location"]["specialHours"] = [period("2025-12-25", "2025-12-25"), period("2027-01-01", "2027-01-01")]
        self.assertEqual(run(ITEM, p).score, 0)

    def test_periodo_que_termina_no_ano_corrente(self):
        p = referencia()
        p["location"]["specialHours"] = [period("2025-12-30", "2026-01-02")]
        self.assertEqual(run(ITEM, p).score, 100)

    def test_sem_horario_especial(self):
        p = referencia()
        p["location"]["specialHours"] = []
        self.assertEqual(run(ITEM, p).score, 0)


if __name__ == "__main__":
    unittest.main()
