from django.conf import settings


def pharmacie(request):
    return {"PHARMACIE": settings.PHARMACIE}
