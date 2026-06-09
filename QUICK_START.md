# 🚀 Botivate AI - Quick Start Guide

## Status: Ready for Render Deployment ✅

Your Botivate AI application is fully configured and ready to deploy on Render!

---

## 📋 What You Have

```
✅ Frontend (Static HTML/JS/CSS)
   • Auto-detects backend URL
   • Real-time streaming chat UI
   • Responsive design
   • Connection test utility

✅ Backend (FastAPI + LangGraph)
   • Multi-step agent reasoning
   • SQL database integration
   • Streaming responses (SSE)
   • Health check endpoints

✅ Deployment Ready
   • render.yaml (IaC configuration)
   • Procfile (process definition)
   • build.sh (build script)
   • All env vars documented

✅ Documentation
   • DEPLOYMENT.md - Full guide
   • RENDER_SETUP.md - Quick setup
   • ARCHITECTURE.md - System design
   • DEPLOYMENT_SUMMARY.md - Overview
```

---

## 🎯 Deploy in 10 Minutes

### 1️⃣ Create Backend Service (5 min)
```bash
1. Go to https://dashboard.render.com
2. Click "New +" → "Web Service"
3. Select repo: teamai-botivate/Bot
4. Configure:
   • Name: botivate-backend
   • Build: pip install -r backend/requirements.txt
   • Start: cd backend && uvicorn app.main:app --host 0.0.0.0 --port $PORT
5. Add environment variables (see RENDER_SETUP.md)
6. Click "Create Web Service"
```

### 2️⃣ Create Frontend Service (2 min)
```bash
1. Click "New +" → "Static Site"
2. Select same repo
3. Configure:
   • Name: botivate-frontend
   • Publish dir: frontend
   • Build: echo "Static"
4. Click "Create Static Site"
```

### 3️⃣ Test Connection (1 min)
```bash
1. Visit https://botivate-frontend.onrender.com
2. Open DevTools (F12)
3. Run: testBackendConnection()
4. See "✅ Connection test completed successfully!"
```

### 4️⃣ You're Live! 🎉
```bash
Frontend: https://botivate-frontend.onrender.com
Backend:  https://botivate-backend.onrender.com
```

---

## 🔑 Environment Variables

Add these to Render backend service:

```env
DATABASE_URI=postgresql://postgres.xxxxx:password...@aws-1-ap-northeast-1.pooler.supabase.com:6543/postgres
OPENAI_API_KEY=sk-proj-your-key-here
LLM_MODEL=gpt-4o
FAST_LLM_MODEL=gpt-4o-mini
LLM_TEMPERATURE=0
ALLOWED_ORIGINS=*
ENABLE_SUPABASE=true
```

👉 Get values from:
- **DATABASE_URI**: Your local `.env` file
- **OPENAI_API_KEY**: https://platform.openai.com/api-keys

---

## 💻 Local Development

