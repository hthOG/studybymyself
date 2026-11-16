"""Default planning range and explicit user-count semantics."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import book


class VolumeCountTests(unittest.TestCase):
    def test_default_range(self):
        for count in (2, 3, 4):
            self.assertEqual(book.volume_count_errors(count), [])
        for count in (0, 1, 5, 100, True, 2.5, '5'):
            self.assertTrue(book.volume_count_errors(count))

    def test_user_can_request_any_positive_count(self):
        for count in (1, 2, 5, 100):
            self.assertEqual(book.volume_count_errors(count, {'count': count, 'evidence': f'User: {count} volumes'}), [])

    def test_user_count_is_exact_and_needs_a_record(self):
        for request in ({'count': 5, 'evidence': 'User: five'}, {}, True,
                        {'count': 2}, {'count': 2, 'evidence': ' '},
                        {'count': 0, 'evidence': 'User'}, {'count': True, 'evidence': 'User'},
                        {'count': 2, 'evidence': []}):
            self.assertTrue(book.volume_count_errors(2, request))


if __name__ == '__main__':
    unittest.main()
