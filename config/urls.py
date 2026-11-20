from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from rapports import views as rapports_views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", rapports_views.tableau_bord, name="tableau_bord"),
    path("utilisateurs/", include("utilisateurs.urls")),
    path("medicaments/", include("medicaments.urls")),
    path("fournisseurs/", include("fournisseurs.urls")),
    path("clients/", include("clients.urls")),
    path("achats/", include("achats.urls")),
    path("stock/", include("stock.urls")),
    path("ventes/", include("ventes.urls")),
    path("rapports/", include("rapports.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
