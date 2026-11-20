from datetime import date, timedelta

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from utilisateurs.decorators import journaliser, permission_requise

from .forms import InventaireForm, LotStockForm
from .models import Inventaire, LigneInventaire, LotStock, MouvementStock
from .services import ServiceStock


@permission_requise("stock.view_lotstock")
def liste_lots(request):
    lots = LotStock.objects.select_related("medicament", "medicament__categorie")
    recherche = request.GET.get("q", "").strip()
    etat = request.GET.get("etat", "")
    if recherche:
        lots = lots.filter(
            Q(numero_lot__icontains=recherche)
            | Q(medicament__nom_commercial__icontains=recherche)
            | Q(medicament__code_barres__icontains=recherche)
        )
    if etat == "disponible":
        lots = lots.filter(
            est_bloque=False, date_peremption__gte=date.today(), quantite_disponible__gt=0
        )
    elif etat == "perime":
        lots = lots.filter(date_peremption__lt=date.today(), quantite_disponible__gt=0)
    elif etat == "bloque":
        lots = lots.filter(est_bloque=True)
    elif etat == "proche":
        lots = lots.filter(
            date_peremption__gte=date.today(),
            date_peremption__lte=date.today() + timedelta(days=30),
            quantite_disponible__gt=0,
        )
    elif etat == "epuise":
        lots = lots.filter(quantite_disponible=0)

    lots = lots.order_by("date_peremption", "medicament__nom_commercial")
    paginator = Paginator(lots, 20)
    page = paginator.get_page(request.GET.get("page"))
    return render(
        request,
        "stock/lots.html",
        {"page": page, "recherche": recherche, "etat": etat},
    )


@permission_requise("stock.view_lotstock")
def detail_lot(request, pk):
    lot = get_object_or_404(LotStock.objects.select_related("medicament"), pk=pk)
    mouvements = lot.mouvements.select_related("utilisateur")[:100]
    return render(
        request, "stock/lot_detail.html", {"lot": lot, "mouvements": mouvements}
    )


@permission_requise("stock.add_lotstock")
@transaction.atomic
def creer_lot(request):
    formulaire = LotStockForm(request.POST or None)
    if request.method == "POST" and formulaire.is_valid():
        lot = formulaire.save()
        if lot.quantite_disponible > 0:
            MouvementStock.enregistrer(
                lot,
                MouvementStock.CORRECTION,
                lot.quantite_disponible,
                utilisateur=request.user,
                reference_type="LotStock",
                reference_id=lot.pk,
                motif="Creation manuelle du lot",
            )
        journaliser(request, "CREATION", lot, {"numero_lot": lot.numero_lot})
        messages.success(request, "Lot cree.")
        return redirect("stock:lots")
    return render(
        request,
        "stock/lot_formulaire.html",
        {"formulaire": formulaire, "titre": "Nouveau lot"},
    )


@permission_requise("stock.change_lotstock")
@transaction.atomic
def modifier_lot(request, pk):
    lot = get_object_or_404(LotStock, pk=pk)
    ancienne_quantite = lot.quantite_disponible
    formulaire = LotStockForm(request.POST or None, instance=lot)
    if request.method == "POST" and formulaire.is_valid():
        lot = formulaire.save()
        delta = lot.quantite_disponible - ancienne_quantite
        if delta:
            MouvementStock.enregistrer(
                lot,
                MouvementStock.CORRECTION,
                delta,
                utilisateur=request.user,
                reference_type="LotStock",
                reference_id=lot.pk,
                motif="Modification manuelle du lot",
            )
        journaliser(request, "MODIFICATION", lot, {"numero_lot": lot.numero_lot})
        messages.success(request, "Lot mis a jour.")
        return redirect("stock:lots")
    return render(
        request,
        "stock/lot_formulaire.html",
        {"formulaire": formulaire, "titre": f"Modifier le lot {lot.numero_lot}"},
    )


@permission_requise("stock.change_lotstock")
def basculer_blocage(request, pk):
    lot = get_object_or_404(LotStock, pk=pk)
    if request.method == "POST":
        if lot.est_bloque:
            lot.debloquer()
            messages.success(request, "Lot debloque.")
        else:
            motif = request.POST.get("motif", "Blocage manuel")
            lot.bloquer(motif)
            messages.warning(request, "Lot bloque : il ne sera plus delivrable.")
        journaliser(
            request,
            "MODIFICATION",
            lot,
            {"est_bloque": lot.est_bloque, "motif": lot.motif_blocage},
        )
    return redirect("stock:lots")


