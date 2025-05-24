# Price Adjustment Security & Best Practices

## Overview
This document outlines the security measures implemented to ensure reliable price adjustment alerts while allowing user edits for receipt accuracy.

## The Challenge
We need to balance two competing needs:
1. **Accuracy**: Allow users to correct OCR errors and add missing sale information
2. **Trust**: Ensure price adjustment alerts are based on reliable data

## Security Measures Implemented

### 1. **Data Source Tracking**
Every price adjustment alert now tracks its source:
- `ocr_parsed`: Original OCR-parsed data (high trust)
- `user_edit`: User-modified data (lower trust)

### 2. **Conservative User Edit Policy**
For user-edited data, we require:
- **Explicit Sale Marking**: Only items explicitly marked "on sale" can trigger alerts
- **Reasonable Discounts**: Maximum 75% discount to prevent abuse
- **Higher Minimum Savings**: $2.00 vs $0.50 for OCR data
- **No Arbitrary Price Changes**: Can't just change any price to trigger alerts

### 3. **Validation Logic**
```python
# Only these user actions can create price adjustment alerts:
if item.on_sale and item.instant_savings:
    # User explicitly marked item as on sale
    if discount_percentage <= 75:
        # Reasonable discount range
        if price_difference >= 2.00:
            # Significant savings only
            create_alert()
```

### 4. **Audit Trail**
- All alerts include `data_source` field
- Detailed logging of alert creation
- Distinguish between OCR vs user-generated alerts

## Recommended Future Enhancements

### 1. **Multi-Source Verification**
```python
# Require multiple users to confirm same sale price
if similar_reports_count >= 2:
    create_alert()
```

### 2. **User Reputation System**
```python
# Weight alerts based on user history
user_accuracy_score = calculate_user_accuracy(user)
if user_accuracy_score > 0.8:
    lower_threshold = True
```

### 3. **External Verification**
```python
# Cross-reference with official Costco data
official_price = get_costco_api_price(item_code)
if abs(reported_price - official_price) < 0.50:
    high_confidence = True
```

### 4. **Community Moderation**
- Flag suspicious price changes for review
- Allow users to report incorrect alerts
- Implement voting system for disputed prices

## Current Implementation Benefits

✅ **Prevents Abuse**: Users can't arbitrarily change prices to create fake alerts  
✅ **Maintains Accuracy**: Users can still correct genuine OCR errors  
✅ **Transparency**: Clear tracking of data sources  
✅ **Conservative Approach**: Higher thresholds for user-edited data  
✅ **Audit Trail**: Full logging for troubleshooting  

## Risk Assessment

| Risk Level | Scenario | Mitigation |
|------------|----------|------------|
| **Low** | Honest user mistakes | Conservative thresholds, validation |
| **Medium** | Malicious fake sales | Explicit sale marking required |
| **High** | Coordinated abuse | Future: Multi-user verification |

## Best Practices for Users

1. **Use "On Sale" Toggle**: Only mark items actually on sale
2. **Enter Accurate Savings**: Use the actual discount amount
3. **Double-Check Item Codes**: Ensures proper matching across users
4. **Report Issues**: Help us identify and fix problematic alerts

This approach maintains the community benefit of crowdsourced price data while implementing appropriate safeguards against abuse and errors. 