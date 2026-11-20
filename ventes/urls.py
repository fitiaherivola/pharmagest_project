from django.urls import path

from . import views

app_name = "ventes"

urlpatterns = [
    path("", views.liste_ventes, name="liste"),
    path("caisse/", views.caisse, name="caisse"),
    path("<int:pk>/", views.detail_vente, name="detail"),
    path("<int:pk>/annuler/", views.annuler_vente, name="annuler"),
    path("<int:pk>/retour/", views.creer_retour, name="retour"),
    path("<int:pk>/recu.pdf", views.recu_pdf, name="recu_pdf"),
    path("<int:pk>/facture.pdf", views.facture_pdf, name="facture_pdf"),
    path("paiements/<int:pk>/confirmer/", views.confirmer_paiement, name="confirmer_paiement"),
]
