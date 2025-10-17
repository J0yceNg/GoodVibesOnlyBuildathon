#!/bin/bash
# Quick network generator for Olympic Corridor
# Use this if you want to generate a simple network instead of using the XML

echo "Generating Olympic Corridor Network..."

# Generate a simple 4-intersection grid network
netgenerate --grid \
    --grid.number=4,1 \
    --grid.length=300 \
    --grid.attach-length=100 \
    --default.lanenumber=3 \
    --default.speed=22.22 \
    --turn-lanes=1 \
    --turn-lanes.length=50 \
    --tls.guess=true \
    --output-file=olympic_corridor.net.xml \
    --junctions.corner-detail=5

echo "Network generated successfully!"
echo "File: olympic_corridor.net.xml"

# Optional: Open in netedit for visual editing
read -p "Open in netedit for editing? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]
then
    netedit olympic_corridor.net.xml
fi