from datetime import date, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from clients.models import Client
from fournisseurs.models import Fournisseur
from medicaments.models import Categorie, Medicament
from stock.models import LotStock, MouvementStock
from utilisateurs.models import Role, Utilisateur

MOT_DE_PASSE_DEMO = "pharma123"


class Command(BaseCommand):
    help = "Cree un jeu de donnees de demonstration pour PharmaGest."

    @transaction.atomic
    def handle(self, *args, **options):
        roles = {
            nom: Role.objects.get_or_create(nom=nom)[0]
            for nom in (
                "Administrateur",
                "Pharmacien",
                "Caissier",
                "Magasinier",
                "Gestionnaire",
            )
        }

        utilisateurs = [
            ("admin", "Administrateur", "Admin", "PharmaGest", True),
            ("pharmacien", "Pharmacien", "Awa", "Traore", False),
            ("caissier", "Caissier", "Moussa", "Diallo", False),
            ("magasinier", "Magasinier", "Fatou", "Kone", False),
            ("gestionnaire", "Gestionnaire", "Ibrahim", "Sanogo", False),
        ]
        for username, role, prenom, nom, superuser in utilisateurs:
            utilisateur, cree = Utilisateur.objects.get_or_create(
                username=username,
                defaults={
                    "first_name": prenom,
                    "last_name": nom,
                    "role": roles[role],
                    "is_staff": superuser,
                    "is_superuser": superuser,
                    "telephone": "+225 07 00 00 00",
                },
            )
            if cree:
                utilisateur.set_password(
                    "admin123" if superuser else MOT_DE_PASSE_DEMO
                )
                utilisateur.save(update_fields=["password"])
            elif utilisateur.role_id != roles[role].pk:
                utilisateur.role = roles[role]
                utilisateur.save(update_fields=["role"])

        fournisseurs = {}
        for nom, telephone, email in [
            ("Pharma Distrib", "+225 27 20 00 00", "contact@pharmadistrib.ci"),
            ("MediPlus CI", "+225 27 21 00 00", "ventes@mediplus.ci"),
        ]:
            fournisseurs[nom] = Fournisseur.objects.get_or_create(
                nom=nom,
                defaults={
                    "telephone": telephone,
                    "email": email,
                    "adresse": "Zone industrielle, Abidjan",
                    "contact_principal": "Service commercial",
                },
            )[0]

        clients = {}
        for nom, telephone in [
            ("Client comptoir", ""),
            ("Aya Kouassi", "+225 05 00 00 01"),
            ("Jean-Baptiste Yao", "+225 05 00 00 02"),
        ]:
            clients[nom] = Client.objects.get_or_create(
                nom=nom, defaults={"telephone": telephone}
            )[0]

        categories = {
            nom: Categorie.objects.get_or_create(nom=nom)[0]
            for nom in (
                "Antalgiques",
                "Antibiotiques",
                "Anti-inflammatoires",
                "Respiratoire",
                "Antipaludiques",
                "Autre",
            )
        }

        medicaments = [
            ("PARA500", "Paracetamol", "Paracetamol", "Antalgiques", "COMPRIME", "500 mg", "100", "250", 30),
            ("AMOX500", "Amoxicilline", "Amoxicilline", "Antibiotiques", "GELULE", "500 mg", "250", "600", 20),
            ("IBU400", "Ibuprofene", "Ibuprofene", "Anti-inflammatoires", "COMPRIME", "400 mg", "150", "350", 20),
            ("SIROP-TOUX", "Sirop toux enfants", "Dextromethorphane", "Respiratoire", "SIROP", "125 ml", "500", "1200", 10),
            ("ART-LUM", "Artemether-Lumefantrine", "Artemether/Lumefantrine", "Antipaludiques", "COMPRIME", "20/120 mg", "800", "1800", 15),
            ("SERUM-PHYS", "Serum physiologique", "Chlorure de sodium", "Autre", "INJECTION", "500 ml", "200", "500", 25),
        ]
        for code, nom, generique, categorie, forme, dosage, prix_achat, prix_vente, seuil in medicaments:
            Medicament.objects.get_or_create(
                code_barres=code,
                defaults={
                    "nom_commercial": nom,
                    "denomination_generique": generique,
                    "categorie": categories[categorie],
                    "forme": forme,
                    "dosage": dosage,
                    "laboratoire": "PharmaGest Demo",
                    "prix_achat": Decimal(prix_achat),
                    "prix_vente": Decimal(prix_vente),
                    "seuil_alerte": seuil,
                },
            )

        lots = [
            ("PARA500", "LOT-PARA-001", 180, 120, 400),
            ("AMOX500", "LOT-AMOX-001", 90, 120, 240),
            ("IBU400", "LOT-IBU-001", 60, 25, 365),
            ("SIROP-TOUX", "LOT-SIROP-001", 24, 18, 180),
            ("ART-LUM", "LOT-ART-001", 45, 12, 300),
            ("SERUM-PHYS", "LOT-SERUM-001", 80, 150, 500),
        ]
        for code, numero_lot, quantite, jours, prix in lots:
            medicament = Medicament.objects.get(code_barres=code)
            lot, cree = LotStock.objects.get_or_create(
                medicament=medicament,
                numero_lot=numero_lot,
                defaults={
                    "date_peremption": date.today() + timedelta(days=jours),
                    "quantite_recue": quantite,
                    "quantite_disponible": quantite,
                },
            )
            if cree:
                MouvementStock.enregistrer(
                    lot,
                    MouvementStock.CORRECTION,
                    quantite,
                    motif="Stock initial de demonstration",
                )

        self.stdout.write(self.style.SUCCESS("Donnees de demonstration creees."))
        self.stdout.write("Comptes :")
        self.stdout.write("  admin / admin123 (superutilisateur)")
        self.stdout.write(f"  pharmacien / {MOT_DE_PASSE_DEMO}")
        self.stdout.write(f"  caissier / {MOT_DE_PASSE_DEMO}")
        self.stdout.write(f"  magasinier / {MOT_DE_PASSE_DEMO}")
        self.stdout.write(f"  gestionnaire / {MOT_DE_PASSE_DEMO}")
