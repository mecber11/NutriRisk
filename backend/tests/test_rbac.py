"""Pruebas de la matriz RBAC."""

from __future__ import annotations

from app.core.rbac import (
    ROLE_PERMISSIONS,
    Action,
    Module,
    RoleCode,
    allowed_modules,
    has_permission,
    module_for_path,
    permissions_for_role,
)


def test_admin_has_every_permission():
    for action in Action:
        assert has_permission(RoleCode.ADMIN, Module.USERS, action.value) is True


def test_auditor_is_read_only():
    assert has_permission(RoleCode.AUDITOR, Module.AUDIT, "read") is True
    assert has_permission(RoleCode.AUDITOR, Module.AUDIT, "export") is True
    assert has_permission(RoleCode.AUDITOR, Module.DATASETS, "create") is False
    assert has_permission(RoleCode.AUDITOR, Module.MODELS, "execute") is False
    assert has_permission(RoleCode.AUDITOR, Module.USERS, "read") is False


def test_analyst_can_generate_reports_but_not_manage_users():
    assert has_permission(RoleCode.PUBLIC_HEALTH_ANALYST, Module.REPORTS, "create") is True
    assert has_permission(RoleCode.PUBLIC_HEALTH_ANALYST, Module.USERS, "read") is False
    assert has_permission(RoleCode.PUBLIC_HEALTH_ANALYST, Module.DATASETS, "create") is False


def test_scientist_can_train_and_export():
    assert has_permission(RoleCode.DATA_SCIENTIST, Module.EXPERIMENTS, "execute") is True
    assert has_permission(RoleCode.DATA_SCIENTIST, Module.XAI, "execute") is True
    assert has_permission(RoleCode.DATA_SCIENTIST, Module.USERS, "create") is False


def test_manager_has_dashboard_and_reports():
    assert has_permission(RoleCode.MANAGER, Module.DASHBOARD, "read") is True
    assert has_permission(RoleCode.MANAGER, Module.REPORTS, "create") is True
    assert has_permission(RoleCode.MANAGER, Module.EXPERIMENTS, "create") is False


def test_all_roles_declared_in_matrix():
    for role in RoleCode:
        assert role.value in ROLE_PERMISSIONS


def test_allowed_modules_serializable():
    matrix = allowed_modules(RoleCode.AUDITOR)
    assert "audit" in matrix
    assert "read" in matrix["audit"]


def test_permissions_for_role_copies_sets():
    permissions = permissions_for_role(RoleCode.MANAGER)
    permissions["dashboard"].add("delete")
    assert has_permission(RoleCode.MANAGER, Module.DASHBOARD, "delete") is False


def test_module_for_path_resolution():
    assert module_for_path("/api/v1/dashboard/overview") == "dashboard"
    assert module_for_path("/api/v1/audit/logs") == "audit"
    assert module_for_path("/api/v1/datasets/upload") == "datasets"
    assert module_for_path("/api/v1/unknown/path") == "system"
