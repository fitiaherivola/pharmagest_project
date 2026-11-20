from django import forms


class FormulaireStyleMixin:
    """Ajoute les classes Bootstrap aux widgets des formulaires."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for champ in self.fields.values():
            widget = champ.widget
            if isinstance(widget, forms.HiddenInput):
                continue
            classes = widget.attrs.get("class", "")
            if isinstance(widget, forms.CheckboxInput):
                widget.attrs["class"] = f"{classes} form-check-input".strip()
            elif isinstance(widget, forms.Select):
                widget.attrs["class"] = f"{classes} form-select".strip()
            else:
                widget.attrs["class"] = f"{classes} form-control".strip()
