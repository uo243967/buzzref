from unittest.mock import patch, MagicMock

from PyQt6 import QtCore, QtWidgets, QtGui
from PyQt6.QtCore import Qt

from buzzref import commands
from buzzref.config import logfile_name
from buzzref.widgets import (
    BuzzNotification,
    ChangeOpacityDialog,
    DebugLogDialog,
    ExportImagesFileExistsDialog,
    ImagesDialog,
    SampleColorWidget,
    SceneToPixmapExporterDialog,
)


def test_debug_log_dialog(qtbot, settings, view):
    with open(logfile_name(), 'w') as f:
        f.write('my log output')

    dialog = DebugLogDialog(view)
    dialog.show()
    qtbot.addWidget(dialog)
    assert dialog.log.toPlainText() == 'my log output'
    qtbot.mouseClick(dialog.copy_button, Qt.MouseButton.LeftButton)
    clipboard = QtWidgets.QApplication.clipboard()
    assert clipboard.text() == 'my log output'


def test_scene_to_pixmap_exporter_dialog_sets_defaults(view):
    dlg = SceneToPixmapExporterDialog(view, QtCore.QSize(1200, 1600))
    assert dlg.width_input.value() == 1200
    assert dlg.height_input.value() == 1600
    assert dlg.value() == QtCore.QSize(1200, 1600)


def test_scene_to_pixmap_exporter_dialog_sets_defaults_when_too_large(view):
    dlg = SceneToPixmapExporterDialog(view, QtCore.QSize(120000, 160000))
    assert dlg.width_input.value() == 75000
    assert dlg.height_input.value() == 100000
    assert dlg.value() == QtCore.QSize(75000, 100000)


def test_scene_to_pixmap_exporter_dialog_updates_height(view):
    dlg = SceneToPixmapExporterDialog(view, QtCore.QSize(1200, 1600))
    dlg.width_input.setValue(600)
    assert dlg.height_input.value() == 800
    assert dlg.value() == QtCore.QSize(600, 800)


def test_scene_to_pixmap_exporter_dialog_updates_width(view):
    dlg = SceneToPixmapExporterDialog(view, QtCore.QSize(1200, 1600))
    dlg.height_input.setValue(160)
    assert dlg.width_input.value() == 120
    assert dlg.value() == QtCore.QSize(120, 160)


def test_change_opacity_dialog_init(view, item):
    item.setOpacity(0.6)
    stack = QtGui.QUndoStack()
    dlg = ChangeOpacityDialog(view, [item], stack)
    assert dlg.input.value() == 60
    assert dlg.label.text() == 'Opacity: 60%'


def test_change_opacity_dialog_live_update(view, item):
    item.setOpacity(0.6)
    stack = QtGui.QUndoStack()
    dlg = ChangeOpacityDialog(view, [item], stack)
    dlg.input.setValue(30)
    assert dlg.label.text() == 'Opacity: 30%'
    assert item.opacity() == 0.3


def test_change_opacity_dialog_accept(view, item):
    item.setOpacity(0.6)
    stack = QtGui.QUndoStack()
    dlg = ChangeOpacityDialog(view, [item], stack)
    dlg.input.setValue(30)
    dlg.accept()
    assert item.opacity() == 0.3
    assert len(stack) == 1


def test_change_opacity_dialog_accept_when_no_items(view):
    stack = QtGui.QUndoStack()
    dlg = ChangeOpacityDialog(view, [], stack)
    assert dlg.input.value() == 100
    dlg.input.setValue(30)
    dlg.accept()
    assert len(stack) == 0


def test_change_opacity_dialog_reject(view, item):
    item.setOpacity(0.6)
    stack = QtGui.QUndoStack()
    dlg = ChangeOpacityDialog(view, [item], stack)
    dlg.input.setValue(30)
    dlg.reject()
    assert item.opacity() == 0.6
    assert len(stack) == 0


