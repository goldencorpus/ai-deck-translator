"""
Tests for the Google authentication module.
"""
import unittest
from unittest.mock import patch, MagicMock, mock_open
import os
import json
import tempfile
from gslides_translator.auth.google_auth import authenticate_google

class TestGoogleAuth(unittest.TestCase):
    """Test cases for the Google authentication module."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create a temporary directory for credentials
        self.temp_dir = tempfile.mkdtemp()
        self.credentials_path = os.path.join(self.temp_dir, 'credentials.json')
        self.token_path = os.path.join(self.temp_dir, 'token.json')
        
        # Sample credentials data
        self.credentials_data = {
            "installed": {
                "client_id": "test_client_id",
                "project_id": "test_project",
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "client_secret": "test_client_secret"
            }
        }
        
        # Sample token data
        self.token_data = {
            "token": "test_token",
            "refresh_token": "test_refresh_token",
            "token_uri": "https://oauth2.googleapis.com/token",
            "client_id": "test_client_id",
            "client_secret": "test_client_secret",
            "scopes": ["https://www.googleapis.com/auth/presentations"]
        }
    
    @patch('google.oauth2.credentials.Credentials.from_authorized_user_info')
    @patch('google_auth_oauthlib.flow.InstalledAppFlow.from_client_secrets_file')
    @patch('googleapiclient.discovery.build')
    @patch('builtins.open', new_callable=mock_open)
    @patch('os.path.exists')
    def test_authenticate_google_with_token(self, mock_exists, mock_file, mock_build, mock_flow, mock_credentials):
        """Test authentication with an existing token."""
        # Mock that the token file exists
        mock_exists.side_effect = lambda path: path == self.token_path
        
        # Mock reading the token file
        mock_file.return_value.read.return_value = json.dumps(self.token_data)
        
        # Mock the credentials and service
        mock_creds = MagicMock()
        mock_credentials.return_value = mock_creds
        mock_slides_service = MagicMock()
        mock_drive_service = MagicMock()
        mock_build.side_effect = [mock_slides_service, mock_drive_service]
        
        # Call the function
        slides_service, drive_service = authenticate_google(
            credentials_path=self.credentials_path,
            token_path=self.token_path
        )
        
        # Verify the token was read
        mock_file.assert_called_with(self.token_path, 'r')
        
        # Verify the credentials were created from the token
        mock_credentials.assert_called_once()
        
        # Verify the services were built
        self.assertEqual(mock_build.call_count, 2)
        mock_build.assert_any_call('slides', 'v1', credentials=mock_creds)
        mock_build.assert_any_call('drive', 'v3', credentials=mock_creds)
        
        # Verify the services were returned
        self.assertEqual(slides_service, mock_slides_service)
        self.assertEqual(drive_service, mock_drive_service)
    
    @patch('google_auth_oauthlib.flow.InstalledAppFlow.from_client_secrets_file')
    @patch('googleapiclient.discovery.build')
    @patch('builtins.open', new_callable=mock_open)
    @patch('os.path.exists')
    def test_authenticate_google_without_token(self, mock_exists, mock_file, mock_build, mock_flow):
        """Test authentication without an existing token."""
        # Mock that the token file doesn't exist
        mock_exists.return_value = False
        
        # Mock the flow and credentials
        mock_flow_instance = MagicMock()
        mock_flow.return_value = mock_flow_instance
        mock_creds = MagicMock()
        mock_flow_instance.run_local_server.return_value = mock_creds
        mock_creds.to_json.return_value = json.dumps(self.token_data)
        
        # Mock the services
        mock_slides_service = MagicMock()
        mock_drive_service = MagicMock()
        mock_build.side_effect = [mock_slides_service, mock_drive_service]
        
        # Call the function
        slides_service, drive_service = authenticate_google(
            credentials_path=self.credentials_path,
            token_path=self.token_path
        )
        
        # Verify the flow was created
        mock_flow.assert_called_with(
            self.credentials_path,
            scopes=['https://www.googleapis.com/auth/presentations', 'https://www.googleapis.com/auth/drive']
        )
        
        # Verify the flow was run
        mock_flow_instance.run_local_server.assert_called_once()
        
        # Verify the token was saved
        mock_file.assert_called_with(self.token_path, 'w')
        mock_file.return_value.write.assert_called_with(mock_creds.to_json())
        
        # Verify the services were built
        self.assertEqual(mock_build.call_count, 2)
        mock_build.assert_any_call('slides', 'v1', credentials=mock_creds)
        mock_build.assert_any_call('drive', 'v3', credentials=mock_creds)
        
        # Verify the services were returned
        self.assertEqual(slides_service, mock_slides_service)
        self.assertEqual(drive_service, mock_drive_service)
    
    @patch('google.oauth2.credentials.Credentials.from_authorized_user_info')
    @patch('googleapiclient.discovery.build')
    @patch('builtins.open', new_callable=mock_open)
    @patch('os.path.exists')
    def test_authenticate_google_with_expired_token(self, mock_exists, mock_file, mock_build, mock_credentials):
        """Test authentication with an expired token."""
        # Mock that the token file exists
        mock_exists.side_effect = lambda path: path == self.token_path
        
        # Mock reading the token file
        mock_file.return_value.read.return_value = json.dumps(self.token_data)
        
        # Mock the credentials and service
        mock_creds = MagicMock()
        mock_creds.expired = True
        mock_creds.refresh_token = "test_refresh_token"
        mock_credentials.return_value = mock_creds
        
        mock_slides_service = MagicMock()
        mock_drive_service = MagicMock()
        mock_build.side_effect = [mock_slides_service, mock_drive_service]
        
        # Call the function
        slides_service, drive_service = authenticate_google(
            credentials_path=self.credentials_path,
            token_path=self.token_path
        )
        
        # Verify the token was read
        mock_file.assert_called_with(self.token_path, 'r')
        
        # Verify the credentials were refreshed
        mock_creds.refresh.assert_called_once()
        
        # Verify the token was saved after refresh
        mock_file.return_value.write.assert_called_with(mock_creds.to_json())
        
        # Verify the services were built
        self.assertEqual(mock_build.call_count, 2)
        mock_build.assert_any_call('slides', 'v1', credentials=mock_creds)
        mock_build.assert_any_call('drive', 'v3', credentials=mock_creds)
        
        # Verify the services were returned
        self.assertEqual(slides_service, mock_slides_service)
        self.assertEqual(drive_service, mock_drive_service)

if __name__ == '__main__':
    unittest.main() 