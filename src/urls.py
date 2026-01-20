"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path
from django.urls import include
from django.contrib.auth import views as auth_views # Importation des vues d'auth
from django.views.generic.base import RedirectView # Import nécessaire
from django.views.generic import TemplateView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', RedirectView.as_view(pattern_name='login', permanent=False), name='index'),

     # Cette ligne "trompe" le navigateur en servant le JS à la racine
    path('serviceworker.js', TemplateView.as_view(
        template_name="serviceworker.js", 
        content_type='application/javascript'), name='sw'),
    
   
    # ------------------------------------------------------------------
    # L'application d'authentification incluse de Django (qui inclut login, logout, etc.)
    # Nous utilisons nos propres noms pour la clarté (conformément à LOGIN_URL = 'login' dans settings)
    
    path('login/', auth_views.LoginView.as_view(template_name='core/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='/login/'), name='logout'),
    path('', include('core.urls')),  # Inclure les URLs de l'application 'core'
    path('serviceworker.js', TemplateView.as_view(template_name="static/serviceworker.js", content_type='application/javascript')),
    path('offline/', TemplateView.as_view(template_name="offline.html"), name='offline'),
]
    
   
