import unittest

from tools.fetch_public_sources import parse_g17, parse_sloos_csv


class PublicSourceParserTests(unittest.TestCase):
    def test_g17_total_ip_parser(self):
        raw='''"B50001: Total index"\n"B50001" 2025 100.0 101.0 102.0 . NA 103.0\n'''
        rows=parse_g17(raw)
        self.assertEqual(rows[0],['2025-01',100.0])
        self.assertEqual(rows[-1],['2025-06',103.0])
        self.assertEqual(len(rows),4)

    def test_g17_rejects_wrong_file(self):
        with self.assertRaises(ValueError):
            parse_g17('not a g17 file')

    def test_sloos_parser_keeps_quarterly_observations(self):
        raw='''Series Description,"Large firms","Small firms"\nUnique Identifier,"SLOOS/SLOOS/SUBLPDCILS_N.Q","SLOOS/SLOOS/SUBLPDCISS_N.Q"\nTime Period,"SUBLPDCILS_N.Q","SUBLPDCISS_N.Q"\n2026Q1,5.3,7.1\n2026Q2,8.1,9.4\n2026Q3,0.0,1.2\n'''
        series=parse_sloos_csv(raw)
        self.assertEqual(series['SUBLPDCILS_N.Q']['observations'][-1],['2026Q3',0.0])
        self.assertEqual(series['SUBLPDCISS_N.Q']['name'],'Small firms')

    def test_sloos_rejects_unidentified_csv(self):
        with self.assertRaises(ValueError):
            parse_sloos_csv('date,value\n2026Q1,5.0\n')


if __name__=='__main__':
    unittest.main()
