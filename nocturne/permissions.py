from rest_framework.permissions import BasePermission


class NocturneViewPermission(BasePermission):
    """Tier 1 (superuser) or Tier 2 (has nocturne.view_nocturne) — read operations."""

    message = "Nocturne: requires superuser or 'nocturne.view_nocturne' permission."

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return request.user.is_superuser or request.user.has_perm("nocturne.view_nocturne")


class NocturneAdminPermission(BasePermission):
    """Tier 1 (superuser) only — mutating / privileged operations."""

    message = "Nocturne: superuser access required."

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return bool(request.user.is_superuser)


# Backwards-compat alias kept so any third-party code importing NocturnePermission
# still resolves to the view-level class (least-surprise default).
NocturnePermission = NocturneViewPermission
