# This file is part of BuzzRef.
#
# BuzzRef is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# BuzzRef is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with BuzzRef.  If not, see <https://www.gnu.org/licenses/>.

from functools import partial
import logging
import os

from PyQt6 import QtCore, QtWidgets, QtGui
from PyQt6.QtCore import Qt

from buzzref import constants, commands, fileio
from buzzref.config import logfile_name, BuzzSettings
from buzzref.widgets import (  # noqa: F401
    controls,
    settings,
    welcome_overlay,
    color_gamut,
    screen_capture,
)


logger = logging.getLogger(__name__)


class BuzzProgressDialog(QtWidgets.QProgressDialog):

    def __init__(self, label, worker, maximum=0, parent=None):
        super().__init__(label, self.tr('Cancel'), 0, maximum, parent=parent)
        logger.debug('Initialised progress bar')
        self.setMinimumDuration(0)
        self.setWindowModality(Qt.WindowModality.WindowModal)
        self.setAutoReset(False)
        self.setAutoClose(False)
        worker.begin_processing.connect(self.on_begin_processing)
        worker.progress.connect(self.on_progress)
        worker.finished.connect(self.on_finished)
        worker.user_input_required.connect(self.on_finished)
        self.canceled.connect(worker.on_canceled)

    def on_progress(self, value):
        logger.debug(f'Progress dialog: {value}')
        self.setValue(value)

    def on_begin_processing(self, value):
        logger.debug(f'Beginn progress dialog: {value}')
        self.setMaximum(value)

    def on_finished(self, *args, **kwargs):
        logger.debug('Finished progress dialog')
        self.setValue(self.maximum())
        self.reset()
        self.hide()
        QtCore.QTimer.singleShot(100, self.deleteLater)


class HelpDialog(QtWidgets.QDialog):
    DOCS_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                             'documentation')

    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle(self.tr('%s Help') % constants.APPNAME)

        tabs = QtWidgets.QTabWidget()

        # Controls
        controls_txt = self._load_localized_help('controls.html')
        controls_label = QtWidgets.QLabel(controls_txt)
        controls_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse)
        scroll = QtWidgets.QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setWidget(controls_label)
        tabs.addTab(scroll, self.tr('&Controls'))

        layout = QtWidgets.QVBoxLayout()
        self.setLayout(layout)
        layout.addWidget(tabs)

        # Bottom row of buttons
        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.show()

    def _get_language_code(self):
        """Get the current language code from settings or system locale."""
        buzz_settings = BuzzSettings()
        lang = buzz_settings.valueOrDefault('General/language')
        if lang == 'system':
            locale = QtCore.QLocale.system()
            lang = locale.name().split('_')[0]
        return lang

    def _load_localized_help(self, filename):
        """Load localized help content, falling back to English."""
        lang = self._get_language_code()
        base, ext = os.path.splitext(filename)

        # Try localized version first (e.g., controls_ko.html)
        if lang and lang != 'en':
            localized = os.path.join(self.DOCS_PATH, f'{base}_{lang}{ext}')
            if os.path.exists(localized):
                with open(localized, 'r', encoding='utf-8') as f:
                    return f.read()

        # Fall back to English
        default = os.path.join(self.DOCS_PATH, filename)
        with open(default, 'r', encoding='utf-8') as f:
            return f.read()


