#!/usr/bin/env python3
"""
Script to run all tests with the proper environment variables set.
"""
import os
import sys
import unittest


def main():
    """Run all tests with the proper environment variables set."""
    # Set environment variables for testing
    os.environ["AI_DECK_TRANSLATOR_TESTING"] = "1"

    # Set the current directory to the tests directory
    tests_dir = os.path.join(os.path.dirname(__file__), "tests")
    os.chdir(tests_dir)

    # Discover and run all tests
    test_suite = unittest.defaultTestLoader.discover(".")
    test_runner = unittest.TextTestRunner(verbosity=2)
    result = test_runner.run(test_suite)

    # Return non-zero exit code if tests fail
    if not result.wasSuccessful():
        sys.exit(1)


if __name__ == "__main__":
    main()
