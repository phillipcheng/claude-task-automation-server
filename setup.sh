#!/bin/bash

echo "Setting up Claude Task Automation Server..."
echo "==========================================="

# Check Python version
python_version=$(python3 --version 2>&1 | awk '{print $2}')
echo "✓ Python version: $python_version"

# Create virtual environment
echo "\n📦 Creating virtual environment..."
python3 -m venv venv

# Activate virtual environment
echo "✓ Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo "\n📦 Upgrading pip..."
pip install --upgrade pip

# Install dependencies
echo "\n📦 Installing dependencies..."
pip install -r requirements.txt

# Check if Claude CLI is available
echo "\n🔍 Checking for Claude CLI..."
if command -v claude &> /dev/null; then
    echo "✓ Claude CLI found: $(claude --version 2>&1 | head -n 1)"
else
    echo "⚠️  Claude CLI not found in PATH"
    echo "   Please install Claude Code and ensure 'claude' command is available"
fi

# Create .env file if it doesn't exist
if [ ! -f .env ]; then
    echo "\n📝 Creating .env file..."
    cp .env.example .env
    echo "✓ .env file created (optional configuration)"
else
    echo "✓ .env file already exists"
fi

# Create tests directory if needed
mkdir -p tests

echo "\n✅ Setup complete!"
echo "\nNext steps:"
echo "1. Ensure Claude CLI is installed and working: claude --version"
echo "2. Activate the virtual environment: source venv/bin/activate"
echo "3. Run the server: python -m app.main"
echo "4. Or run tests: pytest tests/ -v"
echo "\nAPI Documentation will be available at: http://localhost:8000/docs"
echo "\nNote: This system uses your local Claude CLI - no API key needed!"
