from decimal import Decimal

from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Count, Q, Sum
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404, redirect, render

from utilisateurs.decorators import journaliser, permission_requise

from .forms import FournisseurForm
from .models import Fournisseur


@permission_requise("fournisseurs.view_fournisseur")
def liste_fournisseurs(request):
    fournisseurs = Fournisseur.objects.annotate(
        nb_commandes=Count("commandes"),
        total_commandes=Coalesce(Sum("commandes__montant_total"), Decimal("0")),
    ).order_by("nom")
    recherche = request.GET.get("q", "").strip()
    actif = request.GET.get("actif", "")
    if recherche:
        fournisseurs = fournisseurs.filter(
            Q(nom__icontains=recherche)
            | Q(contact_principal__icontains=recherche)
            | Q(telephone__icontains=recherche)
            | Q(email__icontains=recherche)
        )
    if actif in {"0", "1"}:
        fournisseurs = fournisseurs.filter(est_actif=actif == "1")
    paginator = Paginator(fournisseurs, 20)
    page = paginator.get_page(request.GET.get("page"))
    return render(
        request,
        "fournisseurs/liste.html",
        {"page": page, "recherche": recherche, "actif": actif},
    )


@permission_requise("fournisseurs.view_fournisseur")
def detail_fournisseur(request, pk):
    fournisseur = get_object_or_404(Fournisseur, pk=pk)
    return render(
        request,
        "fournisseurs/detail.html",
        {
            "fournisseur": fournisseur,
            "commandes": fournisseur.historique_achats()[:50],
            "total": fournisseur.montant_total_commande(),
        },
    )


@permission_requise("fournisseurs.add_fournisseur")
def creer_fournisseur(request):
    formulaire = FournisseurForm(request.POST or None)
    if request.method == "POST" and formulaire.is_valid():
        fournisseur = formulaire.save()
        journaliser(request, "CREATION", fournisseur, {"nom": fournisseur.nom})
        messages.success(request, "Fournisseur cree.")
        return redirect("fournisseurs:liste")
    return render(
        request,
        "fournisseurs/formulaire.html",
        {"formulaire": formulaire, "titre": "Nouveau fournisseur"},
    )


@permission_requise("fournisseurs.change_fournisseur")
def modifier_fournisseur(request, pk):
    fournisseur = get_object_or_404(Fournisseur, pk=pk)
    formulaire = FournisseurForm(request.POST or None, instance=fournisseur)
    if request.method == "POST" and formulaire.is_valid():
        formulaire.save()
        journaliser(request, "MODIFICATION", fournisseur, {"nom": fournisseur.nom})
        messages.success(request, "Fournisseur mis a jour.")
        return redirect("fournisseurs:liste")
    return render(
        request,
        "fournisseurs/formulaire.html",
        {"formulaire": formulaire, "titre": f"Modifier {fournisseur.nom}"},
    )


@permission_requise("fournisseurs.change_fournisseur")
def basculer_fournisseur(request, pk):
    fournisseur = get_object_or_404(Fournisseur, pk=pk)
    if request.method == "POST":
        fournisseur.est_actif = not fournisseur.est_actif
        fournisseur.save(update_fields=["est_actif"])
        journaliser(
            request,
            "MODIFICATION",
            fournisseur,
            {"est_actif": fournisseur.est_actif},
        )
        messages.success(request, "Statut du fournisseur mis a jour.")
    return redirect("fournisseurs:liste")
