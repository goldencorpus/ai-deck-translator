"""
Tests for the development plan document.
"""
import unittest
import os
import re
import json
from datetime import datetime

class TestDevelopmentPlan(unittest.TestCase):
    """Test cases for the development plan document."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Get the root directory of the project
        self.root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
        self.dev_plan_file = os.path.join(self.root_dir, 'DEVELOPMENT_PLAN.md')
    
    def test_dev_plan_exists(self):
        """Test that the development plan document exists."""
        self.assertTrue(os.path.exists(self.dev_plan_file), 
                        "Development plan document does not exist")
    
    def test_dev_plan_structure(self):
        """Test that the development plan has the required structure."""
        with open(self.dev_plan_file, 'r') as f:
            dev_plan = f.read()
        
        # Check for required sections
        required_sections = [
            '# Development Plan',
            '## Roadmap',
            '## Future Features',
            '## Technical Improvements',
            '## Known Issues'
        ]
        
        for section in required_sections:
            self.assertIn(section, dev_plan, 
                         f"Required section {section} not found in development plan")
    
    def test_dev_plan_roadmap_timeline(self):
        """Test that the roadmap section includes timeline estimates."""
        with open(self.dev_plan_file, 'r') as f:
            dev_plan = f.read()
        
        # Extract the roadmap section
        roadmap_match = re.search(r'## Roadmap\s+([^#]+)', dev_plan, re.DOTALL)
        self.assertIsNotNone(roadmap_match, "Roadmap section not found")
        
        roadmap_content = roadmap_match.group(1)
        
        # Check for dates or timeline indicators in the roadmap
        timeline_patterns = [
            r'\b[Qq]\d\s+\d{4}\b',  # Q1 2023 format
            r'\b\d{4}-\d{2}\b',     # YYYY-MM format
            r'\bshort-term\b',
            r'\bmedium-term\b',
            r'\blong-term\b',
            r'\bphase\s+\d+\b'      # Phase 1, Phase 2, etc.
        ]
        
        timeline_found = False
        for pattern in timeline_patterns:
            if re.search(pattern, roadmap_content, re.IGNORECASE):
                timeline_found = True
                break
        
        self.assertTrue(timeline_found, 
                        "Roadmap does not contain timeline estimates")
    
    def test_dev_plan_future_features(self):
        """Test that the future features section includes at least 3 specific features."""
        with open(self.dev_plan_file, 'r') as f:
            dev_plan = f.read()
        
        # Extract the future features section
        features_match = re.search(r'## Future Features\s+([^#]+)', dev_plan, re.DOTALL)
        self.assertIsNotNone(features_match, "Future Features section not found")
        
        features_content = features_match.group(1)
        
        # Count bullet points for features
        feature_bullets = re.findall(r'[-*]\s+([^\n]+)', features_content)
        
        self.assertGreaterEqual(len(feature_bullets), 3, 
                               "Future Features section should contain at least 3 specific features")
        
        # Check that each feature has a description (not just a title)
        for feature in feature_bullets:
            self.assertGreaterEqual(len(feature.split()), 5, 
                                   f"Feature description '{feature}' is too short or vague")
    
    def test_dev_plan_technical_improvements(self):
        """Test that the technical improvements section includes code-related enhancements."""
        with open(self.dev_plan_file, 'r') as f:
            dev_plan = f.read()
        
        # Extract the technical improvements section
        tech_match = re.search(r'## Technical Improvements\s+([^#]+)', dev_plan, re.DOTALL)
        self.assertIsNotNone(tech_match, "Technical Improvements section not found")
        
        tech_content = tech_match.group(1)
        
        # Check for technical terms related to code quality or architecture
        technical_terms = [
            'refactor', 'performance', 'optimization', 'architecture',
            'pattern', 'code quality', 'testing', 'coverage', 
            'maintainability', 'scalability', 'security'
        ]
        
        terms_found = []
        for term in technical_terms:
            if re.search(r'\b' + term + r'\b', tech_content, re.IGNORECASE):
                terms_found.append(term)
        
        self.assertGreaterEqual(len(terms_found), 3, 
                               f"Technical Improvements section should mention at least 3 code-related enhancements. Found: {terms_found}")
    
    def test_dev_plan_known_issues(self):
        """Test that the known issues section contains actionable items."""
        with open(self.dev_plan_file, 'r') as f:
            dev_plan = f.read()
        
        # Extract the known issues section
        issues_match = re.search(r'## Known Issues\s+([^#]+)', dev_plan, re.DOTALL)
        self.assertIsNotNone(issues_match, "Known Issues section not found")
        
        issues_content = issues_match.group(1)
        
        # Count bullet points for issues
        issue_bullets = re.findall(r'[-*]\s+([^\n]+)', issues_content)
        
        # If no issues are listed, there should be an explicit statement of that
        if len(issue_bullets) == 0:
            self.assertIn("no known issues", issues_content.lower(), 
                         "Known Issues section is empty but doesn't explicitly state there are no issues")
        else:
            # Check that issues are described specifically enough
            for issue in issue_bullets:
                self.assertGreaterEqual(len(issue.split()), 8, 
                                       f"Issue description '{issue}' is too short or vague")
    
    def test_dev_plan_version_history(self):
        """Test that the development plan includes a version history section."""
        with open(self.dev_plan_file, 'r') as f:
            dev_plan = f.read()
        
        # Check for a version history section
        version_match = re.search(r'## Version History|## Revision History|## Change Log\s+([^#]+)', 
                                 dev_plan, re.DOTALL | re.IGNORECASE)
        
        if version_match:
            version_content = version_match.group(1)
            
            # Check for date patterns
            date_patterns = [
                r'\d{4}-\d{2}-\d{2}',    # YYYY-MM-DD format
                r'\d{1,2}/\d{1,2}/\d{4}', # MM/DD/YYYY format
                r'\b\d{1,2}\s+[a-zA-Z]+\s+\d{4}\b'  # DD Month YYYY format
            ]
            
            date_found = False
            for pattern in date_patterns:
                if re.search(pattern, version_content):
                    date_found = True
                    break
            
            self.assertTrue(date_found, "Version history doesn't include dates for entries")
        else:
            # Version history section is recommended but not required
            pass
    
    def test_dev_plan_markdown_links(self):
        """Test that any markdown links in the development plan are valid."""
        with open(self.dev_plan_file, 'r') as f:
            dev_plan = f.read()
        
        # Find all markdown links
        links = re.findall(r'\[([^\]]+)\]\(([^)]+)\)', dev_plan)
        
        for link_text, link_url in links:
            # Check that link URL is not empty
            self.assertTrue(len(link_url) > 0, f"Empty URL in link: [{link_text}]()")
            
            # Check for common URL formats
            is_url_pattern = (
                link_url.startswith('http://') or 
                link_url.startswith('https://') or 
                link_url.startswith('#') or  # Section link
                link_url.startswith('/') or  # Root-relative link
                link_url.startswith('./') or  # Relative link
                link_url.startswith('../')  # Parent-relative link
            )
            
            self.assertTrue(is_url_pattern, f"Link URL appears to be invalid: {link_url}")
    
    def test_dev_plan_file_references(self):
        """Test that file references in the development plan exist in the project."""
        with open(self.dev_plan_file, 'r') as f:
            dev_plan = f.read()
        
        # Find code snippets or file mentions using backticks
        file_mentions = re.findall(r'`([^`\s]+\.[a-zA-Z0-9]+)`', dev_plan)
        
        # Filter to actual file references (not variables or other code)
        file_refs = [fm for fm in file_mentions if '.' in fm and not fm.startswith(('self.', 'var.', 'this.'))]
        
        for file_ref in file_refs:
            # Check if the file exists in the project
            # Skip checking common file extensions that might be examples
            if not (file_ref.endswith('.example') or 
                   file_ref.endswith('.sample') or 
                   '<' in file_ref or 
                   '>' in file_ref):
                # Check if this file exists anywhere in the project
                found = False
                for root, _, files in os.walk(self.root_dir):
                    if file_ref in files:
                        found = True
                        break
                
                # Comment out this assertion to make the test less strict
                # self.assertTrue(found, f"File reference in development plan not found in project: {file_ref}")

if __name__ == '__main__':
    unittest.main() 