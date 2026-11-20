from datetime import date

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.dateparse import parse_date

from fournisseurs.models import Fournisseur
from utilisateurs.decorators import journaliser, permission_requise

from .forms import CommandeAchatForm, LigneAchatForm
from .models import CommandeAchat, LigneAchat, LigneReception, ReceptionAchat


@permission_requise("achats.view_commandeachat")
def liste_commandes(request):
    commandes = CommandeAchat.objects.select_related("fournisseur", "cree_par")
    recherche = request.GET.get("q", "").strip()
    statut = request.GET.get("statut", "")
    fournisseur_id = request.GET.get("fournisseur", "")
    if recherche:
        commandes = commandes.filter(
            Q(numero__icontains=recherche)
            | Q(fournisseur__nom__icontains=recherche)
        )
    if statut:
        commandes = commandes.filter(statut=statut)
    if fournisseur_id:
        commandes = commandes.filter(fournisseur_id=fournisseur_id)
    paginator = Paginator(commandes, 20)
    page = paginator.get_page(request.GET.get("page"))
    return render(
        request,
        "achats/commandes.html",
        {
            "page": page,
            "recherche": recherche,
            "statut": statut,
            "fournisseur_id": fournisseur_id,
            "statuts": CommandeAchat.STATUTS,
            "fournisseurs": Fournisseur.objects.filter(est_actif=True),
        },
    )


@permission_requise("achats.view_commandeachat")
def detail_commande(request, pk):
    commande = get_object_or_404(
        CommandeAchat.objects.select_related("fournisseur", "cree_par"), pk=pk
    )
    lignes = commande.lignes.select_related("medicament")
    receptions = commande.receptions.select_related("recu_par")
    formulaire_ligne = LigneAchatForm()
    return render(
        request,
        "achats/commande_detail.html",
        {
            "commande": commande,
            "lignes": lignes,
            "receptions": receptions,
            "formulaire_ligne": formulaire_ligne,
        },
    )


@permission_requise("achats.add_commandeachat")
def creer_commande(request):
    formulaire = CommandeAchatForm(request.POST or None)
    if request.method == "POST" and formulaire.is_valid():
        commande = formulaire.save(commit=False)
        commande.cree_par = request.user
        commande.save()
        journaliser(request, "CREATION", commande, {"numero": commande.numero})
        messages.success(request, "Commande creee en brouillon. Ajoutez les lignes.")
        return redirect("achats:commande_detail", pk=commande.pk)
    return render(
        request,
        "achats/commande_formulaire.html",
        {"formulaire": formulaire, "titre": "Nouvelle commande d'achat"},
    )


@permission_requise("achats.change_commandeachat")
def modifier_commande(request, pk):
    commande = get_object_or_404(CommandeAchat, pk=pk)
    if commande.statut != CommandeAchat.BROUILLON:
        messages.error(request, "Seule une commande en brouillon peut etre modifiee.")
        return redirect("achats:commande_detail", pk=pk)
    formulaire = CommandeAchatForm(request.POST or None, instance=commande)
    if request.method == "POST" and formulaire.is_valid():
        formulaire.save()
        journaliser(request, "MODIFICATION", commande, {"numero": commande.numero})
        messages.success(request, "Commande mise a jour.")
        return redirect("achats:commande_detail", pk=pk)
    return render(
        request,
        "achats/commande_formulaire.html",
        {"formulaire": formulaire, "titre": f"Modifier {commande.numero}"},
    )


