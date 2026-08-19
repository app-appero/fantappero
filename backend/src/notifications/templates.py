"""Versioned in-app notification template registry (EP09-01).

Each template is keyed by ``(template_key, template_version)`` so a stored
notification always renders the same content it was created with, even if a
newer template version is registered later. EP09-02/03/04 add their own
templates here as they wire real triggers (kickoff reminders, market/result
events); EP09-01 only ships the registry itself plus one generic system
template used to exercise the platform end-to-end.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

NotificationParams = dict[str, object]


@dataclass(frozen=True)
class NotificationContent:
    title: str
    body: str
    deep_link: str | None = None


NotificationRenderer = Callable[[NotificationParams], NotificationContent]

_TEMPLATES: dict[tuple[str, int], NotificationRenderer] = {}


def register_template(
    template_key: str, version: int
) -> Callable[[NotificationRenderer], NotificationRenderer]:
    def _decorator(renderer: NotificationRenderer) -> NotificationRenderer:
        _TEMPLATES[(template_key, version)] = renderer
        return renderer

    return _decorator


def render_notification(
    template_key: str, template_version: int, params: NotificationParams
) -> NotificationContent:
    renderer = _TEMPLATES.get((template_key, template_version))
    if renderer is None:
        msg = f"Nessun template registrato per {template_key} v{template_version}"
        raise KeyError(msg)
    return renderer(params)


@register_template("sistema.generico", 1)
def _render_sistema_generico(params: NotificationParams) -> NotificationContent:
    title = str(params.get("title", "Notifica"))
    body = str(params.get("body", ""))
    deep_link = params.get("deep_link")
    return NotificationContent(
        title=title,
        body=body,
        deep_link=str(deep_link) if deep_link is not None else None,
    )


@register_template("formazione.scadenza_turno", 1)
def _render_formazione_scadenza_turno(params: NotificationParams) -> NotificationContent:
    round_number = params.get("round_number")
    cutoff_local = params.get("cutoff_local")
    return NotificationContent(
        title="Scadenza formazione in arrivo",
        body=(
            f"Il turno {round_number} chiude alle {cutoff_local}. "
            "Salva la formazione prima del fischio d'inizio."
        ),
        deep_link="/formazione",
    )
