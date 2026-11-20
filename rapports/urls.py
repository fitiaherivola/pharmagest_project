from django.urls import path

from . import views

app_name = "rapports"

urlpatterns = [
    path("stock/", views.rapport_stock, name="stock"),
    path("stock.pdf", views.rapport_stock_pdf, name="stock_pdf"),
    path("ventes/", views.rapport_ventes, name="ventes"),
    path("ventes.pdf", views.rapport_ventes_pdf, name="ventes_pdf"),
    path("achats/", views.rapport_achats, name="achats"),
    path("achats.pdf", views.rapport_achats_pdf, name="achats_pdf"),
    path("peremptions/", views.rapport_peremptions, name="peremptions"),
    path("peremptions.pdf", views.peremptions_pdf, name="peremptions_pdf"),
]
