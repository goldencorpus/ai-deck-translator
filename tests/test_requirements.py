"""
Tests for the requirements.txt file.
"""

import unittest
import os
import re
import subprocess
import sys
import tempfile
import venv


class TestRequirements(unittest.TestCase):
    """Test cases for the requirements.txt file."""

    def setUp(self):
        """Set up test fixtures."""
        # Get the root directory of the project
        self.root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        self.requirements_file = os.path.join(self.root_dir, "requirements.txt")

        # Create a temporary directory for the virtual environment
        self.temp_dir = tempfile.mkdtemp()

        # Skip creating a virtual environment if running in CI
        if os.environ.get("CI"):
            self.venv_dir = None
            return

        # Create a virtual environment
        self.venv_dir = os.path.join(self.temp_dir, "venv")
        venv.create(self.venv_dir, with_pip=True)

        # Get the path to the Python executable in the virtual environment
        if sys.platform == "win32":
            self.python_exe = os.path.join(self.venv_dir, "Scripts", "python.exe")
        else:
            self.python_exe = os.path.join(self.venv_dir, "bin", "python")

    def tearDown(self):
        """Tear down test fixtures."""
        # Remove the temporary directory
        import shutil

        shutil.rmtree(self.temp_dir)

    def test_requirements_file_exists(self):
        """Test that requirements.txt exists."""
        self.assertTrue(os.path.exists(self.requirements_file))

    def test_requirements_file_format(self):
        """Test that requirements.txt has the correct format."""
        with open(self.requirements_file, "r") as f:
            requirements = f.readlines()

        # Check that each line is a valid requirement
        for line in requirements:
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            # Check that the line is in the format package==version or package>=version
            self.assertTrue(
                re.match(r"^[a-zA-Z0-9_\-\.]+[=~<>]+[0-9\.]+.*$", line),
                f"Invalid requirement format: {line}",
            )

    def test_requirements_installation(self):
        """Test that the requirements can be installed."""
        # Skip this test if running in CI environment
        if os.environ.get("CI") or not self.venv_dir:
            self.skipTest("Skipping installation test in CI environment")

        # Install the requirements
        result = subprocess.run(
            [self.python_exe, "-m", "pip", "install", "-r", self.requirements_file],
            capture_output=True,
            text=True,
        )
        self.assertEqual(
            result.returncode, 0, f"Failed to install requirements: {result.stderr}"
        )

    def test_required_packages(self):
        """Test that the required packages are in requirements.txt."""
        with open(self.requirements_file, "r") as f:
            requirements = f.read()

        # Check for essential packages
        essential_packages = [
            "google-api-python-client",
            "google-auth-oauthlib",
            "anthropic",
            "flask",
            "python-dotenv",
            "tqdm",
        ]

        for package in essential_packages:
            self.assertIn(
                package,
                requirements,
                f"Essential package {package} not found in requirements.txt",
            )


if __name__ == "__main__":
    unittest.main()
