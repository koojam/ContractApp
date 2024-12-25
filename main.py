class MainWindow(QMainWindow):  # or whatever your window class is named
    def __init__(self):
        super().__init__()
        # ... other initialization code ...
        
        # Add these lines to set minimum window size
        self.setMinimumWidth(1400)  # Width in pixels
        self.setMinimumHeight(1000)  # Height in pixels 