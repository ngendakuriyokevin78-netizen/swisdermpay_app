# Mise en ligne Cash Tel / Swisderm Pay — Internet + USSD

Date : 2026-09-26. Projet : Django 5 + DRF + PostgreSQL + Redis/Celery.
Dev local : SQLite + mock (ne pas mettre en prod tel quel).

---

## A. INTERNET — application web + PWA téléphone (`/m/`)

### A1. Achats préalables
1. VPS (ex Contabo/Hetzner/DigitalOcean, 2 Go RAM mini) + Ubuntu 22/24.
2. Nom de domaine (ex `pay.swisderm.bi`) → DNS `A` vers l'IP du VPS.
3. Compte Africa's Talking (SMS réels) si besoin d'OTP/SMS hors mock.

### A2. Fichiers nécessaires (déjà dans le projet sauf Nginx)
| Fichier | Rôle | État |
|---|---|---|
| `Dockerfile`, `docker-compose.yml` | web + db + redis + celery | OK |
| `.env` (copié de `.env.example`) | secrets + URLs | À REMPLIR (voir A3) |
| `cashtel/settings.py`, `cashtel/urls.py` | config + routes `/`, `/m/`, `/api/...` | OK |
| `apps/*` (auth, wallet, transactions, agent, bills, merchant, shop, banking, interop, mobile) | métier | OK + migrations à jour |
| `nginx.conf` + `docker-compose.prod.yml` | reverse-proxy HTTPS | **À CRÉER** (modèle ci-dessous) |
| Certificat Let's Encrypt | HTTPS obligatoire | À générer sur le VPS |

### A3. `.env` de production (ne jamais commiter)
```
SECRET_KEY=<64 caractères aléatoires>
DEBUG=False
ALLOWED_HOSTS=pay.swisderm.bi
DATABASE_URL=postgres://cashtel:<mot_de_passe_fort>@db:5432/cashtel
POSTGRES_DB=cashtel
POSTGRES_USER=cashtel
POSTGRES_PASSWORD=<mot_de_passe_fort>
REDIS_URL=redis://redis:6379/0
CORS_ALLOWED_ORIGINS=https://pay.swisderm.bi
SMS_BACKEND=africastalking
AFRICAS_TALKING_USERNAME=<fourni>
AFRICAS_TALKING_API_KEY=<fourni>
AFRICAS_TALKING_SENDER_ID=Swisderm
```

### A4. Commandes VPS (ordre strict)
```bash
# 1. Système + Docker
sudo apt update && sudo apt install -y docker.io docker-compose-plugin git
# 2. Code
git clone <votre-repo> && cd <projet>
cp .env.example .env && nano .env   # remplir A3
# 3. HTTPS (Nginx + certbot — voir modèle nginx.conf ci-dessous)
# 4. Démarrage
docker-compose up -d --build
docker-compose exec web python manage.py migrate
docker-compose exec web python manage.py create_initial_data
docker-compose exec web python manage.py seed_partners
docker-compose exec web python manage.py createsuperuser
docker-compose exec web python manage.py collectstatic --noinput
# 5. Vérifs
curl -I https://pay.swisderm.bi/m/            # 200
curl https://pay.swisderm.bi/api/docs/        # Swagger
# Admin : https://pay.swisderm.bi/admin/
# Plafond : Admin → Plafonds cantonnés → CRDB = montant cantonné réel
```

### A5. Modèle `nginx.conf` (à créer, à adapter au domaine)
```nginx
server {
  listen 80; server_name pay.swisderm.bi;
  location / { proxy_pass http://web:8000; proxy_set_header Host $host; }
}
# Puis : certbot --nginx -d pay.swisderm.bi  (passe en 443 auto)
```

### A6. Vérification avant ouverture
- [ ] `pytest` vert en local avant chaque déploiement
- [ ] Login client/agent/admin OK, transfert 1000 BIF OK, scan-pay OK, retrait code OK
- [ ] `/api/banking/float/` → `healthy: true`
- [ ] Sauvegarde auto Postgres (`pg_dump` cron quotidien)

---

## B. SANS INTERNET — code USSD type `*384#`

### B1. Location du code (sans ça, rien ne marche)
1. Demander un code USSD : directement aux opérateurs (Econet/Viettel via ARCT Burundi) OU via agrégateur (Africa's Talking : plus rapide, un seul contrat multi-opérateurs).
2. Signer + payer : location mensuelle + coût par session (~à confirmer au devis).
3. Déclarer la callback : `https://pay.swisderm.bi/api/ussd/` dans leur portail.
4. Récupérer : clé API, identifiants service, doc (`sessionId, phoneNumber, text`).

### B2. Fichiers nécessaires (module à créer — structure imposée)
| Fichier | Rôle | État |
|---|---|---|
| `apps/ussd/__init__.py`, `apps/ussd/apps.py` | déclaration app | **À CRÉER** |
| `apps/ussd/menu.py` | textes des menus (Kirundi/FR) + parsing `text` (`""`, `"1"`, `"2*num*montant*pin"`) | **À CRÉER** |
| `apps/ussd/views.py` | `POST /api/ussd/` → répond `CON ...` / `END ...`, appelle `process_transfer`, `pay_qr_auto`, `request_withdrawal`, `calculate_fee` existants | **À CRÉER** |
| `apps/ussd/urls.py` + ajout `path('api/ussd/', ...)` dans `cashtel/urls.py` | route callback | **À CRÉER** |
| `apps/ussd/models.py` (`UssdSession`) | journal sessionId/téléphone/étape (litiges) | **À CRÉER** |
| `tests/test_ussd.py` | simulateur local (sans opérateur) | **À CRÉER** |
| `cashtel/settings.py` | ajouter `apps.ussd` aux INSTALLED_APPS | 1 ligne |

### B3. Exemple de parcours USSD
```
Client : *384#  →  CON 1.Solde 2.Envoyer 3.Acheter 4.Code retrait
Client : 2*+25762000002*5000*1234  →  END Envoyé 5000 BIF, frais 200.
```

### B4. Mise en service USSD (ordre)
1. Partie A en ligne en HTTPS (prérequis absolu).
2. Créer le module B2 (dites « vas-y », je le génère branché sur vos services).
3. Tester au simulateur (`tests/test_ussd.py`) : solde, envoi, PIN faux ×3 = bloqué, rupture session.
4. Basculer la callback du mode TEST au mode LIVE chez l'opérateur/agrégateur.
5. Tests réels : 2 téléphones (2 opérateurs), tous les menus, montants limites.
6. Affichage boutique : code + tarifs + aide, formation agents.

---

## C. Coûts récurrents prévisionnels
| Poste | Ordre de grandeur |
|---|---|
| VPS + domaine | ~5-15 €/mois |
| Location code USSD | selon devis opérateur/agrégateur |
| Sessions USSD + SMS | à la consommation |
| Maintenance/sauvegardes | temps admin |

## D. Ne jamais faire
- `DEBUG=True`, SQLite, `SMS mock`, clés d'exemple ou plafond fictif en production.
- Émettre de l'e-money au-delà du plafond cantonné (le garde-fou bloque, mais déclarez le vrai montant).
- Partager le mot de passe admin démo (`Admin1234` = local uniquement).
