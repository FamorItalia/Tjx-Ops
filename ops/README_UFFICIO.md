# TJX Ops Hub - Avvio automatico ufficio

## Cosa significa "modalità produzione"
- Non usi `next dev` / `uvicorn --reload` (modalità sviluppo).
- Usi servizi stabili per l'uso quotidiano di ufficio.
- Il frontend gira con `next start` su porta `3001`.
- Il backend gira con `uvicorn` su porta `8000`.

## 1) Primo setup (una sola volta)

Apri **PowerShell come Amministratore** e lancia:

```powershell
cd "C:\Progetti\Tjx operatività\ops"
.\build-frontend-prod.cmd
.\setup-autostart.ps1
```

Questo fa:
- build frontend produzione
- crea avvio automatico all'accesso Windows
- apre firewall porte 3001 e 8000

## 2) Avvio immediato (senza riavviare PC)

```powershell
schtasks /Run /TN TJX-OpsHub-Backend
schtasks /Run /TN TJX-OpsHub-Frontend
```

## 3) Verifica servizi

```powershell
cd "C:\Progetti\Tjx operatività\ops"
.\check-services.ps1
```

Se tutto ok:
- Backend OK porta 8000
- Frontend OK porta 3001

## 4) URL per i colleghi

1. Sul PC server esegui:
```powershell
ipconfig
```
2. Prendi l'IPv4 (esempio `192.168.1.45`)
3. I colleghi aprono:
`http://192.168.1.45:3001/login`

## 5) Se aggiorni codice frontend

Rifai build:
```powershell
cd "C:\Progetti\Tjx operatività\ops"
.\build-frontend-prod.cmd
```

Poi rilancia attività:
```powershell
schtasks /Run /TN TJX-OpsHub-Frontend
```

## 6) Log utili

- `C:\Progetti\Tjx operatività\ops\logs\backend.log`
- `C:\Progetti\Tjx operatività\ops\logs\frontend.log`

## 7) Rimozione autostart (se serve)

```powershell
cd "C:\Progetti\Tjx operatività\ops"
.\remove-autostart.ps1
```

## 8) Watchdog automatico (consigliato)

Controlla ogni minuto backend/frontend e li riavvia se uno dei due cade.

Installazione:
```powershell
cd "C:\Progetti\Tjx operatività\ops"
.\setup-watchdog.ps1
```

Rimozione:
```powershell
cd "C:\Progetti\Tjx operatività\ops"
.\remove-watchdog.ps1
```
