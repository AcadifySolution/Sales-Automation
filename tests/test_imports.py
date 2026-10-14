"""Import regression tests; never run outbound sales workflows."""
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ImportTests(unittest.TestCase):
    def check_import(self, code):
        result = subprocess.run([sys.executable, "-c", code], cwd=ROOT,
                                capture_output=True, text=True, timeout=30, check=False)
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)

    def test_package_import(self):
        self.check_import("from engine import followup_engine, pipeline; "
                          "assert followup_engine.is_valid_email is pipeline.is_valid_email")

    def test_script_import(self):
        self.check_import("import sys, runpy; sys.path.insert(0, 'engine'); "
                          "runpy.run_path('engine/followup_engine.py', run_name='import_check')")
