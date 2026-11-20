from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied

from .models import JournalAudit


def permission_requise(code):
    """Refuse l'acces (HTTP 403) si l'utilisateur n'a pas la permission."""

    def decorateur(vue):
        @wraps(vue)
        @login_required
        def enveloppe(request, *args, **kwargs):
            if not request.user.peut(code):
                JournalAudit.enregistrer(
                    request.user,
                    "ACCES_REFUSE",
                    details={"permission": code, "vue": vue.__name__},
                    request=request,
                )
                raise PermissionDenied(
                    "Vous n'avez pas la permission requise pour cette action."
                )
            return vue(request, *args, **kwargs)

        return enveloppe

    return decorateur


def role_requis(*roles):
    """Refuse l'acces si le role de l'utilisateur ne fait pas partie de la liste."""

    def decorateur(vue):
        @wraps(vue)
        @login_required
        def enveloppe(request, *args, **kwargs):
            utilisateur = request.user
            autorise = utilisateur.is_superuser or (
                utilisateur.role and utilisateur.role.nom in roles
            )
            if not autorise:
                JournalAudit.enregistrer(
                    utilisateur,
                    "ACCES_REFUSE",
                    details={"roles": list(roles), "vue": vue.__name__},
                    request=request,
                )
                raise PermissionDenied("Votre role ne permet pas cette action.")
            return vue(request, *args, **kwargs)

        return enveloppe

    return decorateur


def journaliser(request, action, objet=None, details=None):
    return JournalAudit.enregistrer(
        getattr(request, "user", None),
        action,
        objet=objet,
        details=details,
        request=request,
    )
