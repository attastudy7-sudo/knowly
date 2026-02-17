#!/bin/bash

# EduShare Quick Start Script
# This script sets up and runs the application

echo "🎓 EduShare - Quick Start"
echo "=========================="
echo ""

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed. Please install Python 3.8 or higher."
    exit 1
fi

echo "✅ Python 3 found"

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
    echo "✅ Virtual environment created"
else
    echo "✅ Virtual environment already exists"
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo "📥 Installing dependencies..."
pip install -q -r requirements.txt
echo "✅ Dependencies installed"

# Check if database exists
if [ ! -f "edushare.db" ]; then
    echo "🗄️  Initializing database..."
    flask init-db
    echo "✅ Database initialized"
    
    echo ""
    read -p "Would you like to seed the database with sample data? (y/n) " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        flask seed-db
        echo "✅ Sample data added"
        echo ""
        echo "📝 Test accounts created:"
        echo "   - alice / password123"
        echo "   - bob / password123"
        echo "   - charlie / password123"
    fi
else
    echo "✅ Database already exists"
fi

echo ""
echo "🚀 Starting application..."
echo ""
echo "📍 The application will be available at: http://localhost:5000"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""

# Run the application
python run.py
