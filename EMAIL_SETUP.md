# Email Setup for Password Reset

To enable password reset functionality, you need to configure the following environment variables:

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

You can test the password reset functionality by:
1. Going to `/reset-password` on your website
2. Entering an email address
3. Checking that the email is sent successfully

## Production Notes

- In production, make sure `DEBUG=False` in your environment
- The password reset emails will use HTTPS URLs in production
- Email timeout is set to 30 seconds
- Password reset tokens expire after 1 hour

## Troubleshooting

If emails aren't sending:
1. Verify your app-specific password is correct
2. Check that 2FA is enabled on your Apple ID
3. Ensure the email address in `EMAIL_HOST_USER` is valid
4. Check Django logs for email sending errors
5. **For cloud hosting**: iCloud often blocks cloud server IPs - use SendGrid or Gmail instead 