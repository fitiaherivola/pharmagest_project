from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, LogoutView
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from .decorators import journaliser, permission_requise
from .forms import (
    ConnexionForm,
    ProfilForm,
    UtilisateurCreationForm,
    UtilisateurModificationForm,
)
from .models import JournalAudit, Role, Utilisateur


class ConnexionView(LoginView):
    template_name = "utilisateurs/connexion.html"
    authentication_form = ConnexionForm
    redirect_authenticated_user = True

    def form_invalid(self, form):
        messages.error(self.request, "Identifiant ou mot de passe incorrect.")
        return super().form_invalid(form)


class DeconnexionView(LogoutView):
    next_page = "utilisateurs:connexion"


@login_required
def profil(request):
    formulaire = ProfilForm(instance=request.user)
    if request.method == "POST":
        formulaire = ProfilForm(request.POST, instance=request.user)
        if formulaire.is_valid():
            formulaire.save()
            journaliser(request, "MODIFICATION", request.user, {"champ": "profil"})
            messages.success(request, "Profil mis a jour.")
            return redirect("utilisateurs:profil")
    return render(request, "utilisateurs/profil.html", {"formulaire": formulaire})


@login_required
def changer_mot_de_passe(request):
    if request.method == "POST":
        ancien = request.POST.get("ancien", "")
        nouveau = request.POST.get("nouveau", "")
        confirmation = request.POST.get("confirmation", "")
        if nouveau != confirmation:
            messages.error(request, "La confirmation ne correspond pas au nouveau mot de passe.")
        elif len(nouveau) < 8:
            messages.error(request, "Le nouveau mot de passe doit contenir au moins 8 caracteres.")
        else:
            try:
                request.user.changer_mot_de_passe(ancien, nouveau)
                journaliser(request, "MODIFICATION", request.user, {"champ": "mot_de_passe"})
                messages.success(request, "Mot de passe modifie.")
                return redirect("utilisateurs:profil")
            except ValidationError as erreur:
                messages.error(request, erreur.messages[0])
    return render(request, "utilisateurs/changer_mot_de_passe.html")


@permission_requise("utilisateurs.view_utilisateur")
def liste_utilisateurs(request):
    recherche = request.GET.get("q", "").strip()
    utilisateurs = Utilisateur.objects.select_related("role")
    if recherche:
        utilisateurs = utilisateurs.filter(
            Q(username__icontains=recherche)
            | Q(first_name__icontains=recherche)
            | Q(last_name__icontains=recherche)
            | Q(telephone__icontains=recherche)
        )
    paginator = Paginator(utilisateurs, 20)
    page = paginator.get_page(request.GET.get("page"))
    return render(
        request,
        "utilisateurs/liste.html",
        {"page": page, "recherche": recherche, "roles": Role.objects.all()},
    )


@permission_requise("utilisateurs.add_utilisateur")
def creer_utilisateur(request):
    formulaire = UtilisateurCreationForm(request.POST or None)
    if request.method == "POST" and formulaire.is_valid():
        utilisateur = formulaire.save()
        journaliser(
            request,
            "CREATION",
            utilisateur,
            {"username": utilisateur.username, "role": str(utilisateur.role)},
        )
        messages.success(request, "Utilisateur cree.")
        return redirect("utilisateurs:liste")
    return render(
        request,
        "utilisateurs/formulaire.html",
        {"formulaire": formulaire, "titre": "Nouvel utilisateur"},
    )


@permission_requise("utilisateurs.change_utilisateur")
def modifier_utilisateur(request, pk):
    utilisateur = get_object_or_404(Utilisateur, pk=pk)
    formulaire = UtilisateurModificationForm(request.POST or None, instance=utilisateur)
    if request.method == "POST" and formulaire.is_valid():
        formulaire.save()
        journaliser(request, "MODIFICATION", utilisateur, {"username": utilisateur.username})
        messages.success(request, "Utilisateur mis a jour.")
        return redirect("utilisateurs:liste")
    return render(
        request,
        "utilisateurs/formulaire.html",
        {"formulaire": formulaire, "titre": f"Modifier {utilisateur.nom_complet()}"},
    )


@permission_requise("utilisateurs.change_utilisateur")
def basculer_utilisateur(request, pk):
    utilisateur = get_object_or_404(Utilisateur, pk=pk)
    if request.method == "POST":
        if utilisateur == request.user:
            messages.error(request, "Vous ne pouvez pas desactiver votre propre compte.")
        else:
            if utilisateur.is_active:
                utilisateur.desactiver()
                action = "desactive"
            else:
                utilisateur.activer()
                action = "active"
            journaliser(request, "MODIFICATION", utilisateur, {"action": action})
            messages.success(request, f"Compte {action}.")
    return redirect("utilisateurs:liste")


@permission_requise("utilisateurs.view_journalaudit")
def journal_audit(request):
    entrees = JournalAudit.objects.select_related("utilisateur")
    action = request.GET.get("action", "")
    recherche = request.GET.get("q", "").strip()
    if action:
        entrees = entrees.filter(action=action)
    if recherche:
        entrees = entrees.filter(
            Q(modele_cible__icontains=recherche)
            | Q(utilisateur__username__icontains=recherche)
            | Q(details__icontains=recherche)
        )
    paginator = Paginator(entrees, 50)
    page = paginator.get_page(request.GET.get("page"))
    return render(
        request,
        "utilisateurs/journal.html",
        {
            "page": page,
            "actions": JournalAudit.ACTIONS,
            "action": action,
            "recherche": recherche,
        },
    )
