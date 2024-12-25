import os
import configparser
from pathlib import Path

class ConfigManager:
    def __init__(self):
        # Get the user's home directory
        self.home_dir = str(Path.home())
        # Create a .contractqa directory in user's home folder
        self.config_dir = os.path.join(self.home_dir, '.contractqa')
        self.config_file = os.path.join(self.config_dir, 'config.ini')
        
        # Create config directory if it doesn't exist
        if not os.path.exists(self.config_dir):
            os.makedirs(self.config_dir)
        
        self.config = configparser.ConfigParser()
        self.load_config()

    def load_config(self):
        """Load existing config or create default"""
        if os.path.exists(self.config_file):
            self.config.read(self.config_file)
        
        # Create default sections if they don't exist
        if 'Paths' not in self.config:
            self.config['Paths'] = {}
        
        # Set default values if they don't exist
        if 'contracts_dir' not in self.config['Paths']:
            self.config['Paths']['contracts_dir'] = ''

        self.save_config()

    def save_config(self):
        """Save current configuration to file"""
        with open(self.config_file, 'w') as configfile:
            self.config.write(configfile)

    def get_contracts_dir(self):
        """Get the contracts directory path"""
        return self.config['Paths']['contracts_dir']

    def set_contracts_dir(self, path):
        """Set the contracts directory path"""
        self.config['Paths']['contracts_dir'] = path
        self.save_config()

    def is_setup_complete(self):
        """Check if initial setup is complete"""
        return bool(self.get_contracts_dir().strip()) 