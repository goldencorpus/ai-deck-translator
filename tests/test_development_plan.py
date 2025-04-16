"""
Tests for the development plan.
"""

import os
import re
import unittest
from unittest.mock import patch, mock_open

# Update the path to the development plan
DEV_PLAN_FILE = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "Development Plan.md"
)


class TestDevelopmentPlan(unittest.TestCase):
    """Test cases for the development plan."""

    def setUp(self):
        """Set up test fixtures."""
        self.dev_plan_file = DEV_PLAN_FILE

    def test_dev_plan_exists(self):
        """Test that the development plan document exists."""
        self.assertTrue(
            os.path.exists(self.dev_plan_file),
            "Development plan document does not exist",
        )

    def test_dev_plan_structure(self):
        """Test that the development plan has the required structure."""
        required_sections = [
            "# Development Plan",
            "## Roadmap",
            "## Known Issues",
            "## Future Features",
            "## Technical Improvements",
        ]

        with open(self.dev_plan_file, "r") as f:
            content = f.read()

        for section in required_sections:
            self.assertIn(
                section,
                content,
                f"Required section {section} not found in development plan",
            )

    def test_dev_plan_roadmap_timeline(self):
        """Test that the roadmap section includes timeline estimates."""
        with open(self.dev_plan_file, "r") as f:
            content = f.read()

        # Extract the roadmap section
        roadmap_pattern = r"## Roadmap\s+(.*?)(?=\n## )"
        roadmap_match = re.search(roadmap_pattern, content, re.DOTALL)

        if roadmap_match:
            roadmap_section = roadmap_match.group(1)

            # Check for timeline indicators like dates, weeks, sprints
            timeline_pattern = r"(Q[1-4]|Sprint|Week|Month|Phase|January|February|March|April|May|June|July|August|September|October|November|December|\d{1,2}/\d{1,2}/\d{2,4}|\d{4}-\d{2}-\d{2})"
            timeline_matches = re.findall(
                timeline_pattern, roadmap_section, re.IGNORECASE
            )

            self.assertTrue(
                len(timeline_matches) > 0,
                "Roadmap section does not include timeline estimates",
            )
        else:
            self.fail("Roadmap section not found in expected format")

    def test_dev_plan_future_features(self):
        """Test that the future features section includes at least 3 specific features."""
        with open(self.dev_plan_file, "r") as f:
            content = f.read()

        # Extract the future features section
        features_pattern = r"## Future Features\s+(.*?)(?=\n## |$)"
        features_match = re.search(features_pattern, content, re.DOTALL)

        if features_match:
            features_section = features_match.group(1)

            # Count the number of features (list items)
            feature_items = re.findall(r"- \S+", features_section)

            self.assertTrue(
                len(feature_items) >= 3,
                "Future Features section should include at least 3 specific features",
            )

            # Check that features have descriptive text
            for item in feature_items:
                self.assertTrue(
                    len(item) > 5, f"Feature description is too short: {item}"
                )
        else:
            self.fail("Future Features section not found in expected format")

    def test_dev_plan_technical_improvements(self):
        """Test that the technical improvements section includes code-related enhancements."""
        with open(self.dev_plan_file, "r") as f:
            content = f.read()

        # Extract the technical improvements section
        tech_pattern = r"## Technical Improvements\s+(.*?)(?=\n## |$)"
        tech_match = re.search(tech_pattern, content, re.DOTALL)

        if tech_match:
            tech_section = tech_match.group(1)

            # Check for code-related terms
            code_terms = [
                "refactor",
                "performance",
                "optimize",
                "test",
                "coverage",
                "documentation",
                "clean",
                "modular",
                "interface",
                "api",
                "reusable",
                "component",
            ]

            found_terms = 0
            for term in code_terms:
                if re.search(r"\b" + term + r"\b", tech_section, re.IGNORECASE):
                    found_terms += 1

            self.assertTrue(
                found_terms >= 2,
                "Technical Improvements section should include code-related enhancements",
            )
        else:
            self.fail("Technical Improvements section not found in expected format")

    def test_dev_plan_known_issues(self):
        """Test that the known issues section contains actionable items."""
        with open(self.dev_plan_file, "r") as f:
            content = f.read()

        # Extract the known issues section
        issues_pattern = r"## Known Issues\s+(.*?)(?=\n## |$)"
        issues_match = re.search(issues_pattern, content, re.DOTALL)

        if issues_match:
            issues_section = issues_match.group(1)

            # Check for actionable descriptions (contains verbs)
            action_terms = [
                "fix",
                "resolve",
                "handle",
                "address",
                "update",
                "improve",
                "implement",
                "create",
                "modify",
                "enhance",
                "optimize",
                "correct",
            ]

            found_terms = 0
            for term in action_terms:
                if re.search(r"\b" + term + r"\b", issues_section, re.IGNORECASE):
                    found_terms += 1

            self.assertTrue(
                found_terms >= 1, "Known Issues section should include actionable items"
            )
        else:
            self.fail("Known Issues section not found in expected format")

    def test_dev_plan_version_history(self):
        """Test that the development plan includes a version history section."""
        with open(self.dev_plan_file, "r") as f:
            content = f.read()

        # Look for a version history section
        history_patterns = [
            r"## Version History",
            r"## Changelog",
            r"## Release History",
            r"## Updates",
            r"## Release Notes",
        ]

        has_history_section = False
        for pattern in history_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                has_history_section = True
                break

        self.assertTrue(
            has_history_section,
            "Development plan should include a version history section",
        )

    def test_dev_plan_markdown_links(self):
        """Test that any markdown links in the development plan are valid."""
        with open(self.dev_plan_file, "r") as f:
            content = f.read()

        # Find all markdown links
        link_pattern = r"\[([^\]]+)\]\(([^)]+)\)"
        links = re.findall(link_pattern, content)

        for link_text, link_target in links:
            # Check for broken links (empty targets)
            self.assertTrue(
                len(link_target) > 0, f"Empty link target for '{link_text}'"
            )

            # Check if links to local files actually exist
            if not link_target.startswith(("http://", "https://", "mailto:", "#")):
                if link_target.startswith("/"):
                    # Absolute path relative to repository root
                    link_path = os.path.join(
                        os.path.dirname(os.path.dirname(__file__)), link_target[1:]
                    )
                else:
                    # Relative path from the development plan
                    link_path = os.path.join(
                        os.path.dirname(self.dev_plan_file), link_target
                    )

                self.assertTrue(
                    os.path.exists(link_path),
                    f"Broken link to '{link_path}' from development plan",
                )

    def test_dev_plan_file_references(self):
        """Test that file references in the development plan exist in the project."""
        with open(self.dev_plan_file, "r") as f:
            content = f.read()

        # Find code file references (those in backticks that look like paths)
        file_pattern = r"`([^`]*\.(py|md|sh|json|html|css|js|yml|yaml)[^`]*)`"
        files = re.findall(file_pattern, content)

        for file_match in files:
            file_ref = file_match[0]  # The first capture group is the file path

            # Skip if it's not really a file path (e.g. a code snippet)
            if "(" in file_ref or ")" in file_ref or "=" in file_ref or " " in file_ref:
                continue

            # Try to find the file in the project
            if file_ref.startswith("/"):
                # Absolute path relative to repository root
                file_path = os.path.join(
                    os.path.dirname(os.path.dirname(__file__)), file_ref[1:]
                )
            else:
                # Relative path from the development plan or from the repository root
                file_path_from_dev_plan = os.path.join(
                    os.path.dirname(self.dev_plan_file), file_ref
                )
                file_path_from_root = os.path.join(
                    os.path.dirname(os.path.dirname(__file__)), file_ref
                )

                file_path = (
                    file_path_from_root
                    if os.path.exists(file_path_from_root)
                    else file_path_from_dev_plan
                )

            self.assertTrue(
                os.path.exists(file_path) or "/*" in file_ref or "*." in file_ref,
                f"File reference '{file_ref}' in development plan does not exist",
            )


if __name__ == "__main__":
    unittest.main()
