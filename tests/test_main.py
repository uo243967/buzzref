from unittest.mock import patch, MagicMock

from PyQt6 import QtCore

from buzzref.__main__ import BuzzRefMainWindow, main
from buzzref.actions import get_actions
from buzzref.assets import BuzzAssets
from buzzref.view import BuzzGraphicsView


@patch('PyQt6.QtWidgets.QWidget.show')
def test_buzzref_mainwindow_init(show_mock, qapp):
    window = BuzzRefMainWindow(qapp)
    assert window.windowTitle() == 'BuzzRef'
    assert BuzzAssets().logo == BuzzAssets().logo
    assert window.windowIcon()
    assert window.contentsMargins() == QtCore.QMargins(0, 0, 0, 0)
    assert isinstance(window.view, BuzzGraphicsView)
    show_mock.assert_called()


def test_buzzref_mainwindow_creates_input_transparent_overlay(main_window):
    main_window.view.welcome_overlay.hide()
    main_window.set_input_overlay(True)
    assert main_window.isMinimized()
    assert main_window.input_overlay is not None
    assert main_window.input_overlay.windowFlags() & (
        QtCore.Qt.WindowType.WindowTransparentForInput)
    assert main_window.input_overlay.windowFlags() & (
        QtCore.Qt.WindowType.WindowStaysOnTopHint)
    assert main_window.input_overlay.geometry() == QtCore.QRect(
        main_window.mapToGlobal(QtCore.QPoint(0, 0)), main_window.size())


def test_buzzref_mainwindow_removes_input_transparent_overlay(main_window):
    main_window.view.welcome_overlay.hide()
    main_window.set_input_overlay(True)
    main_window.set_input_overlay(False)
    assert main_window.input_overlay is None
    assert main_window.isVisible()


def test_buzzref_mainwindow_restores_when_application_becomes_active(
        main_window):
    main_window.view.welcome_overlay.hide()
    main_window.set_input_overlay(True)
    main_window.view.transparent_to_mouse_events = True

    main_window.on_application_state_changed(
        QtCore.Qt.ApplicationState.ApplicationActive)

    assert main_window.input_overlay is None
    assert not main_window.view.transparent_to_mouse_events
    assert not get_actions()['transparent_to_mouse_events'].qaction.isChecked()


def test_buzzref_mainwindow_restores_when_window_is_activated(main_window):
    main_window.view.welcome_overlay.hide()
    main_window.set_input_overlay(True)
    main_window.view.transparent_to_mouse_events = True
    ignore_action = get_actions()['transparent_to_mouse_events'].qaction
    ignore_action.setChecked(True)

    main_window.event(QtCore.QEvent(QtCore.QEvent.Type.WindowActivate))

    assert main_window.input_overlay is None
    assert not main_window.view.transparent_to_mouse_events
    assert not ignore_action.isChecked()


@patch('buzzref.view.BuzzGraphicsView.open_from_file')
def test_buzzrefapplication_fileopenevent(open_mock, qapp, main_window):
    event = MagicMock()
    event.type.return_value = QtCore.QEvent.Type.FileOpen
    event.file.return_value = 'test.bee'
    assert qapp.event(event) is True
    open_mock.assert_called_once_with('test.bee')


@patch('buzzref.__main__.BuzzRefApplication')
@patch('buzzref.__main__.CommandlineArgs')
@patch('buzzref.config.BuzzSettings.on_startup')
def test_main(startup_mock, args_mock, app_mock, qapp):
    app_mock.return_value = qapp
    args_mock.return_value.filename = None
    args_mock.return_value.loglevel = 'WARN'
    args_mock.return_value.debug_raise_error = ''

    with patch.object(qapp, 'exec') as exec_mock:
        main()
        exec_mock.assert_called_once_with()

    args_mock.assert_called_once_with(with_check=True)
    startup_mock.assert_called()
