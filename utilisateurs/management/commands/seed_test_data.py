import random
import uuid
from datetime import date, timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from achats.models import CommandeAchat, LigneAchat, LigneReception, ReceptionAchat
from clients.models import Client
from fournisseurs.models import Fournisseur
from medicaments.models import Categorie, Medicament
from stock.models import Inventaire, LigneInventaire, LotStock, MouvementStock
from utilisateurs.models import JournalAudit, Role, Utilisateur
from ventes.models import LigneVente, Paiement, RetourVente, Vente
from ventes.services import ServiceVente

PREFIXE = "TEST-"
MOT_DE_PASSE = "test1234"

NOMS_MEDICAMENTS = [
    "Paracetamol", "Ibuprofene", "Amoxicilline", "Azythromycine", "Ciprofloxacine",
    "Metronidazole", "Artemether", "Lumefantrine", "Quinine", "Pyrantel",
    "Albendazole", "Mebendazole", "Prednisolone", "Dexamethasone", "Diclofenac",
    "Naproxene", "Aspirine", "Tramadol", "Codeine", "Dextromethorphane",
    "Salbutamol", "Beclometasone", "Fluticasone", "Cetirizine", "Loratadine",
    "Ranitidine", "Omeprazole", "Loperamide", "Ondansetron", "Metformine",
    "Glibenclamide", "Amlodipine", "Captopril", "Enalapril", "Hydrochlorothiazide",
    "Atorvastatine", "Simvastatine", "Clopidogrel", "Levothyroxine", "Fer sulfate",
    "Calcium carbonate", "Vitamine C", "Vitamine D3", "Serum physiologique",
    "Ringer lactate", "Glucose 5 pourcent", "Insuline", "Oxytocine",
]
DOSAGES = ["100 mg", "250 mg", "500 mg", "1 g", "5 mg", "20 mg", "125 ml", "500 ml"]
FORMES = ["COMPRIME", "GELULE", "SIROP", "INJECTION", "POMMADE", "GOUTTES", "AUTRE"]
LABORATOIRES = [
    "Labo Test Abidjan", "Pharma CI Demo", "Laboratoire Kokobo", "Medi Sud Test",
    "Nord Pharma Test", "Laboratoire Harmattan",
]
CATEGORIES_TEST = [
    "Cardiologie", "Dermatologie", "Digestif", "Endocrinologie", "Gynecologie",
    "Hematologie", "Neurologie", "Ophtalmologie", "Pediatrie", "Psychiatrie",
    "Rhumatologie", "Urologie", "Vaccins", "Vitamines",
]
VILLES = [
    "Abidjan", "Bouake", "Daloa", "Korhogo", "San Pedro", "Yamoussoukro",
    "Man", "Gagnoa", "Sassandra", "Boundoukou",
]
PRENOMS = [
    "Awa", "Moussa", "Fatou", "Ibrahim", "Aya", "Yao", "Koffi", "Nadie",
    "Bakary", "Mariam", "Serge", "Clarisse", "Herve", "Rokia", "Tchaa", "Edwige",
]
NOMS = [
    "Traore", "Diallo", "Kone", "Sanogo", "Kouassi", "Yao", "Coulibaly", "Ouattara",
    "Bamba", "Camara", "Soro", "Doumbia", "Gueye", "NGuessan", "Brou", "Sekou",
]
MOTIFS_RETOUR = [
    "Erreur de dispensation", "Produit non conforme", "Changement d'ordonnance",
    "Retour client", "Conditionnement endommage",
]
MOTIFS_ANNULATION = [
    "Erreur de saisie", "Client desiste", "Paiement refuse", "Stock insuffisant",
]


