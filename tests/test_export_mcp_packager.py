import json, zipfile
from aptitude.models import SkillDraft, ToolSpec
from aptitude.export.mcp_manifest import McpManifestExporter
from aptitude.export.packager import ZipPackager

def test_mcp_manifest_only_when_tools(tmp_path):
    no_tools = SkillDraft(name="s", description="d", body="b")
    assert McpManifestExporter().export(no_tools, tmp_path) == []
    with_tools = SkillDraft(name="s", description="d", body="b",
                            tools=[ToolSpec("run", "runs it", {"type": "object"})])
    paths = McpManifestExporter().export(with_tools, tmp_path)
    data = json.loads(paths[0].read_text())
    assert data["tools"][0]["name"] == "run"

def test_zip_packager_bundles_skill(tmp_path):
    draft = SkillDraft(name="s", description="d", body="b")
    paths = ZipPackager().export(draft, tmp_path)
    assert paths[0].suffix == ".zip"
    with zipfile.ZipFile(paths[0]) as z:
        assert any(n.endswith("SKILL.md") for n in z.namelist())
