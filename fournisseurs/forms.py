from django import forms

from utilisateurs.formulaires import FormulaireStyleMixin

from .models import Fournisseur


class FournisseurForm(FormulaireStyleMixin, forms.ModelForm):
    class Meta:
        model = Fournisseur
        fields = [
            "nom",
            "contact_principal",
            "telephone",
            "email",
            "adresse",
            "numero_fiscal",
            "est_actif",
        ]
        widgets = {"adresse": forms.Textarea(attrs={"rows": 3})}