class Command(BaseCommand):
    help = "Genere un volume important de donnees de test coherentes pour PharmaGest."

    def add_arguments(self, parser):
        parser.add_argument(
            "--scale",
            type=int,
            default=1,
            help="Multiplicateur du volume genere (defaut : 1).",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        echelle = options["scale"]
        if echelle < 1:
            raise CommandError("L'option --scale doit etre superieure ou egale a 1.")

        modeles_suivis = [
            Utilisateur, Fournisseur, Client, Medicament, CommandeAchat,
            ReceptionAchat, LotStock, MouvementStock, Vente, Paiement,
            RetourVente, Inventaire, JournalAudit,
        ]
        avant = {
            modele: set(modele.objects.values_list("pk", flat=True))
            for modele in modeles_suivis
        }

        roles = self._creer_roles()
        utilisateurs = self._creer_utilisateurs(roles, self._volume(echelle, 12))
        fournisseurs = self._creer_fournisseurs(self._volume(echelle, 30))
        clients = self._creer_clients(self._volume(echelle, 250))
        categories = self._creer_categories()
        medicaments = self._creer_medicaments(categories, self._volume(echelle, 150))

        vendables, alertes, perimes, bloques = self._classer_medicaments(medicaments)
        self._creer_lots_initiaux(vendables, alertes, perimes, bloques, utilisateurs)
        self.stdout.write("References et stocks initiaux crees.")

        self._creer_achats(fournisseurs, utilisateurs, vendables, self._volume(echelle, 120))
        self.stdout.write("Commandes et receptions d'achat creees.")

        self._creer_ventes(clients, utilisateurs, vendables, self._volume(echelle, 600))
        self.stdout.write("Ventes, paiements et retours crees.")

        self._creer_inventaires(utilisateurs, self._volume(echelle, 12))
        self._creer_journal(utilisateurs, self._volume(echelle, 150))
        self._ancienner_donnees(modeles_suivis, avant)

        self.stdout.write(self.style.SUCCESS("Jeu de donnees de test genere."))
        for modele in modeles_suivis:
            crees = modele.objects.count() - len(avant[modele])
            self.stdout.write(
                f"  {modele._meta.verbose_name_plural} : {crees} crees "
                f"({modele.objects.count()} au total)"
            )

    def _volume(self, echelle, base):
        return max(1, base * echelle)

    def _date_passee(self, max_jours):
        return timezone.now() - timedelta(
            days=random.randint(0, max_jours),
            hours=random.randint(0, 23),
            minutes=random.randint(0, 59),
        )

    def _creer_roles(self):
        noms = (
            "Administrateur", "Pharmacien", "Caissier", "Magasinier", "Gestionnaire",
        )
        return {nom: Role.objects.get_or_create(nom=nom)[0] for nom in noms}

    def _creer_utilisateurs(self, roles, quantite):
        resultats = []
        role_noms = list(roles)
        for i in range(quantite):
            username = f"{PREFIXE.lower()}user_{i:03d}"
            role = roles[role_noms[i % len(role_noms)]]
            utilisateur, cree = Utilisateur.objects.get_or_create(
                username=username,
                defaults={
                    "first_name": PRENOMS[i % len(PRENOMS)],
                    "last_name": NOMS[(i * 3) % len(NOMS)],
                    "email": f"{username}@pharmagest.test",
                    "role": role,
                    "telephone": f"+225 0{i % 10} {i:02d} {i:02d} {i:02d} {i:02d}",
                },
            )
            if cree:
                utilisateur.set_password(MOT_DE_PASSE)
                utilisateur.save(update_fields=["password"])
            resultats.append(utilisateur)
        return resultats

    def _creer_fournisseurs(self, quantite):
        resultats = []
        for i in range(quantite):
            ville = VILLES[i % len(VILLES)]
            fournisseur, _ = Fournisseur.objects.get_or_create(
                nom=f"{PREFIXE}Fournisseur {i:03d} - {ville}",
                defaults={
                    "adresse": f"Zone commerciale, {ville}",
                    "telephone": f"+225 2{i % 10} {i:02d} {i:02d} {i:02d} {i:02d}",
                    "email": f"fournisseur{i:03d}@pharmagest.test",
                    "numero_fiscal": f"CI-{i:06d}",
                    "contact_principal": f"{PRENOMS[i % len(PRENOMS)]} {NOMS[i % len(NOMS)]}",
                    "est_actif": i % 11 != 0,
                },
            )
            resultats.append(fournisseur)
        return resultats

    def _creer_clients(self, quantite):
        comptoir = Client.objects.filter(nom__icontains="comptoir").first()
        resultats = [comptoir] if comptoir else []
        for i in range(quantite):
            client, _ = Client.objects.get_or_create(
                nom=f"{PREFIXE}Client {i:04d}",
                defaults={
                    "telephone": "" if i % 7 == 0 else f"+225 0{i % 10} {i:02d} {i:02d} {i:02d} {i:02d}",
                    "adresse": f"Quartier {VILLES[i % len(VILLES)]}, Abidjan",
                    "est_actif": i % 13 != 0,
                },
            )
            resultats.append(client)
        return [client for client in resultats if client]

    def _creer_categories(self):
        categories = list(Categorie.objects.all())
        for nom in CATEGORIES_TEST:
            categorie, _ = Categorie.objects.get_or_create(
                nom=f"{PREFIXE}{nom}",
                defaults={"description": f"Categorie de test {nom}"},
            )
            categories.append(categorie)
        return list({categorie.pk: categorie for categorie in categories}.values())

    def _creer_medicaments(self, categories, quantite):
        resultats = []
        for i in range(quantite):
            base = NOMS_MEDICAMENTS[i % len(NOMS_MEDICAMENTS)]
            dosage = DOSAGES[(i // len(NOMS_MEDICAMENTS)) % len(DOSAGES)]
            prix_achat = Decimal(random.randint(150, 9000))
            code = f"{PREFIXE}MED-{i:04d}"
            medicament, _ = Medicament.objects.get_or_create(
                code_barres=code,
                defaults={
                    "nom_commercial": f"{base} {dosage}",
                    "denomination_generique": base,
                    "categorie": categories[i % len(categories)],
                    "forme": FORMES[i % len(FORMES)],
                    "dosage": dosage,
                    "laboratoire": LABORATOIRES[i % len(LABORATOIRES)],
                    "prix_achat": prix_achat,
                    "prix_vente": prix_achat + Decimal(random.randint(40, 1800)),
                    "seuil_alerte": random.randint(10, 70),
                    "statut": Medicament.ARCHIVE if i % 41 == 0 else Medicament.ACTIF,
                },
            )
            resultats.append(medicament)
        return resultats

    def _classer_medicaments(self, medicaments):
        actifs = [medicament for medicament in medicaments if medicament.statut == Medicament.ACTIF]
        random.shuffle(actifs)
        taille = max(1, len(actifs) // 12)
        alertes = actifs[:taille]
        perimes = actifs[taille:taille + max(2, len(actifs) // 30)]
        bloques = actifs[taille + len(perimes):taille + len(perimes) + max(2, len(actifs) // 30)]
        exclus = {medicament.pk for medicament in alertes + perimes + bloques}
        vendables = [medicament for medicament in actifs if medicament.pk not in exclus]
        return vendables, alertes, perimes, bloques

    def _creer_lots_initiaux(self, vendables, alertes, perimes, bloques, utilisateurs):
        lots = []
        today = date.today()
        for medicament in alertes:
            quantite = max(1, medicament.seuil_alerte - random.randint(0, 4))
            lots.append(LotStock(
                medicament=medicament,
                numero_lot=f"{PREFIXE}LOT-INIT-{uuid.uuid4().hex[:10]}",
                date_peremption=today + timedelta(days=random.randint(120, 500)),
                quantite_recue=quantite,
                quantite_disponible=quantite,
                date_reception=today - timedelta(days=random.randint(0, 90)),
            ))
        for medicament in perimes:
            quantite = random.randint(10, 90)
            lots.append(LotStock(
                medicament=medicament,
                numero_lot=f"{PREFIXE}LOT-INIT-{uuid.uuid4().hex[:10]}",
                date_peremption=today - timedelta(days=random.randint(5, 90)),
                quantite_recue=quantite,
                quantite_disponible=quantite,
                date_reception=today - timedelta(days=random.randint(180, 360)),
            ))
        for medicament in bloques:
            quantite = random.randint(100, 600)
            lots.append(LotStock(
                medicament=medicament,
                numero_lot=f"{PREFIXE}LOT-INIT-{uuid.uuid4().hex[:10]}",
                date_peremption=today + timedelta(days=random.randint(200, 600)),
                quantite_recue=quantite,
                quantite_disponible=quantite,
                est_bloque=True,
                motif_blocage="Controle qualite de test",
                date_reception=today - timedelta(days=random.randint(0, 90)),
            ))
        for medicament in vendables:
            for index, (quantite, jours) in enumerate((
                (random.randint(12000, 22000), random.randint(380, 700)),
                (random.randint(3000, 8000), random.randint(220, 360)),
            )):
                lots.append(LotStock(
                    medicament=medicament,
                    numero_lot=f"{PREFIXE}LOT-INIT-{uuid.uuid4().hex[:10]}",
                    date_peremption=today + timedelta(days=jours),
                    quantite_recue=quantite,
                    quantite_disponible=quantite,
                    date_reception=today - timedelta(days=random.randint(0, 90) + index * 30),
                ))
        lots_avant = set(
            LotStock.objects.filter(
                numero_lot__startswith=f"{PREFIXE}LOT-INIT-"
            ).values_list("pk", flat=True)
        )
        LotStock.objects.bulk_create(lots)
        nouveaux_lots = LotStock.objects.filter(
            numero_lot__startswith=f"{PREFIXE}LOT-INIT-"
        ).exclude(pk__in=lots_avant)
        MouvementStock.objects.bulk_create([
            MouvementStock(
                lot=lot,
                type=MouvementStock.CORRECTION,
                quantite=lot.quantite_disponible,
                stock_apres=lot.quantite_disponible,
                reference_type="SeedTest",
                motif="Stock initial de test",
                utilisateur=random.choice(utilisateurs),
            )
            for lot in nouveaux_lots
        ])

    def _creer_achats(self, fournisseurs, utilisateurs, medicaments, quantite):
        for i in range(quantite):
            commande = CommandeAchat.objects.create(
                fournisseur=random.choice(fournisseurs),
                cree_par=random.choice(utilisateurs),
            )
            medicaments_choisis = random.sample(
                medicaments, min(random.randint(2, 5), len(medicaments))
            )
            for medicament in medicaments_choisis:
                LigneAchat.objects.create(
                    commande=commande,
                    medicament=medicament,
                    quantite_commandee=random.randint(100, 1200),
                    prix_achat_unitaire=medicament.prix_achat,
                )
            commande.valider()

            if i % 17 == 0:
                commande.annuler()
                continue
            if i % 19 == 0:
                continue

            reception = ReceptionAchat.objects.create(
                commande=commande,
                recu_par=random.choice(utilisateurs),
                date_reception=self._date_passee(120),
            )
            lignes = list(commande.lignes.all())
            if i % 5 == 0 or len(lignes) == 1:
                lignes_choisies = lignes
            else:
                lignes_choisies = random.sample(lignes, random.randint(1, len(lignes) - 1))
            for index, ligne in enumerate(lignes_choisies):
                reste = ligne.reste_a_recevoir()
                quantite = reste if i % 5 == 0 else random.randint(1, reste)
                LigneReception.objects.create(
                    reception=reception,
                    ligne_achat=ligne,
                    numero_lot=f"{PREFIXE}LOT-REC-{uuid.uuid4().hex[:10]}",
                    date_peremption=date.today() + timedelta(days=random.randint(180, 800)),
                    quantite_recue=quantite,
                )
            reception.valider(utilisateur=random.choice(utilisateurs))

    def _creer_ventes(self, clients, utilisateurs, medicaments, quantite):
        caissier = Utilisateur.objects.filter(username="caissier").first() or utilisateurs[0]
        caissiers = [
            utilisateur for utilisateur in utilisateurs
            if utilisateur.role and utilisateur.role.nom == "Caissier"
        ] or [caissier]

        for _ in range(quantite):
            vente = Vente.objects.create(
                client=random.choice(clients) if random.random() < 0.8 else None,
                caissier=random.choice(caissiers),
            )
            for medicament in random.sample(medicaments, min(random.randint(1, 4), len(medicaments))):
                lot = LotStock.lots_fefo(medicament).first()
                if lot is None:
                    continue
                quantite_ligne = min(random.randint(1, 9), lot.quantite_disponible)
                if quantite_ligne <= 0:
                    continue
                LigneVente.objects.create(
                    vente=vente,
                    medicament=medicament,
                    lot=lot,
                    quantite=quantite_ligne,
                    prix_unitaire_applique=medicament.prix_vente,
                )
            if not vente.lignes.exists():
                vente.delete()
                continue

            vente.recalculer_total()
            traitement = random.random()
            if traitement < 0.04:
                continue

            vente.valider(utilisateur=vente.caissier)

            if traitement < 0.09:
                paiement = ServiceVente.enregistrer_paiement(
                    vente, Paiement.MOBILE_MONEY, montant=vente.total
                )
            elif traitement < 0.96:
                mode = random.choices(
                    [Paiement.ESPECES, Paiement.MOBILE_MONEY, Paiement.AUTRE],
                    weights=[7, 3, 1],
                )[0]
                reference = (
                    f"TXN-{uuid.uuid4().hex[:12]}" if mode != Paiement.ESPECES else ""
                )
                paiement = ServiceVente.enregistrer_paiement(
                    vente, mode, montant=vente.total, reference=reference
                )
                if random.random() < 0.03:
                    paiement.statut = Paiement.ECHOUE
                    paiement.save(update_fields=["statut"])
            else:
                paiement = None

            if paiement and traitement >= 0.94:
                vente.annuler(random.choice(MOTIFS_ANNULATION), utilisateur=vente.caissier)
            elif paiement and random.random() < 0.06:
                ligne = random.choice(list(vente.lignes.all()))
                retour = RetourVente.objects.create(
                    vente=vente,
                    ligne_vente=ligne,
                    quantite_retournee=random.randint(1, ligne.quantite),
                    motif=random.choice(MOTIFS_RETOUR),
                    remis_en_stock=random.random() < 0.85,
                    utilisateur=vente.caissier,
                )
                try:
                    retour.valider(utilisateur=vente.caissier)
                except ValidationError:
                    retour.delete()

    def _creer_inventaires(self, utilisateurs, quantite):
        lots = list(
            LotStock.objects.filter(
                est_bloque=False,
                date_peremption__gte=date.today(),
                numero_lot__startswith=f"{PREFIXE}LOT-",
            ).order_by("?")[:300]
        )
        if not lots:
            return
        for i in range(quantite):
            inventaire = Inventaire.objects.create(
                date_inventaire=date.today() - timedelta(days=random.randint(0, 90)),
                statut=Inventaire.EN_COURS,
                realise_par=random.choice(utilisateurs),
                commentaire=f"Inventaire de test {i:03d}",
            )
            for lot_a_comter in random.sample(lots, min(random.randint(3, 10), len(lots))):
                lot = LotStock.objects.get(pk=lot_a_comter.pk)
                theorique = lot.quantite_disponible
                ecart = random.randint(-min(theorique, 8), 8)
                LigneInventaire.objects.create(
                    inventaire=inventaire,
                    lot=lot,
                    quantite_theorique=theorique,
                    quantite_comptee=max(0, theorique + ecart),
                )
            if i % 3 == 0:
                inventaire.valider(utilisateur=random.choice(utilisateurs))
            elif i % 3 == 1:
                inventaire.annuler()

    def _creer_journal(self, utilisateurs, quantite):
        actions = [action for action, _ in JournalAudit.ACTIONS]
        modeles = [
            "Vente", "CommandeAchat", "ReceptionAchat", "Medicament", "Client",
            "Fournisseur", "LotStock", "Inventaire", "Utilisateur",
        ]
        JournalAudit.objects.bulk_create([
            JournalAudit(
                utilisateur=random.choice(utilisateurs),
                action=random.choice(actions),
                modele_cible=random.choice(modeles),
                objet_id=random.randint(1, 100000),
                details={"source": "seed_test_data", "index": i},
                adresse_ip=f"192.168.1.{random.randint(2, 254)}",
            )
            for i in range(quantite)
        ])

    def _ancienner_donnees(self, modeles_suivis, avant):
        champs = {
            Utilisateur: "date_creation",
            Fournisseur: "date_creation",
            Client: "date_creation",
            Medicament: "date_creation",
            CommandeAchat: "date_creation",
            ReceptionAchat: "date_reception",
            LotStock: "date_reception",
            MouvementStock: "date_mouvement",
            Vente: "date_vente",
            Paiement: "date_paiement",
            RetourVente: "date_retour",
            Inventaire: "date_inventaire",
            JournalAudit: "date_action",
        }
        for modele in modeles_suivis:
            champ = champs.get(modele)
            if not champ:
                continue
            pks = list(
                modele.objects.exclude(pk__in=avant[modele]).values_list("pk", flat=True)
            )
            for pk in pks:
                modele.objects.filter(pk=pk).update(**{champ: self._date_passee(200)})
