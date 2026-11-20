import uuid

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Sum
from django.db.models.functions import Coalesce
from django.utils import timezone


def _numero(prefixe):
    return f"{prefixe}-{timezone.now():%Y%m%d}-{uuid.uuid4().hex[:6].upper()}"


class CommandeAchat(models.Model):
    BROUILLON = "BROUILLON"
    COMMANDEE = "COMMANDEE"
    PARTIELLE = "PARTIELLE"
    COMPLETE = "COMPLETE"
    ANNULEE = "ANNULEE"
    STATUTS = [
        (BROUILLON, "Brouillon"),
        (COMMANDEE, "Commandee"),
        (PARTIELLE, "Partielle"),
        (COMPLETE, "Complete"),
        (ANNULEE, "Annulee"),
    ]

    numero = models.CharField(max_length=40, unique=True, blank=True)
    fournisseur = models.ForeignKey(
        "fournisseurs.Fournisseur", on_delete=models.PROTECT, related_name="commandes"
    )
    statut = models.CharField(max_length=12, choices=STATUTS, default=BROUILLON)
    date_creation = models.DateTimeField(auto_now_add=True)
    date_commande = models.DateTimeField(null=True, blank=True)
    montant_total = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    cree_par = models.ForeignKey(
        "utilisateurs.Utilisateur",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="commandes_creees",
    )

    class Meta:
        verbose_name = "Commande d'achat"
        verbose_name_plural = "Commandes d'achat"
        ordering = ["-date_creation"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(montant_total__gte=0),
                name="commande_montant_positif",
            )
        ]

    def __str__(self):
        return f"{self.numero} - {self.fournisseur}"

    def save(self, *args, **kwargs):
        if not self.numero:
            self.numero = _numero("CA")
        super().save(*args, **kwargs)

    def calculer_total(self):
        return sum((ligne.sous_total() for ligne in self.lignes.all()), start=0)

    def recalculer_total(self, sauvegarder=True):
        total = sum((ligne.sous_total() for ligne in self.lignes.all()), start=0)
        self.montant_total = total
        if sauvegarder and self.pk:
            self.save(update_fields=["montant_total"])
        return total

    def valider(self):
        if self.statut != self.BROUILLON:
            raise ValidationError("Seule une commande en brouillon peut etre validee.")
        if not self.lignes.exists():
            raise ValidationError("Une commande doit contenir au moins une ligne.")
        self.recalculer_total(sauvegarder=False)
        self.statut = self.COMMANDEE
        self.date_commande = timezone.now()
        self.save(update_fields=["statut", "date_commande", "montant_total"])

    def annuler(self):
        if self.statut == self.ANNULEE:
            raise ValidationError("Cette commande est deja annulee.")
        if self.receptions.filter(est_validee=True).exists():
            raise ValidationError(
                "Une commande deja partiellement ou totalement receptionnee ne peut pas etre annulee."
            )
        self.statut = self.ANNULEE
        self.save(update_fields=["statut"])

    def mettre_a_jour_statut(self):
        if self.statut == self.ANNULEE:
            return
        quantite_commandee = sum(
            ligne.quantite_commandee for ligne in self.lignes.all()
        )
        quantite_recue = sum(ligne.quantite_recue for ligne in self.lignes.all())
        if quantite_recue <= 0:
            if self.statut != self.BROUILLON:
                self.statut = self.COMMANDEE
        elif quantite_recue >= quantite_commandee:
            self.statut = self.COMPLETE
        else:
            self.statut = self.PARTIELLE
        self.save(update_fields=["statut"])

    def est_receptionnable(self):
        return self.statut in {self.COMMANDEE, self.PARTIELLE}


