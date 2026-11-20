from django.contrib import admin

from .models import Inventaire, LigneInventaire, LotStock, MouvementStock


@admin.register(LotStock)
class LotStockAdmin(admin.ModelAdmin):
    list_display = (
        "medicament",
        "numero_lot",
        "date_peremption",
        "quantite_recue",
        "quantite_disponible",
        "est_bloque",
    )
    list_filter = ("est_bloque", "date_peremption")
    search_fields = ("numero_lot", "medicament__nom_commercial")
    date_hierarchy = "date_peremption"


@admin.register(MouvementStock)
class MouvementStockAdmin(admin.ModelAdmin):
    list_display = (
        "date_mouvement",
        "type",
        "lot",
        "quantite",
        "stock_apres",
        "utilisateur",
    )
    list_filter = ("type", "date_mouvement")
    search_fields = ("lot__numero_lot", "lot__medicament__nom_commercial", "motif")
    readonly_fields = (
        "lot",
        "type",
        "quantite",
        "stock_apres",
        "reference_type",
        "reference_id",
        "motif",
        "utilisateur",
        "date_mouvement",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class LigneInventaireInline(admin.TabularInline):
    model = LigneInventaire
    extra = 0
    readonly_fields = ("ecart",)


@admin.register(Inventaire)
class InventaireAdmin(admin.ModelAdmin):
    list_display = ("date_inventaire", "statut", "realise_par", "date_creation")
    list_filter = ("statut", "date_inventaire")
    inlines = [LigneInventaireInline]