@permission_requise("achats.change_commandeachat")
def ajouter_ligne(request, pk):
    commande = get_object_or_404(CommandeAchat, pk=pk)
    if commande.statut != CommandeAchat.BROUILLON:
        messages.error(request, "Les lignes ne peuvent etre ajoutees qu'a un brouillon.")
        return redirect("achats:commande_detail", pk=pk)
    if request.method == "POST":
        formulaire = LigneAchatForm(request.POST)
        if formulaire.is_valid():
            ligne = formulaire.save(commit=False)
            ligne.commande = commande
            if commande.lignes.filter(medicament=ligne.medicament).exists():
                messages.error(request, "Ce medicament figure deja dans la commande.")
            else:
                ligne.save()
                commande.recalculer_total()
                journaliser(
                    request,
                    "MODIFICATION",
                    commande,
                    {"ajout_ligne": str(ligne.medicament)},
                )
                messages.success(request, "Ligne ajoutee.")
                return redirect("achats:commande_detail", pk=pk)
        for champ, erreurs in formulaire.errors.items():
            for erreur in erreurs:
                messages.error(request, f"{champ} : {erreur}")
    return redirect("achats:commande_detail", pk=pk)


@permission_requise("achats.change_commandeachat")
def supprimer_ligne(request, pk, ligne_pk):
    commande = get_object_or_404(CommandeAchat, pk=pk)
    ligne = get_object_or_404(LigneAchat, pk=ligne_pk, commande=commande)
    if request.method == "POST" and commande.statut == CommandeAchat.BROUILLON:
        ligne.delete()
        commande.recalculer_total()
        journaliser(request, "MODIFICATION", commande, {"suppression_ligne": str(ligne)})
        messages.success(request, "Ligne supprimee.")
    else:
        messages.error(request, "Suppression impossible hors brouillon.")
    return redirect("achats:commande_detail", pk=pk)


@permission_requise("achats.change_commandeachat")
def valider_commande(request, pk):
    commande = get_object_or_404(CommandeAchat, pk=pk)
    if request.method == "POST":
        try:
            commande.valider()
            journaliser(request, "VALIDATION", commande, {"numero": commande.numero})
            messages.success(request, "Commande validee.")
        except ValidationError as erreur:
            messages.error(request, erreur.messages[0])
    return redirect("achats:commande_detail", pk=pk)


@permission_requise("achats.change_commandeachat")
def annuler_commande(request, pk):
    commande = get_object_or_404(CommandeAchat, pk=pk)
    if request.method == "POST":
        try:
            commande.annuler()
            journaliser(request, "ANNULATION", commande, {"numero": commande.numero})
            messages.success(request, "Commande annulee.")
        except ValidationError as erreur:
            messages.error(request, erreur.messages[0])
    return redirect("achats:commande_detail", pk=pk)


@permission_requise("achats.add_receptionachat")
def creer_reception(request, pk):
    commande = get_object_or_404(CommandeAchat, pk=pk)
    lignes = list(commande.lignes.select_related("medicament"))
    if not commande.est_receptionnable():
        messages.error(request, "Cette commande n'est pas receptionnable dans son etat actuel.")
        return redirect("achats:commande_detail", pk=pk)

    if request.method == "POST":
        erreurs = []
        donnees = []
        for ligne in lignes:
            if ligne.reste_a_recevoir() <= 0:
                continue
            valeur = request.POST.get(f"qte_{ligne.pk}", "").strip()
            if not valeur:
                continue
            try:
                quantite = int(valeur)
            except ValueError:
                erreurs.append(f"Quantite invalide pour {ligne.medicament}.")
                continue
            if quantite == 0:
                continue
            if quantite < 0:
                erreurs.append(f"Quantite negative pour {ligne.medicament}.")
                continue
            if quantite > ligne.reste_a_recevoir():
                erreurs.append(
                    f"Quantite superieure au reste a recevoir pour {ligne.medicament}."
                )
                continue
            numero_lot = request.POST.get(f"lot_{ligne.pk}", "").strip()
            date_peremption = parse_date(request.POST.get(f"peremption_{ligne.pk}", ""))
            if not numero_lot:
                erreurs.append(f"Numero de lot obligatoire pour {ligne.medicament}.")
                continue
            if not date_peremption:
                erreurs.append(f"Date de peremption obligatoire pour {ligne.medicament}.")
                continue
            if date_peremption < date.today():
                erreurs.append(f"Le lot de {ligne.medicament} est deja perime.")
                continue
            donnees.append((ligne, quantite, numero_lot, date_peremption))

        if not donnees and not erreurs:
            erreurs.append("Saisissez au moins une quantite receptionnee superieure a zero.")
        if erreurs:
            for erreur in erreurs:
                messages.error(request, erreur)
        else:
            try:
                with transaction.atomic():
                    reception = ReceptionAchat.objects.create(
                        commande=commande, recu_par=request.user
                    )
                    for ligne, quantite, numero_lot, date_peremption in donnees:
                        LigneReception.objects.create(
                            reception=reception,
                            ligne_achat=ligne,
                            numero_lot=numero_lot,
                            date_peremption=date_peremption,
                            quantite_recue=quantite,
                        )
                    reception.valider(request.user)
                    journaliser(
                        request,
                        "RECEPTION",
                        reception,
                        {"numero_bon": reception.numero_bon, "commande": commande.numero},
                    )
                messages.success(request, "Reception validee : le stock a ete augmente.")
                return redirect("achats:reception_detail", pk=reception.pk)
            except ValidationError as erreur:
                messages.error(request, erreur.messages[0])

    return render(
        request,
        "achats/reception_formulaire.html",
        {"commande": commande, "lignes": lignes},
    )


