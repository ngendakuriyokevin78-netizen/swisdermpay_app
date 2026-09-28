from docx import Document
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

OUT = "CashTel_Guide_Integration_Banques_Momo_Swisderm.docx"
doc = Document()
st = doc.styles['Normal']
st.font.name = 'Calibri'
st.font.size = Pt(10.5)

def shade(cell, color):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement('w:shd')
    shd.set(qn('w:val'), 'clear'); shd.set(qn('w:fill'), color)
    tcPr.append(shd)

def code(t):
    p = doc.add_paragraph()
    r = p.add_run(t)
    r.font.name = 'Consolas'; r.font.size = Pt(8.5)
    p.paragraph_format.left_indent = Inches(0.2)
    return p

def bullets(items):
    for it in items:
        doc.add_paragraph(it, style='List Bullet')

def flow(steps):
    n=len(steps); cols=n*2-1
    tbl=doc.add_table(rows=1, cols=cols)
    tbl.alignment=WD_TABLE_ALIGNMENT.CENTER; tbl.style='Table Grid'
    for i,s in enumerate(steps):
        c=i*2; cell=tbl.cell(0,c); cell.text=""
        p=cell.paragraphs[0]; p.alignment=WD_ALIGN_PARAGRAPH.CENTER
        r=p.add_run(s); r.bold=True; r.font.size=Pt(9)
        r.font.color.rgb=RGBColor(0xFF,0xFF,0xFF); shade(cell,"1F4E79")
        if i<n-1:
            ac=tbl.cell(0,c+1); ac.text=""
            ap=ac.paragraphs[0]; ap.alignment=WD_ALIGN_PARAGRAPH.CENTER
            ar=ap.add_run("  \u25B6  "); ar.bold=True; ar.font.size=Pt(12)
            ar.font.color.rgb=RGBColor(0x1F,0x4E,0x79); shade(ac,"D9E2F3")
    doc.add_paragraph("")

def table3(headers, rows):
    tbl=doc.add_table(rows=1, cols=3); tbl.style='Table Grid'
    hdr=tbl.rows[0].cells
    for i,h in enumerate(headers): hdr[i].text=h
    for c in hdr:
        shade(c,"1F4E79")
        for p in c.paragraphs:
            for r in p.runs: r.bold=True; r.font.color.rgb=RGBColor(0xFF,0xFF,0xFF)
    for a,b,c_ in rows:
        cells=tbl.add_row().cells; cells[0].text=a; cells[1].text=b; cells[2].text=c_
    doc.add_paragraph("")

doc.add_heading("Cash Tel — Guide d'implementation : Banques, Mobile Money, Achats Swisderm", level=0)
p=doc.add_paragraph(); r=p.add_run("Objectif : brancher des API externes SANS retoucher le coeur (wallet, transferts P2P). Principe : 1 couche adaptateur + 1 table config. Swisderm controle et encaisse."); r.italic=True

doc.add_heading("1. Principe — ne plus passer dans le code", level=1)
flow(["Config Admin (.env + BDD)", "Factory -> Adapter", "Wallet interne", "Callback externe"])
bullets([
    "Aujourd'hui : pay_bill(), cashin(), transfer() = logique interne seule, pas d'appel externe.",
    "Cible : views/services n'appellent jamais une banque en dur, ils appellent BaseAdapter.execute(provider_code).",
    "Ajouter une banque / un MoMo = 1 ligne en admin + cles API, 0 modification de views existantes.",
    "Swisderm = un Merchant comme un Biller, avec wallet d'encaissement + commission.",
])

doc.add_heading("2. Etape 0 — creer la table des fournisseurs externes (1 fois)", level=1)
code("""# apps/external/models.py
class ProviderType(models.TextChoices):
    BANK='BANK','Banque'; MOMO='MOMO','Mobile Money'; MERCHANT='MERCHANT','Marchand'
class ExternalProvider(models.Model):
    code=models.CharField(max_length=30, unique=True)  # ex: BANCOBU, LUMICASH, SWISDERM
    type=models.CharField(max_length=10, choices=ProviderType.choices)
    name=models.CharField(max_length=100)
    base_url=models.URLField(blank=True)
    api_key=models.CharField(max_length=255, blank=True)  # via .env / vault en prod
    wallet=models.ForeignKey('wallet.Wallet', null=True, blank=True, on_delete=models.SET_NULL)  # compte d'encaissement Swisderm
    commission_rate=models.DecimalField(max_digits=5, decimal_places=2, default=0)  # ex: 2.00 = 2%
    is_active=models.BooleanField(default=True)""")
code("""# .env
BANCOBU_API_URL=https://api.bancobu.bi
BANCOBU_API_KEY=xxx
LUMICASH_API_URL=https://api.lumicash.bi
LUMICASH_API_KEY=xxx""")

doc.add_heading("3. Etape 1 — interface adaptateur (1 fois)", level=1)
code("""# apps/external/adapters.py
class BaseAdapter:
    def cashin(self, user, amount, ref): raise NotImplementedError
    def cashout(self, user, amount, ref): raise NotImplementedError
    def verify(self, external_ref): raise NotImplementedError
class Factory:
    _reg = {}
    @classmethod
    def register(cls, code, adapter): cls._reg[code]=adapter
    @classmethod
    def get(cls, code): return cls._reg[code]()
# apps/external/bancobu.py
class BancobuAdapter(BaseAdapter):
    def cashin(self, user, amount, ref):
        import requests; from django.conf import settings
        r=requests.post(f"{settings.BANCOBU_URL}/cashin", json={"account":user.phone_number,"amount":str(amount),"ref":str(ref)}, headers={"Authorization":f"Bearer {settings.BANCOBU_KEY}"}, timeout=15)
        r.raise_for_status(); return r.json()  # {external_ref, status}
Factory.register("BANCOBU", BancobuAdapter)""")
bullets(["Mettre chaque banque / MoMo dans son fichier : bancobu.py, lumicash.py, econet.py.", "Aucune view existante ne change : on appelle Factory.get(code).cashin()."])

