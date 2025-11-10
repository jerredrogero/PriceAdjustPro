/**
 * iOS StoreKit 2 Manager for In-App Purchases
 * Handles subscription purchases, restoration, and status management
 */

// StoreKit 2 types and interfaces
declare global {
  interface Window {
    StoreKit?: {
      Product: {
        products(productIds: string[]): Promise<StoreKitProduct[]>;
      };
      Transaction: {
        currentEntitlements(): AsyncIterable<StoreKitTransaction>;
        updates(): AsyncIterable<StoreKitTransactionUpdate>;
        finish(transactionId: string): Promise<void>;
      };
      AppStore: {
        sync(): Promise<void>;
        showManageSubscriptions(): Promise<void>;
      };
    };
  }
}

export interface StoreKitProduct {
  id: string;
  displayName: string;
  description: string;
  price: number;
  displayPrice: string;
  type: 'autoRenewableSubscription' | 'nonRenewableSubscription' | 'consumable' | 'nonConsumable';
  subscription?: {
    subscriptionGroupID: string;
    subscriptionPeriod: {
      unit: 'day' | 'week' | 'month' | 'year';
      value: number;
    };
    introductoryOffer?: {
      type: 'freeTrial' | 'payAsYouGo' | 'payUpFront';
      period: {
        unit: 'day' | 'week' | 'month' | 'year';
        value: number;
      };
      price?: number;
      displayPrice?: string;
    };
  };
  purchase(): Promise<StoreKitPurchaseResult>;
}

export interface StoreKitTransaction {
  id: string;
  productID: string;
  appAccountToken?: string;
  purchaseDate: Date;
  originalPurchaseDate: Date;
  expirationDate?: Date;
  isUpgraded: boolean;
  revocationDate?: Date;
  revocationReason?: 'refundedDueToIssue' | 'refundedForOtherReason';
  webOrderLineItemID?: string;
  subscriptionGroupID?: string;
  originalTransactionID: string;
  environment: 'production' | 'sandbox';
}

export interface StoreKitTransactionUpdate {
  transaction: StoreKitTransaction;
  renewalInfo?: {
    currentProductID: string;
    willAutoRenew: boolean;
    expirationIntent?: 'canceled' | 'billingError' | 'didNotConsentToPriceIncrease' | 'productNotAvailable' | 'unknown';
  };
}

export interface StoreKitPurchaseResult {
  transaction?: StoreKitTransaction;
  userCancelled: boolean;
  pending: boolean;
  error?: {
    code: string;
    message: string;
  };
}

export interface SubscriptionStatus {
  isActive: boolean;
  productId: string | null;
  expirationDate: Date | null;
  willAutoRenew: boolean;
  isInGracePeriod: boolean;
  environment: 'production' | 'sandbox' | null;
}

class StoreKitManager {
  private static instance: StoreKitManager;
  private products: StoreKitProduct[] = [];
  private subscriptionStatus: SubscriptionStatus = {
    isActive: false,
    productId: null,
    expirationDate: null,
    willAutoRenew: false,
    isInGracePeriod: false,
    environment: null
  };
  private listeners: ((status: SubscriptionStatus) => void)[] = [];

  // Product IDs - these should match your App Store Connect configuration
  public static readonly PRODUCT_IDS = {
    MONTHLY: 'com.priceadjustpro.monthly',
    YEARLY: 'com.priceadjustpro.yearly'
  };

  private constructor() {
    this.initializeTransactionListener();
  }

  public static getInstance(): StoreKitManager {
    if (!StoreKitManager.instance) {
      StoreKitManager.instance = new StoreKitManager();
    }
    return StoreKitManager.instance;
  }

  /**
   * Check if StoreKit is available (iOS environment)
   */
  public isAvailable(): boolean {
    return typeof window !== 'undefined' && !!window.StoreKit;
  }

  /**
   * Initialize the StoreKit manager
   */
  public async initialize(): Promise<void> {
    if (!this.isAvailable()) {
      throw new Error('StoreKit is not available');
    }

    try {
      // Load products
      await this.loadProducts();
      
      // Check current subscription status
      await this.updateSubscriptionStatus();
      
      // Sync with App Store
      await window.StoreKit!.AppStore.sync();
      
      console.log('StoreKit Manager initialized successfully');
    } catch (error) {
      console.error('Failed to initialize StoreKit Manager:', error);
      throw error;
    }
  }

  /**
   * Load available products from the App Store
   */
  private async loadProducts(): Promise<void> {
    if (!this.isAvailable()) return;

    try {
      const productIds = Object.values(StoreKitManager.PRODUCT_IDS);
      this.products = await window.StoreKit!.Product.products(productIds);
      console.log('Loaded products:', this.products);
    } catch (error) {
      console.error('Failed to load products:', error);
      throw error;
    }
  }

  /**
   * Get available subscription products
   */
  public getProducts(): StoreKitProduct[] {
    return this.products;
  }

  /**
   * Get product by ID
   */
  public getProduct(productId: string): StoreKitProduct | undefined {
    return this.products.find(product => product.id === productId);
  }

