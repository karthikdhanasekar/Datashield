# 📧 Email Setup Guide for DataShield OSINT

This guide will help you configure real email verification for user registration and login.

---

## 🎯 Overview

DataShield OSINT uses email verification to:
- ✅ Confirm user email addresses during registration
- 🔐 Enable password reset functionality
- 🔔 Send security notifications

---

## 📝 Step 1: Choose Your Email Provider

### Option A: Gmail (Recommended for Testing)

**Pros**: Free, easy setup, reliable  
**Cons**: Daily sending limits (500 emails/day)

### Option B: SendGrid

**Pros**: Professional, high limits, analytics  
**Cons**: Requires verification, paid plans for higher volumes

### Option C: AWS SES

**Pros**: Scalable, cheap, reliable  
**Cons**: More complex setup

### Option D: Other SMTP Providers

Works with any SMTP provider: Mailgun, Postmark, Outlook, etc.

---

## 🔧 Step 2: Configure Gmail (Easiest Method)

### A. Enable 2-Factor Authentication

1. Go to [Google Account Settings](https://myaccount.google.com/)
2. Click **Security** in left sidebar
3. Enable **2-Step Verification** if not already enabled

### B. Generate App Password

1. Go to [App Passwords](https://myaccount.google.com/apppasswords)
2. Select app: **Mail**
3. Select device: **Other (Custom name)**
4. Enter: **DataShield OSINT**
5. Click **Generate**
6. **Copy the 16-character password** (format: xxxx xxxx xxxx xxxx)

### C. Update .env File

Open your `.env` file and update these lines:

```env
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=xxxx xxxx xxxx xxxx
EMAIL_FROM=your-email@gmail.com
EMAIL_FROM_NAME=DataShield OSINT
FRONTEND_URL=http://localhost:3000
```

**Replace:**
- `your-email@gmail.com` → Your actual Gmail address
- `xxxx xxxx xxxx xxxx` → The app password you just generated

---

## 🚀 Step 3: Test Email Configuration

### A. Restart Backend

```powershell
cd "C:\Users\karth\Downloads\Online foot print detection with OSINT integration\datashield-osint"
docker restart datashield_backend
```

### B. Test Registration

1. Open http://localhost:3000
2. Click **"Sign Up"** or **"Create Account"**
3. Fill in registration form with a **real email address**
4. Click **"Register"**
5. Check your email inbox for verification link

### C. Verify Email Functionality

You should receive an email with:
- Subject: "✅ Verify your DataShield OSINT account"
- A verification button/link
- Expires in 24 hours

### D. Complete Verification

1. Click the verification link in email
2. You'll be redirected to the login page
3. Login with your credentials
4. ✅ Success!

---

## 🔍 Troubleshooting

### Issue: Email Not Received

**Check 1: Spam Folder**
- Verification emails might land in spam
- Mark as "Not Spam" for future emails

**Check 2: Backend Logs**
```powershell
docker logs datashield_backend --tail=50 | Select-String "Email"
```

Look for:
- ✅ `Email sent` → Success
- ❌ `Email send failed` → Check credentials

**Check 3: Gmail App Password**
- Make sure you copied the app password correctly
- No spaces between characters
- Must be 16 characters long

**Check 4: Correct Email in .env**
```powershell
# Verify your settings
Get-Content .env | Select-String "SMTP"
```

### Issue: "Authentication Failed" Error

**Solution**: Check SMTP credentials
```env
# Make sure these match your Gmail account
SMTP_USERNAME=your-email@gmail.com  # Must match your Gmail
SMTP_PASSWORD=xxxx xxxx xxxx xxxx   # Must be app password (not your Gmail password!)
EMAIL_FROM=your-email@gmail.com     # Must match SMTP_USERNAME
```

### Issue: "Email not configured" in Logs

**Solution**: Make sure `.env` has all required fields:
```env
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password
EMAIL_FROM=your-email@gmail.com
EMAIL_FROM_NAME=DataShield OSINT
```

Then restart backend:
```powershell
docker restart datashield_backend
```

---

## 📋 Alternative Providers

### SendGrid Setup

1. Sign up at [SendGrid.com](https://sendgrid.com)
2. Verify your sender email
3. Create an API key
4. Update `.env`:

```env
SMTP_HOST=smtp.sendgrid.net
SMTP_PORT=587
SMTP_USERNAME=apikey
SMTP_PASSWORD=your-sendgrid-api-key
EMAIL_FROM=verified-email@yourdomain.com
EMAIL_FROM_NAME=DataShield OSINT
```

### AWS SES Setup

1. Sign up for [AWS SES](https://aws.amazon.com/ses/)
2. Verify your email/domain
3. Create SMTP credentials
4. Update `.env`:

```env
SMTP_HOST=email-smtp.us-east-1.amazonaws.com
SMTP_PORT=587
SMTP_USERNAME=your-aws-smtp-username
SMTP_PASSWORD=your-aws-smtp-password
EMAIL_FROM=verified-email@yourdomain.com
EMAIL_FROM_NAME=DataShield OSINT
```

---

## 🎨 Customizing Email Templates

Email templates are in: `backend/app/services/notification_service.py`

### Verification Email

Edit the `send_verification_email()` function to customize:
- Email subject
- HTML template
- Brand colors
- Logo (add `<img>` tag)

### Password Reset Email

Edit the `send_password_reset_email()` function to customize.

---

## 📊 Testing Script

Create this file to test email: `test_email.py`

```python
import asyncio
import sys
sys.path.insert(0, '/app')

from app.services.notification_service import send_verification_email

async def test():
    result = await send_verification_email(
        email="your-test-email@gmail.com",
        name="Test User",
        token="test-token-123"
    )
    print(f"Email sent: {result}")

asyncio.run(test())
```

Run it:
```powershell
docker exec -e PYTHONPATH=/app datashield_backend python /app/test_email.py
```

---

## ✅ Verification Checklist

- [ ] Gmail 2FA enabled
- [ ] App password generated
- [ ] `.env` file updated with correct credentials
- [ ] Backend restarted
- [ ] Test registration completed
- [ ] Verification email received
- [ ] Email verification link works
- [ ] Can login after verification

---

## 🔒 Security Best Practices

1. **Never commit `.env` to git**
   - Already in `.gitignore`
   - Contains sensitive credentials

2. **Use environment-specific configs**
   - Development: `.env`
   - Production: `.env.production`

3. **Rotate app passwords regularly**
   - Generate new app password every 3-6 months

4. **Monitor email sending**
   - Check for unusual activity
   - Set up alerts for failed sends

5. **Use dedicated email account**
   - Don't use your personal Gmail
   - Create `noreply@yourdomain.com` for production

---

## 📞 Need Help?

- **Gmail App Passwords**: https://support.google.com/accounts/answer/185833
- **SendGrid Docs**: https://docs.sendgrid.com/
- **AWS SES Docs**: https://docs.aws.amazon.com/ses/

---

## 🎉 You're All Set!

Once configured, your users will:
1. Register with their real email
2. Receive verification email
3. Click verification link
4. Login successfully

The platform now has **real email verification** enabled! 🚀
