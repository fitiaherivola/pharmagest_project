from django.contrib.auth.models import AbstractUser, Permission
from django.core.exceptions import ValidationError
from django.db import models


class Role(models.Model):
    nom = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True)
    permissions = models.ManyToManyField(
        Permission,
        blank=True,
        related_name="roles",
        help_text="Permissions Django accordees aux utilisateurs de ce role.",
    )

    class Meta:
        verbose_name = "Role"
        verbose_name_plural = "Roles"
        ordering = ["nom"]

    def __str__(self):
        return self.nom

    def a_permission(self, code):
        """Verifie une permission sous la forme 'app_label.codename'."""
        if not code:
            return False
        if "." in code:
            app_label, codename = code.split(".", 1)
            return self.permissions.filter(
                codename=codename, content_type__app_label=app_label
            ).exists()
        return self.permissions.filter(codename=code).exists()


class Utilisateur(AbstractUser):
    telephone = models.CharField(max_length=30, blank=True)
    role = models.ForeignKey(
        Role,
        on_delete=models.PROTECT,
        related_name="utilisateurs",
        null=True,
        blank=True,
    )
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Utilisateur"
        verbose_name_plural = "Utilisateurs"
        ordering = ["username"]

    def __str__(self):
        return self.nom_complet()

    @property
    def derniere_connexion(self):
        return self.last_login

    def nom_complet(self):
        nom = f"{self.first_name} {self.last_name}".strip()
        return nom or self.username

    def peut(self, code):
        """Controle d'acces centralise utilise par les vues et les templates."""
        if not self.is_active:
            return False
        if self.is_superuser:
            return True
        if self.has_perm(code):
            return True
        if self.role and self.role.a_permission(code):
            return True
        return False

    def activer(self):
        self.is_active = True
        self.save(update_fields=["is_active"])

    def desactiver(self):
        self.is_active = False
        self.save(update_fields=["is_active"])

    def changer_mot_de_passe(self, ancien, nouveau):
        if self.has_usable_password() and not self.check_password(ancien):
            raise ValidationError("Ancien mot de passe incorrect.")
        self.set_password(nouveau)
        self.save(update_fields=["password"])


class JournalAudit(models.Model):
    ACTIONS = [
        ("CREATION", "Creation"),
        ("MODIFICATION", "Modification"),
        ("SUPPRESSION", "Suppression"),
        ("VALIDATION", "Validation"),
        ("ANNULATION", "Annulation"),
        ("CONNEXION", "Connexion"),
        ("DECONNEXION", "Deconnexion"),
        ("RECEPTION", "Reception"),
        ("PAIEMENT", "Paiement"),
        ("RETOUR", "Retour"),
        ("INVENTAIRE", "Inventaire"),
        ("ACCES_REFUSE", "Acces refuse"),
    ]

    utilisateur = models.ForeignKey(
        "utilisateurs.Utilisateur",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="journal",
    )
    action = models.CharField(max_length=20, choices=ACTIONS)
    modele_cible = models.CharField(max_length=100, blank=True)
    objet_id = models.PositiveBigIntegerField(null=True, blank=True)
    details = models.JSONField(default=dict, blank=True)
    adresse_ip = models.GenericIPAddressField(null=True, blank=True)
    date_action = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Journal d'audit"
        verbose_name_plural = "Journal d'audit"
        ordering = ["-date_action"]
        indexes = [models.Index(fields=["modele_cible", "objet_id"])]

    def __str__(self):
        return f"{self.date_action:%d/%m/%Y %H:%M} - {self.action} - {self.modele_cible}"

    def save(self, *args, **kwargs):
        if self.pk is not None:
            raise ValidationError("Le journal d'audit est en ajout seulement.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Le journal d'audit ne peut pas etre supprime.")

    @staticmethod
    def _ip(request):
        if request is None:
            return None
        xff = request.META.get("HTTP_X_FORWARDED_FOR")
        if xff:
            return xff.split(",")[0].strip()
        return request.META.get("REMOTE_ADDR")

    @classmethod
    def enregistrer(cls, utilisateur, action, objet=None, details=None, request=None):
        modele = ""
        objet_id = None
        if objet is not None:
            modele = objet.__class__.__name__
            objet_id = getattr(objet, "pk", None)
        details = details or {}
        try:
            return cls.objects.create(
                utilisateur=utilisateur if getattr(utilisateur, "pk", None) else None,
                action=action,
                modele_cible=modele,
                objet_id=objet_id,
                details=details,
                adresse_ip=cls._ip(request),
            )
        except Exception:
            # Le journal ne doit jamais casser une operation metier.
            return None