def test_images_dialog_can_unload_and_reload_multiple_images(view, qtbot):
    images = []
    for loaded in (True, True, False):
        image = MagicMock(
            filename=f'image-{len(images)}.png',
            image_loaded=loaded,
            save_id=len(images),
            image_source='scene.bee',
        )
        image.unload_image.return_value = loaded
        image.reload_image.return_value = not loaded
        images.append(image)

    scene = MagicMock()
    scene.items_by_type.return_value = images
    dialog = ImagesDialog(view, scene)

    dialog.image_grid.selectRow(0)
    dialog.image_grid.selectionModel().select(
        dialog.image_grid.model().index(1, 0),
        QtCore.QItemSelectionModel.SelectionFlag.Select
        | QtCore.QItemSelectionModel.SelectionFlag.Rows)
    assert dialog.unload_button.isEnabled()
    dialog.unload_current()
    qtbot.waitUntil(lambda: images[0].unload_image.called)
    command = scene.undo_stack.push.call_args.args[0]
    assert isinstance(command, commands.ChangeImageLoadState)
    images[0].unload_image.assert_called_once_with()
    images[1].unload_image.assert_called_once_with()

    dialog.image_grid.clearSelection()
    dialog.image_grid.selectRow(2)
    with patch('buzzref.fileio.load_image_data', return_value=b'data'):
        dialog.reload_current()
        qtbot.waitUntil(lambda: images[2].reload_image.called)
    command = scene.undo_stack.push.call_args.args[0]
    assert isinstance(command, commands.ChangeImageLoadState)
    images[2].reload_image.assert_called_once_with(b'data')


def test_images_dialog_filters_by_filename_and_status(view):
    images = []
    for filename, loaded in (('alpha.png', True), ('beta.png', False)):
        image = MagicMock(
            filename=filename,
            image_loaded=loaded,
            save_id=1,
            image_source='scene.bee',
        )
        images.append(image)

    scene = MagicMock()
    scene.items_by_type.return_value = images
    dialog = ImagesDialog(view, scene)

    dialog.filename_filter.setText('alpha')
    assert dialog.image_grid.rowCount() == 1
    assert dialog.image_grid.item(0, 1).text() == 'alpha.png'

    dialog.filename_filter.clear()
    dialog.status_filter.setCurrentIndex(2)
    assert dialog.image_grid.rowCount() == 1
    assert dialog.image_grid.item(0, 1).text() == 'beta.png'


def test_images_dialog_name_column_is_sortable_and_filterable(view):
    images = []
    for filename in ('/tmp/zeta.png', '/tmp/alpha.png'):
        image = MagicMock(
            filename=filename,
            image_loaded=True,
            save_id=1,
            image_source='scene.bee',
        )
        images.append(image)

    scene = MagicMock()
    scene.items_by_type.return_value = images
    dialog = ImagesDialog(view, scene)

    assert dialog.image_grid.columnCount() == 3
    assert dialog.image_grid.horizontalHeaderItem(0).text() == 'Name'
    dialog.image_grid.sortItems(0, QtCore.Qt.SortOrder.AscendingOrder)
    assert dialog.image_grid.item(0, 0).text() == 'alpha.png'
    dialog.filename_filter.setText('zeta.png')
    assert dialog.image_grid.rowCount() == 1
    assert dialog.image_grid.item(0, 0).text() == 'zeta.png'


def test_images_dialog_filters_by_name(view):
    images = []
    for filename in ('/tmp/alpha.png', '/tmp/beta.png'):
        images.append(MagicMock(
            filename=filename,
            image_loaded=True,
            save_id=1,
            image_source='scene.bee',
        ))

    scene = MagicMock()
    scene.items_by_type.return_value = images
    dialog = ImagesDialog(view, scene)

    dialog.name_filter.setText('beta')

    assert dialog.image_grid.rowCount() == 1
    assert dialog.image_grid.item(0, 0).text() == 'beta.png'


def test_images_dialog_paginates_images(view):
    images = [
        MagicMock(
            filename=f'image-{index:03}.png',
            image_loaded=True,
            save_id=index,
            image_source='scene.bee',
        )
        for index in range(3)
    ]
    scene = MagicMock()
    scene.items_by_type.return_value = images
    dialog = ImagesDialog(view, scene)
    dialog.page_size = 2
    dialog.refresh()

    assert dialog.image_grid.rowCount() == 2
    assert dialog.page_number_input.value() == 1
    assert dialog.page_label.text() == 'of 2'
    assert dialog.previous_page_button.isEnabled() is False
    assert dialog.next_page_button.isEnabled() is True

    dialog.next_page()
    assert dialog.image_grid.rowCount() == 1
    assert dialog.page_number_input.value() == 2
    assert dialog.page_label.text() == 'of 2'
    assert dialog.previous_page_button.isEnabled() is True
    assert dialog.next_page_button.isEnabled() is False


