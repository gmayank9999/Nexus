from typing import ClassVar

from app.tools.base import PermissionLevel


class PermissionPolicy:
    _automatic: ClassVar[frozenset[PermissionLevel]] = frozenset(
        {PermissionLevel.READ_ONLY, PermissionLevel.WRITE_LOCAL}
    )

    def allows(self, level: PermissionLevel, *, approved: bool = False) -> bool:
        if level == PermissionLevel.DANGEROUS:
            return False
        return level in self._automatic or approved

    def requires_approval(self, level: PermissionLevel) -> bool:
        return level == PermissionLevel.EXTERNAL_ACTION
