import sys
import os
from PySide6.QtWidgets import (QApplication, QMainWindow, QFileDialog, 
                              QPushButton, QVBoxLayout, QWidget, QLabel)
from PySide6.QtCore import QUrl, QTimer, QObject, Slot, Property, Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebEngineCore import QWebEngineProfile, QWebEnginePage
from PySide6.QtWebChannel import QWebChannel
from app.config_manager import ConfigManager
from flask import Flask
from threading import Thread
from app.routes import main as main_blueprint
from app.document_index import DocumentIndex
from typing import List, Set
import logging

class Bridge(QObject):
    def __init__(self, window):
        super().__init__()
        self._window = window

    @Slot()
    def openFolderDialog(self):
        self._window.handle_folder_change()

class MainWindow(QMainWindow):
    def __init__(self, config_manager):
        super().__init__()
        self.config_manager = config_manager
        self.document_index = DocumentIndex()
        self.bridge = Bridge(self)
        
        # Add shortcut for DevTools
        self.web_view = None  # Will be set in setup_ui
        shortcut = QShortcut(QKeySequence(Qt.Key_F12), self)
        shortcut.activated.connect(self.toggle_dev_tools)
        
        self.setup_ui()

    def toggle_dev_tools(self):
        if self.web_view:
            self.web_view.page().setDevToolsPage(self.web_view.page())

    def setup_ui(self):
        self.setWindowTitle("Contract Assistant")
        self.setGeometry(100, 100, 1400, 1000)
        self.setMinimumSize(1400, 1000)

        # Create central widget and layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        # Create and configure web view
        self.web_view = QWebEngineView()
        
        # Set up web channel
        self.channel = QWebChannel()
        self.channel.registerObject("bridge", self.bridge)
        
        # Set up web page
        profile = QWebEngineProfile.defaultProfile()
        page = QWebEnginePage(profile, self.web_view)
        page.setWebChannel(self.channel)
        self.web_view.setPage(page)
        
        # Inject the bridge object
        inject_script = """
            new QWebChannel(qt.webChannelTransport, function(channel) {
                window.bridge = channel.objects.bridge;
            });
        """
        
        page.loadFinished.connect(lambda _: page.runJavaScript(inject_script))
        
        # Check if setup is complete
        if not self.config_manager.is_setup_complete():
            self.show_setup_page()
            return
        
        # If setup is complete, show main page
        QTimer.singleShot(1000, lambda: self.web_view.setUrl(QUrl("http://127.0.0.1:5000")))
        layout.addWidget(self.web_view)

    def show_setup_page(self):
        # Create setup widget
        setup_widget = QWidget()
        setup_layout = QVBoxLayout(setup_widget)

        # Add welcome label
        welcome_label = QLabel("Welcome to Contract QA System!")
        welcome_label.setStyleSheet("font-size: 18px; margin-bottom: 20px;")
        setup_layout.addWidget(welcome_label)

        # Add instruction label
        instruction_label = QLabel("Please select the folder containing your contracts:")
        setup_layout.addWidget(instruction_label)

        # Add select folder button
        select_button = QPushButton("Select Contracts Folder")
        select_button.clicked.connect(self.select_folder)
        setup_layout.addWidget(select_button)

        # Set the central widget to our setup widget
        self.setCentralWidget(setup_widget)

    def select_folder(self):
        folder = QFileDialog.getExistingDirectory(
            self,
            "Select Contracts Folder",
            os.path.expanduser("~"),
            QFileDialog.ShowDirsOnly
        )
        
        if folder:
            self.config_manager.set_contracts_dir(folder)
            # Reload main window with web view
            self.setup_ui()

    def handle_folder_change(self):
        """Handle folder change from settings"""
        folder = QFileDialog.getExistingDirectory(
            self,
            "Select Contracts Folder",
            os.path.expanduser("~"),
            QFileDialog.ShowDirsOnly
        )
        
        if folder:
            # Update configs
            self.config_manager.set_contracts_dir(folder)
            from flask import current_app
            current_app.config['CONTRACTS_DIR'] = folder
            
            # Force reload of documents
            from app.routes import initialize_document_chain
            global qa_chain
            qa_chain = None
            qa_chain = initialize_document_chain()
            
            # Reload the UI
            self.setup_ui()

    def reload_documents(self):
        """Smart document reloading"""
        try:
            self.show_loading("Updating document index...")
            
            # Get current files
            contracts_dir = self.config_manager.get_contracts_dir()
            current_files = self._get_contract_files(contracts_dir)
            
            # Update index
            changed_files = self.document_index.sync_files(current_files)
            if changed_files:
                self.process_changed_documents(changed_files)
            
            return True
        finally:
            self.hide_loading()

    def _get_contract_files(self, directory: str) -> List[str]:
        """Get list of contract files from directory"""
        contract_files = []
        for root, _, files in os.walk(directory):
            for file in files:
                if file.lower().endswith(('.pdf', '.txt')):
                    contract_files.append(os.path.join(root, file))
        return contract_files

    def process_changed_documents(self, changed_files: Set[str]):
        """Process documents that have changed"""
        try:
            for file_path in changed_files:
                self.show_loading(f"Processing {os.path.basename(file_path)}...")
                
                # Extract metadata using existing chain
                from app.routes import extract_contract_info
                metadata = extract_contract_info(file_path)
                
                # Generate embeddings
                from app.routes import generate_embeddings
                embeddings = generate_embeddings(file_path)
                
                # Update index
                self.document_index.update_document(
                    file_path=file_path,
                    metadata=metadata,
                    embeddings=embeddings
                )
                
            # Update QA chain with new data
            from app.routes import initialize_document_chain
            global qa_chain
            qa_chain = initialize_document_chain()
            
        except Exception as e:
            logging.error(f"Error processing documents: {str(e)}")
            self.show_error("Error processing documents")

def create_app():
    """Create and configure Flask app"""
    flask_app = Flask(__name__, 
                     static_folder='../app/static',
                     template_folder='../app/templates')
    
    config_manager = ConfigManager()
    
    # Set the contracts directory in Flask config
    flask_app.config['CONTRACTS_DIR'] = config_manager.get_contracts_dir()
    
    # Remove the SERVER_NAME line and just keep APPLICATION_ROOT
    flask_app.config['APPLICATION_ROOT'] = '/'
    
    # Register blueprint
    flask_app.register_blueprint(main_blueprint)
    
    return flask_app, config_manager

def run_flask(app):
    """Run Flask in a separate thread"""
    app.run(host='127.0.0.1', port=5000, debug=False, use_reloader=False)

def main():
    # Create Flask app and config manager
    flask_app, config_manager = create_app()
    
    # Start Flask in a separate thread
    flask_thread = Thread(target=run_flask, args=(flask_app,))
    flask_thread.daemon = True
    flask_thread.start()
    
    # Create Qt application
    qt_app = QApplication(sys.argv)
    
    # Create and show main window
    window = MainWindow(config_manager)
    window.show()
    
    # Start Qt application
    sys.exit(qt_app.exec())

if __name__ == "__main__":
    main() 