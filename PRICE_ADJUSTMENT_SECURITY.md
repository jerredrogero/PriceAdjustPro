# Price Adjustment Security & Best Practices

## Overview
This document outlines the security measures implemented to ensure reliable price adjustment alerts while allowing user edits for receipt accuracy.

## The Current System
We provide price adjustment alerts from two trusted sources:
1. **Official Costco Promotions**: Highly trusted data from official promotional booklets
2. **User's Own Receipts**: User can compare their own purchase history for price adjustments

## Security Measures Implemented

### 1. **Data Source Tracking**
Every price adjustment alert now tracks its source:
- `user_edit`: User comparing their own receipts (high trust)
- `official_promo`: Official Costco promotions (highest trust)

### 2. **Conservative User Edit Policy**
For user-edited data comparing their own receipts, we require:
- **Explicit Sale Marking**: Only items explicitly marked "on sale" can trigger alerts
- **Reasonable Discounts**: Maximum 75% discount to prevent abuse
- **Higher Minimum Savings**: $2.00 vs $0.50 for official promotions
- **Own Receipts Only**: Users can only compare their own purchase history

### 3. **Validation Logic**
```python
# Only these user actions can create price adjustment alerts:
if item.on_sale and item.instant_savings:
    # User explicitly marked item as on sale in their own receipt
    if discount_percentage <= 75:
        # Reasonable discount range
        if price_difference >= 2.00:
            # Significant savings only
            create_alert()
```

### 4. **Audit Trail**
- All alerts include `data_source` field
- Detailed logging of alert creation
- Distinguish between official promotions vs user receipt comparisons

## Current Implementation Benefits

✅ **Prevents Abuse**: Users can only compare their own receipts
✅ **Maintains Accuracy**: Users can still correct genuine OCR errors  
✅ **Transparency**: Clear tracking of data sources  
✅ **Conservative Approach**: Higher thresholds for user-edited data  
✅ **Audit Trail**: Full logging for troubleshooting  
✅ **Official Priority**: Official promotions have highest trust and lowest thresholds

## Risk Assessment

| Risk Level | Scenario | Mitigation |
|------------|----------|------------|
| **Low** | Honest user mistakes | Conservative thresholds, validation |
| **Low** | User manipulating own data | Only affects their own alerts |
| **Very Low** | Official promotion errors | Sourced directly from Costco booklets |

## Best Practices for Users

1. **Use "On Sale" Toggle**: Only mark items actually on sale in your own receipts
2. **Enter Accurate Savings**: Use the actual discount amount you received
3. **Double-Check Item Codes**: Ensures proper matching across your receipts
4. **Report Issues**: Help us identify and fix problematic alerts

This approach maintains reliable price adjustment alerts while implementing appropriate safeguards against abuse and errors. 