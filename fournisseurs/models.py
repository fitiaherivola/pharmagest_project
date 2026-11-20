from decimal import Decimal

from django.db import models
from django.db.models import Sum
from django.db.models.functions import Coalesce


class Fournisseur(models.Model):
    nom = models.CharField(max_length=150)
    adresse = models.TextField(blank=True)
    telephone = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)
    numero_fiscal = models.CharField(max_length=80, blank=True)
    contact_principal = models.CharField(max_length=120, blank=True)
    est_actif = models.BooleanField(default=True)
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Fournisseur"
        verbose_name_plural = "Fournisseurs"
        ordering = ["nom"]

    def __str__(self):
        return self.nom

    def historique_achats(self):
        return self.commandes.all().order_by("-date_creation")

    def montant_total_commande(self):
        return self.commandes.exclude(statut="ANNULEE").aggregate(
            total=Coalesce(Sum("montant_total"), Decimal("0"))
        )["total"]

    def desactiver(self):
        self.est_actif = False
        self.save(update_fields=["est_actif"])
