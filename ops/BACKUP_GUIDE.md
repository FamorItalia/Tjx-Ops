# Backup Giornaliero TJX Ops Hub

## Cosa salva
- Database completo SQLite (`backend/data/tjx_operativita.db` o path da `.env`)
- Snapshot CSV delle tabelle principali:
  - `customer_orders`, `customer_order_lines`
  - `purchase_orders`, `purchase_order_lines`
  - `packing_lists`, `packing_list_lines`
  - `suppliers`, `products`, `distribution_centers`
- Registro Excel dei PDF ordini ricevuti (tracciamento percorso file + esistenza attuale)
- Anagrafiche e documenti anagrafiche da `TEMPLATES/ANAGRAFICHE`
- Output generati (`backend/output` e, se presente, `frontend/public/output`)

## Dove salva
- Cartella progetto: `BACKUPS\YYYYMMDD_HHMMSS\...`
- Ogni run contiene:
  - `db\tjx_operativita.sqlite3`
  - `snapshot\*.csv`
  - `received_order_pdf_registry.xlsx`
  - `master_data\ANAGRAFICHE\`
  - `output\...`
  - `snapshot_manifest.json`
  - `backup_manifest.json`

## Avvio manuale backup (subito)
Da PowerShell, nella cartella `ops`:

```powershell
powershell -ExecutionPolicy Bypass -File .\backup-daily.ps1
```

## Attivare backup automatico giornaliero
Esempio ore 19:00:

```powershell
powershell -ExecutionPolicy Bypass -File .\setup-backup-task.ps1 -RunAt "19:00"
```

## Disattivare backup automatico
```powershell
powershell -ExecutionPolicy Bypass -File .\remove-backup-task.ps1
```

## Retention (pulizia automatica)
- Default: conserva 180 giorni.
- Per cambiare:

```powershell
powershell -ExecutionPolicy Bypass -File .\backup-daily.ps1 -RetentionDays 365
```

## Ripristino rapido (continuita operativa)
1. Scegli una cartella backup in `BACKUPS\...`.
2. Copia `db\tjx_operativita.sqlite3` in `backend/data/tjx_operativita.db` (a servizi spenti).
3. Se l'app non e disponibile, usa:
   - `snapshot\*.csv` per storico ordini e righe
   - `received_order_pdf_registry.xlsx` per rintracciare ogni PDF sorgente
   - `master_data\ANAGRAFICHE\` per anagrafiche
4. Riavvia servizi TJX.
