# TJX Ops Hub - Technical Handover (Full System)

Versione documento: 2026-05-05  
Repository: `https://github.com/FamorItalia/Tjx-Ops.git`  
Branch di riferimento: `main`

## 1) Obiettivo del sistema
TJX Ops Hub è un applicativo interno per gestire l'intero ciclo operativo ordini TJX:
- ingest/import di PDF ordini cliente multi-formato (Sierra, TJX USA, TJX Canada),
- normalizzazione e manutenzione operativa quantità,
- generazione ordine fornitore,
- calcolo e generazione packing list per DC,
- generazione documenti export (PDF/Excel) a livello ordine e DC,
- gestione anagrafiche (prodotti, fornitori, distribution centers),
- monitoraggio inventario e alert,
- audit trail delle mutate API.

Il sistema è pensato per uso ufficio su Windows, con avvio automatico locale e accesso via browser su `localhost:3001`.

---

## 2) Stack tecnologico
### Frontend
- Next.js 14 (App Router)
- React 18
- TypeScript
- Proxy API server-side Next verso backend (`/api/backend/[...path]`)

### Backend
- FastAPI
- SQLAlchemy ORM
- Pydantic
- SQLite locale

### Output documentale
- PDF/Excel generator servizi backend
- Cartelle template statiche in `TEMPLATES/`

### Runtime/OS
- Windows 10/11
- Script `.ps1` e `.cmd` in `ops/`

---

## 3) Struttura repository
Root:
- `backend/` API + business logic + DB
- `frontend/` UI web + proxy API
- `ops/` script operativi avvio/restart/watchdog
- `TEMPLATES/` input template e asset documentali
- manuali funzionali/operativi in root

File operativi critici:
- `backend/app/main.py`
- `backend/app/api/router.py`
- `frontend/app/layout.tsx`
- `frontend/app/api/backend/[...path]/route.ts`
- `ops/start-now.ps1`
- `ops/restart-services.ps1`
- `ops/run-backend-prod.cmd`
- `ops/run-frontend-prod.cmd`

---

## 4) Architettura applicativa
### 4.1 Frontend -> Backend
Il frontend non chiama direttamente `:8000`; usa un proxy interno Next:
- path frontend: `/api/backend/*`
- proxy target: `${BACKEND}/api/v1/*`

Il proxy:
- inoltra `Authorization` header, oppure token da cookie `ops_session_token`,
- gestisce risposta file binaria (download),
- normalizza risposte no-body (`204/205/304`) per evitare eccezioni client-side.

### 4.2 Auth e sicurezza
- Login backend genera session token (`user_sessions`).
- Route protette via dependency `get_current_user`.
- Ruoli: `admin`, `operatore`, `viewer`.
- Route admin-only in `auth.py` (gestione utenti/password/audit).
- Middleware audit salva mutate successful (`POST/PATCH/PUT/DELETE`) in `audit_logs`.

### 4.3 Persistenza
- SQLite locale, path configurabile (`SQLITE_DB_PATH`).
- `init_db()` crea schema e applica alter additive per colonne nuove (`_ensure_sqlite_columns`).

---

## 5) Data model (schema funzionale)
### 5.1 Ordini
- `customer_orders`: testata ordine cliente importato
- `customer_order_lines`: righe ordine, quantità originali/operative, distribuzione per DC

### 5.2 Ordini fornitore
- `purchase_orders`: snapshot ordine fornitore derivato da customer order
- `purchase_order_lines`: righe con qty base/adjusted/final + metadati logistici

### 5.3 Packing list
- `packing_lists`: documento per DC con totali, destinatari, override manuali
- `packing_list_lines`: righe operative di documento

### 5.4 Master data
- `suppliers`: anagrafica fornitore + email + template mail
- `products`: anagrafica prodotto + prezzi + campi logistici + tracking inventario
- `distribution_centers`: anagrafica DC + dati destinazione documenti
- `supplier_documents` / `product_documents`: allegati anagrafica

### 5.5 Inventario
- `product_inventory_ledger`: consumi da ordini
- `product_inventory_alerts`: alert soglia
- `product_inventory_manual_adjustments`: rettifiche manuali

### 5.6 Auth/Audit
- `user_accounts`
- `user_sessions`
- `audit_logs`

---

## 6) Flussi business principali
## 6.1 Import ordine cliente (PDF)
1. Upload/lista PDF (`/files`).
2. Parse test endpoint (`/parser/*/test`) e salvataggio ordine.
3. Salvataggio testata/righe su `customer_orders*`.

Note:
- parser family supportata: Sierra, TJX USA, TJX Canada.
- mapping supplier/PO/date/linee normalizzato in servizi parser.

