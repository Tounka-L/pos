from django.utils import timezone
from django.db import models
from django.contrib.auth.models import AbstractUser
from decimal import Decimal
from django.conf import settings
from django.db.models import Sum

# --- UTILISATEURS ---

class CustomUser(AbstractUser):
    is_vendeur = models.BooleanField(default=False)
    
    def __str__(self):
        return self.username

# --- LOGICIEL ET AUDIT ---

class AuditLog(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    action = models.CharField(max_length=255)
    timestamp = models.DateTimeField(auto_now_add=True)
    details = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name = "Journal d'Audit (Mouchard)"
        verbose_name_plural = "Journaux d'Audit"
        ordering = ('-timestamp',)

    def __str__(self):
        return f'{self.timestamp.strftime("%Y-%m-%d %H:%M")} - {self.user} - {self.action}'

# --- STOCK ET PRODUITS ---

class Category(models.Model):
    name = models.CharField(max_length=100, unique=True, verbose_name="Nom de la Catégorie")

    class Meta:
        verbose_name = "Catégorie"
        verbose_name_plural = "Catégories"
        
    def __str__(self):
        return self.name

class Product(models.Model):
    name = models.CharField(max_length=200, unique=True, verbose_name="Nom du Produit")
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, verbose_name="Catégorie")
    
    price_achat = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Prix d'Achat")
    price_vente = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Prix de Vente")
    
    # Stock Centralisé (Monomagasin)
    quantity_in_stock = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), verbose_name="Quantité en Stock")
    stock_alert_threshold = models.IntegerField(default=5, verbose_name="Seuil d'Alerte Bas")
    
    barcode = models.CharField(max_length=50, blank=True, null=True, unique=True)

    class Meta:
        verbose_name = "Produit"
        verbose_name_plural = "Produits"
        
    def __str__(self):
        return self.name

    @property
    def is_stock_low(self):
        return self.quantity_in_stock <= self.stock_alert_threshold

# --- CLIENTS ET VENTES ---

class Client(models.Model):
    name = models.CharField(max_length=200, verbose_name="Nom du Client")
    phone_number = models.CharField(max_length=20, blank=True, null=True, verbose_name="Téléphone")
    balance = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), verbose_name="Solde Dette")
    credit_limit = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), verbose_name="Plafond Crédit")

    class Meta:
        verbose_name = "Client"
        verbose_name_plural = "Clients"

    def __str__(self):
        return self.name

class CashSession(models.Model):
    vendeur = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='cash_sessions')
    ouverture_time = models.DateTimeField(auto_now_add=True)
    solde_initial = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    montant_declare_vendeur = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    cloture_time = models.DateTimeField(null=True, blank=True)
    
    STATUS_CHOICES = [('O', 'Ouverte'), ('C', 'Clôturée'), ('D', 'Déclarée')]
    status = models.CharField(max_length=1, choices=STATUS_CHOICES, default='O')

    def calculer_rapport(self):
        ventes_session = self.sale_set.filter(status='V')
        total_especes = ventes_session.filter(payment_method='CA').aggregate(Sum('total_sale'))['total_sale__sum'] or Decimal('0.00')
        theorique = self.solde_initial + total_especes
        ecart = self.montant_declare_vendeur - theorique if self.montant_declare_vendeur is not None else Decimal('0.00')
        return {'total_especes': total_especes, 'theorique': theorique, 'ecart': ecart}
    @property
    def montant_theorique(self):
        """Calcule le montant attendu en caisse dynamiquement"""
        rapport = self.calculer_rapport() # Utilise votre méthode existante
        return rapport.get('theorique', 0)
    class Meta:
        verbose_name = "Session de Caisse"
        verbose_name_plural = "Sessions de Caisse"

class Sale(models.Model):
    PAYMENT_CHOICES = [('CA', 'Espèces'), ('MM', 'Mobile Money'), ('CR', 'Crédit')]
    STATUS_CHOICES = [('V', 'Validée'), ('C', 'Annulée')]
    
    date_sold = models.DateTimeField(auto_now_add=True)
    vendeur = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    client = models.ForeignKey(Client, on_delete=models.SET_NULL, null=True, blank=True)
    payment_method = models.CharField(max_length=2, choices=PAYMENT_CHOICES, default='CA')
    total_sale = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    discount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), verbose_name="Remise")
    total_refunded = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    status = models.CharField(max_length=1, choices=STATUS_CHOICES, default='V')
    cash_session = models.ForeignKey(CashSession, on_delete=models.SET_NULL, null=True, blank=True)
    mm_transaction_id = models.CharField(max_length=100, blank=True, null=True)


    @property
    def final_amount(self):
        return self.total_sale - self.total_refunded

    def __str__(self):
        return f"Vente #{self.pk} - {self.total_sale} FCFA"

class SaleItem(models.Model):
    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    quantity = models.DecimalField(max_digits=10, decimal_places=2)
    price_at_sale = models.DecimalField(max_digits=10, decimal_places=2)
    quantity_returned = models.PositiveIntegerField(default=0)

    @property
    def subtotal(self):
        return self.quantity * self.price_at_sale

    def __str__(self):
        return f"{self.quantity} x {self.product.name}"

# --- PERTES ---

class Perte(models.Model):
    MOTIFS = [('CASSE', 'Casse'), ('PERIME', 'Périmé'), ('VOL', 'Vol')]
    produit = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantite = models.PositiveIntegerField()
    motif = models.CharField(max_length=20, choices=MOTIFS)
    date_perte = models.DateTimeField(auto_now_add=True)
    vendeur = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)

    def __str__(self):
        return f"Perte: {self.produit.name}"