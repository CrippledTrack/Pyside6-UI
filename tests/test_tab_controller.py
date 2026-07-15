import unittest
from unittest.mock import Mock

from app.ui.controllers.tab_controller import TabController


class TabControllerTests(unittest.TestCase):
    def test_remove_tab_keeps_shared_plugin_instance_loaded(self) -> None:
        tab_widget = Mock()
        tab_widget.count.return_value = 1
        tab_widget.tabText.return_value = "Multi Extension Plugin"
        tab_widget.currentChanged.connect = Mock()
        widget = tab_widget.widget.return_value

        plugin_instance = Mock()
        registry = Mock()
        registry.get_plugin_instance.return_value = plugin_instance

        controller = TabController(
            tab_widget=tab_widget,
            admin_service=Mock(),
            daemon_service=None,
            registry=registry,
            plugin_service=Mock(),
        )
        controller.loaded_tabs["Multi Extension Plugin"] = {
            "instance": widget,
            "plugin_class": object,
        }

        controller.remove_tab("Multi Extension Plugin")

        plugin_instance.on_tab_deactivated.assert_called_once_with()
        widget.close.assert_called_once_with()
        widget.deleteLater.assert_called_once_with()
        registry.unload_plugin_instance.assert_not_called()
        self.assertNotIn("Multi Extension Plugin", controller.loaded_tabs)


if __name__ == "__main__":
    unittest.main()