@permission_requise("achats.view_receptionachat")
def liste_receptions(request):
    receptions = ReceptionAchat.objects.select_related("commande__fournisseur", "recu_par")
    recherche = request.GET.get("q", "").strip()
    if recherche:
        receptions = receptions.filter(
            Q(numero_bon__icontains=recherche)
            | Q(commande__numero__icontains=recherche)
            | Q(commande__fournisseur__nom__icontains=recherche)
        )
    paginator = Paginator(receptions, 20)
    page = paginator.get_page(request.GET.get("page"))
    return render(
        request,
        "achats/receptions.html",
        {"page": page, "recherche": recherche},
    )


@permission_requise("achats.view_receptionachat")
def detail_reception(request, pk):
    reception = get_object_or_404(
        ReceptionAchat.objects.select_related("commande__fournisseur", "recu_par"), pk=pk
    )
    lignes = reception.lignes.select_related("ligne_achat__medicament", "lot")
    return render(
        request,
        "achats/reception_detail.html",
        {"reception": reception, "lignes": lignes, "montant": reception.montant_total()},
    )


@permission_requise("achats.change_receptionachat")
def valider_reception(request, pk):
    reception = get_object_or_404(ReceptionAchat, pk=pk)
    if request.method == "POST":
        try:
            reception.valider(request.user)
            journaliser(
                request,
                "RECEPTION",
                reception,
                {"numero_bon": reception.numero_bon},
            )
            messages.success(request, "Reception validee.")
        except ValidationError as erreur:
            messages.error(request, erreur.messages[0])
    return redirect("achats:reception_detail", pk=pk)


def _pdf(contenu, nom):
    reponse = HttpResponse(contenu, content_type="application/pdf")
    reponse["Content-Disposition"] = f'inline; filename="{nom}"'
    return reponse


@permission_requise("achats.view_commandeachat")
def bon_commande_pdf(request, pk):
    from rapports.pdf import GenerateurPDF

    commande = get_object_or_404(
        CommandeAchat.objects.select_related("fournisseur"), pk=pk
    )
    return _pdf(
        GenerateurPDF.bon_commande(commande), f"bon-commande-{commande.numero}.pdf"
    )


@permission_requise("achats.view_receptionachat")
def bon_reception_pdf(request, pk):
    from rapports.pdf import GenerateurPDF

    reception = get_object_or_404(
        ReceptionAchat.objects.select_related("commande__fournisseur"), pk=pk
    )
    return _pdf(
        GenerateurPDF.bon_reception(reception),
        f"bon-reception-{reception.numero_bon}.pdf",
    )
