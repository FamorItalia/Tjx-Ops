# TJX Operativita Backend (STEP 2)

Backend FastAPI modulare con SQLite locale, collegato alle cartelle reali `TEMPLATES`.

## Requisiti

- Python 3.12+ (testato in ambiente Python 3.14)
- Windows PowerShell

## Setup locale

1. Vai nella cartella backend:

```powershell
Set-Location "C:\Progetti\Tjx operatività\backend"
```

2. Crea ambiente virtuale:

```powershell
python -m venv .venv
```

3. Attiva ambiente virtuale:

```powershell
.venv\Scripts\Activate.ps1
```

4. Installa dipendenze:

```powershell
python -m pip install -r requirements.txt
```

5. Crea file `.env` partendo dall'esempio:

```powershell
Copy-Item .env.example .env
```

6. Avvia API:

```powershell
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Endpoint disponibili

- `GET /`
- `GET /api/v1/health`
- `GET /api/v1/files/pdfs`
- `POST /api/v1/parser/test`
- `POST /api/v1/parser/sierra/test`
- `POST /api/v1/parser/tjx_usa/test`
- `POST /api/v1/parser/tjx_canada/test`
- `GET /api/v1/orders`
- `GET /api/v1/orders/{id}`
- `POST /api/v1/purchase-orders/preview`
- `GET /api/v1/purchase-orders/{id}`
- `PATCH /api/v1/purchase-orders/{id}`
- `POST /api/v1/purchase-orders/{id}/pdf`
- `POST /api/v1/products/import`
- `GET /api/v1/products`
- `GET /api/v1/products/{id}`
- `GET /api/v1/products/export/excel`

## Esempio parser test

```powershell
Invoke-RestMethod -Method Post `
  -Uri "http://127.0.0.1:8000/api/v1/parser/test" `
  -ContentType "application/json" `
  -Body '{"file_name":"SIERRA PO# IC985546 R - FAMOR Italia SRL Vendor Copy Report PO#IC985546.pdf"}'
```

## Esempio parser SIERRA reale

```powershell
Invoke-RestMethod -Method Post `
  -Uri "http://127.0.0.1:8000/api/v1/parser/sierra/test" `
  -ContentType "application/json" `
  -Body '{"file_name":"SIERRA PO# IC985546 R - FAMOR Italia SRL Vendor Copy Report PO#IC985546.pdf"}'
```

## Esempio parser SIERRA con salvataggio DB

```powershell
Invoke-RestMethod -Method Post `
  -Uri "http://127.0.0.1:8000/api/v1/parser/sierra/test?save=true" `
  -ContentType "application/json" `
  -Body '{"file_name":"SIERRA PO# IC985546 R - FAMOR Italia SRL Vendor Copy Report PO#IC985546.pdf"}'
```

## Esempio parser TJX USA (solo JSON, no save DB)

```powershell
Invoke-RestMethod -Method Post `
  -Uri "http://127.0.0.1:8000/api/v1/parser/tjx_usa/test" `
  -ContentType "application/json" `
  -Body '{"file_name":"LIKING PO# 133056 - MARSHALLS_DISTRIBUTION_INSTRUCTIONS_04_08_2026_0411_PM_133056_V1.pdf"}'
```

## Esempio parser TJX USA con salvataggio DB

```powershell
Invoke-RestMethod -Method Post `
  -Uri "http://127.0.0.1:8000/api/v1/parser/tjx_usa/test?save=true" `
  -ContentType "application/json" `
  -Body '{"file_name":"LIKING PO# 108745 - HOMEGOODS_DISTRIBUTION_INSTRUCTIONS_04_16_2026_1204_AM_108745_V2.pdf"}'
```

## Esempio parser TJX CANADA (solo JSON)

```powershell
Invoke-RestMethod -Method Post `
  -Uri "http://127.0.0.1:8000/api/v1/parser/tjx_canada/test" `
  -ContentType "application/json" `
  -Body '{"file_name":"LIKING PO# 774750 - WINNERS 04_92_TG59_IMP_D794P0FVJ3_774750_2026-07_VEND_2026-04-10.pdf"}'
```

## Esempio parser TJX CANADA con salvataggio DB

```powershell
Invoke-RestMethod -Method Post `
  -Uri "http://127.0.0.1:8000/api/v1/parser/tjx_canada/test?save=true" `
  -ContentType "application/json" `
  -Body '{"file_name":"LIKING PO# 774749 - CANADIAN MARSHALL CM 04_92_TG59_IMP_D794P0FVJ3_774749_2026-07_VEND_2026-04-10.pdf"}'
```

## Esempio anteprima ordine fornitore (JSON operativo)

```powershell
Invoke-RestMethod -Method Post `
  -Uri "http://127.0.0.1:8000/api/v1/purchase-orders/preview" `
  -ContentType "application/json" `
  -Body '{"customer_order_id":2,"adjustment_percent":2.0}'
```

## Esempio generazione PDF ordine fornitore

```powershell
Invoke-RestMethod -Method Post `
  -Uri "http://127.0.0.1:8000/api/v1/purchase-orders/1/pdf"
```

## Note implementative STEP 2

- SQLite inizializzato automaticamente in `./data/tjx_operativita.db`.
- Parser attuale è mock iniziale (riconoscimento da nome file).
- Parser SIERRA e reale su contenuto PDF (pagina 1 + pagina 2, con prevalenza pagina 2 per dettaglio/quantita).
- OCR non è attivo in questo step (verrà usato solo fallback nei prossimi step).
