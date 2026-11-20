from django import template

register = template.Library()


@register.filter
def a_permission(utilisateur, code):
    return bool(utilisateur and utilisateur.is_authenticated and utilisateur.peut(code))


@register.simple_tag(takes_context=True)
def url_page(context, page):
    request = context.get("request")
    if request is None:
        return f"?page={page}"
    parametres = request.GET.copy()
    parametres["page"] = page
    return "?" + parametres.urlencode()
