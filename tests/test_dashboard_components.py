import pathlib


def test_copilot_v2_component_exists():
    path = pathlib.Path('dashboard_ui/components/CopilotV2.tsx')
    text = path.read_text()
    assert 'export default function' in text


def test_export_panel_component_exists():
    path = pathlib.Path('dashboard_ui/components/ExportPanel.tsx')
    text = path.read_text()
    assert 'export default function' in text
