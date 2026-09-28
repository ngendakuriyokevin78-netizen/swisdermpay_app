#!/usr/bin/env python
"""
Script : générer un QR code et tester un transfert.
Usage :
  python scripts/test_qr_transfer.py --sender-phone +25762XXXXXX --amount 5000
  (nécessite serveur lancé + users existants, ou utilise --demo avec sqlite)

En mode --demo : crée 2 users en sqlite mémoire et simule un transfert QR.
"""
import argparse
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'cashtel.settings')
django.setup()

from decimal import Decimal


def demo_local():
    """Démo locale sans serveur : crée users + transfert QR."""
    from django.contrib.auth import get_user_model
    User = get_user_model()
    from apps.transactions.services import process_qr_transfer

    print("=== Démo Cash Tel QR ===")
    alice, _ = User.objects.get_or_create(
        phone_number='+25762000001',
        defaults={'first_name': 'Alice', 'last_name': 'Demo', 'is_phone_verified': True},
    )
    bob, _ = User.objects.get_or_create(
        phone_number='+25762000002',
        defaults={'first_name': 'Bob', 'last_name': 'Demo', 'is_phone_verified': True},
    )
    for u in (alice, bob):
        if not u.pin:
            u.set_pin('1234')
            u.save()
    alice.wallet.balance = Decimal('50000')
    alice.wallet.save(update_fields=['balance'])
    bob.wallet.refresh_from_db()
    print(f"QR Bob : {bob.wallet.qr_data}")
    print(f"Solde Alice avant : {alice.wallet.balance} BIF")
    txn = process_qr_transfer(alice, bob.wallet.qr_data, Decimal('5000'), '1234')
    alice.wallet.refresh_from_db()
    bob.wallet.refresh_from_db()
    print(f"Transfert OK ref={txn.reference} frais={txn.fee} BIF")
    print(f"Solde Alice après : {alice.wallet.balance} BIF")
    print(f"Solde Bob après : {bob.wallet.balance} BIF")


def via_api(base_url, sender_phone, pin, qr_data, amount, token):
    """Teste via curl-like HTTP API."""
    import json, urllib.request
    url = base_url.rstrip('/') + '/api/transfer/qr/'
    payload = json.dumps({'qr_data': qr_data, 'amount': amount, 'pin': pin}).encode()
    req = urllib.request.Request(url, data=payload, headers={
        'Content-Type': 'application/json', 'Authorization': f'Bearer {token}',
    })
    with urllib.request.urlopen(req) as r:
        print(r.status, r.read().decode()[:1000])


if __name__ == '__main__':
    p = argparse.ArgumentParser(description='Test QR Cash Tel')
    p.add_argument('--demo', action='store_true', help='Démo locale directe (défaut)')
    p.add_argument('--api', help='Base URL API ex: http://localhost:8000')
    p.add_argument('--token', default='', help='JWT access token')
    p.add_argument('--qr-data', default='', help='Données QR')
    p.add_argument('--amount', default='5000')
    p.add_argument('--pin', default='1234')
    a = p.parse_args()
    if a.api:
        via_api(a.api, '', a.pin, a.qr_data, a.amount, a.token)
    else:
        demo_local()
