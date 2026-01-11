from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.db import transaction
from django.db.models import Sum, F
from django.utils import timezone
from django.http import HttpResponse, JsonResponse
from django.template.loader import get_template
from django.views.generic import ListView
from django.contrib.auth.mixins import UserPassesTestMixin, LoginRequiredMixin
from datetime import datetime, time
from django.utils.timezone import make_aware
from io import BytesIO
from decimal import Decimal
from django.contrib.auth import logout
# import xhtml2pdf.pisa as pisa # Décommenter si tu as installé xhtml2pdf

from .models import (
    CashSession, Sale, SaleItem, Product, Client, 
    Perte, Category, AuditLog
)
from django.utils import timezone
from django.db.models import Sum, F
from datetime import datetime, timedelta
from django.db import transaction
from decimal import Decimal
from django.contrib import messages
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from django.http import HttpResponse
from datetime import date

# Règle 1 : Pour le Patron uniquement (Accès total + Dashboard)
def est_patron(user):
    return user.is_superuser and user.is_active

# Règle 2 : Pour le Vendeur ET le Patron (Accès Caisse + Fermeture)
def est_staff(user):
    return (user.groups.filter(name='Vendeur').exists() or user.is_superuser) and user.is_active
# Vérification si l'utilisateur est un vendeur (ajustez selon votre modèle)
def is_vendeur(user):
    return user.groups.filter(name='Vendeur').exists() or user.is_superuser

# --- OUVERTURE DE SESSION ---
@login_required
def open_cash_session_view(request):
    # 1. Si session déjà OUVERTE, direction POS
    if CashSession.objects.filter(vendeur=request.user, status='O').exists():
        return redirect('pos_view')
    
    # 2. Si session DÉCLARÉE ('D'), on redirige vers le Dashboard (Casse la boucle)
    # Le Superuser n'est pas bloqué par ce message
    if CashSession.objects.filter(vendeur=request.user, status='D').exists() and not request.user.is_superuser:
        messages.warning(request, "Votre session est en attente de validation par le patron.")
        return redirect('dashboard')

    if request.method == 'POST':
        solde_initial = request.POST.get('solde_initial', '0')
        try:
            CashSession.objects.create(
                vendeur=request.user, 
                solde_initial=Decimal(solde_initial),
                status='O'
            )
            messages.success(request, "Caisse ouverte avec succès !")
            return redirect('pos_view')
        except Exception as e:
            messages.error(request, f"Erreur : {e}")
            
    return render(request, 'core/open_session.html')

# --- FERMETURE DE SESSION (Placeholder) ---
@login_required
@user_passes_test(est_staff)
def close_cash_session_view(request):
    current_session = CashSession.objects.filter(vendeur=request.user, status='O').first()

    if not current_session:
        messages.error(request, "Aucune session active.")
        return redirect('dashboard')

    if request.method == 'POST':
        try:
            # Récupération du montant depuis le formulaire
            raw_amount = request.POST.get('fond_final_reel', '0').replace(',', '.')
            montant_declare = Decimal(raw_amount)
            
            # Mise à jour de la session
            current_session.montant_declare_vendeur = montant_declare
            current_session.cloture_time = timezone.now()
            current_session.status = 'D' # Statut Déclaré
            current_session.save()
            
            messages.success(request, f"Caisse déclarée ({montant_declare} F). En attente de validation.")
            logout(request) # On déconnecte le vendeur proprement
            return redirect('login') 
            
        except Exception as e:
            messages.error(request, f"Erreur de saisie : {e}")

    return render(request, 'core/close_session.html', {'session': current_session})
