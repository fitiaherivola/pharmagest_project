from django.contrib import admin

from .models import LigneVente, Paiement, RetourVente, Vente


class LigneVenteInline(admin.TabularInline):
    model = LigneVente
    extra = 0
    readonly_fields = ("sous_total",)


class PaiementInline(admin.TabularInline):
    model = Paiement
    extra = 0


@admin.register(Vente)
class VenteAdmin(admin.ModelAdmin):
    list_display = ("numero", "date_vente", "client", "caissier", "total", "statut")
    list_filter = ("statut", "date_vente", "caissier")
    search_fields = ("numero", "client__nom", "caissier__username")
    readonly_fields = ("numero", "cle_idempotence", "date_vente")
    date_hierarchy = "date_vente"
    inlines = [LigneVenteInline, PaiementInline]


@admin.register(RetourVente)
class RetourVenteAdmin(admin.ModelAdmin):
    list_display = (
        "date_retour",
        "vente",
        "ligne_vente",
        "quantite_retournee",
        "remis_en_stock",
        "montant_rembourse",
        "est_valide",
    )
    list_filter = ("est_valide", "remis_en_stock", "date_retour")
    search_fields = ("vente__numero", "motif")


@admin.register(Paiement)
class PaiementAdmin(admin.ModelAdmin):
    list_display = ("vente", "mode", "montant", "statut", "date_paiement")
    list_filter = ("mode", "statut", "date_paiement")
    search_fields = ("vente__numero", "reference_transaction")
