import pytest
import os
from app.google_drive import GoogleDriveManager
from app.config_manager import ConfigManager
from unittest.mock import Mock
import tempfile
import json

@pytest.fixture
def config_manager():
    """Fixture for config manager with test settings"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json') as temp_config:
        test_config = {
            'source_type': 'google_drive',
            'contracts_dir': '',
            'google_drive': {
                'folder_id': 'test_folder_id',
                'folder_name': 'Test Folder'
            }
        }
        json.dump(test_config, temp_config)
        temp_config.flush()
        config = ConfigManager()
        config.config_file = temp_config.name
        yield config

@pytest.fixture
def drive_manager():
    """Fixture for Google Drive manager"""
    return GoogleDriveManager()