# --- POINT DE VENTE (POS) ---
@login_required
def pos_view(request):
    # 1. Vérification de la Session : On laisse passer le Superuser même sans session 'O'
    current_session = CashSession.objects.filter(vendeur=request.user, status='O').first()
    
    if not current_session and not request.user.is_superuser:
        messages.warning(request, "Veuillez ouvrir la caisse d'abord.")
        return redirect('open_cash_session')

    # 2. Gestion du Panier
    cart = request.session.get('cart', {})
    if not isinstance(cart, dict):
        cart = {}
        request.session['cart'] = cart

    # 3. Récupération des Produits et Clients
    query = request.GET.get('q')
    products = Product.objects.filter(name__icontains=query).order_by('name') if query else Product.objects.all().order_by('name')
    all_clients = Client.objects.all().order_by('name')

    # 4. Calcul du Total
    total_cart = Decimal('0.00')
    for p_id, item in cart.items():
        price = Decimal(str(item.get('price', 0)))
        qty = Decimal(str(item.get('qty', 0)))
        subtotal = price * qty
        item['subtotal'] = subtotal 
        total_cart += subtotal

    context = {
        'current_session': current_session,
        'products': products,
        'all_clients': all_clients,
        'cart': cart,
        'total_cart': total_cart,
    }
    return render(request, 'core/pos.html', context)

@login_required
@user_passes_test(is_vendeur)
def add_to_cart(request, product_id):
    product = get_object_or_404(Product, pk=product_id)
    
    # Stock direct
    stock_disponible = product.quantity_in_stock

    cart = request.session.get('cart', {})
    if not isinstance(cart, dict): cart = {}
    
    p_id = str(product_id)

    # Logique d'ajout
    qty_in_cart = 0
    if p_id in cart:
        qty_in_cart = Decimal(str(cart[p_id]['qty']))

    if (qty_in_cart + 1) > stock_disponible:
        messages.error(request, f"Stock insuffisant ({stock_disponible} en stock).")
    else:
        if p_id in cart:
            cart[p_id]['qty'] += 1
        else:
            cart[p_id] = {
                'product_id': p_id,
                'name': product.name,
                'price': float(product.price_vente),
                'qty': 1,
            }
        request.session['cart'] = cart
        request.session.modified = True

    return redirect('pos_view')

@login_required
def remove_from_cart(request, item_index):
    # item_index est ici le product_id (clé du dictionnaire)
    cart = request.session.get('cart', {})
    p_id = str(item_index)
    
    if p_id in cart:
        del cart[p_id]
        request.session['cart'] = cart
        request.session.modified = True
    
    return redirect('pos_view')

@login_required
def update_cart_price(request, item_index, new_price):
    cart = request.session.get('cart', {})
    p_id = str(item_index)
    
    try:
        if p_id in cart:
            product = Product.objects.get(pk=p_id)
            new_p = float(new_price)
            
            # Sécurité Prix Achat
            if new_p < float(product.price_achat):
                messages.error(request, f"Impossible : Prix minimum {product.price_achat} F")
            else:
                cart[p_id]['price'] = new_p
                request.session['cart'] = cart
                request.session.modified = True
                messages.success(request, "Prix modifié.")
    except Exception:
        messages.error(request, "Erreur modification prix.")
        
    return redirect('pos_view')



