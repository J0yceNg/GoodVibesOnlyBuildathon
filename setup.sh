#!/bin/bash
# FairLane Setup Script

echo "=========================================="
echo "FairLane Setup"
echo "=========================================="
echo ""

# Check if SUMO is installed
echo "1. Checking SUMO installation..."
if command -v sumo &> /dev/null; then
    echo "   ✓ SUMO found: $(which sumo)"
    sumo --version
else
    echo "   ✗ SUMO not found!"
    echo "   Please install SUMO first"
    exit 1
fi

# Check SUMO_HOME
echo ""
echo "2. Checking SUMO_HOME..."
if [ -z "$SUMO_HOME" ]; then
    echo "   ✗ SUMO_HOME not set!"
    echo "   Please set SUMO_HOME environment variable"
    echo "   Example: export SUMO_HOME=\"/Library/Frameworks/EclipseSUMO.framework/Versions/Current/EclipseSUMO/share/sumo\""
    exit 1
else
    echo "   ✓ SUMO_HOME: $SUMO_HOME"
fi

# Check if tools directory exists
echo ""
echo "3. Checking SUMO tools..."
if [ -d "$SUMO_HOME/tools" ]; then
    echo "   ✓ Tools directory found"
else
    echo "   ✗ Tools directory not found at $SUMO_HOME/tools"
    exit 1
fi

# Create virtual environment
echo ""
echo "4. Setting up Python environment..."
if [ -d "fairlane_env" ]; then
    echo "   Virtual environment already exists"
else
    python3 -m venv fairlane_env
    echo "   ✓ Virtual environment created"
fi

# Activate virtual environment
echo ""
echo "5. Activating virtual environment..."
source fairlane_env/bin/activate
echo "   ✓ Virtual environment activated"

# Add SUMO tools to PYTHONPATH
echo ""
echo "6. Adding SUMO tools to PYTHONPATH..."
export PYTHONPATH="$SUMO_HOME/tools:$PYTHONPATH"
echo "   ✓ PYTHONPATH updated"

# Install requirements
echo ""
echo "7. Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt
echo "   ✓ Dependencies installed"

# Verify TraCI installation
echo ""
echo "8. Verifying TraCI..."
python3 -c "import traci; print('   ✓ TraCI imported successfully')" 2>/dev/null || {
    echo "   Trying alternative installation..."
    # Try adding SUMO tools to Python path directly
    pip install "$SUMO_HOME/tools"
}

echo ""
echo "=========================================="
echo "Setup Complete!"
echo "=========================================="
echo ""
echo "To run the simulation:"
echo "  1. Activate the virtual environment:"
echo "     source fairlane_env/bin/activate"
echo ""
echo "  2. Set PYTHONPATH (if not already set):"
echo "     export PYTHONPATH=\"$SUMO_HOME/tools:\$PYTHONPATH\""
echo ""
echo "  3. Run the simulation:"
echo "     python3 fairlane_controller.py"
echo ""
echo "Or use the quick start script:"
echo "  bash run.sh"
echo ""