def test_images_dialog_page_size_is_customizable(view):
    images = [
        MagicMock(
            filename=f'image-{index:03}.png',
            image_loaded=True,
            save_id=index,
            image_source='scene.bee',
        )
        for index in range(3)
    ]
    scene = MagicMock()
    scene.items_by_type.return_value = images
    dialog = ImagesDialog(view, scene)

    dialog.page_size_input.setValue(1)

    assert dialog.page_size == 1
    assert dialog.image_grid.rowCount() == 1
    assert dialog.page_number_input.value() == 1
    assert dialog.page_label.text() == 'of 3'


def test_images_dialog_can_set_page_number(view):
    images = [
        MagicMock(
            filename=f'image-{index:03}.png',
            image_loaded=True,
            save_id=index,
            image_source='scene.bee',
        )
        for index in range(3)
    ]
    scene = MagicMock()
    scene.items_by_type.return_value = images
    dialog = ImagesDialog(view, scene)
    dialog.page_size_input.setValue(1)

    dialog.page_number_input.setValue(3)

    assert dialog.current_page == 2
    assert dialog.image_grid.item(0, 0).text() == 'image-002.png'


@patch('PyQt6.QtCore.QTimer.singleShot')
def test_bee_notification(single_shot_mock, view):
    widget = BuzzNotification(view, 'Hello World')
    assert widget.label.text() == 'Hello World'
    single_shot_mock.assert_called_once_with(1000 * 3, widget.deleteLater)


def test_sample_color_widget(view):
    widget = SampleColorWidget(
        view, QtCore.QPoint(2, 5), QtGui.QColor(255, 0, 0))
    assert widget.color == QtGui.QColor(255, 0, 0)
    assert widget.geometry() == QtCore.QRect(12, 15, 50, 50)

    widget.update(QtCore.QPoint(13, 15), QtGui.QColor(0, 255, 0))
    assert widget.color == QtGui.QColor(0, 255, 0)
    assert widget.geometry() == QtCore.QRect(23, 25, 50, 50)


def test_sample_color_widget_paint_event_when_color(view):
    widget = SampleColorWidget(
        view, QtCore.QPoint(2, 5), QtGui.QColor(255, 0, 0))
    with patch('PyQt6.QtGui.QPainter') as painter_cls_mock:
        painter_mock = MagicMock()
        painter_cls_mock.return_value = painter_mock
        widget.paintEvent(MagicMock())
        brush = QtGui.QBrush(QtGui.QColor(255, 0, 0))
        painter_mock.setBrush.assert_called_once_with(brush)
        painter_mock.drawRect.assert_called_once_with(0, 0, 50, 50)


def test_sample_color_widget_paint_event_when_no_color(view):
    widget = SampleColorWidget(view, QtCore.QPoint(2, 5), None)
    with patch('PyQt6.QtGui.QPainter') as painter_cls_mock:
        painter_mock = MagicMock()
        painter_cls_mock.return_value = painter_mock
        widget.paintEvent(MagicMock())
        brush = QtGui.QBrush(QtGui.QColor(0, 0, 0, 0))
        painter_mock.setBrush.assert_called_once_with(brush)
        painter_mock.drawRect.assert_called_once_with(0, 0, 50, 50)


def test_export_images_file_exists_dialog(view):
    dlg = ExportImagesFileExistsDialog(view, '/tmp/foo.png')
    assert len(dlg.radio_buttons) == 4
    assert dlg.get_answer() == 'skip'


def test_export_images_file_exists_dialog_get_answer(view):
    dlg = ExportImagesFileExistsDialog(view, '/tmp/foo.png')
    dlg.radio_buttons['overwrite'].setChecked(True)
    assert dlg.get_answer() == 'overwrite'
