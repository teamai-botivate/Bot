# 🚀 Single Service Deployment (Recommended)

## Overview
**Ek hi port, Ek hi deployment! 🎯**

Frontend aur Backend dono same service se chalenge:
- Backend API: `/chat`, `/chat/stream`, `/health`
- Frontend: `/` (root se serve hoga)
- Dono: Same port par (automatically handled)

```
User visits https://botivate-ai.onrender.com
    ↓
Backend FastAPI app chalta hai
    ↓
Serve karti hai:
├── / → index.html (frontend)
├── /static/* → CSS, JS, images
├── /chat → API
└── /health → Health check
```

---

## 🎯 Deploy in 3 Steps

### Step 1: Create Single Web Service (2 min)
```
1. Go to https://dashboard.render.com
2. Click "New +" → "Web Service"
3. Select repo: teamai-botivate/Bot
4. Configure:
   • Name: botivate-ai
   • Environment: Python 3.10
   • Region: Singapore
   • Build: pip install -r backend/requirements.txt
   • Start: cd backend && uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

### Step 2: Add Environment Variables (1 min)
```
DATABASE_URI=postgresql://postgres.xxxxx:password...@aws...
OPENAI_API_KEY=sk-proj-your-key-here
LLM_MODEL=gpt-4o
FAST_LLM_MODEL=gpt-4o-mini
LLM_TEMPERATURE=0
ALLOWED_ORIGINS=*
ENABLE_SUPABASE=true
```

### Step 3: Deploy! (2-5 min)
```
Click "Create Web Service"
Wait for deployment (green status)
Your app is live! 🎉
```

---

## ✅ Verification

1. **Access your app**:
   ```
   https://botivate-ai.onrender.com
   ```

2. **Check frontend loads**:
   ```
   Visit https://botivate-ai.onrender.com
   Should see Botivate AI chat interface
   ```

3. **Check backend works**:
   ```bash
   curl https://botivate-ai.onrender.com/health
   # Response: {"status": "ok"}
   ```

4. **Test connection** (in browser console):
   ```javascript
   testBackendConnection()
   ```

---

## 🔧 How It Works

### URL Structure
```
Frontend:
  GET /              → Returns index.html
  GET /static/...    → CSS, JS, images

Backend API:
  POST /chat         → Chat endpoint
  POST /chat/stream  → Streaming endpoint
  GET /health        → Health check
```

### Requests Flow
```
Browser requests: http://botivate-ai.onrender.com/
    ↓
Server returns: frontend/index.html
    ↓
Frontend loads (index.html)
    ↓
Loads JS files from /static/
    ↓
JS detects: CONFIG.API_BASE_URL = "" (empty)
    ↓
Uses relative URLs: /chat, /chat/stream
    ↓
Since both are on same domain & port, no CORS issues!
    ↓
Send message → /chat/stream → Get response ✅
```

---

## 📁 Directory Structure

```
botivate-ai/                    (Root)
├── frontend/                   (Served at /)
│   ├── index.html             → GET /
│   ├── css/
│   │   └── style.css          → GET /static/css/style.css
│   └── js/
│       ├── config.js          → GET /static/js/config.js
│       ├── api.js
│       ├── ui.js
│       └── app.js
│
└── backend/                    (Runs the server)
    ├── app/
    │   ├── main.py            (mounts /static and /)
    │   ├── api/routes.py      (/chat endpoints)
    │   ├── db.py
    │   └── ...
    ├── requirements.txt
    └── uvicorn command
```

---

## 🎨 Frontend Configuration

`frontend/js/config.js`:
```javascript
const CONFIG = {
    API_BASE_URL: "",  // Empty = relative URLs
    DIRECTOR_NAME: "Satyendra",
    HISTORY_TURNS_TO_KEEP: 5,
};
```

`frontend/js/api.js` automatically becomes:
```javascript
const url = `${CONFIG.API_BASE_URL}/chat`;  // → "/chat"
await fetch(url);  // → GET /chat (same domain, same port)
```

---

## 🚀 Benefits

✅ **Single deployment** - Ek hi service chalegi
✅ **Same port** - Koi config headache nahi
✅ **No CORS issues** - Same origin se requests
✅ **Simple** - Bilkul straightforward
✅ **Cost-effective** - Free tier per ek service
✅ **Easy debugging** - Dono logs same place

---

## 🐛 Debugging

### Check Frontend Loads
```bash
curl https://botivate-ai.onrender.com/
# Should see HTML content
```

### Check Backend Works
```bash
curl -X POST https://botivate-ai.onrender.com/chat \
  -H "Content-Type: application/json" \
  -d '{"question":"Hello","chat_history":[]}'
