from datetime import date
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import HttpResponse
from django.shortcuts import render
from django.utils.dateparse import parse_date

from achats.models import CommandeAchat
from stock.models import LotStock
from utilisateurs.decorators import role_requis
from ventes.models import Vente

from .pdf import GenerateurPDF
from .services import ServiceStatistiques, ServiceStock


@login_required
def tableau_bord(request):
    resume = ServiceStatistiques.resume()
    produits = ServiceStatistiques.produits_plus_vendus(5)
    ventes_7_jours = ServiceStatistiques.ventes_par_jour(7)
    paiements = ServiceStatistiques.paiements_par_mode()
    categories = ServiceStatistiques.medicaments_par_categorie(6)
    sante_stock = ServiceStatistiques.sante_stock()
    max_vente_jour = max((jour["total"] for jour in ventes_7_jours), default=0)
    moyenne_ventes = sum(
        (jour["total"] for jour in ventes_7_jours), Decimal("0")
    ) / len(ventes_7_jours)

    graphiques = {
        "ventes": {
            "labels": [jour["jour"].strftime("%d/%m") for jour in ventes_7_jours],
            "valeurs": [float(jour["total"]) for jour in ventes_7_jours],
        },
        "produits": {
            "labels": [p["medicament__nom_commercial"] for p in produits],
            "valeurs": [int(p["quantite"]) for p in produits],
        },
        "paiements": {
            "labels": [p["mode"] for p in paiements],
            "valeurs": [float(p["total"]) for p in paiements],
        },
        "categories": {
            "labels": [c["nom"] for c in categories],
            "valeurs": [int(c["total"]) for c in categories],
        },
        "stock": {
            "labels": ["Lots sains", "Proches peremption", "Bloques", "Perimes"],
            "valeurs": [
                sante_stock["sains"],
                sante_stock["proches"],
                sante_stock["bloques"],
                sante_stock["perimes"],
            ],
        },
        "finances": {
            "labels": ["CA global", "Encaissements", "Marge brute", "Valeur stock"],
            "valeurs": [
                float(resume["chiffre_affaires"]),
                float(resume["encaissements"]),
                float(resume["marge_commerciale"]),
                float(resume["valeur_stock"]),
            ],
        },
    }

    return render(
        request,
        "rapports/tableau_bord.html",
        {
            "graphiques": graphiques,
            "resume": resume,
            "stocks_faibles": ServiceStock.alertes_stock_faible()[:8],
            "proches_peremption": ServiceStock.lots_proches_peremption(30)[:8],
            "perimes": ServiceStock.lots_perimes()[:5],
            "produits_plus_vendus": produits,
            "ventes_recentes": Vente.objects.select_related("client", "caissier")[:8],
            "ventes_7_jours": ventes_7_jours,
            "max_vente_jour": max_vente_jour,
            "moyenne_ventes": moyenne_ventes,
            "aujourdhui": date.today(),
        },
    )


@role_requis("Administrateur", "Pharmacien", "Gestionnaire")
def rapport_stock(request):
    lots = LotStock.objects.select_related("medicament").order_by(
        "medicament__nom_commercial", "date_peremption"
    )
    return render(
        request,
        "rapports/stock.html",
        {
            "lots": lots,
            "valeur_totale": ServiceStatistiques.valeur_stock(),
            "stocks_faibles": ServiceStock.alertes_stock_faible(),
        },
    )


@role_requis("Administrateur", "Pharmacien", "Gestionnaire")
def rapport_ventes(request):
    debut = parse_date(request.GET.get("debut", ""))
    fin = parse_date(request.GET.get("fin", ""))
    ventes = Vente.objects.select_related("client", "caissier")
    if debut:
        ventes = ventes.filter(date_vente__date__gte=debut)
    if fin:
        ventes = ventes.filter(date_vente__date__lte=fin)
    paginator = Paginator(ventes, 30)
    page = paginator.get_page(request.GET.get("page"))
    return render(
        request,
        "rapports/ventes.html",
        {
            "page": page,
            "debut": request.GET.get("debut", ""),
            "fin": request.GET.get("fin", ""),
            "total": ServiceStatistiques.ventes_periode(debut, fin),
            "ca": ServiceStatistiques.chiffre_affaires(debut, fin),
            "encaissements": ServiceStatistiques.encaissements(debut, fin),
            "marge": ServiceStatistiques.marge_commerciale(debut, fin),
            "produits": ServiceStatistiques.produits_plus_vendus(10, debut, fin),
        },
    )


@role_requis("Administrateur", "Pharmacien", "Gestionnaire")
def rapport_achats(request):
    debut = parse_date(request.GET.get("debut", ""))
    fin = parse_date(request.GET.get("fin", ""))
    commandes = CommandeAchat.objects.select_related("fournisseur")
    if debut:
        commandes = commandes.filter(date_creation__date__gte=debut)
    if fin:
        commandes = commandes.filter(date_creation__date__lte=fin)
    paginator = Paginator(commandes, 30)
    page = paginator.get_page(request.GET.get("page"))
    return render(
        request,
        "rapports/achats.html",
        {
            "page": page,
            "debut": request.GET.get("debut", ""),
            "fin": request.GET.get("fin", ""),
            "total": ServiceStatistiques.achats_periode(debut, fin),
        },
    )


@role_requis("Administrateur", "Pharmacien", "Gestionnaire")
def rapport_peremptions(request):
    return render(
        request,
        "rapports/peremptions.html",
        {
            "proches": ServiceStock.lots_proches_peremption(30),
            "perimes": ServiceStock.lots_perimes(),
        },
    )


def _pdf(contenu, nom):
    reponse = HttpResponse(contenu, content_type="application/pdf")
    reponse["Content-Disposition"] = f'inline; filename="{nom}"'
    return reponse


@role_requis("Administrateur", "Pharmacien", "Gestionnaire")
def rapport_stock_pdf(request):
    return _pdf(GenerateurPDF.rapport_stock(), "rapport-stock.pdf")


@role_requis("Administrateur", "Pharmacien", "Gestionnaire")
def rapport_ventes_pdf(request):
    debut = parse_date(request.GET.get("debut", ""))
    fin = parse_date(request.GET.get("fin", ""))
    return _pdf(
        GenerateurPDF.rapport_ventes(debut=debut, fin=fin), "rapport-ventes.pdf"
    )


@role_requis("Administrateur", "Pharmacien", "Gestionnaire")
def rapport_achats_pdf(request):
    debut = parse_date(request.GET.get("debut", ""))
    fin = parse_date(request.GET.get("fin", ""))
    return _pdf(
        GenerateurPDF.rapport_achats(debut=debut, fin=fin), "rapport-achats.pdf"
    )


@role_requis("Administrateur", "Pharmacien", "Gestionnaire")
def peremptions_pdf(request):
    return _pdf(GenerateurPDF.liste_peremptions(), "peremptions.pdf")
