from datetime import date

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Count, Q, Sum
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404, redirect, render

from utilisateurs.decorators import journaliser, permission_requise

from .forms import CategorieForm, MedicamentForm
from .models import Categorie, Medicament


@permission_requise("medicaments.view_medicament")
def liste_medicaments(request):
    medicaments = Medicament.objects.select_related("categorie").annotate(
        stock_disponible=Coalesce(
            Sum(
                "lots__quantite_disponible",
                filter=Q(
                    lots__est_bloque=False,
                    lots__date_peremption__gte=date.today(),
                ),
            ),
            0,
        )
    )
    recherche = request.GET.get("q", "").strip()
    categorie_id = request.GET.get("categorie", "")
    statut = request.GET.get("statut", "")
    tri = request.GET.get("tri", "nom")

    if recherche:
        medicaments = medicaments.filter(
            Q(nom_commercial__icontains=recherche)
            | Q(denomination_generique__icontains=recherche)
            | Q(code_barres__icontains=recherche)
        )
    if categorie_id:
        medicaments = medicaments.filter(categorie_id=categorie_id)
    if statut:
        medicaments = medicaments.filter(statut=statut)

    ordres = {
        "nom": "nom_commercial",
        "prix": "prix_vente",
        "recent": "-date_creation",
        "stock": "stock_disponible",
    }
    medicaments = medicaments.order_by(ordres.get(tri, "nom_commercial"))

    paginator = Paginator(medicaments, 15)
    page = paginator.get_page(request.GET.get("page"))
    return render(
        request,
        "medicaments/liste.html",
        {
            "page": page,
            "recherche": recherche,
            "categories": Categorie.objects.all(),
            "categorie_id": categorie_id,
            "statut": statut,
            "tri": tri,
        },
    )


@permission_requise("medicaments.view_medicament")
def detail_medicament(request, pk):
    medicament = get_object_or_404(Medicament.objects.select_related("categorie"), pk=pk)
    lots = medicament.lots.order_by("date_peremption")
    return render(
        request,
        "medicaments/detail.html",
        {"medicament": medicament, "lots": lots, "stock": medicament.stock_total()},
    )


@permission_requise("medicaments.add_medicament")
def creer_medicament(request):
    formulaire = MedicamentForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and formulaire.is_valid():
        medicament = formulaire.save()
        journaliser(request, "CREATION", medicament, {"nom": medicament.nom_commercial})
        messages.success(request, "Medicament cree.")
        return redirect("medicaments:detail", pk=medicament.pk)
    return render(
        request,
        "medicaments/formulaire.html",
        {"formulaire": formulaire, "titre": "Nouveau medicament"},
    )


@permission_requise("medicaments.change_medicament")
def modifier_medicament(request, pk):
    medicament = get_object_or_404(Medicament, pk=pk)
    formulaire = MedicamentForm(
        request.POST or None, request.FILES or None, instance=medicament
    )
    if request.method == "POST" and formulaire.is_valid():
        formulaire.save()
        journaliser(request, "MODIFICATION", medicament, {"nom": medicament.nom_commercial})
        messages.success(request, "Medicament mis a jour.")
        return redirect("medicaments:detail", pk=medicament.pk)
    return render(
        request,
        "medicaments/formulaire.html",
        {"formulaire": formulaire, "titre": f"Modifier {medicament}"},
    )


@permission_requise("medicaments.change_medicament")
def basculer_medicament(request, pk):
    medicament = get_object_or_404(Medicament, pk=pk)
    if request.method == "POST":
        if medicament.statut == Medicament.ACTIF:
            medicament.archiver()
            messages.success(request, "Medicament archive.")
        else:
            medicament.desarchiver()
            messages.success(request, "Medicament reactive.")
        journaliser(request, "MODIFICATION", medicament, {"statut": medicament.statut})
    return redirect("medicaments:liste")


@permission_requise("medicaments.delete_medicament")
def supprimer_medicament(request, pk):
    medicament = get_object_or_404(Medicament, pk=pk)
    if request.method == "POST":
        if medicament.peut_etre_supprime():
            nom = str(medicament)
            medicament.delete()
            journaliser(request, "SUPPRESSION", details={"medicament": nom})
            messages.success(request, "Medicament supprime.")
        else:
            medicament.archiver()
            messages.warning(
                request,
                "Ce medicament possede un historique : il a ete archive au lieu d'etre supprime.",
            )
    return redirect("medicaments:liste")


@permission_requise("medicaments.view_categorie")
def liste_categories(request):
    categories = Categorie.objects.annotate(nb_medicaments=Count("medicaments"))
    return render(request, "medicaments/categories.html", {"categories": categories})


@permission_requise("medicaments.add_categorie")
def creer_categorie(request):
    formulaire = CategorieForm(request.POST or None)
    if request.method == "POST" and formulaire.is_valid():
        categorie = formulaire.save()
        journaliser(request, "CREATION", categorie, {"nom": categorie.nom})
        messages.success(request, "Categorie creee.")
        return redirect("medicaments:categories")
    return render(
        request,
        "medicaments/formulaire.html",
        {"formulaire": formulaire, "titre": "Nouvelle categorie"},
    )


@permission_requise("medicaments.change_categorie")
def modifier_categorie(request, pk):
    categorie = get_object_or_404(Categorie, pk=pk)
    formulaire = CategorieForm(request.POST or None, instance=categorie)
    if request.method == "POST" and formulaire.is_valid():
        formulaire.save()
        journaliser(request, "MODIFICATION", categorie, {"nom": categorie.nom})
        messages.success(request, "Categorie mise a jour.")
        return redirect("medicaments:categories")
    return render(
        request,
        "medicaments/formulaire.html",
        {"formulaire": formulaire, "titre": f"Modifier {categorie.nom}"},
    )


@permission_requise("medicaments.delete_categorie")
def supprimer_categorie(request, pk):
    categorie = get_object_or_404(Categorie, pk=pk)
    if request.method == "POST":
        try:
            categorie.supprimer()
            journaliser(request, "SUPPRESSION", details={"categorie": categorie.nom})
            messages.success(request, "Categorie supprimee.")
        except ValidationError as erreur:
            messages.error(request, erreur.messages[0])
    return redirect("medicaments:categories")
