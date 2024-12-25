import pytest
from unittest.mock import Mock, patch
from app.google_drive import GoogleDriveManager

class TestGoogleDriveIntegration:
    def test_source_switching(self, config_manager):
        """Test switching between local and Google Drive sources"""
        config_manager.set_source_type('local')
        assert config_manager.get_source_type() == 'local'
        
        config_manager.set_source_type('google_drive')
        assert config_manager.get_source_type() == 'google_drive'

    @patch('app.google_drive.GoogleDriveManager.authenticate')
    def test_authentication(self, mock_auth, drive_manager):
        """Test Google Drive authentication"""
        mock_service = Mock()
        mock_auth.return_value = mock_service
        
        service = drive_manager.authenticate()
        assert service is not None
        assert service == mock_service
