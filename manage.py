#!/usr/bin/env python
"""Utilitaire de gestion Django pour Cash Tel."""
import os
import sys


def main():
    """Lance les tâches administratives Django."""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'cashtel.settings')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Impossible d'importer Django. Vérifiez que Django est installé "
            "et disponible dans votre PYTHONPATH environment variable."
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()
