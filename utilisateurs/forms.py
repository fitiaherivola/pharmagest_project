from django import forms

from utilisateurs.formulaires import FormulaireStyleMixin
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm

from .models import Role, Utilisateur


class ConnexionForm(FormulaireStyleMixin, AuthenticationForm):
    username = forms.CharField(label="Identifiant", widget=forms.TextInput(attrs={"autofocus": True}))
    password = forms.CharField(label="Mot de passe", widget=forms.PasswordInput)


class UtilisateurCreationForm(FormulaireStyleMixin, UserCreationForm):
    class Meta:
        model = Utilisateur
        fields = [
            "username",
            "first_name",
            "last_name",
            "email",
            "telephone",
            "role",
            "is_active",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["role"].queryset = Role.objects.all()
        self.fields["role"].required = True


class UtilisateurModificationForm(FormulaireStyleMixin, forms.ModelForm):
    class Meta:
        model = Utilisateur
        fields = [
            "username",
            "first_name",
            "last_name",
            "email",
            "telephone",
            "role",
            "is_active",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["role"].queryset = Role.objects.all()
        self.fields["role"].required = True
        if self.instance and self.instance.is_superuser:
            self.fields["is_active"].disabled = True


class ProfilForm(FormulaireStyleMixin, forms.ModelForm):
    class Meta:
        model = Utilisateur
        fields = ["first_name", "last_name", "email", "telephone"]


