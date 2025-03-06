"""
Tests for the README.md file.
"""
import unittest
import os
import re

class TestReadme(unittest.TestCase):
    """Test cases for the README.md file."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Get the root directory of the project
        self.root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
        self.readme_file = os.path.join(self.root_dir, 'README.md')
    
    def test_readme_exists(self):
        """Test that README.md exists."""
        self.assertTrue(os.path.exists(self.readme_file))
    
    def test_readme_content(self):
        """Test that README.md has the required content."""
        with open(self.readme_file, 'r') as f:
            readme = f.read()
        
        # Check for required sections
        required_sections = [
            '# Google Slides Translator',
            '## Installation',
            '## Usage',
            '## Features',
            '## Configuration'
        ]
        
        for section in required_sections:
            self.assertIn(section, readme, f"Required section {section} not found in README.md")
    
    def test_readme_installation_instructions(self):
        """Test that README.md has installation instructions."""
        with open(self.readme_file, 'r') as f:
            readme = f.read()
        
        # Check for installation instructions
        installation_patterns = [
            r'pip install',
            r'git clone',
            r'setup\.py'
        ]
        
        installation_found = False
        for pattern in installation_patterns:
            if re.search(pattern, readme, re.IGNORECASE):
                installation_found = True
                break
        
        self.assertTrue(installation_found, "Installation instructions not found in README.md")
    
    def test_readme_usage_examples(self):
        """Test that README.md has usage examples."""
        with open(self.readme_file, 'r') as f:
            readme = f.read()
        
        # Check for usage examples
        usage_patterns = [
            r'python -m gslides_translator',
            r'gslides_translator',
            r'translate',
            r'--presentation-id'
        ]
        
        usage_found = False
        for pattern in usage_patterns:
            if re.search(pattern, readme, re.IGNORECASE):
                usage_found = True
                break
        
        self.assertTrue(usage_found, "Usage examples not found in README.md")
    
    def test_readme_features_list(self):
        """Test that README.md has a features list."""
        with open(self.readme_file, 'r') as f:
            readme = f.read()
        
        # Check for features list
        features_section = re.search(r'## Features\s+([^#]+)', readme, re.DOTALL)
        self.assertIsNotNone(features_section, "Features section not found in README.md")
        
        features_content = features_section.group(1)
        self.assertIn('-', features_content, "Features list not found in README.md")
    
    def test_readme_configuration_instructions(self):
        """Test that README.md has configuration instructions."""
        with open(self.readme_file, 'r') as f:
            readme = f.read()
        
        # Check for configuration instructions
        config_section = re.search(r'## Configuration\s+([^#]+)', readme, re.DOTALL)
        self.assertIsNotNone(config_section, "Configuration section not found in README.md")
        
        config_content = config_section.group(1)
        self.assertTrue(
            'ANTHROPIC_API_KEY' in config_content or '.env' in config_content,
            "Configuration instructions not found in README.md"
        )

if __name__ == '__main__':
    unittest.main() 