class DebugLogDialog(QtWidgets.QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle(self.tr('%s Debug Log') % constants.APPNAME)
        with open(logfile_name()) as f:
            self.log_txt = f.read()

        self.log = QtWidgets.QPlainTextEdit(self.log_txt)
        self.log.setReadOnly(True)

        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        self.copy_button = QtWidgets.QPushButton(self.tr('Co&py To Clipboard'))
        self.copy_button.released.connect(self.copy_to_clipboard)
        buttons.addButton(
            self.copy_button, QtWidgets.QDialogButtonBox.ButtonRole.ActionRole)

        layout = QtWidgets.QVBoxLayout()
        self.setLayout(layout)
        name_widget = QtWidgets.QLabel(logfile_name())
        name_widget.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(name_widget)
        layout.addWidget(self.log)
        layout.addWidget(buttons)
        self.show()

    def copy_to_clipboard(self):
        clipboard = QtWidgets.QApplication.clipboard()
        clipboard.setText(self.log_txt)


class SceneToPixmapExporterDialog(QtWidgets.QDialog):
    MIN_SIZE = 10
    MAX_SIZE = 100000

    def __init__(self, parent, default_size):
        super().__init__(parent)
        self.default_size = default_size
        if (self.default_size.width() > self.MAX_SIZE
                or self.default_size.width() >= self.MAX_SIZE):
            self.default_size.scale(
                self.MAX_SIZE, self.MAX_SIZE,
                Qt.AspectRatioMode.KeepAspectRatio)

        self.ignore_change = False
        self.setWindowTitle(self.tr('Export Scene to Image'))
        self.setWindowModality(Qt.WindowModality.WindowModal)
        layout = QtWidgets.QGridLayout()
        self.setLayout(layout)

        width_label = QtWidgets.QLabel(self.tr('Width:'))
        layout.addWidget(width_label, 0, 0)
        self.width_input = QtWidgets.QSpinBox()
        self.width_input.setRange(self.MIN_SIZE, self.MAX_SIZE)
        self.width_input.setValue(default_size.width())
        self.width_input.valueChanged.connect(self.on_width_changed)
        layout.addWidget(self.width_input, 0, 1)

        height_label = QtWidgets.QLabel(self.tr('Height:'))
        layout.addWidget(height_label, 1, 0)
        self.height_input = QtWidgets.QSpinBox()
        self.height_input.setMinimum(10)
        self.height_input.setRange(self.MIN_SIZE, self.MAX_SIZE)
        self.height_input.setValue(default_size.height())
        self.height_input.valueChanged.connect(self.on_height_changed)
        layout.addWidget(self.height_input, 1, 1)

        # Bottom row of buttons
        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok |
            QtWidgets.QDialogButtonBox.StandardButton.Cancel)

        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons, 3, 1)

    def on_width_changed(self, width):
        if not self.ignore_change:
            self.ignore_change = True
            new = self.default_size.scaled(
                width, self.MAX_SIZE, Qt.AspectRatioMode.KeepAspectRatio)
            self.height_input.setValue(new.height())
            self.ignore_change = False

    def on_height_changed(self, height):
        if not self.ignore_change:
            self.ignore_change = True
            new = self.default_size.scaled(
                self.MAX_SIZE, height, Qt.AspectRatioMode.KeepAspectRatio)
            self.width_input.setValue(new.width())
            self.ignore_change = False

    def value(self):
        return QtCore.QSize(self.width_input.value(),
                            self.height_input.value())


class ChangeOpacityDialog(QtWidgets.QDialog):

    def __init__(self, parent, images: list[QtWidgets.QGraphicsItem], undo_stack):
        super().__init__(parent)
        self.undo_stack = undo_stack
        self.images = images
        self.command = commands.ChangeOpacity(images, opacity=1)

        value = int(images[0].opacity() * 100) if images else 100

        self.setWindowTitle(self.tr('Change Opacity:'))
        self.setWindowModality(Qt.WindowModality.WindowModal)
        layout = QtWidgets.QVBoxLayout()
        self.setLayout(layout)

        self.label = QtWidgets.QLabel(self.tr('Opacity:'))
        layout.addWidget(self.label)

        self.input = QtWidgets.QSlider(Qt.Orientation.Horizontal)
        self.input.valueChanged.connect(self.on_value_changed)
        self.input.setRange(0, 100)
        self.input.setValue(value)
        layout.addWidget(self.input)

        # Bottom row of buttons
        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok |
            QtWidgets.QDialogButtonBox.StandardButton.Cancel)

        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.show()

    def on_value_changed(self, value):
        self.label.setText(self.tr('Opacity: %s%%') % value)
        self.command.opacity = value / 100
        self.command.redo()

    def accept(self):
        if self.images:
            logger.debug(f'Setting opacity to {self.command.opacity}')
            self.command.ignore_first_redo = True
            self.undo_stack.push(self.command)
        return super().accept()

    def reject(self):
        self.command.undo()
        return super().reject()


