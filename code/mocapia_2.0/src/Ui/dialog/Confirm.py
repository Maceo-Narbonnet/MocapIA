from PyQt5.QtWidgets import QDialog, QLabel, QPushButton, QVBoxLayout, QApplication, QHBoxLayout

class Confirm(QDialog):
    def __init__(self, action, on_confirm, confirm_args=None, parent=None):
        """
        Confirmation dialog.
        :param action: The action to confirm (text).
        :param on_confirm: Function to call if the user confirms.
        :param confirm_args: Tuple of arguments for the on_confirm function.
        :param parent: Parent widget.
        """
        super(Confirm, self).__init__(parent)
        self.setWindowTitle("Confirmation")

        # Create the main layout
        self.main_layout = QVBoxLayout(self)

        # Confirmation message
        self.message_label = QLabel(f"Are you sure you want to {action}?", self)
        self.main_layout.addWidget(self.message_label)

        # Layout for buttons
        self.button_layout = QHBoxLayout()

        # Yes button
        self.yes_button = QPushButton("Yes")
        self.yes_button.clicked.connect(self.accept_action)
        self.button_layout.addWidget(self.yes_button)

        # No button
        self.no_button = QPushButton("No")
        self.no_button.clicked.connect(self.reject)
        self.button_layout.addWidget(self.no_button)

        # Add the buttons to the main layout
        self.main_layout.addLayout(self.button_layout)

        # Store the function to execute and its arguments if the confirmation is accepted
        self.on_confirm = on_confirm
        self.confirm_args = confirm_args if confirm_args is not None else ()

    def accept_action(self):
        """Called when the user clicks 'Yes'."""
        # Execute the action with the provided arguments
        self.on_confirm(*self.confirm_args)
        self.accept()  # Close the dialog
