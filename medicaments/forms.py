from django import forms

from utilisateurs.formulaires import FormulaireStyleMixin

from .models import Categorie, Medicament


class CategorieForm(FormulaireStyleMixin, forms.ModelForm):
    class Meta:
        model = Categorie
        fields = ["nom", "description"]
        widgets = {"description": forms.Textarea(attrs={"rows": 3})}


class MedicamentForm(FormulaireStyleMixin, forms.ModelForm):
    class Meta:
        model = Medicament
        fields = [
            "nom_commercial",
            "denomination_generique",
            "categorie",
            "forme",
            "dosage",
            "laboratoire",
            "code_barres",
            "photo",
            "prix_achat",
            "prix_vente",
            "seuil_alerte",
            "statut",
        ]
        widgets = {
            "prix_achat": forms.NumberInput(attrs={"step": "0.01", "min": "0.01"}),
            "prix_vente": forms.NumberInput(attrs={"step": "0.01", "min": "0.01"}),
        }

    def clean_code_barres(self):
        code = (self.cleaned_data.get("code_barres") or "").strip()
        return code or None

    def clean(self):
        donnees = super().clean()
        achete = donnees.get("prix_achat")
        vendu = donnees.get("prix_vente")
        if achete and vendu and vendu < achete:
            self.add_error("prix_vente", "Le prix de vente doit etre superieur ou egal au prix d'achat.")
        return donnees


