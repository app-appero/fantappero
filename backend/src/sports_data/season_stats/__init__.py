"""Storico stagionale dei calciatori (release 1.3).

Una riga per calciatore + stagione + club + competizione:

- stagioni passate (2024/25 e 2025/26) dal fornitore, scaricate una volta
  (``provider_import``) dall'endpoint aggregato ``/players``;
- stagione in corso (e le prossime) dai dati di FantApperò (``current_season``):
  statistiche per partita e voti nostri, materializzate dopo ogni giornata.

Vedi ``docs/operations/valore_di_mercato_e_storico.md``.
"""
