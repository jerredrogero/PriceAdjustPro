from django.urls import path
from . import views

# Split URL patterns into web and API
web_urlpatterns = [
    path('', views.receipt_list, name='receipt_list'),
    path('upload/', views.upload_receipt, name='upload_receipt'),
    path('receipt/<int:receipt_id>/', views.receipt_detail, name='receipt_detail'),
]

api_urlpatterns = [
    path('receipts/', views.api_receipt_list, name='api_receipt_list'),
    path('receipts/<int:receipt_id>/', views.api_receipt_detail, name='api_receipt_detail'),
    path('receipts/upload/', views.api_receipt_upload, name='api_receipt_upload'),
]

# Use web_urlpatterns by default
urlpatterns = web_urlpatterns

# Add API patterns if this is included under /api/
def urls_api():
    return api_urlpatterns 