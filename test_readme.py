def test_readme_configuration_instructions(self):
        """Test that README.md has configuration instructions."""
        with open(self.readme_file, 'r') as f:
            readme = f.read()
        
        # Check for environment variable configuration instructions
        env_var_patterns = [
            r'CLAUDE_API_KEY',
            r'export',
            r'\.env',
            r'environment variable'
        ]
        
        env_var_found = False
        for pattern in env_var_patterns:
            if re.search(pattern, readme, re.IGNORECASE):
                env_var_found = True
                break
        
        self.assertTrue(env_var_found, "Environment variable configuration instructions not found in README.md") 