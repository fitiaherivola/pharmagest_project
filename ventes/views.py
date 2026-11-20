import uuid
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.dateparse import parse_date

from clients.models import Client
from stock.models import LotStock
from utilisateurs.decorators import journaliser, permission_requise

from .forms import RetourVenteForm
from .models import LigneVente, Paiement, RetourVente, Vente
from .services import ServiceVente

CLE_PANIER = "panier"
CLE_IDEMPOTENCE = "vente_cle_idempotence"


def _panier(request):
    panier = request.session.get(CLE_PANIER, {})
    return {str(cle): int(valeur) for cle, valeur in panier.items() if int(valeur) > 0}


def _enregistrer_panier(request, panier):
    request.session[CLE_PANIER] = panier
    request.session.modified = True


def _lignes_panier(request):
    panier = _panier(request)
    if not panier:
        return [], Decimal("0")
    lots = {
        str(lot.pk): lot
        for lot in LotStock.objects.filter(pk__in=panier.keys()).select_related(
            "medicament"
        )
    }
    lignes = []
    total = Decimal("0")
    for lot_id, quantite in panier.items():
        lot = lots.get(lot_id)
        if lot is None:
            continue
        prix = lot.medicament.prix_vente
        sous_total = prix * quantite
        total += sous_total
        lignes.append(
            {
                "lot": lot,
                "quantite": quantite,
                "prix": prix,
                "sous_total": sous_total,
                "disponible": lot.quantite_disponible,
                "delivrable": lot.est_delivrable() and quantite <= lot.quantite_disponible,
            }
        )
    return lignes, total


