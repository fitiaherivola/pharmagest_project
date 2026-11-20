from datetime import date

from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator, MinValueValidator
from django.db import models
from django.db.models import Q, Sum
from django.db.models.functions import Coalesce


def valider_image(fichier):
    """Controle le type MIME et la taille des photos de medicaments."""
    if fichier.size > 2 * 1024 * 1024:
        raise ValidationError("La photo ne doit pas depasser 2 Mo.")
    type_mime = getattr(fichier, "content_type", "")
    if type_mime and type_mime not in {"image/jpeg", "image/png", "image/webp"}:
        raise ValidationError("Format d'image non autorise (JPEG, PNG ou WebP).")


class Categorie(models.Model):
    nom = models.CharField(max_length=120, unique=True)
    description = models.TextField(blank=True)

    class Meta:
        verbose_name = "Categorie"
        verbose_name_plural = "Categories"
        ordering = ["nom"]

    def __str__(self):
        return self.nom

    def est_utilisee(self):
        return self.medicaments.exists()

    def supprimer(self):
        if self.est_utilisee():
            raise ValidationError(
                "Cette categorie est utilisee par des medicaments : suppression interdite."
            )
        self.delete()


class Medicament(models.Model):
    ACTIF = "ACTIF"
    ARCHIVE = "ARCHIVE"
    STATUTS = [(ACTIF, "Actif"), (ARCHIVE, "Archive")]

    FORMES = [
        ("COMPRIME", "Comprime"),
        ("SIROP", "Sirop"),
        ("GELULE", "Gelule"),
        ("INJECTION", "Injection"),
        ("POMMADE", "Pommade"),
        ("GOUTTES", "Gouttes"),
        ("AUTRE", "Autre"),
    ]

    nom_commercial = models.CharField(max_length=150)
    denomination_generique = models.CharField(max_length=150, blank=True)
    categorie = models.ForeignKey(
        Categorie, on_delete=models.PROTECT, related_name="medicaments"
    )
    forme = models.CharField(max_length=20, choices=FORMES, default="COMPRIME")
    dosage = models.CharField(max_length=80, blank=True)
    laboratoire = models.CharField(max_length=120, blank=True)
    code_barres = models.CharField(max_length=80, unique=True, null=True, blank=True)
    photo = models.ImageField(
        upload_to="medicaments/%Y/%m/",
        blank=True,
        null=True,
        validators=[FileExtensionValidator(["jpg", "jpeg", "png", "webp"]), valider_image],
    )
    prix_achat = models.DecimalField(max_digits=12, decimal_places=2)
    prix_vente = models.DecimalField(max_digits=12, decimal_places=2)
    seuil_alerte = models.PositiveIntegerField(default=10)
    statut = models.CharField(max_length=10, choices=STATUTS, default=ACTIF)
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Medicament"
        verbose_name_plural = "Medicaments"
        ordering = ["nom_commercial"]
        indexes = [
            models.Index(fields=["nom_commercial"]),
            models.Index(fields=["code_barres"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(prix_achat__gt=0), name="medicament_prix_achat_positif"
            ),
            models.CheckConstraint(
                condition=Q(prix_vente__gt=0), name="medicament_prix_vente_positif"
            ),
        ]

    def __str__(self):
        return f"{self.nom_commercial} {self.dosage}".strip()

    def save(self, *args, **kwargs):
        if not self.code_barres:
            self.code_barres = None
        else:
            self.code_barres = self.code_barres.strip() or None
        super().save(*args, **kwargs)

    def lots_delivrables(self):
        return self.lots.filter(
            est_bloque=False, date_peremption__gte=date.today(), quantite_disponible__gt=0
        )

    def stock_total(self):
        return self.lots_delivrables().aggregate(
            total=Coalesce(Sum("quantite_disponible"), 0)
        )["total"]

    def est_en_alerte(self):
        return self.stock_total() <= self.seuil_alerte

    def est_en_rupture(self):
        return self.stock_total() == 0

    def archiver(self):
        self.statut = self.ARCHIVE
        self.save(update_fields=["statut"])

    def desarchiver(self):
        self.statut = self.ACTIF
        self.save(update_fields=["statut"])

    def peut_etre_supprime(self):
        return not (
            self.lots.exists()
            or self.lignes_vente.exists()
            or self.lignes_achat.exists()
        )
