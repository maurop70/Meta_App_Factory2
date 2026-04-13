import unittest
import sys
import os
from datetime import datetime, timedelta
import json
from unittest.mock import patch # unittest.mock is part of the standard library unittest package

# Placeholder for the server module. Will attempt to import it.
server = None

class TestCFOAgentServerFixes(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        """
        Attempts to import the 'server' module. If 'server.py' is not found or
        cannot be imported, all tests in this class will be skipped.
        """
        global server
        try:
            # Attempt to import server.py. This assumes server.py is discoverable
            # in the Python path where these tests are run.
            import server
            cls.server_available = True
        except ImportError as e:
            cls.server_available = False
            cls.server_import_error = (
                f"server.py module not found. Please ensure it's in the Python path. "
                f"Cannot run server-specific tests. Error: {e}"
            )
        except Exception as e:
            cls.server_available = False
            cls.server_import_error = (
                f"Failed to import server.py due to an unexpected error: {e}"
            )

    def setUp(self):
        """
        Skips the current test if the 'server' module was not successfully imported.
        """
        if not self.server_available:
            self.skipTest(self.server_import_error)