from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from utilisateurs.decorators import journaliser, permission_requise

from .forms import ClientForm
from .models import Client


@permission_requise("clients.view_client")
def liste_clients(request):
    clients = Client.objects.all()
    recherche = request.GET.get("q", "").strip()
    if recherche:
        clients = clients.filter(
            Q(nom__icontains=recherche)
            | Q(telephone__icontains=recherche)
            | Q(adresse__icontains=recherche)
        )
    paginator = Paginator(clients, 20)
    page = paginator.get_page(request.GET.get("page"))
    return render(
        request, "clients/liste.html", {"page": page, "recherche": recherche}
    )


@permission_requise("clients.view_client")
def detail_client(request, pk):
    client = get_object_or_404(Client, pk=pk)
    return render(
        request,
        "clients/detail.html",
        {
            "client": client,
            "ventes": client.historique_ventes()[:50],
            "total": client.total_achats(),
        },
    )


@permission_requise("clients.add_client")
def creer_client(request):
    formulaire = ClientForm(request.POST or None)
    if request.method == "POST" and formulaire.is_valid():
        client = formulaire.save()
        journaliser(request, "CREATION", client, {"nom": str(client)})
        messages.success(request, "Client cree.")
        return redirect("clients:liste")
    return render(
        request,
        "clients/formulaire.html",
        {"formulaire": formulaire, "titre": "Nouveau client"},
    )


@permission_requise("clients.change_client")
def modifier_client(request, pk):
    client = get_object_or_404(Client, pk=pk)
    formulaire = ClientForm(request.POST or None, instance=client)
    if request.method == "POST" and formulaire.is_valid():
        formulaire.save()
        journaliser(request, "MODIFICATION", client, {"nom": str(client)})
        messages.success(request, "Client mis a jour.")
        return redirect("clients:liste")
    return render(
        request,
        "clients/formulaire.html",
        {"formulaire": formulaire, "titre": f"Modifier {client}"},
    )