class LigneAchat(models.Model):
    commande = models.ForeignKey(
        CommandeAchat, on_delete=models.CASCADE, related_name="lignes"
    )
    medicament = models.ForeignKey(
        "medicaments.Medicament", on_delete=models.PROTECT, related_name="lignes_achat"
    )
    quantite_commandee = models.PositiveIntegerField()
    quantite_recue = models.PositiveIntegerField(default=0)
    prix_achat_unitaire = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        verbose_name = "Ligne d'achat"
        verbose_name_plural = "Lignes d'achat"
        constraints = [
            models.UniqueConstraint(
                fields=["commande", "medicament"], name="ligne_achat_unique"
            ),
            models.CheckConstraint(
                condition=models.Q(quantite_commandee__gt=0),
                name="ligne_achat_quantite_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(prix_achat_unitaire__gt=0),
                name="ligne_achat_prix_positif",
            ),
            models.CheckConstraint(
                condition=models.Q(quantite_recue__lte=models.F("quantite_commandee")),
                name="ligne_achat_recue_inferieure_commandee",
            ),
        ]

    def __str__(self):
        return f"{self.medicament} x {self.quantite_commandee}"

    def sous_total(self):
        return self.prix_achat_unitaire * self.quantite_commandee

    def reste_a_recevoir(self):
        return max(self.quantite_commandee - self.quantite_recue, 0)


class ReceptionAchat(models.Model):
    numero_bon = models.CharField(max_length=40, unique=True, blank=True)
    commande = models.ForeignKey(
        CommandeAchat, on_delete=models.PROTECT, related_name="receptions"
    )
    date_reception = models.DateTimeField(default=timezone.now)
    recu_par = models.ForeignKey(
        "utilisateurs.Utilisateur",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="receptions",
    )
    est_validee = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Reception d'achat"
        verbose_name_plural = "Receptions d'achat"
        ordering = ["-date_reception"]

    def __str__(self):
        return f"{self.numero_bon} - {self.commande.fournisseur}"

    def save(self, *args, **kwargs):
        if not self.numero_bon:
            self.numero_bon = _numero("BR")
        super().save(*args, **kwargs)

    def valider(self, utilisateur=None):
        from stock.services import ServiceStock

        reception = ServiceStock.entrer_stock(self, utilisateur=utilisateur)
        self.est_validee = reception.est_validee
        return reception

    def montant_total(self):
        return sum(
            (
                ligne.quantite_recue * ligne.ligne_achat.prix_achat_unitaire
                for ligne in self.lignes.select_related("ligne_achat")
            ),
            start=0,
        )


class LigneReception(models.Model):
    reception = models.ForeignKey(
        ReceptionAchat, on_delete=models.CASCADE, related_name="lignes"
    )
    ligne_achat = models.ForeignKey(
        LigneAchat, on_delete=models.PROTECT, related_name="lignes_reception"
    )
    numero_lot = models.CharField(max_length=80)
    date_peremption = models.DateField()
    quantite_recue = models.PositiveIntegerField()
    lot = models.ForeignKey(
        "stock.LotStock",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="lignes_reception",
    )

    class Meta:
        verbose_name = "Ligne de reception"
        verbose_name_plural = "Lignes de reception"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(quantite_recue__gt=0),
                name="ligne_reception_quantite_positive",
            )
        ]

    def __str__(self):
        return f"{self.ligne_achat.medicament} - lot {self.numero_lot}"

    def sous_total(self):
        return self.quantite_recue * self.ligne_achat.prix_achat_unitaire

    def creer_lot(self):
        from stock.models import LotStock

        medicament = self.ligne_achat.medicament
        lot = (
            LotStock.objects.select_for_update()
            .filter(medicament=medicament, numero_lot=self.numero_lot)
            .first()
        )
        if lot is not None:
            if lot.date_peremption != self.date_peremption:
                raise ValidationError(
                    "Un lot portant ce numero existe deja avec une autre date de peremption."
                )
            lot.quantite_recue += self.quantite_recue
            lot.quantite_disponible += self.quantite_recue
            lot.save(update_fields=["quantite_recue", "quantite_disponible"])
        else:
            lot = LotStock.objects.create(
                medicament=medicament,
                numero_lot=self.numero_lot,
                date_peremption=self.date_peremption,
                quantite_recue=self.quantite_recue,
                quantite_disponible=self.quantite_recue,
                date_reception=timezone.localdate(self.reception.date_reception),
            )
        self.lot = lot
        self.save(update_fields=["lot"])
        return lot