doc.add_heading("4. Etape 2 — services internes (reutiliser l'existant)", level=1)
code("""# apps/external/services.py — pseudo-code
@transaction.atomic
def external_cashin(user, provider_code, amount):
    from apps.wallet.models import Wallet; from apps.transactions.models import Transaction
    provider = ExternalProvider.objects.get(code=provider_code, is_active=True)
    txn = Transaction.objects.create(sender=None, receiver=user, amount=amount, fee=calculate_fee(amount), transaction_type='DEPOSIT', status='PENDING', metadata={'provider':provider_code})
    ext = Factory.get(provider_code).cashin(user, amount, txn.reference)  # appel banque/MoMo
    wallet = Wallet.objects.select_for_update().get(user=user)
    wallet.balance += amount; wallet.save(update_fields=['balance'])
    txn.status='SUCCESS'; txn.metadata['external_ref']=ext['external_ref']; txn.save()
    return txn""")
bullets(["Copier le pattern de apps/transactions/services.py (_execute_transfer) et apps/agent/services.py (commission).", "Toujours : 1) Transaction PENDING, 2) appel externe, 3) MAJ wallet + SUCCESS, 4) SMS + AuditService.log().", "Ajouter DEPOSIT/WITHDRAWAL/BILL avec metadata={provider, external_ref, order_id} — pas de nouvelle table.", "Idempotence : contrainte unique sur reference + verifier external_ref avant de recreer."])

doc.add_heading("5. Etape 3 — endpoints generiques (1 fois, jamais retouches)", level=1)
table3(["Methode","URL","Usage"],[
    ("POST","/api/external/cashin/","{provider_code, amount, pin} : banque/MoMo -> wallet"),
    ("POST","/api/external/cashout/","{provider_code, account_no, amount, pin} : wallet -> banque/MoMo"),
    ("POST","/api/external/callback/<code>/","webhook operateur (signature) -> confirme PENDING"),
    ("POST","/api/merchant/pay/","{merchant_code:SWISDERM, order_id, amount, pin} ou {qr_data}"),
])
code("""# QR marchandises : afficher SWISDERM:<order_id>:<montant>
# Client scanne -> POST /api/merchant/pay/ -> debit client, credit wallet Swisderm - commission""")

doc.add_heading("6. Etape 4 — Swisderm, controle et encaissement", level=1)
flow(["Client scanne QR Swisderm", "POST /merchant/pay + PIN", "Credit wallet Swisderm", "Swisderm gere"])
bullets([
    "Creer Provider(code=SWISDERM, type=MERCHANT, wallet=wallet_swisderm, commission_rate=2%).",
    "Biller(code=SWISDERM) pour garder compatibilite avec /api/bills/pay/ existant, ou nouvelle route /merchant/pay/ qui fait : debit client + credit Swisderm + commission plateforme.",
    "Controle Swisderm : compte ADMIN (is_staff) -> admin Django : voir Transactions, AuditLog, Fee, Providers, bloquer/debloquer, exporter.",
    "Tous les flux loggues via AuditService (BILL_PAID, EXTERNAL_CASHIN, MERCHANT_PAID) + SMS des deux cotes (pattern SMSService).",
])

doc.add_heading("7. Etape 5 — securite et tests (obligatoire)", level=1)
bullets([
    "PIN verifie a chaque debit (check_pin), JWT Bearer, role AGENT/ADMIN verifie cote serveur.",
    "Webhooks : verifier signature/HMAC operateur + whitelist IP + rejouer = meme reference -> pas de double credit.",
    "Timeouts + statuts PENDING -> tache Celery verify() qui reconcilie.",
    "Secrets jamais en dur : .env / vault, cles par provider.",
    "Tests : pytest avec mock d'adapter (FakeAdapter qui rend SUCCESS sans HTTP) + test PENDING->SUCCESS + double callback.",
])
code("pytest -v\n# ajouter tests/test_external.py avec FakeAdapter + APIClient JWT")

doc.add_heading("8. Fiche d'ajout d'une nouvelle banque / MoMo (sans code)", level=1)
bullets([
    "1) Obtenir doc API operateur : cashin, cashout, statut, callback, signature.",
    "2) Admin -> ExternalProvider -> + code (ex: ECONET), type MOMO, base_url, cle, actif.",
    "3) Si adaptateur existe deja pour ce protocole : rien a coder. Sinon : 1 fichier ~50 lignes classe XAdapter(BaseAdapter).",
    "4) Tester en sandbox : POST /api/external/cashin/ -> verifier wallet + Transaction + AuditLog.",
    "5) Activer en prod + configurer callback URL https://votre-domaine/api/external/callback/<code>/ chez l'operateur.",
])

doc.add_paragraph("Document genere — Cash Tel.").italic=True
doc.save(OUT); print(f"saved {OUT}")
