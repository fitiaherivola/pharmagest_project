import uuid
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


def _numero_vente():
    return f"V-{timezone.now():%Y%m%d}-{uuid.uuid4().hex[:6].upper()}"


class Vente(models.Model):
    EN_COURS = "EN_COURS"
    VALIDEE = "VALIDEE"
    ANNULEE = "ANNULEE"
    STATUTS = [
        (EN_COURS, "En cours"),
        (VALIDEE, "Validee"),
        (ANNULEE, "Annulee"),
    ]

    numero = models.CharField(max_length=40, unique=True, blank=True)
    client = models.ForeignKey(
        "clients.Client",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ventes",
    )
    caissier = models.ForeignKey(
        "utilisateurs.Utilisateur",
        on_delete=models.PROTECT,
        related_name="ventes",
    )
    date_vente = models.DateTimeField(auto_now_add=True)
    statut = models.CharField(max_length=10, choices=STATUTS, default=EN_COURS)
    total = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    cle_idempotence = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    motif_annulation = models.TextField(blank=True)

    class Meta:
        verbose_name = "Vente"
        verbose_name_plural = "Ventes"
        ordering = ["-date_vente"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(total__gte=0), name="vente_total_positif"
            )
        ]
        indexes = [models.Index(fields=["statut", "date_vente"])]

    def __str__(self):
        return self.numero

    def save(self, *args, **kwargs):
        if not self.numero:
            self.numero = _numero_vente()
        super().save(*args, **kwargs)

    def calculer_total(self):
        return sum(
            (ligne.sous_total() for ligne in self.lignes.all()), start=Decimal("0")
        )

    def recalculer_total(self, sauvegarder=True):
        self.total = self.calculer_total()
        if sauvegarder and self.pk:
            self.save(update_fields=["total"])
        return self.total

    def ajouter_ligne(self, lot, quantite, prix_unitaire=None):
        quantite = int(quantite)
        if quantite <= 0:
            raise ValidationError("La quantite doit etre strictement positive.")
        prix = prix_unitaire if prix_unitaire is not None else lot.medicament.prix_vente
        ligne, cree = LigneVente.objects.get_or_create(
            vente=self,
            lot=lot,
            defaults={
                "medicament": lot.medicament,
                "quantite": quantite,
                "prix_unitaire_applique": prix,
            },
        )
        if not cree:
            ligne.quantite += quantite
            ligne.save(update_fields=["quantite"])
        self.recalculer_total()
        return ligne

    def valider(self, utilisateur=None):
        from .services import ServiceVente

        vente = ServiceVente.valider_vente(
            self, utilisateur=utilisateur or self.caissier
        )
        self.statut = vente.statut
        self.total = vente.total
        return vente

    def annuler(self, motif, utilisateur=None):
        from .services import ServiceVente

        vente = ServiceVente.annuler_vente(
            self, motif, utilisateur=utilisateur or self.caissier
        )
        self.statut = vente.statut
        self.motif_annulation = vente.motif_annulation
        return vente

    def quantite_totale(self):
        return sum(ligne.quantite for ligne in self.lignes.all())


class LigneVente(models.Model):
    vente = models.ForeignKey(Vente, on_delete=models.CASCADE, related_name="lignes")
    medicament = models.ForeignKey(
        "medicaments.Medicament", on_delete=models.PROTECT, related_name="lignes_vente"
    )
    lot = models.ForeignKey(
        "stock.LotStock", on_delete=models.PROTECT, related_name="lignes_vente"
    )
    quantite = models.PositiveIntegerField()
    prix_unitaire_applique = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        verbose_name = "Ligne de vente"
        verbose_name_plural = "Lignes de vente"
        constraints = [
            models.UniqueConstraint(fields=["vente", "lot"], name="ligne_vente_unique_lot"),
            models.CheckConstraint(
                condition=models.Q(quantite__gt=0), name="ligne_vente_quantite_positive"
            ),
            models.CheckConstraint(
                condition=models.Q(prix_unitaire_applique__gt=0),
                name="ligne_vente_prix_positif",
            ),
        ]

    def __str__(self):
        return f"{self.medicament} x {self.quantite}"

    def sous_total(self):
        return self.prix_unitaire_applique * self.quantite

    def verifier_disponibilite(self):
        return self.lot.est_delivrable() and self.quantite <= self.lot.quantite_disponible

    def quantite_retournee(self):
        return sum(
            retour.quantite_retournee
            for retour in self.retours.filter(est_valide=True)
        )

    def quantite_restante_retournable(self):
        return max(self.quantite - self.quantite_retournee(), 0)


