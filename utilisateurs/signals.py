"""Initialisation des roles et de leurs permissions apres les migrations."""

from django.contrib.auth.models import Permission
from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.db import connection
from django.db.models.signals import post_migrate
from django.dispatch import receiver

from .models import JournalAudit, Role

ROLES = {
    "Administrateur": "Acces complet au systeme, gestion des utilisateurs et du journal.",
    "Pharmacien": "Responsable des medicaments, achats, stock, ventes et rapports.",
    "Caissier": "Encaissement des ventes et gestion des clients au comptoir.",
    "Magasinier": "Reception des commandes, gestion des lots et inventaires.",
    "Gestionnaire": "Consultation des donnees, du stock et des rapports.",
}


def _codes(*codes):
    return list(codes)


def _tous_les_codes(apps):
    codes = []
    for app in apps:
        codes.extend(
            Permission.objects.filter(content_type__app_label=app).values_list(
                "content_type__app_label", "codename"
            )
        )
    return [f"{app}.{codename}" for app, codename in codes]


def _permissions_par_role():
    return {
        "Pharmacien": (
            _tous_les_codes(
                ["medicaments", "fournisseurs", "clients", "achats", "stock", "ventes"]
            )
            + _codes(
                "utilisateurs.view_utilisateur",
                "utilisateurs.view_role",
            )
        ),
        "Caissier": _codes(
            "medicaments.view_medicament",
            "medicaments.view_categorie",
            "clients.view_client",
            "clients.add_client",
            "clients.change_client",
            "ventes.view_vente",
            "ventes.add_vente",
            "ventes.change_vente",
            "ventes.view_lignevente",
            "ventes.add_lignevente",
            "ventes.view_paiement",
            "ventes.add_paiement",
            "ventes.view_retourvente",
            "ventes.add_retourvente",
            "stock.view_lotstock",
            "stock.view_mouvementstock",
        ),
        "Magasinier": _codes(
            "medicaments.view_medicament",
            "medicaments.view_categorie",
            "fournisseurs.view_fournisseur",
            "fournisseurs.add_fournisseur",
            "fournisseurs.change_fournisseur",
            "achats.view_commandeachat",
            "achats.add_commandeachat",
            "achats.change_commandeachat",
            "achats.view_ligneachat",
            "achats.add_ligneachat",
            "achats.change_ligneachat",
            "achats.view_receptionachat",
            "achats.add_receptionachat",
            "achats.change_receptionachat",
            "achats.view_lignereception",
            "achats.add_lignereception",
            "stock.view_lotstock",
            "stock.add_lotstock",
            "stock.change_lotstock",
            "stock.view_mouvementstock",
            "stock.view_inventaire",
            "stock.add_inventaire",
            "stock.change_inventaire",
            "stock.view_ligneinventaire",
            "stock.add_ligneinventaire",
            "stock.change_ligneinventaire",
        ),
        "Gestionnaire": (
            [
                code
                for code in _tous_les_codes(
                    ["medicaments", "fournisseurs", "clients", "achats", "stock", "ventes"]
                )
                if code.split(".")[1].startswith("view_")
            ]
            + _codes(
                "utilisateurs.view_utilisateur",
                "utilisateurs.view_role",
            )
        ),
    }


def _permissions_depuis_codes(codes):
    permissions = []
    for code in codes:
        try:
            app_label, codename = code.split(".", 1)
        except ValueError:
            continue
        permission = Permission.objects.filter(
            content_type__app_label=app_label, codename=codename
        ).first()
        if permission:
            permissions.append(permission)
    return permissions


@receiver(post_migrate)
def initialiser_roles(sender, **kwargs):
    """Recree les roles apres chaque app pour disposer de toutes les permissions.

    Django emet ``post_migrate`` application par application : les permissions
    des apps suivantes ne sont pas encore creees lors du premier passage.
    """
    if "utilisateurs_role" not in connection.introspection.table_names():
        return

    toutes = list(Permission.objects.all())
    permissions_par_role = _permissions_par_role()
    for nom, description in ROLES.items():
        role, cree = Role.objects.get_or_create(
            nom=nom, defaults={"description": description}
        )
        if nom == "Administrateur":
            role.permissions.set(toutes)
            continue
        codes = permissions_par_role.get(nom, [])
        permissions = _permissions_depuis_codes(codes)
        if len(permissions) < len(codes):
            continue
        if cree or len(permissions) > role.permissions.count():
            role.permissions.set(permissions)


@receiver(user_logged_in)
def journaliser_connexion(sender, request, user, **kwargs):
    JournalAudit.enregistrer(user, "CONNEXION", details={"username": user.username}, request=request)


@receiver(user_logged_out)
def journaliser_deconnexion(sender, request, user, **kwargs):
    if user is not None:
        JournalAudit.enregistrer(user, "DECONNEXION", details={"username": user.username}, request=request)