class ImagesDialog(QtWidgets.QDialog):

    def __init__(self, parent, scene):
        super().__init__(parent)
        self.scene = scene
        self.image_items = list(scene.items_by_type(
            'pixmap', include_unloaded=True))
        self.setWindowTitle(self.tr('Images'))
        self.resize(500, 300)

        layout = QtWidgets.QVBoxLayout(self)
        filters = QtWidgets.QHBoxLayout()
        filters.addWidget(QtWidgets.QLabel(self.tr('Filename:')))
        self.filename_filter = QtWidgets.QLineEdit()
        self.filename_filter.setPlaceholderText(
            self.tr('Filter by filename'))
        self.filename_filter.textChanged.connect(self.refresh)
        filters.addWidget(self.filename_filter)
        filters.addWidget(QtWidgets.QLabel(self.tr('Status:')))
        self.status_filter = QtWidgets.QComboBox()
        self.status_filter.addItem(self.tr('All'), 'all')
        self.status_filter.addItem(self.tr('Loaded'), 'loaded')
        self.status_filter.addItem(self.tr('Unloaded'), 'unloaded')
        self.status_filter.currentIndexChanged.connect(self.refresh)
        filters.addWidget(self.status_filter)
        layout.addLayout(filters)

        self.image_grid = QtWidgets.QTableWidget(0, 3)
        self.image_grid.setHorizontalHeaderLabels(
            [self.tr('#'), self.tr('Filename'), self.tr('Status')])
        self.image_grid.setSelectionMode(
            QtWidgets.QAbstractItemView.SelectionMode.ExtendedSelection)
        self.image_grid.setSelectionBehavior(
            QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.image_grid.setSortingEnabled(True)
        self.image_grid.setEditTriggers(
            QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        header = self.image_grid.horizontalHeader()
        assert header is not None
        header.setStretchLastSection(True)
        header.setSortIndicator(1, QtCore.Qt.SortOrder.AscendingOrder)
        self.image_grid.itemSelectionChanged.connect(
            self.on_selection_changed)
        layout.addWidget(self.image_grid)
        # Keep the old attribute available to integrations using the dialog.
        self.image_list = self.image_grid

        buttons = QtWidgets.QHBoxLayout()
        self.unload_button = QtWidgets.QPushButton(self.tr('Unload'))
        self.unload_button.clicked.connect(self.unload_current)
        self.unload_button.setToolTip(
            self.tr('Only images loaded from a saved scene can be unloaded.'))
        buttons.addWidget(self.unload_button)
        self.reload_button = QtWidgets.QPushButton(self.tr('Reload'))
        self.reload_button.clicked.connect(self.reload_current)
        buttons.addWidget(self.reload_button)
        buttons.addStretch()
        close_button = QtWidgets.QPushButton(self.tr('Close'))
        close_button.clicked.connect(self.close)
        buttons.addWidget(close_button)
        layout.addLayout(buttons)

        self.refresh()
        self.show()

    def refresh(self):
        selected_images = set(self.selected_images())
        filename_query = self.filename_filter.text().casefold()
        status = self.status_filter.currentData()
        self.image_items = list(self.scene.items_by_type(
            'pixmap', include_unloaded=True))
        filtered_images = [
            item for item in self.image_items
            if filename_query in (item.filename or '').casefold()
            and (status == 'all'
                 or status == ('loaded' if item.image_loaded else 'unloaded'))
        ]

        self.image_grid.blockSignals(True)
        self.image_grid.setSortingEnabled(False)
        self.image_grid.setRowCount(0)
        for row, item in enumerate(filtered_images):
            filename = item.filename or self.tr('(unnamed image)')
            item_status = (self.tr('Loaded') if item.image_loaded
                           else self.tr('Unloaded'))
            self.image_grid.insertRow(row)
            number = QtWidgets.QTableWidgetItem(str(row + 1))
            number.setData(QtCore.Qt.ItemDataRole.UserRole, id(item))
            name = QtWidgets.QTableWidgetItem(filename)
            name.setData(QtCore.Qt.ItemDataRole.UserRole, id(item))
            state = QtWidgets.QTableWidgetItem(item_status)
            state.setData(QtCore.Qt.ItemDataRole.UserRole, id(item))
            self.image_grid.setItem(row, 0, number)
            self.image_grid.setItem(row, 1, name)
            self.image_grid.setItem(row, 2, state)
            if item in selected_images:
                self.image_grid.selectRow(row)
        self.image_grid.setSortingEnabled(True)
        self.image_grid.blockSignals(False)
        self.on_selection_changed()

    def selected_images(self):
        item_by_id = {id(item): item for item in self.image_items}
        rows = {index.row() for index in self.image_grid.selectedIndexes()}
        return [
            item_by_id[self.image_grid.item(row, 0).data(
                QtCore.Qt.ItemDataRole.UserRole)]
            for row in rows
        ]

    def on_selection_changed(self):
        images = self.selected_images()
        self.unload_button.setEnabled(
            any(item.image_loaded
                and item.save_id is not None
                and item.image_source is not None
                for item in images))
        self.reload_button.setEnabled(
            any(not item.image_loaded
                and item.save_id is not None
                and item.image_source is not None
                for item in images))

    def unload_current(self):
        command = commands.ChangeImageLoadState(
            self.selected_images(), unload=True)
        if command.items:
            self.start_image_load_state(command)

    def reload_current(self):
        command = commands.ChangeImageLoadState(
            self.selected_images(), unload=False)
        if command.items:
            self.start_image_load_state(command)

    def start_image_load_state(self, command):
        self.worker = fileio.ThreadedIO(
            fileio.prepare_image_load_state,
            command.items, command.unload)
        self.worker.finished.connect(
            partial(self.on_image_load_state_finished, command))
        self.progress = BuzzProgressDialog(
            self.tr('Unloading images' if command.unload
                    else 'Reloading images'),
            worker=self.worker,
            parent=self)
        self.worker.start()

    def on_image_load_state_finished(self, command, filename, errors):
        if errors or self.worker.canceled:
            if errors:
                QtWidgets.QMessageBox.warning(
                    self,
                    self.tr('Problem changing image state'),
                    self.tr('Some images could not be processed.'))
            return
        command.image_data = getattr(self.worker, 'image_data', {})
        command.redo()
        command.ignore_first_redo = True
        self.scene.undo_stack.push(command)
        self.refresh()


class ChangeWindowOpacityDialog(QtWidgets.QDialog):

    def __init__(self, parent, buzz_settings, set_opacity, opacity):
        super().__init__(parent)
        self.buzz_settings = buzz_settings
        self.set_opacity = set_opacity
        self.previous_opacity = opacity
        value = round(opacity * 100)

        self.setWindowTitle(self.tr('Change Window Opacity:'))
        self.setWindowModality(Qt.WindowModality.WindowModal)
        layout = QtWidgets.QVBoxLayout()
        self.setLayout(layout)

        self.label = QtWidgets.QLabel()
        layout.addWidget(self.label)

        self.input = QtWidgets.QSlider(Qt.Orientation.Horizontal)
        self.input.setRange(0, 100)
        self.input.valueChanged.connect(self.on_value_changed)
        self.input.setValue(value)
        self.on_value_changed(value)
        layout.addWidget(self.input)

        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok |
            QtWidgets.QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.show()

    def on_value_changed(self, value):
        self.label.setText(self.tr('Window opacity: %s%%') % value)
        self.set_opacity(value / 100)

    def accept(self):
        self.previous_opacity = self.input.value() / 100
        self.buzz_settings.setValue(
            'View/window_opacity', self.previous_opacity)
        return super().accept()

    def reject(self):
        self.set_opacity(self.previous_opacity)
        return super().reject()


class BuzzNotification(QtWidgets.QWidget):
    def __init__(self, parent, text):
        super().__init__(parent)
        self.label = QtWidgets.QLabel(text)
        self.setObjectName('BuzzNotification')
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAutoFillBackground(True)
        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(self.label)
        self.setLayout(layout)
        color = constants.COLORS['Active:Window']
        self.setStyleSheet(
            f'background-color: rgba({color[0]}, {color[1]}, {color[2]}, 0.9);'
            'padding: 0.7em;'
            'border-radius: 5px;')
        self.show()
        # We only get own width after showing it;
        # updateGeometry doesn't work on hidden widgets
        x = (parent.width() - self.width()) / 2
        self.move(int(x), 10)

        QtCore.QTimer.singleShot(1000 * 3, self.deleteLater)


class SampleColorWidget(QtWidgets.QWidget):

    OFFSET = 10  # Offset from mouse pointer
    SIZE = 50
    NONE_COLOR = QtGui.QColor(0, 0, 0, 0)

    def __init__(self, parent, pos, color):
        super().__init__(parent)
        self.color = color
        self.set_pos(pos)
        self.show()

    def set_pos(self, pos):
        self.setGeometry(int(pos.x() + self.OFFSET),
                         int(pos.y() + self.OFFSET),
                         self.SIZE, self.SIZE)

    def paintEvent(self, event):
        color = self.color if self.color else self.NONE_COLOR
        painter = QtGui.QPainter(self)
        painter.setBrush(QtGui.QBrush(color))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRect(0, 0, self.SIZE, self.SIZE)

    def update(self, pos, color):
        self.set_pos(pos)
        self.color = color
        self.repaint()


class ExportImagesFileExistsDialog(QtWidgets.QDialog):

    def __init__(self, parent, filename):
        super().__init__(parent)
        self.setWindowTitle(self.tr('File exists'))

        layout = QtWidgets.QVBoxLayout()
        self.setLayout(layout)

        label = QtWidgets.QLabel(
            self.tr('File already exists:') + f'\n{filename}')
        layout.addWidget(label)

        choices = (('skip', self.tr('Skip this file')),
                   ('skip_all', self.tr('Skip all existing files')),
                   ('overwrite', self.tr('Overwrite this file')),
                   ('overwrite_all', self.tr('Overwrite all existing files')))

        self.radio_buttons = {}
        for (value, label) in choices:
            btn = QtWidgets.QRadioButton(label)
            self.radio_buttons[value] = btn
            layout.addWidget(btn)
        self.radio_buttons['skip'].setChecked(True)

        # Bottom row of buttons
        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok
            | QtWidgets.QDialogButtonBox.StandardButton.Cancel)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)

    def get_answer(self):
        for value, btn in self.radio_buttons.items():
            if btn.isChecked():
                return value
