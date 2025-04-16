#!/usr/bin/env python3
"""
Script to update all test files to use ai_deck_translator instead of gslides_translator.
"""
import os
import re
from pathlib import Path


def update_file(file_path):
    """
    Update import statements in the file to use ai_deck_translator instead of gslides_translator.
    """
    with open(file_path, "r") as f:
        content = f.read()

    # Replace in imports
    updated_content = re.sub(
        r"from gslides_translator", "from ai_deck_translator", content
    )
    updated_content = re.sub(
        r"import gslides_translator", "import ai_deck_translator", updated_content
    )

    # Replace in patch decorators and other references
    updated_content = re.sub(
        r"@patch\('gslides_translator", "@patch('ai_deck_translator", updated_content
    )
    updated_content = re.sub(
        r"'gslides_translator", "'ai_deck_translator", updated_content
    )
    updated_content = re.sub(
        r'"gslides_translator', '"ai_deck_translator', updated_content
    )

    if content != updated_content:
        with open(file_path, "w") as f:
            f.write(updated_content)
        print(f"Updated: {file_path}")
    else:
        print(f"No changes needed: {file_path}")


def main():
    """
    Update all test files in the tests directory.
    """
    test_dir = Path("tests")
    standalone_files = [
        Path("test_glossary.py"),
        Path("standalone_test_memory.py"),
        Path("test_translation_memory.py"),
        Path("test_notes_translation_simple.py"),
        Path("simple_test.py"),
        Path("standalone_test_notes.py"),
        Path("test_notes_translation.py"),
    ]

    # Update files in the tests directory
    for test_file in test_dir.glob("test_*.py"):
        update_file(test_file)

    # Update standalone test files in the root directory
    for file_path in standalone_files:
        if file_path.exists():
            update_file(file_path)


if __name__ == "__main__":
    main()