  /**
   * Purchase a subscription product
   */
  public async purchaseProduct(productId: string, appAccountToken?: string): Promise<StoreKitPurchaseResult> {
    const product = this.getProduct(productId);
    if (!product) {
      throw new Error(`Product not found: ${productId}`);
    }

    try {
      // Set app account token if provided (for linking to your backend user)
      if (appAccountToken) {
        // This would be set before purchase in a real implementation
        console.log('App account token:', appAccountToken);
      }

      const result = await product.purchase();
      
      if (result.transaction && !result.userCancelled && !result.pending) {
        // Purchase successful, update subscription status
        await this.updateSubscriptionStatus();
        
        // Notify backend of the purchase
        await this.notifyBackendOfPurchase(result.transaction);
      }

      return result;
    } catch (error) {
      console.error('Purchase failed:', error);
      throw error;
    }
  }

  /**
   * Restore previous purchases
   */
  public async restorePurchases(): Promise<void> {
    if (!this.isAvailable()) return;

    try {
      await window.StoreKit!.AppStore.sync();
      await this.updateSubscriptionStatus();
    } catch (error) {
      console.error('Failed to restore purchases:', error);
      throw error;
    }
  }

  /**
   * Show manage subscriptions page
   */
  public async showManageSubscriptions(): Promise<void> {
    if (!this.isAvailable()) return;

    try {
      await window.StoreKit!.AppStore.showManageSubscriptions();
    } catch (error) {
      console.error('Failed to show manage subscriptions:', error);
      throw error;
    }
  }

  /**
   * Get current subscription status
   */
  public getSubscriptionStatus(): SubscriptionStatus {
    return { ...this.subscriptionStatus };
  }

  /**
   * Add listener for subscription status changes
   */
  public addStatusListener(listener: (status: SubscriptionStatus) => void): () => void {
    this.listeners.push(listener);
    return () => {
      const index = this.listeners.indexOf(listener);
      if (index > -1) {
        this.listeners.splice(index, 1);
      }
    };
  }

  /**
   * Update subscription status by checking current entitlements
   */
  private async updateSubscriptionStatus(): Promise<void> {
    if (!this.isAvailable()) return;

    try {
      let activeSubscription: StoreKitTransaction | null = null;
      let latestTransaction: StoreKitTransaction | null = null;

      // Check all current entitlements
      for await (const transaction of window.StoreKit!.Transaction.currentEntitlements()) {
        // Find the most recent subscription transaction
        if (!latestTransaction || transaction.purchaseDate > latestTransaction.purchaseDate) {
          latestTransaction = transaction;
        }

        // Check if this subscription is currently active
        const now = new Date();
        if (transaction.expirationDate && transaction.expirationDate > now && !transaction.revocationDate) {
          activeSubscription = transaction;
        }
      }

      // Update subscription status
      if (activeSubscription) {
        this.subscriptionStatus = {
          isActive: true,
          productId: activeSubscription.productID,
          expirationDate: activeSubscription.expirationDate!,
          willAutoRenew: true, // This would need to be checked from renewal info
          isInGracePeriod: false, // This would need additional logic
          environment: activeSubscription.environment
        };
      } else {
        this.subscriptionStatus = {
          isActive: false,
          productId: latestTransaction?.productID || null,
          expirationDate: latestTransaction?.expirationDate || null,
          willAutoRenew: false,
          isInGracePeriod: false,
          environment: latestTransaction?.environment || null
        };
      }

      // Notify listeners
      this.notifyStatusListeners();

    } catch (error) {
      console.error('Failed to update subscription status:', error);
    }
  }

  /**
   * Initialize transaction listener for automatic updates
   */
  private async initializeTransactionListener(): Promise<void> {
    if (!this.isAvailable()) return;

    try {
      // Listen for transaction updates
      for await (const update of window.StoreKit!.Transaction.updates()) {
        console.log('Transaction update received:', update);
        
        // Finish the transaction
        await window.StoreKit!.Transaction.finish(update.transaction.id);
        
        // Update subscription status
        await this.updateSubscriptionStatus();
        
        // Notify backend
        await this.notifyBackendOfPurchase(update.transaction);
      }
    } catch (error) {
      console.error('Transaction listener error:', error);
    }
  }

  /**
   * Notify backend of purchase/transaction
   */
  private async notifyBackendOfPurchase(transaction: StoreKitTransaction): Promise<void> {
    try {
      // This would send the transaction to your backend for receipt validation
      const response = await fetch('/api/subscriptions/ios-purchase/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          transactionId: transaction.id,
          originalTransactionId: transaction.originalTransactionID,
          productId: transaction.productID,
          purchaseDate: transaction.purchaseDate.toISOString(),
          expirationDate: transaction.expirationDate?.toISOString(),
          environment: transaction.environment,
          appAccountToken: transaction.appAccountToken
        })
      });

      if (!response.ok) {
        throw new Error(`Backend notification failed: ${response.status}`);
      }

      console.log('Backend notified of purchase successfully');
    } catch (error) {
      console.error('Failed to notify backend of purchase:', error);
      // Don't throw here - the purchase was successful even if backend notification failed
    }
  }

  /**
   * Notify all status listeners
   */
  private notifyStatusListeners(): void {
    const status = this.getSubscriptionStatus();
    this.listeners.forEach(listener => {
      try {
        listener(status);
      } catch (error) {
        console.error('Status listener error:', error);
      }
    });
  }
}

export default StoreKitManager;

