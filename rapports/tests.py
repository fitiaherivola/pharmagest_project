from datetime import date, timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.test import Client as ClientHTTP
from django.urls import reverse

from achats.models import CommandeAchat, LigneAchat, LigneReception, ReceptionAchat
from clients.models import Client
from fournisseurs.models import Fournisseur
from medicaments.models import Categorie, Medicament
from stock.models import Inventaire, LigneInventaire, LotStock, MouvementStock
from utilisateurs.models import Role, Utilisateur
from ventes.models import LigneVente, RetourVente, Vente
from ventes.services import ServiceVente


class FluxPharmaGestTests(TestCase):
    def setUp(self):
        self.http = ClientHTTP()
        self.user = Utilisateur.objects.create_superuser(
            username="admin-test", password="motdepasse", email="admin@example.com"
        )
        self.user_sans_role = Utilisateur.objects.create_user(
            username="sans-role", password="motdepasse"
        )
        self.categorie = Categorie.objects.create(nom="Antalgiques")
        self.medicament = Medicament.objects.create(
            nom_commercial="Paracetamol",
            categorie=self.categorie,
            dosage="500 mg",
            prix_achat=Decimal("100"),
            prix_vente=Decimal("250"),
            seuil_alerte=10,
        )
        self.fournisseur = Fournisseur.objects.create(nom="Fournisseur test")
        self.client = Client.objects.create(nom="Client test")

    def _reception(self, quantite=20, numero_lot="LOT-TEST", jours=365):
        commande = CommandeAchat.objects.create(
            fournisseur=self.fournisseur, cree_par=self.user
        )
        ligne = LigneAchat.objects.create(
            commande=commande,
            medicament=self.medicament,
            quantite_commandee=quantite,
            prix_achat_unitaire=Decimal("100"),
        )
        commande.valider()
        reception = ReceptionAchat.objects.create(
            commande=commande, recu_par=self.user
        )
        LigneReception.objects.create(
            reception=reception,
            ligne_achat=ligne,
            numero_lot=numero_lot,
            date_peremption=date.today() + timedelta(days=jours),
            quantite_recue=quantite,
        )
        reception.valider(self.user)
        lot = LotStock.objects.get(
            medicament=self.medicament, numero_lot=numero_lot
        )
        return commande, ligne, reception, lot

    def _vendre(self, lot, quantite=3):
        vente = Vente.objects.create(caissier=self.user, client=self.client)
        LigneVente.objects.create(
            vente=vente,
            medicament=self.medicament,
            lot=lot,
            quantite=quantite,
            prix_unitaire_applique=self.medicament.prix_vente,
        )
        vente.valider(self.user)
        return vente

    def test_reception_augmente_stock_et_mouvement(self):
        commande, ligne, reception, lot = self._reception()

        self.assertTrue(reception.est_validee)
        commande.refresh_from_db()
        ligne.refresh_from_db()
        lot.refresh_from_db()
        self.assertEqual(ligne.quantite_recue, 20)
        self.assertEqual(commande.statut, CommandeAchat.COMPLETE)
        self.assertEqual(lot.quantite_disponible, 20)
        self.assertTrue(
            MouvementStock.objects.filter(
                lot=lot,
                type=MouvementStock.ENTREE_ACHAT,
                quantite=20,
                stock_apres=20,
            ).exists()
        )

    def test_double_validation_reception_refusee(self):
        _, ligne, reception, lot = self._reception()

        with self.assertRaises(ValidationError):
            reception.valider(self.user)

        ligne.refresh_from_db()
        lot.refresh_from_db()
        self.assertEqual(ligne.quantite_recue, 20)
        self.assertEqual(lot.quantite_disponible, 20)

    def test_vente_de_trois_unites_diminue_stock(self):
        _, _, _, lot = self._reception()
        vente = self._vendre(lot, 3)

        lot.refresh_from_db()
        self.assertEqual(vente.statut, Vente.VALIDEE)
        self.assertEqual(vente.total, Decimal("750"))
        self.assertEqual(lot.quantite_disponible, 17)
        self.assertTrue(
            MouvementStock.objects.filter(
                lot=lot,
                type=MouvementStock.SORTIE_VENTE,
                quantite=-3,
                stock_apres=17,
            ).exists()
        )

    def test_vente_superieure_au_stock_refusee(self):
        _, _, _, lot = self._reception()
        vente = Vente.objects.create(caissier=self.user)
        LigneVente.objects.create(
            vente=vente,
            medicament=self.medicament,
            lot=lot,
            quantite=21,
            prix_unitaire_applique=self.medicament.prix_vente,
        )

        with self.assertRaises(ValidationError):
            vente.valider(self.user)

        lot.refresh_from_db()
        self.assertEqual(lot.quantite_disponible, 20)
        self.assertEqual(vente.statut, Vente.EN_COURS)

    def test_lot_perime_refuse_a_la_vente(self):
        lot = LotStock.objects.create(
            medicament=self.medicament,
            numero_lot="LOT-PERIME",
            date_peremption=date.today() - timedelta(days=1),
            quantite_recue=5,
            quantite_disponible=5,
        )
        vente = Vente.objects.create(caissier=self.user)
        LigneVente.objects.create(
            vente=vente,
            medicament=self.medicament,
            lot=lot,
            quantite=1,
            prix_unitaire_applique=self.medicament.prix_vente,
        )

        with self.assertRaises(ValidationError):
            vente.valider(self.user)

        lot.refresh_from_db()
        self.assertEqual(lot.quantite_disponible, 5)

    def test_double_validation_vente_refusee(self):
        _, _, _, lot = self._reception()
        vente = self._vendre(lot, 3)

        with self.assertRaises(ValidationError):
            vente.valider(self.user)

        lot.refresh_from_db()
        self.assertEqual(lot.quantite_disponible, 17)

    def test_fefo_refuse_la_vente_d_un_lot_plus_recent(self):
        _, _, _, lot_recent = self._reception(jours=365)
        lot_ancien = LotStock.objects.create(
            medicament=self.medicament,
            numero_lot="LOT-ANCIEN",
            date_peremption=date.today() + timedelta(days=30),
            quantite_recue=10,
            quantite_disponible=10,
            date_reception=date.today() - timedelta(days=1),
        )
        vente = Vente.objects.create(caissier=self.user)
        LigneVente.objects.create(
            vente=vente,
            medicament=self.medicament,
            lot=lot_recent,
            quantite=1,
            prix_unitaire_applique=self.medicament.prix_vente,
        )

        with self.assertRaises(ValidationError):
            vente.valider(self.user)

        lot_ancien.refresh_from_db()
        lot_recent.refresh_from_db()
        self.assertEqual(lot_ancien.quantite_disponible, 10)
        self.assertEqual(lot_recent.quantite_disponible, 20)

    def test_retour_remet_le_stock_et_ne_se_double_pas(self):
        _, _, _, lot = self._reception()
        vente = self._vendre(lot, 3)
        ligne = vente.lignes.get()
        retour = RetourVente.objects.create(
            vente=vente,
            ligne_vente=ligne,
            quantite_retournee=2,
            motif="Erreur de dosage",
            remis_en_stock=True,
            utilisateur=self.user,
        )
        retour.valider(self.user)

        lot.refresh_from_db()
        self.assertEqual(lot.quantite_disponible, 19)
        self.assertTrue(retour.est_valide)
        self.assertEqual(retour.montant_rembourse, Decimal("500"))
        self.assertTrue(
            MouvementStock.objects.filter(
                lot=lot, type=MouvementStock.RETOUR, quantite=2
            ).exists()
        )

        with self.assertRaises(ValidationError):
            ServiceVente.traiter_retour(retour, utilisateur=self.user)

        lot.refresh_from_db()
        self.assertEqual(lot.quantite_disponible, 19)

    def test_inventaire_corrige_le_stock_et_trace_le_mouvement(self):
        _, _, _, lot = self._reception()
        inventaire = Inventaire.objects.create(realise_par=self.user)
        ligne = LigneInventaire.objects.create(
            inventaire=inventaire,
            lot=lot,
            quantite_theorique=20,
            quantite_comptee=18,
        )
        inventaire.valider(self.user)

        lot.refresh_from_db()
        inventaire.refresh_from_db()
        self.assertEqual(inventaire.statut, Inventaire.VALIDE)
        self.assertEqual(lot.quantite_disponible, 18)
        self.assertTrue(
            MouvementStock.objects.filter(
                lot=lot,
                type=MouvementStock.INVENTAIRE,
                quantite=-2,
                reference_id=inventaire.pk,
            ).exists()
        )

    def test_inventaire_via_vue_valide_les_ecarts(self):
        _, _, _, lot = self._reception()
        inventaire = Inventaire.objects.create(realise_par=self.user)
        ligne = LigneInventaire.objects.create(
            inventaire=inventaire,
            lot=lot,
            quantite_theorique=20,
            quantite_comptee=20,
        )
        self.http.force_login(self.user)

        reponse = self.http.post(
            reverse("stock:saisir_inventaire", args=[inventaire.pk]),
            {f"compte_{ligne.pk}": "18", "action": "valider"},
        )

        self.assertEqual(reponse.status_code, 302)
        inventaire.refresh_from_db()
        lot.refresh_from_db()
        self.assertEqual(inventaire.statut, Inventaire.VALIDE)
        self.assertEqual(lot.quantite_disponible, 18)

    def test_acces_sans_permission_refuse(self):
        self.http.force_login(self.user_sans_role)
        reponse = self.http.get(reverse("achats:commandes"))

        self.assertEqual(reponse.status_code, 403)

    def test_reception_via_vue_cree_le_lot(self):
        commande = CommandeAchat.objects.create(
            fournisseur=self.fournisseur, cree_par=self.user
        )
        ligne = LigneAchat.objects.create(
            commande=commande,
            medicament=self.medicament,
            quantite_commandee=10,
            prix_achat_unitaire=Decimal("100"),
        )
        commande.valider()
        self.http.force_login(self.user)

        reponse = self.http.post(
            reverse("achats:creer_reception", args=[commande.pk]),
            {
                f"qte_{ligne.pk}": "10",
                f"lot_{ligne.pk}": "LOT-VUE",
                f"peremption_{ligne.pk}": (
                    date.today() + timedelta(days=180)
                ).isoformat(),
            },
        )

        self.assertEqual(reponse.status_code, 302)
        lot = LotStock.objects.get(
            medicament=self.medicament, numero_lot="LOT-VUE"
        )
        self.assertEqual(lot.quantite_disponible, 10)
        self.assertTrue(ReceptionAchat.objects.filter(est_validee=True).exists())

    def test_caisse_via_vue_valide_la_vente(self):
        _, _, _, lot = self._reception()
        self.http.force_login(self.user)

        ajout = self.http.post(
            reverse("ventes:caisse"),
            {"action": "ajouter", "lot_id": lot.pk, "quantite": "2"},
        )
        self.assertEqual(ajout.status_code, 302)
        self.assertEqual(self.http.session["panier"], {str(lot.pk): 2})

        validation = self.http.post(
            reverse("ventes:caisse"),
            {
                "action": "valider",
                "mode": "ESPECES",
                "montant_recu": "500",
            },
        )

        self.assertEqual(validation.status_code, 302)
        vente = Vente.objects.get()
        self.assertEqual(vente.statut, Vente.VALIDEE)
        self.assertEqual(vente.total, Decimal("500"))
        lot.refresh_from_db()
        self.assertEqual(lot.quantite_disponible, 18)
        self.assertEqual(self.http.session["panier"], {})

    def test_roles_seedes_avec_permissions_attendues(self):
        caissier = Role.objects.get(nom="Caissier")
        magasinier = Role.objects.get(nom="Magasinier")

        self.assertTrue(caissier.a_permission("ventes.add_vente"))
        self.assertFalse(caissier.a_permission("achats.view_commandeachat"))
        self.assertTrue(magasinier.a_permission("achats.add_receptionachat"))
        self.assertFalse(magasinier.a_permission("ventes.add_vente"))

    def test_pages_principales_et_pdf_render(self):
        commande, _, reception, lot = self._reception()
        vente = self._vendre(lot, 3)
        inventaire = Inventaire.objects.create(realise_par=self.user)
        LigneInventaire.objects.create(
            inventaire=inventaire,
            lot=lot,
            quantite_theorique=17,
            quantite_comptee=17,
        )
        self.http.force_login(self.user)

        urls = [
            reverse("tableau_bord"),
            reverse("medicaments:liste"),
            reverse("medicaments:creer"),
            reverse("medicaments:categories"),
            reverse("medicaments:creer_categorie"),
            reverse("medicaments:modifier_categorie", args=[self.categorie.pk]),
            reverse("medicaments:detail", args=[self.medicament.pk]),
            reverse("medicaments:modifier", args=[self.medicament.pk]),
            reverse("fournisseurs:liste"),
            reverse("fournisseurs:creer"),
            reverse("fournisseurs:detail", args=[self.fournisseur.pk]),
            reverse("fournisseurs:modifier", args=[self.fournisseur.pk]),
            reverse("clients:liste"),
            reverse("clients:creer"),
            reverse("clients:detail", args=[self.client.pk]),
            reverse("clients:modifier", args=[self.client.pk]),
            reverse("stock:lots"),
            reverse("stock:creer_lot"),
            reverse("stock:lot_detail", args=[lot.pk]),
            reverse("stock:modifier_lot", args=[lot.pk]),
            reverse("stock:mouvements"),
            reverse("stock:alertes"),
            reverse("stock:inventaires"),
            reverse("stock:creer_inventaire"),
            reverse("stock:inventaire_detail", args=[inventaire.pk]),
            reverse("achats:commandes"),
            reverse("achats:creer_commande"),
            reverse("achats:commande_detail", args=[commande.pk]),
            reverse("achats:receptions"),
            reverse("achats:reception_detail", args=[reception.pk]),
            reverse("ventes:liste"),
            reverse("ventes:detail", args=[vente.pk]),
            reverse("ventes:retour", args=[vente.pk]),
            reverse("ventes:caisse"),
            reverse("rapports:stock"),
            reverse("rapports:ventes"),
            reverse("rapports:achats"),
            reverse("rapports:peremptions"),
            reverse("utilisateurs:liste"),
            reverse("utilisateurs:creer"),
            reverse("utilisateurs:modifier", args=[self.user_sans_role.pk]),
            reverse("utilisateurs:mot_de_passe"),
            reverse("utilisateurs:journal"),
            reverse("utilisateurs:profil"),
        ]
        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(self.http.get(url).status_code, 200)

        for url in [
            reverse("ventes:recu_pdf", args=[vente.pk]),
            reverse("ventes:facture_pdf", args=[vente.pk]),
            reverse("achats:bon_commande_pdf", args=[commande.pk]),
            reverse("achats:bon_reception_pdf", args=[reception.pk]),
            reverse("rapports:stock_pdf"),
            reverse("rapports:ventes_pdf"),
            reverse("rapports:achats_pdf"),
            reverse("rapports:peremptions_pdf"),
        ]:
            with self.subTest(pdf=url):
                reponse = self.http.get(url)
                self.assertEqual(reponse.status_code, 200)
                self.assertEqual(reponse["Content-Type"], "application/pdf")
