from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser, Product, Category, Sale, SaleItem, CashSession, Client, Perte, AuditLog

# 1. Configuration des produits et catégories
@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name',)

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'price_achat', 'price_vente', 'quantity_in_stock', 'stock_alert_threshold')
    list_editable = ('price_vente', 'quantity_in_stock', 'stock_alert_threshold')
    search_fields = ('name', 'barcode')
    list_filter = ('category',)

# 2. Gestion des articles à l'intérieur d'une vente
class SaleItemInline(admin.TabularInline):
    model = SaleItem
    extra = 0
    # On affiche les champs réels : product, quantity, price_at_sale
    readonly_fields = ('product', 'quantity', 'price_at_sale')

# 3. Gestion des ventes
@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = ('id', 'date_sold', 'vendeur', 'client', 'payment_method', 'total_sale', 'status')
    list_filter = ('date_sold', 'payment_method', 'status')
    search_fields = ('id', 'vendeur__username', 'client__name', 'mm_transaction_id')
    inlines = [SaleItemInline]

# 4. Gestion des sessions de caisse
@admin.register(CashSession)
class CashSessionAdmin(admin.ModelAdmin):
    # Champs réels : ouverture_time, solde_initial, montant_declare_vendeur
    list_display = ('vendeur', 'ouverture_time', 'cloture_time', 'solde_initial', 'status')
    list_filter = ('status', 'vendeur')

# 5. Gestion des clients
@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    # Champ réel : phone_number
    list_display = ('name', 'phone_number', 'balance', 'credit_limit')
    search_fields = ('name', 'phone_number')

# 6. Gestion des pertes
@admin.register(Perte)
class PerteAdmin(admin.ModelAdmin):
    # Champ réel : motif
    list_display = ('produit', 'quantite', 'motif', 'date_perte', 'vendeur')
    list_filter = ('motif', 'date_perte')

# 7. Journal d'audit (Le mouchard)
@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'user', 'action')
    readonly_fields = ('timestamp', 'user', 'action', 'details')

# Personnalisation de l'interface
admin.site.site_header = "Administration RBA Digital"
admin.site.index_title = "Gestion Électronique & POS"

@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    # On définit ici les champs qui s'affichent dans l'admin
    list_display = ('username', 'email', 'is_staff', 'is_active')
    
    # C'est ce bloc qui fait apparaître le lien de changement de mot de passe
    fieldsets = UserAdmin.fieldsets 
    add_fieldsets = UserAdmin.add_fieldsets