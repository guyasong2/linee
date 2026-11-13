from django import template

register = template.Library()


@register.filter
def xaf(value) -> str:
    """Format an integer XAF amount without misleading decimals."""
    try:
        amount = int(value)
    except (TypeError, ValueError):
        return ""
    return f"{amount:,}".replace(",", " ") + " FCFA"
