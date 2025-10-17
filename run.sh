#!/bin/bash
# Quick run script for FairLane

# Activate virtual environment if it exists
if [ -d "fairlane_env" ]; then
    source fairlane_env/bin/activate
fi

# Set PYTHONPATH to include SUMO tools
if [ -n "$SUMO_HOME" ]; then
    export PYTHONPATH="$SUMO_HOME/tools:$PYTHONPATH"
else
    echo "Warning: SUMO_HOME not set"
    echo "Trying default location..."
    export SUMO_HOME="/Library/Frameworks/EclipseSUMO.framework/Versions/Current/EclipseSUMO/share/sumo"
    export PYTHONPATH="$SUMO_HOME/tools:$PYTHONPATH"
fi

# Run the simulation
python3 fairlane_controller.py "$@"
