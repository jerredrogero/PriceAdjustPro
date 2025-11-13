# Email Setup for Password Reset and Email Verification

This project uses email for two main features:
1. **Email Verification**: New users must verify their email address before logging in
2. **Password Reset**: Users can reset their passwords via email

To enable these features, you need to configure the following environment variables:

## For Production (Recommended): Use SendGrid

1. **Sign up for SendGrid** at https://sendgrid.com (free tier available)
2. **Create an API key** in SendGrid dashboard
3. **Add these environment variables to Render:**
   ```bash
   EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
   EMAIL_HOST=smtp.sendgrid.net
   EMAIL_PORT=587
   EMAIL_USE_TLS=True
   EMAIL_HOST_USER=apikey
   EMAIL_HOST_PASSWORD=your-sendgrid-api-key
   ```

## Alternative: Use Gmail with App Password

1. **Enable 2FA** on your Gmail account
2. **Create an app-specific password**
3. **Use these settings:**
   ```bash
   EMAIL_HOST=smtp.gmail.com
   EMAIL_PORT=587
   EMAIL_USE_TLS=True
   EMAIL_HOST_USER=your-gmail@gmail.com
   EMAIL_HOST_PASSWORD=your-app-specific-password
   ```

## For Development: iCloud Email

Add these to your `.env` file:

```bash
# Email configuration for password reset
EMAIL_HOST_USER=noreply@priceadjustpro.com
EMAIL_HOST_PASSWORD=bocx-nvcy-wgss-cbsp
```

## Setting Up iCloud Email

1. **Create an App-Specific Password for iCloud:**
   - Go to [appleid.apple.com](https://appleid.apple.com)
   - Sign in with your Apple ID
   - Navigate to "Security" section
   - Under "App-Specific Passwords", click "Generate Password"
   - Enter a label like "PriceAdjustPro Email"
   - Copy the generated password (it will look like: `abcd-efgh-ijkl-mnop`)

2. **Configure your email domain:**
   - Make sure your domain `priceadjustpro` is set up to use iCloud email
   - Or update the `EMAIL_HOST_USER` to use your actual iCloud email address

3. **Update environment variables:**
   ```bash
   EMAIL_HOST_USER=noreply@priceadjustpro  # or your iCloud email
   EMAIL_HOST_PASSWORD=abcd-efgh-ijkl-mnop  # your app-specific password
   ```

## Testing

### Email Verification
1. Register a new account at `/register`
2. Check that you're redirected to the verification pending page
3. Check your email for the verification link
4. Click the verification link
5. Try to log in - you should be able to access the dashboard

### Password Reset
1. Go to `/reset-password` on your website
2. Enter an email address
3. Check that the email is sent successfully
4. Click the reset link and set a new password

## Production Notes

- In production, make sure `DEBUG=False` in your environment
- Emails will use HTTPS URLs in production
- Email timeout is set to 30 seconds
- Password reset tokens expire after 1 hour
- Email verification tokens expire after 24 hours
- Users cannot log in until they verify their email address

## Troubleshooting

If emails aren't sending:
1. Verify your app-specific password is correct
2. Check that 2FA is enabled on your Apple ID
3. Ensure the email address in `EMAIL_HOST_USER` is valid
4. Check Django logs for email sending errors
5. **For cloud hosting**: iCloud often blocks cloud server IPs - use SendGrid or Gmail instead 