@login_required
@user_passes_test(is_vendeur)
def checkout_sale_view(request):
    if request.method != 'POST': 
        return redirect('pos_view')

    # 1. Récupération du panier
    cart = request.session.get('cart', {})
    if not cart:
        messages.error(request, "Le panier est vide.")
        return redirect('pos_view')

    # 2. Vérification de la session de caisse ouverte
    current_session = CashSession.objects.filter(vendeur=request.user, status='O').first()
    if not current_session:
        messages.error(request, "Aucune session de caisse ouverte.")
        return redirect('open_cash_session')

    try:
        with transaction.atomic():
            # 3. Récupération des données du formulaire
            client_id = request.POST.get('client_id')
            payment_method = request.POST.get('payment_method', 'CA')
            # Gestion de la remise (discount)
            discount_input = request.POST.get('discount', '0').replace(',', '.')
            discount_amount = Decimal(discount_input or '0.00')

            client = Client.objects.get(id=client_id) if client_id else None

            # 4. Création initiale de la vente (le total sera mis à jour après la boucle)
            sale = Sale.objects.create(
                cash_session=current_session,
                vendeur=request.user,
                client=client,
                payment_method=payment_method,
                discount=discount_amount, # On enregistre la remise
                status='V'
            )

            total_ht = Decimal('0.00')

            # 5. Boucle sur les articles du panier
            for p_id, item in cart.items():
                qty = Decimal(str(item['qty']))
                price = Decimal(str(item['price']))

                # Verrouillage du produit pour éviter les conflits de stock (concurrence)
                product = Product.objects.select_for_update().get(id=p_id)

                if product.quantity_in_stock < qty:
                    raise ValueError(f"Stock insuffisant pour {product.name} ({product.quantity_in_stock} restants).")

                # Décrémentation du stock
                product.quantity_in_stock -= qty
                product.save()

                # Création de la ligne de vente
                SaleItem.objects.create(
                    sale=sale,
                    product=product,
                    quantity=qty,
                    price_at_sale=price
                )

                total_ht += (price * qty)

            # 6. Calcul final avec remise
            total_final = total_ht - discount_amount
            if total_final < 0:
                raise ValueError("La remise ne peut pas être supérieure au montant total.")

            sale.total_sale = total_final
            
            # 7. Gestion du Crédit Client
            if payment_method == 'CR':
                if not client: 
                    raise ValueError("Un client doit être sélectionné pour une vente à crédit.")
                
                # Vérification du plafond de crédit
                if client.credit_limit > 0 and (client.balance + total_final) > client.credit_limit:
                    raise ValueError(f"Le plafond de crédit de {client.name} est dépassé.")
                
                client.balance += total_final
                client.save()

            sale.save()

            # 8. Nettoyage de la session
            request.session['cart'] = {}
            request.session.modified = True
            
            messages.success(request, f"Vente #{sale.id} réussie ! Total: {total_final} F")
            return redirect('sale_detail', sale_id=sale.id)

    except ValueError as e:
        messages.error(request, str(e))
    except Product.DoesNotExist:
        messages.error(request, "Un produit dans votre panier n'existe plus.")
    except Exception as e:
        messages.error(request, f"Erreur critique : {str(e)}")
        
    return redirect('pos_view')



