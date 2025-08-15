#!/bin/bash
# Railway build script for What the repo

set -e

echo "🚀 Starting Railway build process..."

# Check Python version
echo "🐍 Python version:"
python --version

# Upgrade pip
echo "📦 Upgrading pip..."
pip install --upgrade pip

# Install dependencies
echo "📚 Installing dependencies..."
pip install -r requirements.txt

# Test imports
echo "🧪 Testing imports..."
python test_deployment.py

echo "✅ Build completed successfully!"
