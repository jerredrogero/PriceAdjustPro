/**
 * Platform Detection Utilities
 * Determines the current platform and payment method to use
 */

export interface PlatformInfo {
  isIOS: boolean;
  isAndroid: boolean;
  isWeb: boolean;
  isMobile: boolean;
  isInApp: boolean;
  userAgent: string;
  shouldUseIAP: boolean;
  shouldUseStripe: boolean;
}

class PlatformDetection {
  private static cachedInfo: PlatformInfo | null = null;

  /**
   * Get comprehensive platform information
   */
  public static getPlatformInfo(): PlatformInfo {
    if (this.cachedInfo) {
      return this.cachedInfo;
    }

    const userAgent = navigator.userAgent || '';
    const isIOS = this.isIOSDevice();
    const isAndroid = this.isAndroidDevice();
    const isWeb = !isIOS && !isAndroid;
    const isMobile = isIOS || isAndroid;
    const isInApp = this.isInAppBrowser();

    // Determine payment method
    const shouldUseIAP = isIOS && isInApp && this.hasStoreKitSupport();
    const shouldUseStripe = !shouldUseIAP;

    this.cachedInfo = {
      isIOS,
      isAndroid,
      isWeb,
      isMobile,
      isInApp,
      userAgent,
      shouldUseIAP,
      shouldUseStripe
    };

    return this.cachedInfo;
  }

  /**
   * Check if device is iOS
   */
  public static isIOSDevice(): boolean {
    if (typeof window === 'undefined') return false;
    
    const userAgent = navigator.userAgent;
    return /iPad|iPhone|iPod/.test(userAgent) || 
           (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1); // iPad on iOS 13+
  }

  /**
   * Check if device is Android
   */
  public static isAndroidDevice(): boolean {
    if (typeof window === 'undefined') return false;
    
    return /Android/.test(navigator.userAgent);
  }

  /**
   * Check if running in an in-app browser (iOS app)
   */
  public static isInAppBrowser(): boolean {
    if (typeof window === 'undefined') return false;
    
    const userAgent = navigator.userAgent;
    
    // Check for common in-app browser indicators
    const inAppIndicators = [
      'PriceAdjustPro', // Your app's user agent
      'WebKit', // iOS WebKit
      'Mobile', // Mobile indicator
    ];

    // Check for web browser indicators (these suggest NOT in-app)
    const webBrowserIndicators = [
      'Safari', // Safari browser
      'Chrome', // Chrome browser
      'Firefox', // Firefox browser
      'Edge', // Edge browser
    ];

    // If we detect web browser indicators, likely not in-app
    if (webBrowserIndicators.some(indicator => userAgent.includes(indicator))) {
      // However, some in-app browsers still include these, so check for more specific indicators
      return userAgent.includes('PriceAdjustPro') || 
             (this.isIOSDevice() && !userAgent.includes('Version/')); // iOS Safari includes Version/
    }

    // Default to in-app if on mobile and no clear web browser indicators
    return this.isIOSDevice() || this.isAndroidDevice();
  }

  /**
   * Check if StoreKit is available (iOS IAP support)
   */
  public static hasStoreKitSupport(): boolean {
    if (typeof window === 'undefined') return false;
    
    return !!(window as any).StoreKit;
  }

  /**
   * Check if Google Play Billing is available (Android IAP support)
   */
  public static hasPlayBillingSupport(): boolean {
    if (typeof window === 'undefined') return false;
    
    return !!(window as any).PlayBilling;
  }

  /**
   * Get recommended payment method
   */
  public static getRecommendedPaymentMethod(): 'ios_iap' | 'android_iap' | 'stripe' {
    const info = this.getPlatformInfo();
    
    if (info.isIOS && info.isInApp && this.hasStoreKitSupport()) {
      return 'ios_iap';
    } else if (info.isAndroid && info.isInApp && this.hasPlayBillingSupport()) {
      return 'android_iap';
    } else {
      return 'stripe';
    }
  }

  /**
   * Check if current environment requires IAP (App Store guidelines compliance)
   */
  public static requiresIAP(): boolean {
    const info = this.getPlatformInfo();
    return info.isIOS && info.isInApp;
  }

  /**
   * Get user-friendly platform name
   */
  public static getPlatformName(): string {
    const info = this.getPlatformInfo();
    
    if (info.isIOS) {
      return info.isInApp ? 'iOS App' : 'iOS Safari';
    } else if (info.isAndroid) {
      return info.isInApp ? 'Android App' : 'Android Browser';
    } else {
      return 'Web Browser';
    }
  }

  /**
   * Clear cached platform info (useful for testing)
   */
  public static clearCache(): void {
    this.cachedInfo = null;
  }

  /**
   * Log platform information for debugging
   */
  public static logPlatformInfo(): void {
    const info = this.getPlatformInfo();
    console.log('Platform Detection Info:', {
      platform: this.getPlatformName(),
      paymentMethod: this.getRecommendedPaymentMethod(),
      requiresIAP: this.requiresIAP(),
      hasStoreKit: this.hasStoreKitSupport(),
      hasPlayBilling: this.hasPlayBillingSupport(),
      ...info
    });
  }
}

export default PlatformDetection;

