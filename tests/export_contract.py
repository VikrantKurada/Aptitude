def assert_exporter_contract(exporter, draft, tmp_path):
    paths = exporter.export(draft, tmp_path)
    assert paths and all(p.exists() for p in paths)
    return paths
