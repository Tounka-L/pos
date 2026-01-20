# core/urls.py
from django.urls import path
from . import views

urlpatterns = [
    # --- GESTION DES SESSIONS DE CAISSE ---
    path('caisse/ouvrir/', views.open_cash_session_view, name='open_cash_session'),
    path('caisse/fermer/', views.close_cash_session_view, name='close_cash_session'),
    path('caisse/liste_sessions/', views.session_list_view, name='session_list_view'),
    path('caisse/audit/<int:session_id>/', views.audit_session_detail_view, name='audit_session_detail_view'),

    # --- POINT DE VENTE (POS) ---
    path('pos/', views.pos_view, name='pos_view'), 
    path('pos/ajouter/<int:product_id>/', views.add_to_cart, name='add_to_cart'),
    path('pos/vider/', views.clear_cart, name='clear_cart'),
    path('cart/remove/<int:item_index>/', views.remove_from_cart, name='remove_from_cart'),
    path('cart/update-price/<int:item_index>/<str:new_price>/', views.update_cart_price, name='update_cart_price'),
    path('pos/valider/', views.checkout_sale_view, name='checkout_sale'),

    # --- VENTES & DOCUMENTS ---
    path('vente/<int:sale_id>/', views.sale_detail, name='sale_detail'),
    path('sale/<int:sale_id>/print/', views.print_receipt_view, name='print_receipt'),
    
   
    path('vente/retour/<int:item_id>/', views.process_partial_return, name='process_partial_return'),

    # --- GESTION DU STOCK ---
    path('stock/approvisionnement/', views.add_stock_view, name='add_stock'),
    path('stock/perte/', views.declarer_perte_view, name='declarer_perte'), 
    
    # --- ADMIN & CLIENTS ---
    path('dashboard/', views.dashboard_patron_view, name='dashboard'),
    path('clients/', views.client_list_view, name='client_list'),
    path('caisse/valider/<int:session_id>/', views.valider_session_caisse, name='valider_session_caisse'),
    path('sync-vente/', views.sync_vente, name='sync_vente'),
    path('rapport/pdf/', views.export_rapport_pdf, name='export_rapport_pdf'),
] # <--- On ferme bien la liste ici et c'est tout !