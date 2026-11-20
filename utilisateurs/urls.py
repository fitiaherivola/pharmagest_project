from django.urls import path

from . import views

app_name = "utilisateurs"

urlpatterns = [
    path("connexion/", views.ConnexionView.as_view(), name="connexion"),
    path("deconnexion/", views.DeconnexionView.as_view(), name="deconnexion"),
    path("profil/", views.profil, name="profil"),
    path("profil/mot-de-passe/", views.changer_mot_de_passe, name="mot_de_passe"),
    path("", views.liste_utilisateurs, name="liste"),
    path("nouveau/", views.creer_utilisateur, name="creer"),
    path("<int:pk>/modifier/", views.modifier_utilisateur, name="modifier"),
    path("<int:pk>/basculer/", views.basculer_utilisateur, name="basculer"),
    path("journal/", views.journal_audit, name="journal"),
]