@permission_requise("ventes.add_vente")
def caisse(request):
    if request.method == "POST":
        action = request.POST.get("action", "")

        if action in {"ajouter", "ajouter_fefo"}:
            panier = _panier(request)
            try:
                quantite = int(request.POST.get("quantite", "1"))
            except ValueError:
                quantite = 0
            if action == "ajouter_fefo":
                medicament_id = request.POST.get("medicament_id")
                premier = (
                    LotStock.lots_fefo()
                    .filter(medicament_id=medicament_id)
                    .select_related("medicament")
                    .first()
                )
                lot = premier
            else:
                lot = LotStock.objects.select_related("medicament").filter(
                    pk=request.POST.get("lot_id")
                ).first()
            if lot is None:
                messages.error(request, "Aucun lot delivrable disponible.")
            elif quantite <= 0:
                messages.error(request, "La quantite doit etre strictement positive.")
            elif not lot.est_delivrable():
                messages.error(request, "Ce lot est perime, bloque ou epuise.")
            elif panier.get(str(lot.pk), 0) + quantite > lot.quantite_disponible:
                messages.error(
                    request,
                    f"Stock insuffisant : {lot.quantite_disponible} unite(s) disponible(s) dans ce lot.",
                )
            else:
                panier[str(lot.pk)] = panier.get(str(lot.pk), 0) + quantite
                _enregistrer_panier(request, panier)
                if not request.session.get(CLE_IDEMPOTENCE):
                    request.session[CLE_IDEMPOTENCE] = str(uuid.uuid4())
                messages.success(request, f"{lot.medicament} ajoute au panier.")
            return redirect("ventes:caisse")

        if action == "retirer":
            panier = _panier(request)
            panier.pop(str(request.POST.get("lot_id")), None)
            _enregistrer_panier(request, panier)
            return redirect("ventes:caisse")

        if action == "vider":
            _enregistrer_panier(request, {})
            request.session.pop(CLE_IDEMPOTENCE, None)
            return redirect("ventes:caisse")

        if action == "valider":
            lignes, total = _lignes_panier(request)
            if not lignes:
                messages.error(request, "Le panier est vide.")
                return redirect("ventes:caisse")
            if any(not ligne["delivrable"] for ligne in lignes):
                messages.error(
                    request,
                    "Certaines lignes ne sont plus disponibles (stock, peremption ou blocage).",
                )
                return redirect("ventes:caisse")

            mode = request.POST.get("mode", Paiement.ESPECES)
            if mode not in dict(Paiement.MODES):
                messages.error(request, "Mode de paiement invalide.")
                return redirect("ventes:caisse")
            reference = request.POST.get("reference", "").strip()
            montant_recu = request.POST.get("montant_recu", "").strip()
            if montant_recu:
                try:
                    montant_recu = Decimal(montant_recu)
                except InvalidOperation:
                    messages.error(request, "Montant recu invalide.")
                    return redirect("ventes:caisse")
                if mode == Paiement.ESPECES and montant_recu < total:
                    messages.error(request, "Le montant recu est inferieur au total a payer.")
                    return redirect("ventes:caisse")

            client = None
            client_id = request.POST.get("client", "").strip()
            if client_id:
                try:
                    client_id = int(client_id)
                except ValueError:
                    messages.error(request, "Client invalide.")
                    return redirect("ventes:caisse")
                client = Client.objects.filter(pk=client_id, est_actif=True).first()

            cle = request.session.get(CLE_IDEMPOTENCE)
            if cle:
                existante = Vente.objects.filter(cle_idempotence=cle).first()
                if existante:
                    _enregistrer_panier(request, {})
                    request.session.pop(CLE_IDEMPOTENCE, None)
                    messages.info(request, "Cette vente a deja ete enregistree.")
                    return redirect("ventes:detail", pk=existante.pk)
            else:
                cle = str(uuid.uuid4())
                request.session[CLE_IDEMPOTENCE] = cle

            try:
                with transaction.atomic():
                    vente = Vente.objects.create(
                        client=client,
                        caissier=request.user,
                        total=total,
                        cle_idempotence=cle,
                    )
                    for ligne in lignes:
                        lot = ligne["lot"]
                        LigneVente.objects.create(
                            vente=vente,
                            medicament=lot.medicament,
                            lot=lot,
                            quantite=ligne["quantite"],
                            prix_unitaire_applique=lot.medicament.prix_vente,
                        )
                    vente.valider(request.user)
                    ServiceVente.enregistrer_paiement(
                        vente, mode, vente.total, reference
                    )
                    journaliser(
                        request,
                        "VALIDATION",
                        vente,
                        {"total": str(vente.total), "mode": mode},
                    )
                _enregistrer_panier(request, {})
                request.session.pop(CLE_IDEMPOTENCE, None)
                messages.success(request, f"Vente {vente.numero} validee.")
                return redirect("ventes:detail", pk=vente.pk)
            except ValidationError as erreur:
                messages.error(request, erreur.messages[0])
            except IntegrityError:
                existante = Vente.objects.filter(cle_idempotence=cle).first()
                if existante:
                    _enregistrer_panier(request, {})
                    request.session.pop(CLE_IDEMPOTENCE, None)
                    messages.info(request, "Cette vente a deja ete enregistree.")
                    return redirect("ventes:detail", pk=existante.pk)
                messages.error(request, "Erreur d'enregistrement de la vente.")
            return redirect("ventes:caisse")

    recherche = request.GET.get("q", "").strip()
    lots = LotStock.lots_fefo().select_related("medicament", "medicament__categorie")
    if recherche:
        lots = lots.filter(
            Q(medicament__nom_commercial__icontains=recherche)
            | Q(medicament__code_barres__icontains=recherche)
            | Q(medicament__denomination_generique__icontains=recherche)
        )
    lots = lots[:200]
    lignes, total = _lignes_panier(request)
    return render(
        request,
        "ventes/caisse.html",
        {
            "lots": lots,
            "recherche": recherche,
            "lignes": lignes,
            "total": total,
            "clients": Client.objects.filter(est_actif=True).order_by("nom"),
            "modes": Paiement.MODES,
        },
    )


@permission_requise("ventes.view_vente")
def liste_ventes(request):
    ventes = Vente.objects.select_related("client", "caissier")
    recherche = request.GET.get("q", "").strip()
    statut = request.GET.get("statut", "")
    debut = parse_date(request.GET.get("debut", ""))
    fin = parse_date(request.GET.get("fin", ""))
    if recherche:
        ventes = ventes.filter(
            Q(numero__icontains=recherche)
            | Q(client__nom__icontains=recherche)
            | Q(caissier__username__icontains=recherche)
        )
    if statut:
        ventes = ventes.filter(statut=statut)
    if debut:
        ventes = ventes.filter(date_vente__date__gte=debut)
    if fin:
        ventes = ventes.filter(date_vente__date__lte=fin)
    paginator = Paginator(ventes, 20)
    page = paginator.get_page(request.GET.get("page"))
    return render(
        request,
        "ventes/liste.html",
        {
            "page": page,
            "recherche": recherche,
            "statut": statut,
            "debut": request.GET.get("debut", ""),
            "fin": request.GET.get("fin", ""),
            "statuts": Vente.STATUTS,
        },
    )


