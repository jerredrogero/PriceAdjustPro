# Official Promotions Processing Guide

This system processes **official** Costco promotional booklets, creating **highly trusted** price adjustment alerts for users based on their purchase history.

## How It Works

1. **Upload**: Admin uploads promotional booklet pages as images
2. **OCR**: System extracts text from each page using advanced AI
3. **Parse**: Text is analyzed to find item codes, prices, and sale types
4. **Process**: Official sale items are saved to database
5. **Alerts**: System compares with user purchase history to create alerts

### Key Benefits

- ✅ **100% Official Data**: Direct from Costco promotional materials
- ✅ **High Trust Level**: No user-generated pricing data
- ✅ **Automatic Processing**: AI extracts structured data from images
- ✅ **Smart Matching**: Finds users who bought items before they went on sale
- ✅ **Creates price adjustment alerts for matching user purchases**
- ✅ **Respects 30-day adjustment policy**

## What Users See

Users see enhanced price adjustment alerts:
- **Official Promotion Source**: Clear indication this is from Costco
- **Promotion Details**: Sale price, regular price, discount amount
- **Validity Period**: When the promotion starts/ends
- **Action Items**: Clear instructions on how to get the adjustment

## Alert Creation Process

When a promotion is processed:

1. **Find Eligible Users**: Look for users who bought the item in the last 30 days
2. **Price Comparison**: Check if they paid more than the current sale price
3. **Validate Savings**: Only create alerts for meaningful savings ($0.50+)
4. **Skip Existing Sales**: Don't alert users who already bought on sale
5. **Create Alerts**: Generate official promotion alerts

## Processing Status

Each promotion tracks:
- **Processing Date**: When it was parsed
- **Success Status**: Whether parsing completed successfully
- **Error Details**: Any issues encountered during processing
- **Alert Count**: Number of price alerts generated

## Example Workflow

1. **Admin uploads January 2024 Member Deals booklet** (10 pages)
2. **System processes all pages automatically**
3. **Finds 150 sale items with valid item codes**
4. **Matches against user purchase history**
5. **Results**: Hundreds of users automatically get legitimate price adjustment alerts**

This creates a highly reliable, abuse-resistant system for price adjustment notifications based entirely on official Costco promotional data. 