# ⚡ Quick Email Setup (5 Minutes)

## 🎯 What You Need

1. A Gmail account
2. 5 minutes

---

## 🚀 Steps

### 1. Get Gmail App Password

1. Go to: https://myaccount.google.com/apppasswords
2. If asked, enable 2-Step Verification first
3. Select: **Mail** → **Other (Custom name)** → Type: **DataShield**
4. Click **Generate**
5. **Copy the 16-character password** (looks like: `xxxx xxxx xxxx xxxx`)

### 2. Update .env File

Open `.env` and update these 3 lines:

```env
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=xxxx xxxx xxxx xxxx
EMAIL_FROM=your-email@gmail.com
```

**Replace with your actual Gmail and the app password you just generated.**

### 3. Restart Backend

```powershell
cd "C:\Users\karth\Downloads\Online foot print detection with OSINT integration\datashield-osint"
docker restart datashield_backend
```

### 4. Test It!

1. Go to http://localhost:3000
2. Click **Sign Up**
3. Register with **your real email**
4. Check your inbox for verification email
5. Click the verification link
6. Login!

---

## ✅ Done!

Your platform now sends real verification emails!

**See EMAIL_SETUP_GUIDE.md for detailed troubleshooting.**
