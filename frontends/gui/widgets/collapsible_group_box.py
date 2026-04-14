from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)


class CollapsibleGroupBox(QWidget):
    def __init__(self, title: str, content_widget: QWidget, expanded: bool = False):
        super().__init__()

        self._content_widget = content_widget
        self._expanded = expanded

        self.toggle_button = QToolButton()
        self.toggle_button.setText(title)
        self.toggle_button.setCheckable(True)
        self.toggle_button.setChecked(expanded)
        self.toggle_button.setToolButtonStyle(
            Qt.ToolButtonStyle.ToolButtonTextBesideIcon
        )
        self.toggle_button.setArrowType(
            Qt.ArrowType.DownArrow if expanded else Qt.ArrowType.RightArrow
        )
        self.toggle_button.setSizePolicy(
            QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed
        )
        self.toggle_button.setMinimumHeight(28)
        self.toggle_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.toggle_button.setStyleSheet(
            """
            QToolButton {
                padding: 4px 8px 4px 4px;
                font-weight: 600;
                text-align: left;
            }
            """
        )
        self.toggle_button.clicked.connect(self._on_toggled)

        header_line = QFrame()
        header_line.setFrameShape(QFrame.Shape.HLine)
        header_line.setFrameShadow(QFrame.Shadow.Sunken)
        header_line.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )

        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(8)
        header_layout.addWidget(self.toggle_button, 0, Qt.AlignmentFlag.AlignLeft)
        header_layout.addWidget(header_line, 1)

        self._content_widget.setVisible(expanded)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(4)
        outer.addLayout(header_layout)
        outer.addWidget(self._content_widget)

    def _on_toggled(self, checked: bool):
        self._expanded = checked
        self.toggle_button.setArrowType(
            Qt.ArrowType.DownArrow if checked else Qt.ArrowType.RightArrow
        )
        self._content_widget.setVisible(checked)

    def set_expanded(self, expanded: bool):
        self.toggle_button.setChecked(expanded)
        self._on_toggled(expanded)

    def is_expanded(self) -> bool:
        return self._expanded
