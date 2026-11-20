from django import forms

from utilisateurs.formulaires import FormulaireStyleMixin

from .models import Client


class ClientForm(FormulaireStyleMixin, forms.ModelForm):
    class Meta:
        model = Client
        fields = ["nom", "telephone", "adresse", "est_actif"]


