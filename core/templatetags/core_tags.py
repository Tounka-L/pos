# core/templatetags/core_tags.py
from django import template
from django.contrib.auth.models import Group

register = template.Library()

@register.filter(name='has_group')
def has_group(user, group_name):
    """
    Vérifie si l'utilisateur est membre du groupe spécifié.
    Utilisation dans le template: {% if user|has_group:"Vendeur" %}
    """
    try:
        group = Group.objects.get(name=group_name)
    except Group.DoesNotExist:
        return False
    return group in user.groups.all()