# Cash Tel API — Guide d'utilisation

Base URL local : `http://127.0.0.1:8000`
Docs interactives : `/api/docs/` (Swagger), `/api/redoc/`
Devise : BIF. Auth : JWT `Authorization: Bearer <access>`.

## 1. Démarrage

```bash
cp .env.example .env
python manage.py migrate
python manage.py create_initial_data
python manage.py runserver
```

OTP en dev (backend `mock`) : voir logs console / `OTPService`.

## 2. Authentification `/api/auth/`

### 2.1 Inscription
`POST /api/auth/register/`
```json
{"phone_number": "+25762000001", "first_name": "Alice", "last_name": "Test", "pin": "1234"}
```
PIN : 4 chiffres. Réponse `201` : `{"success": true, "message": "...OTP...", "phone_number": "..."}`.

```bash
curl -X POST http://127.0.0.1:8000/api/auth/register/ -H "Content-Type: application/json" -d '{"phone_number":"+25762000001","first_name":"Alice","last_name":"Test","pin":"1234"}'
```

### 2.2 Vérifier OTP
`POST /api/auth/verify-otp/`
```json
{"phone_number": "+25762000001", "otp": "123456"}
```

### 2.3 Renvoyer OTP
`POST /api/auth/resend-otp/`
```json
{"phone_number": "+25762000001"}
```

### 2.4 Login
`POST /api/auth/login/`
```json
{"phone_number": "+25762000001", "pin": "1234"}
```
Réponse `200` :
```json
{"success": true, "access": "<JWT>", "refresh": "<JWT>", "user": {"id": "...", "phone_number": "...", "full_name": "...", "role": "USER"}}
```
Erreurs : `401` PIN incorrect (reste N tentatives), `403` compte bloqué après 3 échecs / non vérifié / désactivé.

```bash
curl -X POST http://127.0.0.1:8000/api/auth/login/ -H "Content-Type: application/json" -d '{"phone_number":"+25762000001","pin":"1234"}'
```

### 2.5 Refresh / Logout / Profil
```bash
# Refresh
curl -X POST http://127.0.0.1:8000/api/auth/token/refresh/ -H "Content-Type: application/json" -d '{"refresh":"<REFRESH>"}'

# Profil (auth requise)
curl http://127.0.0.1:8000/api/auth/profile/ -H "Authorization: Bearer <ACCESS>"

# Changer PIN
curl -X POST http://127.0.0.1:8000/api/auth/change-pin/ -H "Authorization: Bearer <ACCESS>" -H "Content-Type: application/json" -d '{"current_pin":"1234","new_pin":"4321","confirm_pin":"4321"}'

# Logout (blacklist refresh)
curl -X POST http://127.0.0.1:8000/api/auth/logout/ -H "Authorization: Bearer <ACCESS>" -H "Content-Type: application/json" -d '{"refresh":"<REFRESH>"}'
```
`GET /api/auth/profile/` retourne `id, phone_number, first_name, last_name, full_name, role, is_phone_verified, wallet_id, balance`.

## 3. Wallet `/api/wallet/` (auth requise)

```bash
# Détail wallet + solde
curl http://127.0.0.1:8000/api/wallet/me/ -H "Authorization: Bearer <ACCESS>"

# Données QR pour recevoir (à partager à l'expéditeur)
curl http://127.0.0.1:8000/api/wallet/qr-data/ -H "Authorization: Bearer <ACCESS>"
# -> {"success": true, "qr_data": "CASHTEL:<wallet_id>:+257...", "wallet_id": "..."}

# Image QR PNG
curl http://127.0.0.1:8000/api/wallet/qr/ -H "Authorization: Bearer <ACCESS>" --output qr.png
```

## 4. Transferts `/api/transfer/` (auth requise)

### 4.1 Envoi par numéro
`POST /api/transfer/send/`
```json
{"receiver_phone": "+25762000002", "amount": "5000.00", "pin": "1234"}
```

### 4.2 Envoi par QR
`POST /api/transfer/qr/`
```json
{"qr_data": "CASHTEL:<wallet_id>:+25762000002", "amount": "5000.00", "pin": "1234"}
```

### 4.3 Frais
```bash
curl http://127.0.0.1:8000/api/transfer/fees/ -H "Authorization: Bearer <ACCESS>"
curl "http://127.0.0.1:8000/api/transfer/simulate/?amount=5000" -H "Authorization: Bearer <ACCESS>"
# -> {"success": true, "amount": "5000", "fee": "...", "total": "...", "currency": "BIF"}
```

### 4.4 Historique
```bash
curl http://127.0.0.1:8000/api/transfer/history/ -H "Authorization: Bearer <ACCESS>"
curl "http://127.0.0.1:8000/api/transactions/?type=TRANSFER&status=SUCCESS" -H "Authorization: Bearer <ACCESS>"
```
Types : `TRANSFER, DEPOSIT, WITHDRAWAL, BILL`. Status : `PENDING, SUCCESS, FAILED`. Pagination 20/page.

## 5. Agent `/api/agent/` (auth requise, rôle AGENT)

```bash
# Dépôt (cash-in, pas de PIN)
curl -X POST http://127.0.0.1:8000/api/agent/cashin/ -H "Authorization: Bearer <ACCESS_AGENT>" -H "Content-Type: application/json" -d '{"customer_phone":"+25762000001","amount":"10000.00"}'

# Retrait (cash-out)
curl -X POST http://127.0.0.1:8000/api/agent/cashout/ -H "Authorization: Bearer <ACCESS_AGENT>" -H "Content-Type: application/json" -d '{"customer_phone":"+25762000001","amount":"5000.00","pin":"1234"}'
```

## 6. Factures `/api/bills/` (auth requise)

```bash
# Fournisseurs
curl http://127.0.0.1:8000/api/bills/billers/ -H "Authorization: Bearer <ACCESS>"

# Payer
curl -X POST http://127.0.0.1:8000/api/bills/pay/ -H "Authorization: Bearer <ACCESS>" -H "Content-Type: application/json" -d '{"biller_code":"REGIDESO","reference_number":"123456","amount":"5000.00","pin":"1234"}'
```

## 7. Parcours complet type

1. Register A + B → Verify OTP → Login A + B.
2. B appelle `GET /api/wallet/qr-data/` → donne `qr_data` à A.
3. A appelle `POST /api/transfer/qr/` avec `qr_data + amount + pin`.
4. Vérif soldes via `GET /api/wallet/me/`.
5. Historique via `GET /api/transactions/`.

Script alternatif : `python scripts/test_qr_transfer.py --demo`.

## 8. Erreurs standard

`{"success": false, "error": "...", "details": {...}}` avec 400 validation, 401 non authentifié / PIN faux, 403 bloqué / non vérifié, 404 introuvable.
