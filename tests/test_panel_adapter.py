import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools/sync_omarchy_panels.py"
SPEC = importlib.util.spec_from_file_location("sync_omarchy_panels", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class PanelAdapterTests(unittest.TestCase):
    def test_generated_panels_use_inline_hosts_without_ipc_conflicts(self):
        for panel_name in MODULE.PANELS:
            with self.subTest(panel=panel_name):
                panel = (MODULE.DESTINATION_ROOT / panel_name / "Panel.qml").read_text()
                self.assertIn("Item {\n  id: root", panel)
                self.assertNotIn("  BarIconButton {", panel)
                self.assertNotIn("  KeyboardPanel {", panel)
                self.assertNotIn("  IpcHandler {", panel)
                self.assertIn("anchors.fill: parent", panel)
                self.assertRegex(panel, r"id: (panelColumn|column)\n\s+height: childrenRect.height")

    def test_generated_directories_declare_local_qml_types(self):
        for panel_name in MODULE.PANELS:
            with self.subTest(panel=panel_name):
                panel_directory = MODULE.DESTINATION_ROOT / panel_name
                declarations = (panel_directory / "qmldir").read_text()
                for qml_path in panel_directory.glob("*.qml"):
                    self.assertIn(f"{qml_path.stem} 1.0 {qml_path.name}", declarations)

    def test_network_custom_close_is_preserved(self):
        network = (MODULE.DESTINATION_ROOT / "network/Panel.qml").read_text()
        self.assertEqual(network.count("  function close() {"), 1)
        self.assertIn("cancelPasswordPrompt()", network)

    def test_panel_page_does_not_shadow_item_data(self):
        panel_page = (ROOT / "standalone/pages/BuiltinPanelPage.qml").read_text()
        self.assertNotIn("property var data:", panel_page)


if __name__ == "__main__":
    unittest.main()
