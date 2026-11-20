from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import JournalAudit, Role, Utilisateur


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ("nom", "description")
    search_fields = ("nom",)
    filter_horizontal = ("permissions",)


@admin.register(Utilisateur)
class UtilisateurAdmin(UserAdmin):
    list_display = ("username", "nom_complet", "role", "is_active", "is_staff", "last_login")
    list_filter = ("role", "is_active", "is_staff", "is_superuser")
    search_fields = ("username", "first_name", "last_name", "email", "telephone")
    fieldsets = UserAdmin.fieldsets + (
        ("Pharmacie", {"fields": ("telephone", "role")}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ("Pharmacie", {"fields": ("telephone", "role")}),
    )

    @admin.display(description="Nom complet")
    def nom_complet(self, obj):
        return obj.nom_complet()


@admin.register(JournalAudit)
class JournalAuditAdmin(admin.ModelAdmin):
    list_display = ("date_action", "utilisateur", "action", "modele_cible", "objet_id", "adresse_ip")
    list_filter = ("action", "modele_cible")
    search_fields = ("modele_cible", "utilisateur__username", "details")
    readonly_fields = (
        "utilisateur",
        "action",
        "modele_cible",
        "objet_id",
        "details",
        "adresse_ip",
        "date_action",
    )
    date_hierarchy = "date_action"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
