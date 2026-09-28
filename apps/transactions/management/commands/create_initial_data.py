"""
Commande : python manage.py create_initial_data
Crée la grille des frais + fournisseurs de factures par défaut.
Idempotente (get_or_create).
"""
from decimal import Decimal
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Crée frais + billers par défaut pour Cash Tel'

    def handle(self, *args, **options):
        from apps.transactions.models import Fee
        from apps.bills.models import Biller

        tranches = [
            (100, 10000, 200, 'FIXED'),
            (10001, 50000, 500, 'FIXED'),
            (50001, 200000, 1000, 'FIXED'),
            (200001, 1000000, 2000, 'FIXED'),
            (1000001, 10000000, 1, 'PERCENTAGE'),
        ]
        for min_a, max_a, fee_v, fee_t in tranches:
            Fee.objects.get_or_create(
                min_amount=Decimal(min_a), max_amount=Decimal(max_a),
                defaults={'fee_value': Decimal(fee_v), 'fee_type': fee_t, 'is_active': True},
            )
        self.stdout.write(self.style.SUCCESS(f"{Fee.objects.count()} tranches de frais OK."))

        billers = [
            ('REGIDESO Eau', 'REGIDESO', 'WATER'),
            ('ENDEL Électricité', 'ENDEL', 'ELECTRICITY'),
            ('Lumicash Airtime', 'LUMICASH', 'AIRTIME'),
            ('Econet Airtime', 'ECONET', 'AIRTIME'),
        ]
        for name, code, cat in billers:
            Biller.objects.get_or_create(code=code, defaults={'name': name, 'category': cat})
        self.stdout.write(self.style.SUCCESS(f"{Biller.objects.count()} fournisseurs OK."))
