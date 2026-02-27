
import sys
import os
import unittest
from unittest.mock import MagicMock, patch
import json

# Add shared utils to path
SHARED_UTILS = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "utils"))
if SHARED_UTILS not in sys.path: sys.path.append(SHARED_UTILS)

from atomizer import Atomizer

class TestAtomizer(unittest.TestCase):
    def setUp(self):
        self.atomizer = Atomizer()

    @patch('bridge.call_app')
    def test_evaluate_complex(self, mock_call):
        # Mock response for a complex task
        mock_response = '["Task 1", "Task 2", "Task 3", "Task 4"]'
        mock_call.return_value = mock_response

        chunks = self.atomizer.evaluate("Complex Prompt")
        self.assertEqual(len(chunks), 4)
        self.assertEqual(chunks[0], "Task 1")

    @patch('bridge.call_app')
    def test_evaluate_simple(self, mock_call):
        # Mock response for a simple task
        mock_call.return_value = "[]"
        
        chunks = self.atomizer.evaluate("Simple Prompt")
        self.assertEqual(len(chunks), 0)

    def test_stitch(self):
        results = ["Result 1", "Result 2"]
        report = self.atomizer.stitch(results)
        self.assertIn("# ATOMIZER SYNTHESIS REPORT", report)
        self.assertIn("## Part 1", report)
        self.assertIn("Result 1", report)

if __name__ == '__main__':
    unittest.main()
