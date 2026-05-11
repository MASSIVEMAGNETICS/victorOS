"""
Tests for vos_apps
"""
from vos_apps import load_registry

def test_load_registry_loads_all_apps():
    apps = load_registry()
    assert len(apps) == 6
    app_ids = {app.id for app in apps}
    assert app_ids == {
        "meta_forge",
        "rollout_engine",
        "creative_core",
        "synth_mind",
        "audit_vault",
        "admin_portal"
    }

def test_app_meta_structure():
    apps = load_registry()
    for app in apps:
        assert hasattr(app, "id") and isinstance(app.id, str)
        assert hasattr(app, "name") and isinstance(app.name, str)
        assert hasattr(app, "icon") and isinstance(app.icon, str)
        assert hasattr(app, "tagline") and isinstance(app.tagline, str)
        assert hasattr(app, "category") and isinstance(app.category, str)
        assert app.category in {"creator", "system"}
        assert callable(app.render)
