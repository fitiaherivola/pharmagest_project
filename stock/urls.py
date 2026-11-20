from django.urls import path

from . import views

app_name = "stock"

urlpatterns = [
    path("", views.liste_lots, name="lots"),
    path("nouveau/", views.creer_lot, name="creer_lot"),
    path("mouvements/", views.liste_mouvements, name="mouvements"),
    path("alertes/", views.alertes, name="alertes"),
    path("inventaires/", views.liste_inventaires, name="inventaires"),
    path("inventaires/nouveau/", views.creer_inventaire, name="creer_inventaire"),
    path("inventaires/<int:pk>/", views.detail_inventaire, name="inventaire_detail"),
    path("inventaires/<int:pk>/saisir/", views.saisir_inventaire, name="saisir_inventaire"),
    path("inventaires/<int:pk>/annuler/", views.annuler_inventaire, name="annuler_inventaire"),
    path("<int:pk>/", views.detail_lot, name="lot_detail"),
    path("<int:pk>/modifier/", views.modifier_lot, name="modifier_lot"),
    path("<int:pk>/basculer/", views.basculer_blocage, name="basculer_blocage"),
]
