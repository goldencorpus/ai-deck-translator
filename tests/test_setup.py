"""
Tests for the setup.py module.
"""
import unittest
import os
import sys
import subprocess
import tempfile
import shutil

class TestSetup(unittest.TestCase):
    """Test cases for the setup.py module."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Get the root directory of the project
        self.root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
        self.setup_py = os.path.join(self.root_dir, 'setup.py')
        
        # Create a temporary directory for installation
        self.temp_dir = tempfile.mkdtemp()
        self.old_cwd = os.getcwd()
        os.chdir(self.root_dir)
    
    def tearDown(self):
        """Tear down test fixtures."""
        # Restore the working directory
        os.chdir(self.old_cwd)
        
        # Remove the temporary directory
        shutil.rmtree(self.temp_dir)
    
    def test_setup_py_exists(self):
        """Test that setup.py exists."""
        self.assertTrue(os.path.exists(self.setup_py))
    
    def test_setup_py_syntax(self):
        """Test that setup.py has valid syntax."""
        # Check that setup.py can be imported without syntax errors
        result = subprocess.run(
            [sys.executable, '-m', 'py_compile', self.setup_py],
            capture_output=True,
            text=True
        )
        self.assertEqual(result.returncode, 0, f"setup.py has syntax errors: {result.stderr}")
    
    def test_setup_py_metadata(self):
        """Test that setup.py has the required metadata."""
        # Run setup.py with --name to get the package name
        result = subprocess.run(
            [sys.executable, self.setup_py, '--name'],
            capture_output=True,
            text=True
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn('gslides-translator', result.stdout.strip())
        
        # Run setup.py with --version to get the package version
        result = subprocess.run(
            [sys.executable, self.setup_py, '--version'],
            capture_output=True,
            text=True
        )
        self.assertEqual(result.returncode, 0)
        version = result.stdout.strip()
        self.assertTrue(len(version.split('.')) == 3, f"Version {version} is not in the format x.y.z")
    
    def test_setup_py_install(self):
        """Test that setup.py can install the package."""
        # Skip this test if running in CI environment
        if os.environ.get('CI'):
            self.skipTest("Skipping installation test in CI environment")
        
        # Install the package in development mode to a temporary directory
        result = subprocess.run(
            [
                sys.executable, '-m', 'pip', 'install', '-e', '.',
                '--target', self.temp_dir,
                '--no-deps'
            ],
            capture_output=True,
            text=True
        )
        self.assertEqual(result.returncode, 0, f"Failed to install package: {result.stderr}")
        
        # Check that the package was installed
        site_packages = os.path.join(self.temp_dir, 'gslides_translator')
        self.assertTrue(os.path.exists(site_packages), "Package was not installed correctly")

if __name__ == '__main__':
    unittest.main() 