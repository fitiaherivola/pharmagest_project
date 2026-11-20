from django.urls import path

from . import views

app_name = "medicaments"

urlpatterns = [
    path("", views.liste_medicaments, name="liste"),
    path("nouveau/", views.creer_medicament, name="creer"),
    path("<int:pk>/", views.detail_medicament, name="detail"),
    path("<int:pk>/modifier/", views.modifier_medicament, name="modifier"),
    path("<int:pk>/basculer/", views.basculer_medicament, name="basculer"),
    path("<int:pk>/supprimer/", views.supprimer_medicament, name="supprimer"),
    path("categories/", views.liste_categories, name="categories"),
    path("categories/nouvelle/", views.creer_categorie, name="creer_categorie"),
    path("categories/<int:pk>/modifier/", views.modifier_categorie, name="modifier_categorie"),
    path("categories/<int:pk>/supprimer/", views.supprimer_categorie, name="supprimer_categorie"),
]
