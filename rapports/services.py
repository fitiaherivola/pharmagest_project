from datetime import date
from decimal import Decimal

from django.db.models import DecimalField, ExpressionWrapper, F, Sum
from django.db.models.functions import Coalesce
from django.utils import timezone

from achats.models import LigneReception
from medicaments.models import Medicament
from stock.models import LotStock
from ventes.models import LigneVente, Paiement, Vente

from stock.services import ServiceStock
from ventes.services import ServiceVente

__all__ = ["ServiceStatistiques", "ServiceStock", "ServiceVente"]


class ServiceStatistiques:
    """Indicateurs separes : chiffre d'affaires, encaissements et marge."""

    @staticmethod
    def medicaments_actifs():
        return Medicament.objects.filter(statut=Medicament.ACTIF).count()

    @staticmethod
    def ventes_du_jour():
        return Vente.objects.filter(
            statut=Vente.VALIDEE, date_vente__date=timezone.localdate()
        ).aggregate(total=Coalesce(Sum("total"), Decimal("0")))["total"]

    @staticmethod
    def ventes_periode(debut=None, fin=None):
        ventes = Vente.objects.filter(statut=Vente.VALIDEE)
        if debut:
            ventes = ventes.filter(date_vente__date__gte=debut)
        if fin:
            ventes = ventes.filter(date_vente__date__lte=fin)
        return ventes.aggregate(total=Coalesce(Sum("total"), Decimal("0")))["total"]

    @staticmethod
    def achats_periode(debut=None, fin=None):
        lignes = LigneReception.objects.filter(
            reception__est_validee=True
        ).select_related("ligne_achat")
        if debut:
            lignes = lignes.filter(reception__date_reception__date__gte=debut)
        if fin:
            lignes = lignes.filter(reception__date_reception__date__lte=fin)
        montant = Decimal("0")
        for ligne in lignes:
            montant += ligne.quantite_recue * ligne.ligne_achat.prix_achat_unitaire
        return montant

    @staticmethod
    def produits_plus_vendus(n=5, debut=None, fin=None):
        lignes = LigneVente.objects.filter(vente__statut=Vente.VALIDEE)
        if debut:
            lignes = lignes.filter(vente__date_vente__date__gte=debut)
        if fin:
            lignes = lignes.filter(vente__date_vente__date__lte=fin)
        return list(
            lignes.values("medicament__id", "medicament__nom_commercial")
            .annotate(quantite=Sum("quantite"))
            .order_by("-quantite")[:n]
        )

    @staticmethod
    def chiffre_affaires(debut=None, fin=None):
        return ServiceStatistiques.ventes_periode(debut, fin)

    @staticmethod
    def encaissements(debut=None, fin=None):
        paiements = Paiement.objects.filter(statut=Paiement.CONFIRME)
        if debut:
            paiements = paiements.filter(date_paiement__date__gte=debut)
        if fin:
            paiements = paiements.filter(date_paiement__date__lte=fin)
        return paiements.aggregate(total=Coalesce(Sum("montant"), Decimal("0")))["total"]

    @staticmethod
    def marge_commerciale(debut=None, fin=None):
        lignes = LigneVente.objects.filter(vente__statut=Vente.VALIDEE).select_related(
            "lot__medicament"
        )
        if debut:
            lignes = lignes.filter(vente__date_vente__date__gte=debut)
        if fin:
            lignes = lignes.filter(vente__date_vente__date__lte=fin)
        marge = Decimal("0")
        for ligne in lignes:
            marge += (
                ligne.prix_unitaire_applique - ligne.lot.medicament.prix_achat
            ) * ligne.quantite
        return marge

    @staticmethod
    def ventes_par_jour(n=7):
        from datetime import timedelta

        resultat = []
        aujourdhui = timezone.localdate()
        for decalage in range(n - 1, -1, -1):
            jour = aujourdhui - timedelta(days=decalage)
            total = Vente.objects.filter(
                statut=Vente.VALIDEE, date_vente__date=jour
            ).aggregate(total=Coalesce(Sum("total"), Decimal("0")))["total"]
            resultat.append({"jour": jour, "total": total})
        return resultat

    @staticmethod
    def valeur_stock():
        return ServiceStock.valeur_stock()

    @staticmethod
    def resume():
        return {
            "medicaments_actifs": ServiceStatistiques.medicaments_actifs(),
            "ventes_du_jour": ServiceStatistiques.ventes_du_jour(),
            "chiffre_affaires": ServiceStatistiques.chiffre_affaires(),
            "encaissements": ServiceStatistiques.encaissements(),
            "marge_commerciale": ServiceStatistiques.marge_commerciale(),
            "valeur_stock": ServiceStatistiques.valeur_stock(),
        }
