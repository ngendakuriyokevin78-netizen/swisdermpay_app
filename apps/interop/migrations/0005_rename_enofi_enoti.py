# Correction ENOFI → ENOTI (Bancobu eNoti). Données seules, sans toucher au schéma.
from django.db import migrations


def rename_enofi_enoti(apps, schema_editor):
    ExternalProvider = apps.get_model('interop', 'ExternalProvider')
    try:
        row = ExternalProvider.objects.filter(code='ENOFI').first()
    except Exception:
        return
    if row:
        row.code = 'ENOTI'
        if (row.name or '').strip().lower() in ('enofi', ''):
            row.name = 'Bancobu eNoti'
        try:
            if row.adapter_class and 'enofi_adapter.EnofiAdapter' in row.adapter_class:
                row.adapter_class = row.adapter_class.replace(
                    'enofi_adapter.EnofiAdapter', 'enoti_adapter.EnotiAdapter')
        except Exception:
            pass
        row.save()


def reverse_rename(apps, schema_editor):
    ExternalProvider = apps.get_model('interop', 'ExternalProvider')
    try:
        row = ExternalProvider.objects.filter(code='ENOTI').first()
    except Exception:
        return
    if row:
        row.code = 'ENOFI'
        row.save()


class Migration(migrations.Migration):

    dependencies = [
        ('interop', '0004_ussdconfig_ussdmenuoption'),
    ]

    operations = [
        migrations.RunPython(rename_enofi_enoti, reverse_rename),
    ]