@permission_requise("stock.view_mouvementstock")
def liste_mouvements(request):
    mouvements = MouvementStock.objects.select_related(
        "lot__medicament", "utilisateur"
    )
    type_mouvement = request.GET.get("type", "")
    recherche = request.GET.get("q", "").strip()
    if type_mouvement:
        mouvements = mouvements.filter(type=type_mouvement)
    if recherche:
        mouvements = mouvements.filter(
            Q(lot__numero_lot__icontains=recherche)
            | Q(lot__medicament__nom_commercial__icontains=recherche)
            | Q(motif__icontains=recherche)
        )
    paginator = Paginator(mouvements, 50)
    page = paginator.get_page(request.GET.get("page"))
    return render(
        request,
        "stock/mouvements.html",
        {
            "page": page,
            "types": MouvementStock.TYPES,
            "type_mouvement": type_mouvement,
            "recherche": recherche,
        },
    )


@permission_requise("stock.view_lotstock")
def alertes(request):
    return render(
        request,
        "stock/alertes.html",
        {
            "stocks_faibles": ServiceStock.alertes_stock_faible(),
            "proches_peremption": ServiceStock.lots_proches_peremption(30),
            "perimes": ServiceStock.lots_perimes(),
        },
    )


@permission_requise("stock.view_inventaire")
def liste_inventaires(request):
    inventaires = Inventaire.objects.select_related("realise_par")
    paginator = Paginator(inventaires, 20)
    page = paginator.get_page(request.GET.get("page"))
    return render(request, "stock/inventaires.html", {"page": page})


@permission_requise("stock.add_inventaire")
@transaction.atomic
def creer_inventaire(request):
    formulaire = InventaireForm(request.POST or None)
    if request.method == "POST" and formulaire.is_valid():
        inventaire = formulaire.save(commit=False)
        inventaire.realise_par = request.user
        inventaire.save()
        lots = LotStock.objects.filter(quantite_disponible__gt=0).order_by(
            "medicament__nom_commercial", "date_peremption"
        )
        if not lots.exists():
            inventaire.delete()
            messages.error(request, "Aucun lot avec du stock a inventorier.")
            return redirect("stock:inventaires")
        LigneInventaire.objects.bulk_create(
            [
                LigneInventaire(
                    inventaire=inventaire,
                    lot=lot,
                    quantite_theorique=lot.quantite_disponible,
                    quantite_comptee=lot.quantite_disponible,
                )
                for lot in lots
            ]
        )
        journaliser(request, "INVENTAIRE", inventaire, {"date": str(inventaire.date_inventaire)})
        messages.success(request, "Inventaire cree. Saisissez les quantites comptees.")
        return redirect("stock:inventaire_detail", pk=inventaire.pk)
    return render(
        request,
        "stock/inventaire_formulaire.html",
        {"formulaire": formulaire, "titre": "Nouvel inventaire"},
    )


@permission_requise("stock.view_inventaire")
def detail_inventaire(request, pk):
    inventaire = get_object_or_404(
        Inventaire.objects.select_related("realise_par"), pk=pk
    )
    lignes = inventaire.lignes.select_related("lot__medicament").order_by(
        "lot__medicament__nom_commercial", "lot__date_peremption"
    )
    return render(
        request,
        "stock/inventaire_detail.html",
        {"inventaire": inventaire, "lignes": lignes},
    )


@permission_requise("stock.change_inventaire")
def saisir_inventaire(request, pk):
    inventaire = get_object_or_404(Inventaire, pk=pk)
    if request.method != "POST":
        return redirect("stock:inventaire_detail", pk=pk)
    if inventaire.statut != Inventaire.EN_COURS:
        messages.error(request, "Cet inventaire n'est plus modifiable.")
        return redirect("stock:inventaire_detail", pk=pk)

    action = request.POST.get("action", "enregistrer")
    for ligne in inventaire.lignes.select_related("lot"):
        valeur = request.POST.get(f"compte_{ligne.pk}")
        if valeur is None or valeur == "":
            continue
        try:
            quantite = int(valeur)
        except ValueError:
            messages.error(request, "Les quantites doivent etre des nombres entiers.")
            return redirect("stock:inventaire_detail", pk=pk)
        if quantite < 0:
            messages.error(request, "Les quantites comptees ne peuvent pas etre negatives.")
            return redirect("stock:inventaire_detail", pk=pk)
        ligne.quantite_comptee = quantite
        ligne.save(update_fields=["quantite_comptee"])

    if action == "valider":
        try:
            inventaire.valider(request.user)
            journaliser(request, "VALIDATION", inventaire, {"type": "inventaire"})
            messages.success(request, "Inventaire valide : les ecarts ont ete corriges.")
        except ValidationError as erreur:
            messages.error(request, erreur.messages[0])
    else:
        messages.success(request, "Quantites comptees enregistrees.")
    return redirect("stock:inventaire_detail", pk=pk)


@permission_requise("stock.change_inventaire")
def annuler_inventaire(request, pk):
    inventaire = get_object_or_404(Inventaire, pk=pk)
    if request.method == "POST":
        try:
            inventaire.annuler()
            journaliser(request, "ANNULATION", inventaire, {"type": "inventaire"})
            messages.success(request, "Inventaire annule.")
        except ValidationError as erreur:
            messages.error(request, erreur.messages[0])
    return redirect("stock:inventaire_detail", pk=pk)
