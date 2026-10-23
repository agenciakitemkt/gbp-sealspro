import unittest

from scoring.items.logo import ITEM
from tests.scoring.helpers import media, run, referencia


class LogoTest(unittest.TestCase):
    def test_midia_profile_com_data_1970_conta(self):
        p = referencia()
        p["media"] = [media(category="PROFILE", created="1970-01-01T00:00:00Z")]
        self.assertEqual(run(ITEM, p).score, 100)

    def test_referencia(self):
        self.assertEqual(run(ITEM, referencia()).score, 100)

    def test_sem_profile(self):
        p = referencia()
        p["media"] = [m for m in p["media"] if m["category"] != "PROFILE"]
        self.assertEqual(run(ITEM, p).score, 0)


if __name__ == "__main__":
    unittest.main()
