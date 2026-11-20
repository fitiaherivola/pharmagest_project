from datetime import date, timedelta

from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models import Q, Sum


class LotStock(models.Model):
    medicament = models.ForeignKey(
        "medicaments.Medicament", on_delete=models.PROTECT, related_name="lots"
    )
    numero_lot = models.CharField(max_length=80)
    date_peremption = models.DateField()
    quantite_recue = models.PositiveIntegerField(default=0)
    quantite_disponible = models.PositiveIntegerField(default=0)
    est_bloque = models.BooleanField(default=False)
    motif_blocage = models.TextField(blank=True)
    date_reception = models.DateField(default=date.today)

    class Meta:
        verbose_name = "Lot de stock"
        verbose_name_plural = "Lots de stock"
        ordering = ["date_peremption", "numero_lot"]
        constraints = [
            models.UniqueConstraint(
                fields=["medicament", "numero_lot"], name="lot_unique_par_medicament"
            ),
            models.CheckConstraint(
                condition=Q(quantite_disponible__gte=0),
                name="lot_quantite_disponible_non_negative",
            ),
        ]
        indexes = [models.Index(fields=["date_peremption"])]

    def __str__(self):
        return f"{self.medicament} - lot {self.numero_lot}"

    def est_perime(self):
        return self.date_peremption < date.today()

    def est_delivrable(self):
        return (
            not self.est_bloque
            and not self.est_perime()
            and self.quantite_disponible > 0
        )

    def jours_avant_peremption(self):
        return (self.date_peremption - date.today()).days

    def bloquer(self, motif=""):
        self.est_bloque = True
        self.motif_blocage = motif
        self.save(update_fields=["est_bloque", "motif_blocage"])

    def debloquer(self):
        self.est_bloque = False
        self.motif_blocage = ""
        self.save(update_fields=["est_bloque", "motif_blocage"])

    @classmethod
    def lots_fefo(cls, medicament=None, for_update=False):
        """Lots delivrables tries par peremption la plus proche (FEFO)."""
        lots = cls.objects.filter(
            est_bloque=False,
            date_peremption__gte=date.today(),
            quantite_disponible__gt=0,
        )
        if medicament is not None:
            lots = lots.filter(medicament=medicament)
        if for_update:
            lots = lots.select_for_update()
        return lots.order_by("date_peremption", "date_reception", "pk")

    def valeur_stock(self):
        return self.quantite_disponible * self.medicament.prix_achat


class MouvementStock(models.Model):
    ENTREE_ACHAT = "ENTREE_ACHAT"
    SORTIE_VENTE = "SORTIE_VENTE"
    RETOUR = "RETOUR"
    CORRECTION = "CORRECTION"
    INVENTAIRE = "INVENTAIRE"
    PEREMPTION = "PEREMPTION"
    TYPES = [
        (ENTREE_ACHAT, "Entree achat"),
        (SORTIE_VENTE, "Sortie vente"),
        (RETOUR, "Retour"),
        (CORRECTION, "Correction"),
        (INVENTAIRE, "Inventaire"),
        (PEREMPTION, "Peremption"),
    ]

    lot = models.ForeignKey(LotStock, on_delete=models.PROTECT, related_name="mouvements")
    type = models.CharField(max_length=20, choices=TYPES)
    quantite = models.IntegerField(help_text="Quantite signee : positive en entree, negative en sortie.")
    stock_apres = models.PositiveIntegerField()
    reference_type = models.CharField(max_length=50, blank=True)
    reference_id = models.PositiveBigIntegerField(null=True, blank=True)
    motif = models.TextField(blank=True)
    utilisateur = models.ForeignKey(
        "utilisateurs.Utilisateur",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="mouvements_stock",
    )
    date_mouvement = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Mouvement de stock"
        verbose_name_plural = "Mouvements de stock"
        ordering = ["-date_mouvement"]
        constraints = [
            models.CheckConstraint(
                condition=~Q(quantite=0), name="mouvement_quantite_non_nulle"
            )
        ]
        indexes = [models.Index(fields=["type", "date_mouvement"])]

    def __str__(self):
        return f"{self.type} {self.quantite:+d} - {self.lot}"

    def save(self, *args, **kwargs):
        if self.pk is not None:
            raise ValidationError("Un mouvement de stock ne peut pas etre modifie.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Un mouvement de stock ne peut pas etre supprime.")

    @classmethod
    def enregistrer(
        cls,
        lot,
        type_mouvement,
        quantite,
        utilisateur=None,
        reference_type="",
        reference_id=None,
        motif="",
    ):
        quantite = int(quantite)
        if quantite == 0:
            raise ValidationError("Un mouvement de stock ne peut pas avoir une quantite nulle.")
        return cls.objects.create(
            lot=lot,
            type=type_mouvement,
            quantite=quantite,
            stock_apres=lot.quantite_disponible,
            reference_type=reference_type,
            reference_id=reference_id,
            motif=motif,
            utilisateur=utilisateur if getattr(utilisateur, "pk", None) else None,
        )


