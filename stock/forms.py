from django import forms

from utilisateurs.formulaires import FormulaireStyleMixin

from .models import Inventaire, LotStock


class LotStockForm(FormulaireStyleMixin, forms.ModelForm):
    class Meta:
        model = LotStock
        fields = [
            "medicament",
            "numero_lot",
            "date_peremption",
            "quantite_recue",
            "quantite_disponible",
            "date_reception",
            "est_bloque",
            "motif_blocage",
        ]
        widgets = {
            "date_peremption": forms.DateInput(attrs={"type": "date"}),
            "date_reception": forms.DateInput(attrs={"type": "date"}),
            "motif_blocage": forms.Textarea(attrs={"rows": 2}),
        }

    def clean(self):
        donnees = super().clean()
        disponible = donnees.get("quantite_disponible") or 0
        recue = donnees.get("quantite_recue") or 0
        if disponible < 0 or recue < 0:
            raise forms.ValidationError("Les quantites ne peuvent pas etre negatives.")
        if donnees.get("est_bloque") and not donnees.get("motif_blocage"):
            self.add_error("motif_blocage", "Indiquez le motif du blocage.")
        return donnees


class InventaireForm(FormulaireStyleMixin, forms.ModelForm):
    class Meta:
        model = Inventaire
        fields = ["date_inventaire", "commentaire"]
        widgets = {
            "date_inventaire": forms.DateInput(attrs={"type": "date"}),
            "commentaire": forms.Textarea(attrs={"rows": 2}),
        }


