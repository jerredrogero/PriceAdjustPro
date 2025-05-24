# Official Costco Promotions System

## Overview
The Official Promotions system allows administrators to upload and process Costco's monthly promotional booklets, creating **highly trusted** price adjustment alerts for all users.

## How It Works

### 1. **Admin Upload Process**
1. **Access Django Admin** → `Costco Promotions`
2. **Create New Promotion**:
   - Title: "January 2024 Member Deals"  
   - Sale Start/End Dates
   - Upload multiple booklet page images

3. **Process Promotion**:
   - Use admin action "Process selected promotions"
   - Or command line: `python manage.py process_promotions --promotion-id 1`

### 2. **Automated Processing**
The system automatically:
- ✅ Extracts sale items from each booklet page using AI
- ✅ Parses item codes, descriptions, prices, and rebate amounts
- ✅ Creates price adjustment alerts for matching user purchases
- ✅ Marks alerts as "Official" with high confidence

### 3. **User Experience**
Users see enhanced price adjustment alerts:
- 🏆 **Official Promotion**: Verified by Costco booklet
- 🏪 **Store Coverage**: "All Costco Locations" 
- 📅 **Sale Dates**: Clear start/end periods
- 💯 **High Confidence**: No validation needed

## Admin Interface Features

### **Costco Promotions**
- Upload promotional booklet images
- Set sale date ranges  
- Track processing status
- View extracted items and alerts created

### **Promotion Pages**
- Individual booklet page management
- Image previews
- Processing status and errors
- Extracted text viewing

### **Official Sale Items**
- All extracted sale items
- Regular vs sale prices
- Instant rebate amounts
- Number of alerts generated

## Command Line Tools

### **Process All Unprocessed Promotions**
```bash
python manage.py process_promotions --all-unprocessed
```

### **Process Only Active Promotions**
```bash
python manage.py process_promotions --all-unprocessed --active-only
```

### **Process Specific Promotion**
```bash
python manage.py process_promotions --promotion-id 1
```

### **View Status**
```bash
python manage.py process_promotions
```

## Data Quality & Trust Levels

### **Three-Tier Trust System**
1. **Official Promotions** (Highest Trust)
   - Source: Official Costco booklets
   - Confidence: High
   - Validation: None needed
   - Coverage: All warehouses

2. **OCR Parsed Receipts** (Medium Trust)  
   - Source: User receipt uploads
   - Confidence: Medium
   - Validation: Basic checks
   - Coverage: Specific warehouse

3. **User Edited Receipts** (Lower Trust)
   - Source: Manual user corrections
   - Confidence: Low
   - Validation: Strict requirements
   - Coverage: Specific warehouse

## Benefits

### **For Users**
- 💰 **Guaranteed Savings**: Official promotions are 100% accurate
- 🌍 **Universal Coverage**: Applies to all Costco locations
- ⚡ **Instant Alerts**: No waiting for other users to report sales
- 🔒 **Trusted Source**: No risk of fake or incorrect data

### **For Administrators**
- 📈 **Bulk Processing**: Handle entire promotional periods at once
- 🎯 **Targeted Alerts**: Only users who paid more get notified
- 📊 **Analytics**: Track items extracted and alerts created
- 🛡️ **Data Integrity**: Eliminates user manipulation concerns

## Example Workflow

1. **Monthly Routine**: Upload new Costco promotional booklet
2. **Processing**: Run `process_promotions --all-unprocessed --active-only`
3. **Results**: Hundreds of users automatically get legitimate price adjustment alerts
4. **Impact**: Users save money on items they recently purchased

## File Format Support
- **Images**: JPG, PNG, WebP
- **Processing**: AI-powered text extraction
- **Validation**: Automatic price and item code parsing

This system transforms the app from user-dependent to admin-curated, ensuring **reliable, official sale data** for all users while maintaining the community benefit of receipt sharing. 