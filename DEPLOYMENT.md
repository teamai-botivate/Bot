# Botivate AI - Render Deployment Guide

## Overview
This guide covers deploying Botivate AI on Render with both frontend and backend services.

## Architecture
```
┌─────────────────────────────────────────────────────┐
│  Frontend (Static Site)                             │
│  - Served from Render Static Site                   │
│  - Auto-detects backend URL                         │
│  - API calls proxied to backend                     │
└─────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────┐
│  Backend (Web Service)                              │
│  - FastAPI + LangGraph Agent                        │
│  - Connects to Supabase PostgreSQL                  │
│  - Handles /chat and /chat/stream endpoints         │
└─────────────────────────────────────────────────────┘
```

## Prerequisites
- GitHub account with repository access
- Render account (https://render.com)
- Supabase PostgreSQL credentials
- OpenAI API key

## Step 1: Set Up Render Services

### Backend Service (Web)
1. Log in to [Render Dashboard](https://dashboard.render.com)
2. Click **"New +"** → **"Web Service"**
3. Connect your GitHub repository: `teamai-botivate/Bot`
4. Configure:
   - **Name**: `botivate-backend`
   - **Environment**: `Python 3.10`
   - **Build Command**: `pip install -r backend/requirements.txt`
   - **Start Command**: `cd backend && uvicorn app.main:app --host 0.0.0.0 --port $PORT`
   - **Plan**: Free or Paid (choose based on needs)

5. Add Environment Variables:
   ```
   DATABASE_URI=postgresql://postgres.vaaafjsdlopppabuquaz:teamai-botivate%402025@aws-1-ap-northeast-1.pooler.supabase.com:6543/postgres
   OPENAI_API_KEY=sk-proj-...
   LLM_MODEL=gpt-4o
   FAST_LLM_MODEL=gpt-4o-mini
   LLM_TEMPERATURE=0
   ALLOWED_ORIGINS=*
   ENABLE_SUPABASE=true
   ```

6. Click **"Create Web Service"** and wait for deployment

### Frontend Service (Static Site)
1. Click **"New +"** → **"Static Site"**
2. Connect the same repository: `teamai-botivate/Bot`
3. Configure:
   - **Name**: `botivate-frontend`
   - **Publish directory**: `frontend`
   - **Build Command**: `echo "Frontend is static HTML/JS"`

4. Click **"Create Static Site"** and wait for deployment

## Step 2: Configure Frontend-Backend Communication

The frontend automatically detects the environment:
- **Local dev**: Uses `http://localhost:8000`
- **Production**: Uses the same origin (Render domain)

The frontend code in `frontend/js/config.js` handles this via:
```javascript
function getApiBaseUrl() {
    const isLocalhost = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';
    if (isLocalhost) return 'http://localhost:8000';
    return `${window.location.protocol}//${window.location.hostname}${window.location.port ? ':' + window.location.port : ''}`;
}
```

## Step 3: Test the Connection

### Local Testing
1. Start the backend:
   ```bash
   cd backend
   pip install -r requirements.txt
   uvicorn app.main:app --reload --port 8000
   ```

2. Open `http://localhost:8000` in your browser
3. Try sending a message through the chat interface

### Production Testing
1. Visit your Render frontend URL (e.g., `https://botivate-frontend.onrender.com`)
2. The frontend will auto-detect the backend URL
3. Try sending a message through the chat interface

## Available Endpoints

### POST `/chat`
Send a message and get a complete response.

**Request**:
```json
{
  "question": "What tasks do we have?",
  "chat_history": [
    {"type": "human", "content": "Hello"},
    {"type": "ai", "content": "Hi there!"}
  ]
}
```

**Response**:
```json
{
  "answer": "We have the following tasks..."
}
```

### POST `/chat/stream`
Send a message and stream the response token-by-token using Server-Sent Events.

**Request**: Same as `/chat`

**Response**: Server-Sent Events stream
```
data: {"status": "Processing..."}
data: {"chunk": "We"}
data: {"chunk": " have"}
data: {"chunk": " ..."}
data: {"done": true}
```

### GET `/health`
Health check endpoint.

**Response**:
```json
{
  "status": "ok"
}
```

## Troubleshooting

### Database Connection Issues
- Verify `DATABASE_URI` is correct in Render environment variables
- Check Supabase credentials are valid
- Ensure Render IP is whitelisted in Supabase (if applicable)

### Frontend Not Connecting to Backend
- Check browser console for CORS errors
- Verify `ALLOWED_ORIGINS` includes your frontend domain
- Ensure backend is running (check `/health` endpoint)

### Build Failures
- Check build logs in Render dashboard
- Ensure `requirements.txt` is up-to-date
- Verify Python 3.10+ is available

## Monitoring

Monitor request latency from the backend logs:
```
[LATENCY] /chat/stream rolling n=200 p50=1234.5ms p95=5678.9ms
[LATENCY] /chat rolling n=200 p50=2345.6ms p95=7890.1ms
```

## Deployment Files

- **`render.yaml`**: Infrastructure as code for Render (optional, for automated deployments)
- **`Procfile`**: Process file for Render web service
- **`build.sh`**: Build script for deployment
- **`frontend/js/config.js`**: Frontend configuration with auto-detection

## Next Steps

1. Push changes to GitHub:
   ```bash
   git add .
   git commit -m "Add Render deployment configuration"
   git push origin main
   ```

2. Monitor deployments in Render dashboard
3. Test thoroughly with real data
4. Set up error tracking (e.g., Sentry)
5. Configure custom domain (optional)

## Support

For issues, check:
- Render documentation: https://render.com/docs
- FastAPI documentation: https://fastapi.tiangolo.com
- GitHub issues: https://github.com/teamai-botivate/Bot/issues
