# Cash Tel — Mobile Money Burundi (BIF)

Stack : Django 5 + DRF + PostgreSQL + Celery/Redis + JWT + Swagger.

## Lancer avec Docker (recommandé)

```bash
cp .env.example .env
docker-compose up --build
# API : http://localhost:8000/api/docs/
# Admin : http://localhost:8000/admin/
```

Cela exécute automatiquement : `migrate` + `create_initial_data` + `runserver`.

## Lancer en local (sans Docker)

```bash
python -m venv venv; venv\\Scripts\\activate  # Windows
pip install -r requirements.txt
cp .env.example .env
python manage.py migrate
python manage.py create_initial_data
python manage.py createsuperuser  # phone comme username, ex +25762000000
python manage.py runserver
```

## Endpoints

| Méthode | Route | Body |
|---|---|---|
| POST | /api/auth/register/ | {phone_number, first_name, last_name, pin} |
| POST | /api/auth/verify-otp/ | {phone_number, otp} |
| POST | /api/auth/login/ | {phone_number, pin} -> {access, refresh} |
| GET | /api/wallet/me/ | Bearer JWT |
| GET | /api/wallet/qr-data/ | Bearer JWT -> {qr_data} |
| POST | /api/transfer/send/ | {receiver_phone, amount, pin} |
| POST | /api/transfer/qr/ | {qr_data, amount, pin} |
| POST | /api/agent/cashin/ | {customer_phone, amount} (rôle AGENT) |
| POST | /api/agent/cashout/ | {customer_phone, amount, pin} |
| POST | /api/bills/pay/ | {biller_code, reference_number, amount, pin} |
| GET | /api/transactions/ | Bearer JWT + ?type=&status= |

Docs Swagger : `/api/docs/`

## Tester transfert QR avec curl

```bash
# 1. Register + OTP (voir logs docker pour OTP mock)
curl -X POST http://localhost:8000/api/auth/register/ -H "Content-Type: application/json" -d '{"phone_number":"+25762000001","first_name":"Alice","last_name":"Test","pin":"1234"}'
curl -X POST http://localhost:8000/api/auth/verify-otp/ -H "Content-Type: application/json" -d '{"phone_number":"+25762000001","otp":"XXXXXX"}'

# 2. Login -> récupère access token
curl -X POST http://localhost:8000/api/auth/login/ -H "Content-Type: application/json" -d '{"phone_number":"+25762000001","pin":"1234"}'

# 3. Récupère QR du destinataire (connecté en tant que destinataire)
curl http://localhost:8000/api/wallet/qr-data/ -H "Authorization: Bearer <ACCESS_B>"

# 4. Envoie via QR (connecté en tant qu'expéditeur)
curl -X POST http://localhost:8000/api/transfer/qr/ -H "Content-Type: application/json" -H "Authorization: Bearer <ACCESS_A>" -d '{"qr_data":"CASHTEL:<wallet_id>:+25762000002","amount":"5000.00","pin":"1234"}'

# 5. Vérifie solde
curl http://localhost:8000/api/wallet/me/ -H "Authorization: Bearer <ACCESS_A>"

# Script Python alternatif :
python scripts/test_qr_transfer.py --demo
```

## Tests

```bash
pytest -v
```
"# swisdermpay_app" 
