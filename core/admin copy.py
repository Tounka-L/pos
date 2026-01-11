from django.contrib import admin
from .models import AuditLog, Category, Product, Client, Sale, SaleItem, CashSession, CustomUser, Perte, Magasin , Transfert, StockItem
from django.contrib.auth.admin import UserAdmin

# Register your models here.
admin.site.register(AuditLog)
admin.site.register(Perte)
admin.site.register(Magasin)
admin.site.register(Transfert)
admin.site.register(StockItem)
admin.site.register(Category)
admin.site.register(Product)
admin.site.register(Client)
admin.site.register(Sale)
admin.site.register(SaleItem)
admin.site.register(CashSession)
@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    # On définit ici les champs qui s'affichent dans l'admin
    list_display = ('username', 'email', 'is_staff', 'is_active')
    
    # C'est ce bloc qui fait apparaître le lien de changement de mot de passe
    fieldsets = UserAdmin.fieldsets 
    add_fieldsets = UserAdmin.add_fieldsets
