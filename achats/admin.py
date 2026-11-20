from django.contrib import admin

from .models import CommandeAchat, LigneAchat, LigneReception, ReceptionAchat


class LigneAchatInline(admin.TabularInline):
    model = LigneAchat
    extra = 0


@admin.register(CommandeAchat)
class CommandeAchatAdmin(admin.ModelAdmin):
    list_display = (
        "numero",
        "fournisseur",
        "statut",
        "date_creation",
        "montant_total",
        "cree_par",
    )
    list_filter = ("statut", "fournisseur", "date_creation")
    search_fields = ("numero", "fournisseur__nom")
    readonly_fields = ("numero", "date_creation")
    inlines = [LigneAchatInline]


class LigneReceptionInline(admin.TabularInline):
    model = LigneReception
    extra = 0
    readonly_fields = ("lot",)


@admin.register(ReceptionAchat)
class ReceptionAchatAdmin(admin.ModelAdmin):
    list_display = ("numero_bon", "commande", "date_reception", "recu_par", "est_validee")
    list_filter = ("est_validee", "date_reception")
    search_fields = ("numero_bon", "commande__numero", "commande__fournisseur__nom")
    readonly_fields = ("numero_bon",)
    inlines = [LigneReceptionInline]
