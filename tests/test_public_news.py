import unittest
from unittest.mock import patch

from tools.fetch_public_news_resilient import parse_bls_ics, fetch_bls, BLS_ICS


SAMPLE_ICS = b"""BEGIN:VCALENDAR\r\nVERSION:2.0\r\nBEGIN:VEVENT\r\nDTSTART:20261002T083000\r\nSUMMARY:Employment Situation for September 2026\r\nURL:https://www.bls.gov/news.release/empsit.nr0.htm\r\nEND:VEVENT\r\nBEGIN:VEVENT\r\nDTSTART:20261015T083000\r\nSUMMARY:Consumer Price Index for September 2026\r\nEND:VEVENT\r\nEND:VCALENDAR\r\n"""


class PublicNewsTests(unittest.TestCase):
    def test_parse_bls_ics(self):
        rows = parse_bls_ics(SAMPLE_ICS)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]['date'], '2026-10-02')
        self.assertIn('Employment Situation', rows[0]['title'])
        self.assertTrue(rows[0]['url'].startswith('https://www.bls.gov/'))

    @patch('tools.fetch_public_news_resilient.fetch_feed')
    @patch('tools.fetch_public_news_resilient.request')
    def test_bls_uses_calendar_when_rss_is_blocked(self, mock_request, mock_feed):
        mock_feed.return_value = {
            'status': 'error', 'provider': 'BLS', 'source_url': 'rss',
            'error': 'HTTPError: HTTP Error 403: Forbidden'
        }
        mock_request.return_value = SAMPLE_ICS
        result = fetch_bls()
        self.assertEqual(result['status'], 'ok')
        self.assertEqual(result['mode'], 'official_release_calendar_fallback')
        self.assertEqual(result['source_url'], BLS_ICS)
        self.assertEqual(len(result['entries']), 2)


if __name__ == '__main__':
    unittest.main()