class Paiement(models.Model):
    ESPECES = "ESPECES"
    MOBILE_MONEY = "MOBILE_MONEY"
    AUTRE = "AUTRE"
    MODES = [(ESPECES, "Especes"), (MOBILE_MONEY, "Mobile money"), (AUTRE, "Autre")]

    EN_ATTENTE = "EN_ATTENTE"
    CONFIRME = "CONFIRME"
    ECHOUE = "ECHOUE"
    REMBOURSE = "REMBOURSE"
    STATUTS = [
        (EN_ATTENTE, "En attente"),
        (CONFIRME, "Confirme"),
        (ECHOUE, "Echoue"),
        (REMBOURSE, "Rembourse"),
    ]

    vente = models.ForeignKey(Vente, on_delete=models.CASCADE, related_name="paiements")
    mode = models.CharField(max_length=20, choices=MODES, default=ESPECES)
    montant = models.DecimalField(max_digits=14, decimal_places=2)
    statut = models.CharField(max_length=12, choices=STATUTS, default=EN_ATTENTE)
    reference_transaction = models.CharField(max_length=120, blank=True)
    date_paiement = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Paiement"
        verbose_name_plural = "Paiements"
        ordering = ["-date_paiement"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(montant__gt=0), name="paiement_montant_positif"
            )
        ]

    def __str__(self):
        return f"{self.get_mode_display()} - {self.montant}"

    def confirmer(self):
        self.statut = self.CONFIRME
        self.save(update_fields=["statut"])

    def rembourser(self, montant=None):
        self.statut = self.REMBOURSE
        if montant is not None:
            self.montant = montant
            self.save(update_fields=["statut", "montant"])
        else:
            self.save(update_fields=["statut"])


class RetourVente(models.Model):
    vente = models.ForeignKey(Vente, on_delete=models.PROTECT, related_name="retours")
    ligne_vente = models.ForeignKey(
        LigneVente, on_delete=models.PROTECT, related_name="retours"
    )
    quantite_retournee = models.PositiveIntegerField()
    motif = models.TextField()
    remis_en_stock = models.BooleanField(default=True)
    montant_rembourse = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    utilisateur = models.ForeignKey(
        "utilisateurs.Utilisateur",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="retours_vente",
    )
    date_retour = models.DateTimeField(auto_now_add=True)
    est_valide = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Retour de vente"
        verbose_name_plural = "Retours de vente"
        ordering = ["-date_retour"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(quantite_retournee__gt=0),
                name="retour_quantite_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(montant_rembourse__gte=0),
                name="retour_montant_positif",
            ),
        ]

    def __str__(self):
        return f"Retour {self.quantite_retournee} - {self.ligne_vente.medicament}"

    def est_eligible_remise_en_stock(self):
        lot = self.ligne_vente.lot
        return not lot.est_perime() and not lot.est_bloque

    def valider(self, utilisateur=None):
        from .services import ServiceVente

        retour = ServiceVente.traiter_retour(
            self, utilisateur=utilisateur or self.utilisateur
        )
        self.montant_rembourse = retour.montant_rembourse
        self.remis_en_stock = retour.remis_en_stock
        self.est_valide = retour.est_valide
        return retour
