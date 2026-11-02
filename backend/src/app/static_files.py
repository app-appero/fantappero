"""File statici serviti dall'API."""

from __future__ import annotations

from fastapi import HTTPException
from starlette.staticfiles import StaticFiles
from starlette.types import Scope


class FlatStaticFiles(StaticFiles):
    """Serve solo i file nella radice della cartella, mai le sottocartelle.

    Nel volume degli avatar convivono cartelle private (es. gli allegati delle
    segnalazioni utente): un avatar è sempre `<user_id>.<ext>`, quindi qualunque
    percorso con una sottocartella (o nascosto) non deve mai essere raggiungibile
    da fuori.
    """

    async def get_response(self, path: str, scope: Scope):  # type: ignore[no-untyped-def]
        if "/" in path.strip("/") or "\\" in path or path.startswith("."):
            raise HTTPException(status_code=404)
        return await super().get_response(path, scope)
