import unittest
from docrecon.normalization import normalize_phone, name_similarity, address_similarity, normalize_reference

class NormalizationTests(unittest.TestCase):
    def test_phone_nigeria(self):
        self.assertEqual(normalize_phone("0803 061 2844"), "2348030612844")
        self.assertEqual(normalize_phone("+2348030612844"), "2348030612844")

    def test_name_reordered(self):
        self.assertGreaterEqual(name_similarity("John Smith", "Smith John"), 95)

    def test_address_formatting(self):
        self.assertGreaterEqual(address_similarity("12 Allen Avenue, Ikeja Lagos", "12 Allen Ave Ikeja, Lagos State"), 85)

    def test_reference(self):
        self.assertEqual(normalize_reference("demo-123 abc"), "DEMO123ABC")

if __name__ == "__main__":
    unittest.main()
