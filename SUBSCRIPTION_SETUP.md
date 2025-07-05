# Subscription Setup Guide

## 🚀 What Was Implemented

### Backend (Django)
- **Subscription Models**: SubscriptionProduct, UserSubscription, SubscriptionEvent
- **API Endpoints**: Complete subscription management API
- **Admin Interface**: Full admin panels for subscription management
- **Database Migration**: Successfully applied migration 0012

### Frontend (React)
- **Subscription Page**: `/subscription` - Complete subscription upgrade interface
- **Stripe Integration**: Card payment processing with Stripe Elements
- **Navigation**: Added "Upgrade" button with Crown icon
- **Responsive Design**: Mobile-friendly subscription interface

## 🔧 Next Steps Required

### 1. Get Stripe Price IDs
You need to get the actual price IDs from your Stripe Dashboard:

1. Go to **Stripe Dashboard → Products**
2. Find your monthly product (`prod_ScaEJwnoEX6k5a`)
3. Copy the **Price ID** (starts with `price_`)
4. Find your yearly product (`prod_ScaGa23kaHXo9w`)
5. Copy the **Price ID** (starts with `price_`)

### 2. Update Environment Variables
Add these to your `.env` file:

```bash
# Stripe Configuration
STRIPE_PUBLISHABLE_KEY=pk_live_your_publishable_key_here
STRIPE_SECRET_KEY=sk_live_your_secret_key_here
STRIPE_WEBHOOK_SECRET=whsec_your_webhook_secret_here
```

### 3. Update Subscription Products with Correct Price IDs

Run this command with the correct price IDs:

```bash
python manage.py shell
```

Then in the shell:
```python
from receipt_parser.models import SubscriptionProduct

# Update monthly product
monthly = SubscriptionProduct.objects.get(stripe_product_id='prod_ScaEJwnoEX6k5a')
monthly.stripe_price_id = 'price_YOUR_ACTUAL_MONTHLY_PRICE_ID'
monthly.save()

# Update yearly product  
yearly = SubscriptionProduct.objects.get(stripe_product_id='prod_ScaGa23kaHXo9w')
yearly.stripe_price_id = 'price_YOUR_ACTUAL_YEARLY_PRICE_ID'
yearly.save()

print("Price IDs updated successfully!")
```

### 4. Install Frontend Dependencies

```bash
cd frontend
npm install
```

This will install the new Stripe dependencies:
- `@stripe/stripe-js`
- `@stripe/react-stripe-js`

### 5. Set Up Stripe Webhooks

1. Go to **Stripe Dashboard → Webhooks**
2. Create new webhook endpoint: `https://yourdomain.com/api/subscriptions/webhook/`
3. Select these events:
   - `customer.subscription.created`
   - `customer.subscription.updated`
   - `customer.subscription.deleted`
   - `invoice.payment_succeeded`
   - `invoice.payment_failed`
4. Copy the webhook signing secret and add to your environment variables

### 6. Test the Subscription Flow

1. Start your development server
2. Navigate to `/subscription`
3. Test the subscription process with Stripe test cards

## 🎯 Features Available

### For Users
- **Subscription Plans**: Monthly ($1.99) and Yearly ($19.99) options
- **Secure Payments**: Stripe-powered card processing
- **Subscription Management**: Cancel, reactivate, view status
- **Premium Features Display**: Clear value proposition

### For Admin
- **Subscription Management**: View all user subscriptions
- **Product Management**: Manage subscription plans
- **Webhook Monitoring**: Track Stripe events
- **CSV Export**: Export subscription data

## 🔒 Security Notes

- Live Stripe keys are configured in the code
- Webhook signature verification is implemented
- CSRF protection on all API endpoints
- Secure payment method handling

## 📱 Mobile Ready

The subscription interface is fully responsive and works great on mobile devices, matching your iOS app experience.

---

**Important**: Remember to test thoroughly in Stripe's test mode before going live with production keys! 