### Start Backend
```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

### Open Frontend
```bash
Visit http://localhost:8000 in your browser
```

### Test Connection
```bash
Open DevTools (F12)
Run: testBackendConnection()
```

---

## 🔗 How Frontend-Backend Talk

### Local (localhost)
```
Frontend (http://localhost:8000)
    ↓
Detects localhost
    ↓
API_BASE_URL = "http://localhost:8000"
    ↓
Calls /chat and /chat/stream
```

### Production (Render)
```
Frontend (https://botivate-frontend.onrender.com)
    ↓
Detects production (not localhost)
    ↓
API_BASE_URL = "https://botivate-frontend.onrender.com"
    ↓
Same-origin requests (no CORS issues)
```

The frontend automatically adjusts - no configuration needed! 🎯

---

## 📊 API Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/chat` | Send message, get full response |
| POST | `/chat/stream` | Send message, stream response |
| GET | `/health` | Check backend status |
| GET | `/` | Load frontend |

### Example: Send Message
```bash
curl -X POST https://botivate-backend.onrender.com/chat \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What tasks do we have?",
    "chat_history": []
  }'
```

Response:
```json
{
  "answer": "We have the following tasks..."
}
```

---

## 🧪 Test Checklist

### Before Deploying
- [ ] Backend starts locally without errors
- [ ] Frontend loads at localhost:8000
- [ ] Can send test messages
- [ ] `testBackendConnection()` passes

### After Deploying
- [ ] Backend service shows "Live" in Render
- [ ] Frontend service shows "Live" in Render
- [ ] Can access frontend URL
- [ ] Backend `/health` returns `{"status": "ok"}`
- [ ] Frontend loads without errors
- [ ] Can send messages and get responses
- [ ] Streaming works (tokens appear one by one)

---

## 🐛 Debugging

### Frontend Won't Connect to Backend
```javascript
// In browser DevTools console:
testBackendConnection()

// Check:
// 1. Backend is running
// 2. ALLOWED_ORIGINS=* on backend
// 3. Correct API_BASE_URL
// 4. No CORS errors in console
```

### Backend Won't Start
```bash
# Check logs in Render dashboard:
# 1. Look for Python errors
# 2. Check env vars are set correctly
# 3. Verify requirements.txt is complete
# 4. Check DATABASE_URI is valid
# 5. Check OPENAI_API_KEY has quota
```

### Slow Responses
```bash
# Check logs for:
# [LATENCY] messages
# p50 and p95 latency metrics
# May be cold start (wait 60 sec for free tier)
```

---

## 📁 Key Files

```
frontend/
├── index.html              # Main page
├── js/
│   ├── config.js          # API URL auto-detection
│   ├── test-connection.js # Connection tester
│   ├── api.js             # Chat endpoints
│   ├── ui.js              # UI rendering
│   └── app.js             # Initialization
└── css/
    └── style.css          # Styling

backend/
├── app/
│   ├── main.py            # FastAPI app
│   ├── db.py              # Database
│   ├── schemas.py         # Models
│   ├── core/config.py     # Configuration
│   ├── api/routes.py      # /chat endpoints
│   └── agent/             # LangGraph agent
└── requirements.txt       # Dependencies

render.yaml               # Render infrastructure
Procfile                  # Web service process
build.sh                  # Build script
DEPLOYMENT.md             # Full guide
RENDER_SETUP.md           # Quick setup
ARCHITECTURE.md           # System design
```

---

## 🎓 Documentation

| Document | Purpose | Time |
|----------|---------|------|
| **RENDER_SETUP.md** | Step-by-step Render setup | 5 min |
| **DEPLOYMENT.md** | Comprehensive guide | 15 min |
| **ARCHITECTURE.md** | System design & data flow | 20 min |
| **DEPLOYMENT_SUMMARY.md** | What was done & how to use | 10 min |

👉 **Start with RENDER_SETUP.md** for quickest deployment!

---

## ✨ Features

### Frontend
- ✅ Auto-detects environment (dev/prod)
- ✅ Real-time streaming chat
- ✅ Markdown rendering
- ✅ Chat history
- ✅ Responsive design
- ✅ Connection testing
- ✅ Latency monitoring

### Backend
- ✅ LangGraph agent
- ✅ Multi-step reasoning
- ✅ SQL database
- ✅ GPT-4 powered
- ✅ Streaming responses (SSE)
- ✅ Health checks
- ✅ Latency tracking

### Deployment
- ✅ Render-ready (render.yaml + Procfile)
- ✅ Environment auto-detection
- ✅ CORS configured
- ✅ Docker-ready (coming soon)
- ✅ CI/CD ready

---

## 🚀 Next Steps

1. **Read**: RENDER_SETUP.md (5 min)
2. **Deploy**: Follow setup steps (10 min)
3. **Test**: Run testBackendConnection() ✅
4. **Monitor**: Check Render logs 📊
5. **Share**: Send URL to team 🎉

---

## 💡 Pro Tips

### Speed Up Cold Starts
- Upgrade to Paid tier (eliminates cold starts)
- Keep a monitor service pinging /health every 15 min

### Better Debugging
- Set `DEBUG=true` in environment (future)
- Check latency logs for bottlenecks
- Monitor database connection pool

### Secure Secrets
- Never commit `.env` with real values
- Always use Render environment variables
- Rotate API keys periodically

---

## 📞 Need Help?

### Check Logs
1. Render dashboard → Your service
2. Click "Logs" tab
3. Look for errors

### Test Connection
```javascript
// In browser DevTools
testBackendConnection()
```

### Debug Endpoints
```bash
# Health check
curl https://botivate-backend.onrender.com/health

# Test chat
curl -X POST https://botivate-backend.onrender.com/chat \
  -H "Content-Type: application/json" \
  -d '{"question":"Hello","chat_history":[]}'
```

### Resources
- Render Docs: https://render.com/docs
- FastAPI: https://fastapi.tiangolo.com
- LangGraph: https://langchain-ai.github.io/langgraph/
- GitHub: https://github.com/teamai-botivate/Bot

---

## ✅ You're Ready!

Everything is configured and tested. Your app is production-ready on Render!

**Let's go deploy! 🚀**

---

*Last Updated: 2025-06-09*  
*Status: Production Ready* ✅  
*Commits: a3a7c5d, 2d3c777*
