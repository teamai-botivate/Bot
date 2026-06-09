# Quick Render Deployment Setup

## 🚀 Quick Start (5 minutes)

### 1. Create Backend Service
1. Go to https://dashboard.render.com
2. Click **"New +"** → **"Web Service"**
3. Select your repo: `teamai-botivate/Bot`
4. Fill in:
   - **Name**: `botivate-backend`
   - **Environment**: Python 3.10
   - **Region**: Singapore (closest to you)
   - **Build Command**: `pip install -r backend/requirements.txt`
   - **Start Command**: `cd backend && uvicorn app.main:app --host 0.0.0.0 --port $PORT`

5. Click **"Advanced"** and add these env vars:
   ```
   DATABASE_URI=postgresql://postgres.vaaafjsdlopppabuquaz:teamai-botivate%402025@aws-1-ap-northeast-1.pooler.supabase.com:6543/postgres
   OPENAI_API_KEY=sk-proj-...your-key-here...
   LLM_MODEL=gpt-4o
   FAST_LLM_MODEL=gpt-4o-mini
   LLM_TEMPERATURE=0
   ALLOWED_ORIGINS=*
   ENABLE_SUPABASE=true
   ```

6. Click **"Create Web Service"**
7. Wait for deployment (2-5 minutes)
8. Note the URL: `https://botivate-backend.onrender.com`

### 2. Create Frontend Service
1. In Render dashboard, click **"New +"** → **"Static Site"**
2. Select same repo: `teamai-botivate/Bot`
3. Fill in:
   - **Name**: `botivate-frontend`
   - **Publish directory**: `frontend`
   - **Build Command**: `echo "Static site"`

4. Click **"Create Static Site"**
5. Wait for deployment
6. Your site is live at: `https://botivate-frontend.onrender.com`

## ✅ Verification Checklist

- [ ] Backend service is running (check green status in Render)
- [ ] Frontend service is running (check green status in Render)
- [ ] Can access backend health check: `https://botivate-backend.onrender.com/health`
- [ ] Frontend loads: `https://botivate-frontend.onrender.com`
- [ ] Can send test message and get response
- [ ] Check browser console for any CORS errors

## 🔍 Testing Connection

### From Frontend
Open browser DevTools (F12) and run:
```javascript
testBackendConnection()
```

### From Terminal
```bash
curl https://botivate-backend.onrender.com/health
```

Expected response:
```json
{"status": "ok"}
```

## 📊 Monitor Logs

1. Go to your service in Render dashboard
2. Click **"Logs"** tab
3. Look for:
   - `✅ Botivate AI agent compiled and ready` (startup success)
   - `[LATENCY]` entries (request performance)
   - Error messages if any

## 🚨 Troubleshooting

| Issue | Solution |
|-------|----------|
| Backend won't start | Check env vars, especially `DATABASE_URI` |
| Frontend can't reach backend | Ensure `ALLOWED_ORIGINS=*` on backend |
| Database connection error | Verify Supabase credentials, check IP whitelist |
| 502 Bad Gateway | Check backend logs, may be Python error |
| Slow responses | Check `/health` endpoint, may be cold start |

## 📝 Environment Variables

| Variable | Example | Required |
|----------|---------|----------|
| `DATABASE_URI` | `postgresql://...` | Yes |
| `OPENAI_API_KEY` | `sk-proj-...` | Yes |
| `LLM_MODEL` | `gpt-4o` | No (default: gpt-4o) |
| `FAST_LLM_MODEL` | `gpt-4o-mini` | No (default: gpt-4o-mini) |
| `LLM_TEMPERATURE` | `0` | No (default: 0) |
| `ALLOWED_ORIGINS` | `*` | No (default: *) |
| `ENABLE_SUPABASE` | `true` | No (default: true) |

## 🔄 How Frontend-Backend Communication Works

```
User opens https://botivate-frontend.onrender.com
    ↓
Frontend loads, detects production environment
    ↓
Reads CONFIG.API_BASE_URL = "https://botivate-frontend.onrender.com"
    ↓
User sends message
    ↓
Frontend calls fetch("https://botivate-frontend.onrender.com/chat/stream")
    ↓
Browser sees same-origin, no CORS issues
    ↓
Backend handles request, returns response
    ↓
Frontend displays answer
```

## 📚 References

- Render Docs: https://render.com/docs
- Python on Render: https://render.com/docs/deploy-python
- Static Sites: https://render.com/docs/static-sites
- Environment Variables: https://render.com/docs/environment-variables

## 🎯 Next Steps

1. **Monitor Performance**: Set up alerts for error rates
2. **Custom Domain**: Add your domain in Service Settings
3. **Auto-deploy**: Enable GitHub auto-deploy on push
4. **Scaling**: Upgrade from Free plan if needed
5. **Error Tracking**: Add Sentry or similar for production monitoring

---

**Deployed?** Great! Your Botivate AI is now live! 🎉
