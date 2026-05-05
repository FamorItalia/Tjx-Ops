# TJX Ops Hub

Console operativa interna per gestione ordini TJX: import PDF ordine cliente, gestione operativa quantità, ordine fornitore, packing list, documenti export, anagrafiche e inventario.

## Start Here
- Documento tecnico completo (handover): [TECHNICAL_HANDOVER_TJX_OPS_HUB.md](C:\Progetti\Tjx operatività\TECHNICAL_HANDOVER_TJX_OPS_HUB.md)
- Runbook ufficio: [ops/README_UFFICIO.md](C:\Progetti\Tjx operatività\ops\README_UFFICIO.md)

## Architettura (breve)
- Frontend: Next.js (`frontend/`) su porta `3001`
- Backend: FastAPI (`backend/`) su porta `8000`
- DB: SQLite locale
- Template/documenti: `TEMPLATES/`
- Script operativi Windows: `ops/`

## Prerequisiti
- Windows 10/11
- Node.js + npm
- Python con virtualenv backend già predisposto in `backend/.venv`

## Avvio rapido (operativo)
Da PowerShell:

```powershell
cd "C:\Progetti\Tjx operatività\ops"
powershell -ExecutionPolicy Bypass -File .\start-now.ps1
powershell -ExecutionPolicy Bypass -File .\check-services.ps1
```

URL:
- Frontend: [http://localhost:3001/login](http://localhost:3001/login)
- Backend health: [http://127.0.0.1:8000/api/v1/health](http://127.0.0.1:8000/api/v1/health)

## Riavvio robusto (senza reboot PC)
```powershell
cd "C:\Progetti\Tjx operatività\ops"
powershell -ExecutionPolicy Bypass -File .\restart-services.ps1
```

## Flusso ordine (essenziale)
1. Import PDF ordine cliente (`/import/new`).
2. Verifica e correzione quantità operative in dettaglio ordine (`/orders/[id]`).
3. Genera ordine fornitore.
4. Invia ordine a fornitore (mail precompilata).
5. Genera/controlla packing list per DC.
6. Genera e scarica documenti export necessari.

## Funzionalità email fornitore
- Pulsante `Invia ordine a fornitore` in dettaglio ordine.
- To da anagrafica fornitore, Cc include `operations@famoritalia.com`.
- Oggetto/corpo con template fornitore e placeholder dinamici.

Placeholder disponibili:
- `{{po}}`, `{{brand}}`, `{{supplier}}`, `{{fornitore}}`
- `{{start_ship_date}}`, `{{cancel_ship_date}}`
- `{{contact_name}}`, `{{supplier_company}}`

## Troubleshooting rapido
### 1) Frontend non carica / 404 asset / errori chunk
```powershell
cd "C:\Progetti\Tjx operatività\ops"
powershell -ExecutionPolicy Bypass -File .\restart-services.ps1
```
Poi `Ctrl+F5` nel browser.

### 2) Errore Next `Cannot find module './xxx.js'`
- È stato di build/cache incoerente.
- Eseguire `restart-services.ps1`; se persiste, pulire `.next` e rifare build frontend.

### 3) `npm` bloccato con EPERM/EACCES su Windows
- Chiudere processi `node/npm`.
- Usare cache locale `frontend/.npm-cache`.
- Ripetere install/build.

### 4) L’app non prende aggiornamenti senza reboot
- Usare sempre `restart-services.ps1` (gestisce anche processi zombie).

## Git/GitHub
- Repo remoto: [https://github.com/FamorItalia/Tjx-Ops.git](https://github.com/FamorItalia/Tjx-Ops.git)
- Branch principale: `main`

## Note importanti
- Non committare file `.env`, output runtime, cache o log.
- Per dettagli completi di dominio, API, DB e logiche: vedere `TECHNICAL_HANDOVER_TJX_OPS_HUB.md`.
