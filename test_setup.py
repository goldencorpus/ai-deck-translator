import subprocess
import re


class TestSetupPyMetadata:
    def test_setup_py_metadata(self):
        """Test that setup.py has the required metadata."""
        # Run setup.py --name to get the package name
        result = subprocess.run(
            ["python3", "setup.py", "--name"],
            cwd=self.root_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        self.assertEqual(result.returncode, 0, "setup.py --name command failed")
        self.assertIn("ai_deck_translator", result.stdout.strip())

        # Run setup.py --version to get the version
        result = subprocess.run(
            ["python3", "setup.py", "--version"],
            cwd=self.root_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        self.assertEqual(result.returncode, 0, "setup.py --version command failed")
        # Check that version follows semantic versioning
        version = result.stdout.strip()
        self.assertRegex(
            version,
            r"^\d+\.\d+\.\d+",
            f"Version '{version}' does not follow semantic versioning",
        )

        # Run setup.py --classifiers to get classifiers
        result = subprocess.run(
            ["python3", "setup.py", "--classifiers"],
            cwd=self.root_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        self.assertEqual(result.returncode, 0, "setup.py --classifiers command failed")
        classifiers = result.stdout.strip().split("\n")

        # Check for required classifiers
        required_classifier_patterns = [
            r"Programming Language :: Python :: 3",
            r"License ::",
            r"Topic ::",
        ]

        for pattern in required_classifier_patterns:
            self.assertTrue(
                any(re.search(pattern, c) for c in classifiers),
                f"Required classifier pattern '{pattern}' not found in classifiers",
            )