@login_required
@user_passes_test(est_patron)
def dashboard_patron_view(request):
    today_now = timezone.now()
    
    # --- 1. GESTION DES DATES ---
    default_start = today_now.replace(day=1).strftime('%Y-%m-%d')
    default_end = today_now.strftime('%Y-%m-%d')

    start_date = request.GET.get('start_date', default_start)
    end_date = request.GET.get('end_date', default_end)

    try:
        start = datetime.strptime(start_date, '%Y-%m-%d')
        end = datetime.strptime(end_date, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
    except ValueError:
        start = today_now.replace(hour=0, minute=0, second=0)
        end = today_now.replace(hour=23, minute=59, second=59)

    # --- 2. RÉCUPÉRATION DES SESSIONS À VALIDER (NOUVEAU) ---
    # C'est ce qui permettra de supprimer le message d'attente sur le dashboard
    sessions_a_valider = CashSession.objects.filter(status='D').order_by('-ouverture_time')

    # --- 3. RÉCUPÉRATION DES DONNÉES FINANCIÈRES ---
    sales_list = Sale.objects.filter(date_sold__range=[start, end])
    pertes_list = Perte.objects.filter(date_perte__range=[start, end])
    
    total_ventes = sales_list.aggregate(total=Sum('total_sale'))['total'] or 0
    nb_transactions = sales_list.count()
    
    # Calcul du bénéfice brut (Optimisé)
    benefice_brut = Decimal('0.00')
    for sale in sales_list.prefetch_related('items__product'):
        for item in sale.items.all():
            benefice_brut += (item.price_at_sale - item.product.price_achat) * item.quantity

    valeur_pertes = pertes_list.aggregate(
        total=Sum(F('quantite') * F('produit__price_achat'))
    )['total'] or 0

    # Alertes Stock
    products_alert = Product.objects.filter(
        quantity_in_stock__lte=F('stock_alert_threshold')
    ).order_by('quantity_in_stock')

    # --- 4. DONNÉES GRAPHIQUE ---
    labels = []
    data_ventes = []
    for i in range(6, -1, -1):
        day = today_now.date() - timedelta(days=i)
        labels.append(day.strftime('%a'))
        daily_total = Sale.objects.filter(date_sold__date=day).aggregate(total=Sum('total_sale'))['total'] or 0
        data_ventes.append(float(daily_total))

    # --- 5. ENVOI AU TEMPLATE ---
    context = {
        'sessions_a_valider': sessions_a_valider, # Pour le tableau de validation
        'total_ventes_jour': total_ventes,
        'nb_transactions_jour': nb_transactions,
        'benefice_jour': benefice_brut - Decimal(str(valeur_pertes)),
        'products_low_stock_count': products_alert.count(),
        'low_stock_products': products_alert[:5],
        'valeur_pertes': valeur_pertes,
        'start_date': start_date, 
        'end_date': end_date,
        'labels_jours': labels,
        'data_ventes': data_ventes,
        'today': today_now,
    }
    
    return render(request, 'core/dashboard_patron.html', context)
@user_passes_test(lambda u: u.is_superuser)
def cancel_sale_admin(request, sale_id):
    sale = get_object_or_404(Sale, id=sale_id)
    
    if sale.status == 'C':
        messages.warning(request, "Déjà annulée.")
        return redirect('dashboard_patron')

    try:
        with transaction.atomic():
            # Remettre le stock
            for item in sale.items.all():
                product = item.product
                product.quantity_in_stock += item.quantity # Correction nom champ
                product.save()
            
            sale.status = 'C'
            sale.save()
            
            # Annuler dette client si crédit
            if sale.payment_method == 'CR' and sale.client:
                sale.client.balance -= sale.total_sale
                sale.client.save()

            messages.success(request, f"Vente #{sale.id} annulée. Stock restauré.")
            
    except Exception as e:
        messages.error(request, f"Erreur : {e}")

    return redirect('dashboard_patron')

@user_passes_test(lambda u: u.is_superuser)
def process_partial_return(request, item_id):
    if request.method == "POST":
        sale_item = get_object_or_404(SaleItem, id=item_id)
        try:
            qty_to_return = int(request.POST.get('return_qty', 0))
        except ValueError:
            return redirect('sale_detail', sale_id=sale_item.sale.id)

        max_returnable = sale_item.quantity - sale_item.quantity_returned
        
        if 0 < qty_to_return <= max_returnable:
            with transaction.atomic():
                # Update ligne
                sale_item.quantity_returned += qty_to_return
                sale_item.save()

                # Update Stock Produit (Correction nom champ)
                product = sale_item.product
                product.quantity_in_stock += qty_to_return
                product.save()

                # Update Vente
                refund_amount = Decimal(str(qty_to_return)) * sale_item.price_at_sale
                sale = sale_item.sale
                sale.total_refunded += refund_amount
                sale.save()

                messages.success(request, f"Retour effectué : {refund_amount} F remboursés.")
    
    return redirect('sale_detail', sale_id=sale_item.sale.id)






@login_required
@user_passes_test(lambda u: u.is_superuser or u.is_staff)
def declarer_perte_view(request):
    # Récupération des produits pour le menu déroulant
    products = Product.objects.all().order_by('name')

    if request.method == "POST":
        product_id = request.POST.get('product_id')
        qty = int(request.POST.get('quantite', 0))
        motif = request.POST.get('motif')
        
        produit = get_object_or_404(Product, id=product_id)
        
        if qty <= 0:
            messages.error(request, "La quantité doit être positive.")
            return render(request, 'core/declarer_perte.html', {'products': products})

        if produit.quantity_in_stock >= qty:
            try:
                with transaction.atomic():
                    # 1. Créer l'enregistrement de perte
                    Perte.objects.create(
                        produit=produit,
                        quantite=qty,
                        motif=motif,
                        vendeur=request.user
                        # Note: Si tu veux un commentaire, ajoute le champ dans le modèle Perte d'abord
                    )
                    
                    # 2. Diminuer le stock réel (Monomagasin)
                    produit.quantity_in_stock -= qty
                    produit.save()
                    
                    messages.success(request, f"Perte de {qty} x {produit.name} enregistrée.")
                    return redirect('dashboard_patron') # Ou recharger la page
                    
            except Exception as e:
                messages.error(request, f"Erreur technique : {str(e)}")
        else:
            messages.error(request, f"Impossible : Stock insuffisant ({produit.quantity_in_stock} dispo).")
            
    return render(request, 'core/declarer_perte.html', {'products': products})



@login_required
@user_passes_test(lambda u: u.is_superuser) # Seul le patron gère les arrivages
def add_stock_view(request):
    """
    Remplace le transfert : permet d'ajouter du stock (Arrivage Fournisseur)
    """
    products = Product.objects.all().order_by('name')

    if request.method == 'POST':
        product_id = request.POST.get('product_id')
        qty = Decimal(request.POST.get('quantity', '0'))
        
        # Optionnel : Prix d'achat modifié lors de l'arrivage ?
        new_price_achat = request.POST.get('new_price_achat') 

        if qty <= 0:
            messages.error(request, "La quantité doit être supérieure à 0.")
        else:
            try:
                with transaction.atomic():
                    product = get_object_or_404(Product, id=product_id)
                    
                    # Mise à jour du stock
                    old_qty = product.quantity_in_stock
                    product.quantity_in_stock += qty
                    
                    # Mise à jour du prix d'achat si fourni (Moyenne pondérée ou Remplacement ?)
                    # Ici, on fait un remplacement simple pour l'exemple
                    if new_price_achat and float(new_price_achat) > 0:
                        product.price_achat = Decimal(new_price_achat)

                    product.save()

                    # Audit (Très important pour les entrées de stock)
                    AuditLog.objects.create(
                        user=request.user,
                        action="APPROVISIONNEMENT",
                        details=f"Ajout de {qty} {product.name}. Stock: {old_qty} -> {product.quantity_in_stock}"
                    )

                    messages.success(request, f"Stock mis à jour : {product.name} (+{qty})")
                    return redirect('add_stock')

            except Exception as e:
                messages.error(request, f"Erreur : {str(e)}")

    return render(request, 'core/add_stock.html', {'products': products})
@login_required
def clear_cart(request):
    """
    Vide complètement le panier en cours.
    """
    request.session['cart'] = {} # On remplace le panier par un dictionnaire vide
    request.session.modified = True
    messages.info(request, "Le panier a été vidé.")
    return redirect("pos_view")

@login_required
def sale_detail(request, sale_id):
    """
    Affiche le détail d'une vente après paiement.
    """
    sale = get_object_or_404(Sale, id=sale_id)
    return render(request, 'core/sale_detail.html', {'sale': sale})

# core/views.py

@login_required
@user_passes_test(lambda u: u.is_superuser)
def session_list_view(request):
    sessions = CashSession.objects.all().order_by('-start_time')
    return render(request, 'core/session_list.html', {'sessions': sessions})

@login_required
@user_passes_test(lambda u: u.is_superuser)
def audit_session_detail_view(request, session_id):
    session = get_object_or_404(CashSession, id=session_id)
    return render(request, 'core/audit_session_detail.html', {'session': session})

@login_required
def print_receipt_view(request, sale_id):
    """
    Affiche une vue simplifiée (format ticket) pour l'impression thermique.
    """
    sale = get_object_or_404(Sale, id=sale_id)
    
    # On récupère les items de la vente pour les lister sur le ticket
    items = sale.items.all() 
    
    context = {
        'sale': sale,
        'items': items,
        'company_name': "RBA SARL", # Nom de votre boutique
        'address': "Bamako, Mali",
        'phone': "+223 00 00 00 00",
    }
    
    return render(request, 'core/print_receipt.html', context)
from django.template.loader import render_to_string
# Note: Nécessite souvent une bibliothèque comme xhtml2pdf ou weasyprint
def export_sale_pdf(request, sale_id):
    sale = get_object_or_404(Sale, id=sale_id)
    # Logique d'export PDF ici...
    messages.info(request, "Fonctionnalité PDF en cours de configuration.")
    return redirect('sale_detail', sale_id=sale.id)

@login_required
def client_list_view(request):
    """
    Affiche la liste des clients et permet d'en chercher un.
    """
    query = request.GET.get('q')
    if query:
        clients = Client.objects.filter(name__icontains=query).order_by('name')
    else:
        clients = Client.objects.all().order_by('name')
        
    return render(request, 'core/client_list.html', {'clients': clients})

from django.http import JsonResponse
from decimal import Decimal

def update_line_discount(request, product_id, discount):
    cart = request.session.get('cart', {})
    
    if str(product_id) in cart:
        item = cart[str(product_id)]
        qty = Decimal(str(item['qty']))
        price = Decimal(str(item['price']))
        
        # Mise à jour de la remise et recalcul du sous-total
        item['line_discount'] = str(discount)
        new_subtotal = (price * qty) - Decimal(str(discount))
        item['subtotal'] = str(max(0, new_subtotal)) # Pas de prix négatif
        
        request.session['cart'] = cart
        
        # Recalcul du total général du panier
        total_cart = sum(Decimal(i['subtotal']) for i in cart.values())
        
        return JsonResponse({
            'success': True,
            'new_subtotal': f"{item['subtotal']}",
            'new_cart_total': f"{total_cart}"
        })
    
    return JsonResponse({'success': False})


@login_required
@user_passes_test(lambda u: u.is_superuser)
def valider_session_caisse(request, session_id):
    if request.method == 'POST':
        session = get_object_or_404(CashSession, id=session_id)
        session.status = 'V'  # On passe le statut à Validé (ou 'C' selon ton choix)
        session.save()
        messages.success(request, f"La session de {session.vendeur.username} a été validée et clôturée.")
    return redirect('dashboard') # Redirige vers ton dashboard

# Dans views.py
@login_required
@user_passes_test(est_patron)
def export_rapport_pdf(request):
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="RBA_Rapport_{date.today()}.pdf"'

    p = canvas.Canvas(response, pagesize=A4)
    
    # Titre principal
    p.setFont("Helvetica-Bold", 18)
    p.drawCentredString(300, 800, "LAFIA ELECTRONIQUE - BILAN JOURNALIER")
    
    # Détails de la période
    p.setFont("Helvetica", 12)
    p.drawString(50, 750, f"Généré le : {date.today().strftime('%d/%m/%Y à %H:%M')}")
    p.line(50, 740, 550, 740)

    # Section Finance
    p.setFont("Helvetica-Bold", 14)
    p.drawString(50, 700, "Indicateurs Clés :")
    
    p.setFont("Helvetica", 12)
    p.drawString(70, 675, f"- Chiffre d'Affaires total : {request.GET.get('ca')} FCFA")
    p.drawString(70, 655, f"- Bénéfice net estimé : {request.GET.get('benef')} FCFA")
    p.drawString(70, 635, f"- Valeur des pertes : {request.GET.get('pertes')} FCFA")

    p.showPage()
    p.save()
    return response