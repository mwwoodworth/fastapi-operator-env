import pathlib


def test_copilot_v2_component_exists():
    path = pathlib.Path('dashboard_ui/components/CopilotV2.tsx')
    text = path.read_text()
    assert 'export default function' in text


def test_export_panel_component_exists():
    path = pathlib.Path('dashboard_ui/components/ExportPanel.tsx')
    text = path.read_text()
    assert 'export default function' in text


def test_assistant_chat_widget_exists():
    path = pathlib.Path('dashboard_ui/components/AssistantChatWidget.tsx')
    text = path.read_text()
    assert 'export default function' in text


def test_assistant_chat_api_route_exists():
    path = pathlib.Path('dashboard_ui/app/api/assistant/chat/route.ts')
    text = path.read_text()
    assert 'async function POST' in text


def test_pipeline_component_exists():
    path = pathlib.Path('dashboard_ui/components/ClaudePipeline.tsx')
    assert path.exists()


def test_products_page_exists():
    path = pathlib.Path('dashboard_ui/app/dashboard/products/page.tsx')
    assert path.exists()


def test_ops_page_exists():
    path = pathlib.Path('dashboard_ui/app/dashboard/ops/page.tsx')
    assert path.exists()
