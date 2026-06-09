#!/bin/bash
set -e

echo "🔨 Building Botivate AI..."

# Install backend dependencies
echo "📦 Installing Python dependencies..."
cd backend
pip install -r requirements.txt
cd ..

echo "✅ Build complete!"
