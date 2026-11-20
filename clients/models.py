from decimal import Decimal

from django.db import models
from django.db.models import Sum
from django.db.models.functions import Coalesce


class Client(models.Model):
    nom = models.CharField(max_length=150, blank=True)
    telephone = models.CharField(max_length=30, blank=True)
    adresse = models.CharField(max_length=255, blank=True)
    est_actif = models.BooleanField(default=True)
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Client"
        verbose_name_plural = "Clients"
        ordering = ["nom", "telephone"]

    def __str__(self):
        return self.nom or self.telephone or f"Client #{self.pk}"

    def historique_ventes(self):
        return self.ventes.all().order_by("-date_vente")

    def total_achats(self):
        return self.ventes.filter(statut="VALIDEE").aggregate(
            total=Coalesce(Sum("total"), Decimal("0"))
        )["total"]
