"""Rollback esplicito quando un'operazione di servizio fallisce a metà.

I router trasformano un errore di dominio (``AuthError``) in una normale risposta JSON
4xx: per FastAPI la richiesta è riuscita e ``get_db_session`` fa commit di tutto ciò che
l'operazione aveva già scritto. Un servizio che scrive e poi può sollevare (es. assegna
lo slot e poi scopre che i crediti non bastano) deve quindi annullare da sé le modifiche.
"""

from __future__ import annotations

import functools
from collections.abc import Callable
from typing import Any

from auth.exceptions import AuthError


def rollback_on_error[F: Callable[..., Any]](method: F) -> F:
    """Decorator per metodi di servizio con ``self._session``: su ``AuthError`` annulla la
    transazione e rilancia, così nulla di parziale viene salvato dal commit del router."""

    @functools.wraps(method)
    def wrapper(self: Any, *args: Any, **kwargs: Any) -> Any:
        try:
            return method(self, *args, **kwargs)
        except AuthError:
            self._session.rollback()
            raise

    return wrapper  # type: ignore[return-value]
