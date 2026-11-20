from django import forms

from utilisateurs.formulaires import FormulaireStyleMixin

from .models import LigneVente, RetourVente, Vente


class RetourVenteForm(FormulaireStyleMixin, forms.Form):
    ligne_vente = forms.ModelChoiceField(
        queryset=LigneVente.objects.none(), label="Ligne de vente"
    )
    quantite_retournee = forms.IntegerField(min_value=1, label="Quantite retournee")
    motif = forms.CharField(widget=forms.Textarea(attrs={"rows": 3}), label="Motif")
    remis_en_stock = forms.BooleanField(
        required=False, initial=True, label="Remettre en stock si le lot est delivrable"
    )

    def __init__(self, *args, vente=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.vente = vente
        if vente is not None:
            self.fields["ligne_vente"].queryset = vente.lignes.select_related(
                "medicament", "lot"
            )

    def clean(self):
        donnees = super().clean()
        ligne = donnees.get("ligne_vente")
        quantite = donnees.get("quantite_retournee")
        if ligne and quantite:
            if ligne.vente_id != self.vente.pk:
                self.add_error("ligne_vente", "Cette ligne n'appartient pas a la vente.")
            elif quantite > ligne.quantite_restante_retournable():
                self.add_error(
                    "quantite_retournee",
                    f"Quantite retournable restante : {ligne.quantite_restante_retournable()}.",
                )
        return donnees


