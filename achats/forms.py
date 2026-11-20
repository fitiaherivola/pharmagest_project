from django import forms

from utilisateurs.formulaires import FormulaireStyleMixin

from medicaments.models import Medicament

from .models import CommandeAchat, LigneAchat


class CommandeAchatForm(FormulaireStyleMixin, forms.ModelForm):
    class Meta:
        model = CommandeAchat
        fields = ["fournisseur"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["fournisseur"].queryset = self.fields["fournisseur"].queryset.filter(
            est_actif=True
        )
        self.fields["fournisseur"].empty_label = "Selectionner un fournisseur"


class LigneAchatForm(FormulaireStyleMixin, forms.ModelForm):
    class Meta:
        model = LigneAchat
        fields = ["medicament", "quantite_commandee", "prix_achat_unitaire"]
        widgets = {
            "prix_achat_unitaire": forms.NumberInput(
                attrs={"step": "0.01", "min": "0.01"}
            ),
            "quantite_commandee": forms.NumberInput(attrs={"min": "1"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["medicament"].queryset = Medicament.objects.filter(
            statut=Medicament.ACTIF
        ).order_by("nom_commercial")
        self.fields["medicament"].empty_label = "Selectionner un medicament"

    def clean_quantite_commandee(self):
        quantite = self.cleaned_data.get("quantite_commandee")
        if quantite is None or quantite <= 0:
            raise forms.ValidationError("La quantite commandee doit etre strictement positive.")
        return quantite

    def clean_prix_achat_unitaire(self):
        prix = self.cleaned_data.get("prix_achat_unitaire")
        if prix is None or prix <= 0:
            raise forms.ValidationError("Le prix d'achat doit etre strictement positif.")
        return prix