# Should get JSON response
```

### Check Logs
```
1. Render Dashboard → botivate-ai service
2. Logs tab → Look for errors
3. Common issues:
   - ImportError → Missing in requirements.txt
   - DATABASE_URI invalid → Check credentials
   - OPENAI_API_KEY invalid → Check key
```

### Test in Browser
```javascript
// Open DevTools (F12)
testBackendConnection()

// Should see:
// ✅ Health check passed
// ✅ Root endpoint accessible
// ✅ Chat endpoint working
// ✅ Connection test completed successfully!
```

---

## 📊 File Sizes

```
Frontend:
  index.html:      ~3 KB
  css/style.css:   ~10 KB
  js/*.js:         ~10 KB
  Total:           ~23 KB

Backend:
  Python deps:     ~500 MB (after pip install)
  Source code:     ~100 KB
```

---

## ⚡ Performance

**Local (localhost:8000)**:
- p50 latency: 50-100ms
- p95 latency: 500-1000ms
- Depends on: Database, OpenAI API

**Render (Free tier)**:
- p50 latency: 100-200ms
- p95 latency: 1-5 seconds
- May have cold starts (30-60 sec after 15 min inactivity)
- Upgrade to Paid for consistent performance

---

## 🔒 Security

- ✅ No credentials in code
- ✅ All secrets in Render env vars
- ✅ CORS configured properly
- ✅ Frontend served as static files
- ✅ Backend protected by Render

---

## 📝 Environment Variables

| Var | Example | Required |
|-----|---------|----------|
| DATABASE_URI | postgresql://... | ✅ Yes |
| OPENAI_API_KEY | sk-proj-... | ✅ Yes |
| LLM_MODEL | gpt-4o | No (default: gpt-4o) |
| FAST_LLM_MODEL | gpt-4o-mini | No |
| LLM_TEMPERATURE | 0 | No |
| ALLOWED_ORIGINS | * | No |
| ENABLE_SUPABASE | true | No |

---

## 🎯 Next Steps

1. ✅ Read this guide
2. ✅ Follow "Deploy in 3 Steps"
3. ✅ Test with `/health` endpoint
4. ✅ Test in browser with `testBackendConnection()`
5. ✅ Share URL with team! 🎉

---

## ❓ FAQ

**Q: Kya dono alag deploy kar sakta hoon?**
A: Haan, par iska koi faayda nahi. Single deployment simplest hai.

**Q: Frontend kab serve hota hai?**
A: Backend startup ke time. FastAPI mount kar deta hai root par.

**Q: API calls kaise karte hain?**
A: Relative URLs se: `/chat`, `/chat/stream`
Frontend aur Backend same domain & port, to automatic!

**Q: CORS ka issue ayega?**
A: Nahi! Same origin se requests aa rahe hain.

**Q: Local test kaisa karun?**
A: Backend chalao: `uvicorn app.main:app --reload --port 8000`
Browser kholo: `http://localhost:8000`

---

## 📞 Support

- **Logs**: Render Dashboard → Logs tab
- **Test API**: Use `testBackendConnection()` in browser
- **Debug**: Check browser DevTools Console
- **Read**: ARCHITECTURE.md for detailed flow

---

**Status**: ✅ Single Service Setup Complete!

**Ready to Deploy?** 🚀

```bash
# Just push to GitHub
git add .
git commit -m "Single service deployment setup"
git push origin main

# Then create Web Service on Render
# Follow "Deploy in 3 Steps" above
```

---

*Last Updated: 2025-06-09*
*Deployment Type: Single Web Service*
*Total Services Needed: 1*
*Estimated Cost: Free (Render free tier)*