## 6.2 Gestione operativa ordine
Su pagina dettaglio ordine (`/orders/[id]`):
- modifica quantità per riga/DC,
- reset a import,
- normalizzazione quantità,
- applicazione incremento automatico (+2%),
- reset a original.

Le quantità operative guidano i passaggi successivi (PO fornitore e packing list).

## 6.3 Generazione ordine fornitore
- Preview ordine fornitore: `POST /purchase-orders/preview`
- Persistenza ordine fornitore con righe derivate
- Export PDF ordine fornitore: `POST /purchase-orders/{id}/pdf`

UI: pulsante `Genera ordine fornitore`.

## 6.4 Invio ordine a fornitore (Outlook)
UI: pulsante `Invia ordine a fornitore` (accanto a genera ordine fornitore).

Logica implementata:
1. crea preview PO se assente,
2. genera PDF PO,
3. richiede draft email (`POST /email/prepare/{poId}`),
4. apre compose con `mailto:` precompilato.

Campi precompilati:
- To: prima email fornitore,
- Cc: ulteriori email fornitore + `operations@famoritalia.com`,
- Subject/body: da template fornitore (con fallback automatico),
- Allegato: percorso PDF ordine fornitore in response draft (limite client mailto: allegati non auto-attaccabili via standard browser; l'informazione è comunque disponibile).

Nota Outlook:
- uso `mailto` per rispettare default mail client Windows (classic/new Outlook dipende da impostazioni OS).

## 6.5 Template email dinamico fornitore
Anagrafica fornitore include:
- `email_subject_template`
- `email_order_template`

Placeholder supportati (subject e body):
- `{{po}}`
- `{{brand}}`
- `{{supplier}}`
- `{{fornitore}}`
- `{{start_ship_date}}`
- `{{cancel_ship_date}}`
- `{{contact_name}}`
- `{{supplier_company}}`

Se template vuoto: fallback automatico server-side.

## 6.6 Packing list e recap logistico
- preview batch packing list da purchase order,
- calcolo gruppi (`mono`/`nested`) e totali,
- possibilità override manuale totali,
- export PDF/Excel per DC o batch.

Aggiornamenti recenti:
- formattazione pesi a 2 decimali in recap/DC/export.

## 6.7 Documenti export
Endpoint ordini coprono:
- lista documenti,
- generate bulk/item,
- opzioni disponibili per ordine/DC,
- download all zip/bundle.

Famiglie documenti supportate incluse nei servizi backend (DLE, P2, Sfarinati, Packing List, ecc.).

## 6.8 Dashboard e stati
Dashboard attiva mostra:
- ordini attivi,
- stato ordine (`Programmato` / `Pronto al ritiro` / `In ritardo`),
- preview DC,
- alert inventario.

Sono stati inseriti guard rail su array/null per robustezza rendering.

---

## 7) API surface (sintesi per modulo)
### 7.1 `auth`
- login/logout/me
- list/create utenti (admin)
- reset password utente (admin)
- audit logs (admin)

### 7.2 `files`
- lista PDF disponibili
- upload PDF
- download file

### 7.3 `parser`
- parse test generico
- parse test Sierra
- parse test TJX USA
- parse test TJX Canada

### 7.4 `orders`
- lista/active/archive
- dashboard active + inventory alerts
- dettaglio ordine + archive toggle + delete
- document list/generate/options/download-all
- packing list list/reset totals
- logistics summary
- mutate quantità riga/DC + identity + nested cartons
- apply auto increase/reset flows

### 7.5 `brands`
- summary per brand
- lista ordini brand

### 7.6 `purchase-orders`
- preview generate
- get by id
- patch
- generate pdf

### 7.7 `email`
- prepare draft invio fornitore da purchase order

### 7.8 `products`
- import excel
- CRUD base
- export excel
- inventory history
- document management (upload/download/delete)

### 7.9 `distribution-centers`
- import excel
- list/get
- export excel

### 7.10 `suppliers`
- import excel
- CRUD base
- export excel
- prodotti associati
- document management

### 7.11 `packing-lists`
- preview
- get/patch
- pdf singolo
- pdf batch by purchase order

---

## 8) Frontend information architecture
Route pages principali:
- `/login`
- `/dashboard`
- `/import/new`
- `/orders/active`
- `/orders/archive`
- `/orders/[id]`
- `/brands`
- `/brands/[brand]`
- `/products`
- `/products/[id]`
- `/suppliers`
- `/suppliers/[id]`
- `/users`
- `/errors`

Componenti core:
- `components/layout/*`: shell app, sidebar, header
- `components/orders/OrderDetailClient.tsx`: nucleo operativo ordine
- `components/import/ImportWorkbench.tsx`: ingest ordine
- `components/suppliers/SupplierDetailClient.tsx`: template email e documenti fornitore
- `components/products/*`: anagrafica/inventario prodotto

---

## 9) Configurazioni e variabili ambiente
Backend (`backend/.env`):
- `SQLITE_DB_PATH`
- `TEMPLATES_ROOT`
- path templates documento/logo/firma
- SMTP settings
- `SUPPLIER_ALIASES_JSON`

Frontend (`frontend/.env`):
- `BACKEND_URL` / `NEXT_PUBLIC_BACKEND_URL`

Fallback default backend in proxy: `http://127.0.0.1:8000`.

---

## 10) Operatività Windows (`ops/`)
Script principali:
- `start-now.ps1`: start backend + frontend hidden
- `restart-services.ps1`: stop porte + kill processi zombie + restart
- `check-services.ps1`: health check
- `run-backend-prod.cmd`: uvicorn porta 8000
- `run-frontend-prod.cmd`: build if missing + `next start` porta 3001
- `setup-autostart.ps1`: task scheduler on logon
- `setup-watchdog.ps1`: watchdog scheduler (attualmente hourly)
- `watchdog.ps1`: verifica health e auto-restart se KO

Log file:
- `ops/logs/backend.log`
- `ops/logs/frontend.log`

Problema storico risolto:
- sessioni stale/chunk inconsistenti -> `restart-services.ps1` ora più aggressivo.

---

## 11) Stato Git/GitHub
- Repo inizializzato in root progetto
- Branch `main`
- Remote `origin`: `https://github.com/FamorItalia/Tjx-Ops.git`
- Push riuscito

`.gitignore` root copre:
- ambienti virtuali, `node_modules`, `.next`, cache npm locale,
- output runtime/log,
- env locali/segreti,
- `.deps`.

---

## 12) Modifiche rilevanti introdotte nel ciclo attuale
1. Pulsante `Invia ordine a fornitore` in dettaglio ordine.
2. Draft email backend con template da fornitore.
3. Nuovo campo fornitore `email_subject_template` + placeholder dinamici.
4. Risoluzione encoding/misformat (`mÂ³` -> `m³` e affini) su UI toccata.
5. Pesi a 2 decimali in recap DC e documenti generati.
6. Hardening frontend su null/array e routing.
7. Stabilizzazione proxy API no-body statuses.
8. Stabilizzazione script di riavvio/avvio senza reboot PC.
9. Watchdog configurato su frequenza oraria nello script setup.

---

## 13) Limitazioni e note tecniche
1. `mailto:` non supporta allegato automatico cross-client in modo standard browser. Il backend prepara il percorso allegato, ma l'attach automatico dipende dal client locale.
2. Ambiente Windows può bloccare file `next-swc`/cache npm (`EPERM/EACCES`): usare `restart-services.ps1` e, se necessario, cache npm locale in `frontend/.npm-cache`.
3. Parte dei template/config default contiene path locali legacy; verificare in ambienti diversi.
4. `init_db` usa migrazione additiva manuale per SQLite: per evoluzioni strutturali complesse valutare Alembic.

---

## 14) Runbook rapido per sviluppatore/AI che subentra
1. Verifica stato servizi
```powershell
cd "C:\Progetti\Tjx operatività\ops"
powershell -ExecutionPolicy Bypass -File .\check-services.ps1
```

2. Riavvio robusto senza reboot
```powershell
powershell -ExecutionPolicy Bypass -File .\restart-services.ps1
```

3. Se frontend non allinea asset/chunk
- stop servizi,
- pulizia `.next`,
- rebuild frontend,
- restart services.

4. Punto d'ingresso debug business
- ordine: `frontend/components/orders/OrderDetailClient.tsx`
- email: `backend/app/services/email_service.py`
- packing list: `backend/app/services/packing_lists_service.py`
- parser: `backend/app/services/parser/*`

5. Verifica API health
- backend: `http://127.0.0.1:8000/api/v1/health`
- frontend: `http://127.0.0.1:3001/login`

---

## 15) Suggerimenti evolutivi (tecnici)
1. Introduzione test end-to-end su flussi order->PO->email->packing list.
2. Introduzione migration tool (Alembic) al posto alter manuali.
3. Centralized error monitoring (frontend + backend).
4. Backup automatico DB/output con retention.
5. Documentazione API machine-readable (OpenAPI snapshot versionato).
6. Hardening codifica charset (UTF-8 consistency check in CI).

---

## 16) Allegati documentali correlati nel repo
- `MANUALE_USO_TJX_OPS_HUB.md` (manuale utente)
- `MANUALE_OPERATIVO_TJX_OPS_HUB.md` (manuale operativo)
- `ops/README_UFFICIO.md` (runbook ufficio)

Questo documento è il riferimento tecnico principale per handover sviluppo/manutenzione.
