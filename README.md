# Sentinella Butter Burger

Controlla ogni 5 minuti circa la disponibilità dei tavoli per 2 persone da Butter Burger (Pomigliano d'Arco), da oggi ai prossimi 7 giorni, turni dalle 19:30 alle 22:30, e manda un avviso (ntfy + email) solo quando si libera un tavolo.

- Impostazioni: in cima a `butterburger_sentinella.py`.
- Segreto richiesto: `NTFY_TOPIC`. Quando trova un tavolo, la run termina "fallita" apposta: così GitHub manda anche una email all'indirizzo dell'account.
- Per fermarla: Actions → Sentinella Butter Burger → "…" → Disable workflow.
