from django.urls import path

from . import views

app_name = "achats"

urlpatterns = [
    path("", views.liste_commandes, name="commandes"),
    path("nouvelle/", views.creer_commande, name="creer_commande"),
    path("receptions/", views.liste_receptions, name="receptions"),
    path("receptions/<int:pk>/", views.detail_reception, name="reception_detail"),
    path("receptions/<int:pk>/valider/", views.valider_reception, name="valider_reception"),
    path("receptions/<int:pk>/pdf/", views.bon_reception_pdf, name="bon_reception_pdf"),
    path("<int:pk>/", views.detail_commande, name="commande_detail"),
    path("<int:pk>/modifier/", views.modifier_commande, name="modifier_commande"),
    path("<int:pk>/lignes/ajouter/", views.ajouter_ligne, name="ajouter_ligne"),
    path("<int:pk>/lignes/<int:ligne_pk>/supprimer/", views.supprimer_ligne, name="supprimer_ligne"),
    path("<int:pk>/valider/", views.valider_commande, name="valider_commande"),
    path("<int:pk>/annuler/", views.annuler_commande, name="annuler_commande"),
    path("<int:pk>/reception/", views.creer_reception, name="creer_reception"),
    path("<int:pk>/pdf/", views.bon_commande_pdf, name="bon_commande_pdf"),
]