@permission_requise("ventes.view_vente")
def detail_vente(request, pk):
    vente = get_object_or_404(
        Vente.objects.select_related("client", "caissier"), pk=pk
    )
    lignes = vente.lignes.select_related("medicament", "lot")
    paiements = vente.paiements.all()
    retours = vente.retours.select_related("ligne_vente__medicament", "utilisateur")
    return render(
        request,
        "ventes/detail.html",
        {
            "vente": vente,
            "lignes": lignes,
            "paiements": paiements,
            "retours": retours,
        },
    )


@permission_requise("ventes.change_vente")
def annuler_vente(request, pk):
    vente = get_object_or_404(Vente, pk=pk)
    if request.method == "POST":
        motif = request.POST.get("motif", "").strip()
        try:
            vente.annuler(motif, request.user)
            journaliser(request, "ANNULATION", vente, {"motif": motif})
            messages.success(request, "Vente annulee : stock et paiements compensés.")
        except ValidationError as erreur:
            messages.error(request, erreur.messages[0])
    return redirect("ventes:detail", pk=pk)


@permission_requise("ventes.add_retourvente")
def creer_retour(request, pk):
    vente = get_object_or_404(Vente, pk=pk)
    if vente.statut != Vente.VALIDEE:
        messages.error(request, "Seule une vente validee peut faire l'objet d'un retour.")
        return redirect("ventes:detail", pk=pk)
    formulaire = RetourVenteForm(request.POST or None, vente=vente)
    if request.method == "POST" and formulaire.is_valid():
        try:
            with transaction.atomic():
                retour = RetourVente.objects.create(
                    vente=vente,
                    ligne_vente=formulaire.cleaned_data["ligne_vente"],
                    quantite_retournee=formulaire.cleaned_data["quantite_retournee"],
                    motif=formulaire.cleaned_data["motif"],
                    remis_en_stock=formulaire.cleaned_data["remis_en_stock"],
                    utilisateur=request.user,
                )
                retour.valider(request.user)
                journaliser(
                    request,
                    "RETOUR",
                    retour,
                    {"vente": vente.numero, "quantite": retour.quantite_retournee},
                )
            messages.success(request, "Retour enregistre.")
            return redirect("ventes:detail", pk=pk)
        except ValidationError as erreur:
            messages.error(request, erreur.messages[0])
    return render(
        request,
        "ventes/retour_formulaire.html",
        {"vente": vente, "formulaire": formulaire},
    )


@permission_requise("ventes.change_paiement")
def confirmer_paiement(request, pk):
    paiement = get_object_or_404(Paiement, pk=pk)
    if request.method == "POST":
        if paiement.statut == Paiement.EN_ATTENTE:
            paiement.confirmer()
            journaliser(
                request,
                "PAIEMENT",
                paiement,
                {"vente": paiement.vente.numero, "montant": str(paiement.montant)},
            )
            messages.success(request, "Paiement confirme.")
        else:
            messages.info(request, "Ce paiement n'est pas en attente.")
    return redirect("ventes:detail", pk=paiement.vente_id)


def _pdf(contenu, nom):
    reponse = HttpResponse(contenu, content_type="application/pdf")
    reponse["Content-Disposition"] = f'inline; filename="{nom}"'
    return reponse


@permission_requise("ventes.view_vente")
def recu_pdf(request, pk):
    from rapports.pdf import GenerateurPDF

    vente = get_object_or_404(Vente, pk=pk)
    return _pdf(GenerateurPDF.recu_vente(vente), f"recu-{vente.numero}.pdf")


@permission_requise("ventes.view_vente")
def facture_pdf(request, pk):
    from rapports.pdf import GenerateurPDF

    vente = get_object_or_404(Vente, pk=pk)
    return _pdf(GenerateurPDF.facture(vente), f"facture-{vente.numero}.pdf")