class Inventaire(models.Model):
    EN_COURS = "EN_COURS"
    VALIDE = "VALIDE"
    ANNULE = "ANNULE"
    STATUTS = [(EN_COURS, "En cours"), (VALIDE, "Valide"), (ANNULE, "Annule")]

    date_inventaire = models.DateField(default=date.today)
    statut = models.CharField(max_length=10, choices=STATUTS, default=EN_COURS)
    realise_par = models.ForeignKey(
        "utilisateurs.Utilisateur",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="inventaires",
    )
    commentaire = models.TextField(blank=True)
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Inventaire"
        verbose_name_plural = "Inventaires"
        ordering = ["-date_inventaire", "-pk"]

    def __str__(self):
        return f"Inventaire du {self.date_inventaire:%d/%m/%Y} ({self.get_statut_display()})"

    def total_ecarts(self):
        return sum(abs(ligne.ecart()) for ligne in self.lignes.all())

    @transaction.atomic
    def valider(self, utilisateur=None):
        inventaire = Inventaire.objects.select_for_update().get(pk=self.pk)
        if inventaire.statut != self.EN_COURS:
            raise ValidationError("Seul un inventaire en cours peut etre valide.")
        lignes = list(inventaire.lignes.select_related("lot"))
        if not lignes:
            raise ValidationError("Impossible de valider un inventaire sans ligne.")
        for ligne in lignes:
            lot = LotStock.objects.select_for_update().get(pk=ligne.lot_id)
            ecart = ligne.ecart()
            if ecart == 0:
                continue
            nouvelle_quantite = lot.quantite_disponible + ecart
            if nouvelle_quantite < 0:
                raise ValidationError(
                    f"La correction du lot {lot.numero_lot} rendrait le stock negatif."
                )
            lot.quantite_disponible = nouvelle_quantite
            lot.save(update_fields=["quantite_disponible"])
            MouvementStock.enregistrer(
                lot,
                MouvementStock.INVENTAIRE,
                ecart,
                utilisateur=utilisateur or inventaire.realise_par,
                reference_type="Inventaire",
                reference_id=inventaire.pk,
                motif=f"Inventaire du {inventaire.date_inventaire:%d/%m/%Y}",
            )
        inventaire.statut = self.VALIDE
        inventaire.save(update_fields=["statut"])
        self.statut = self.VALIDE
        return inventaire

    def annuler(self):
        if self.statut == self.VALIDE:
            raise ValidationError("Un inventaire valide ne peut pas etre annule.")
        self.statut = self.ANNULE
        self.save(update_fields=["statut"])


class LigneInventaire(models.Model):
    inventaire = models.ForeignKey(
        Inventaire, on_delete=models.CASCADE, related_name="lignes"
    )
    lot = models.ForeignKey(
        LotStock, on_delete=models.PROTECT, related_name="lignes_inventaire"
    )
    quantite_theorique = models.PositiveIntegerField(default=0)
    quantite_comptee = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = "Ligne d'inventaire"
        verbose_name_plural = "Lignes d'inventaire"
        constraints = [
            models.UniqueConstraint(
                fields=["inventaire", "lot"], name="ligne_inventaire_unique"
            )
        ]

    def __str__(self):
        return f"{self.lot} - theorique {self.quantite_theorique} / compte {self.quantite_comptee}"

    def ecart(self):
        return self.quantite_comptee - self.quantite_theorique
