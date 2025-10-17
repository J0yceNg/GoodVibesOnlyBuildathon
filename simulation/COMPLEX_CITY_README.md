# Complex City Network - SUMO Simulation

This is a significantly more complex traffic simulation compared to the original 4x3 grid.

## Network Specifications

### Grid Configuration
- **Size**: 10 columns × 8 rows = **80 intersections**
- **Columns**: A through J (10 columns)
- **Rows**: 0 through 7 (8 rows)
- **Block Length**: 350 meters (vs 400m in original)
- **Total Coverage**: 3,500m × 2,800m (3.5km × 2.8km)
- **Lanes per Direction**: 4 (vs 3 in original)
- **Turn Lanes**: 2 dedicated turn lanes per intersection
- **Max Speed**: 60 km/h (16.67 m/s)
- **Traffic Lights**: All intersections with 90-second cycles

### Network Complexity
- Original: 4×3 grid = 12 intersections
- New: 10×8 grid = **80 intersections** (6.67× increase)
- Original: ~40 edges
- New: **~360 edges** (9× increase)

## Traffic Configuration

### Vehicle Types (14 types)
1. **car** - Standard passenger vehicle
2. **sedan** - Compact car
3. **suv** - SUV/crossover
4. **sports_car** - High-performance vehicle
5. **regular_bus** - City bus
6. **express_bus** - Express/BRT bus
7. **olympic_shuttle** - Olympic event shuttle
8. **accessible_vehicle** - Accessible transport
9. **emergency** - Emergency vehicles (ambulance, fire, police)
10. **taxi** - Taxi/rideshare
11. **delivery_van** - Small delivery vehicle
12. **small_truck** - Light truck
13. **large_truck** - Heavy truck
14. **motorcycle** - Motorcycle
15. **bicycle** - Bicycle

### Routes
- **Main Arterial Routes**: 15+ routes on Row 4 (Olympic corridor)
- **Secondary Arterials**: 20+ routes on Rows 2, 3, 5, 6
- **Local Streets**: 10+ routes on Rows 0, 1, 7
- **North-South Routes**: 30+ routes across 10 columns (A-J)
- **Complex Routes**: 30+ L-shaped, diagonal, U-turn, and loop patterns
- **Total Unique Routes**: **~150 routes** (vs ~20 in original)

### Traffic Periods (3-hour simulation)

#### Period 1: Early Morning (0-1800s / 0-30min)
- Light traffic on all routes
- Early morning deliveries active
- Probability: 0.03-0.06 for main routes

#### Period 2: Morning Rush (1800-3600s / 30-60min)
- **HEAVY TRAFFIC** - Peak congestion
- Main arterial: 0.35 probability (thousands of vehicles)
- All routes heavily utilized
- High bus frequency (45-60s periods)
- High taxi demand
- Motorcycle lane-splitting
- Probability: 0.17-0.35 across network

#### Period 3: Olympic Events (3600-5400s / 60-90min)
- **OLYMPIC PRIORITY MODE**
- Regular traffic reduced on main corridor
- Olympic shuttles every 20-25 seconds
- Accessible vehicles every 40-45 seconds
- Heavy diverted traffic on alternate routes (Rows 2, 6)
- High taxi activity to venues

#### Period 4: Evening Rush (5400-7200s / 90-120min)
- Heavy return traffic
- Similar to morning but reversed patterns
- All routes congested
- Express bus service active

#### Period 5: Night (7200-10800s / 120-180min)
- Light traffic
- Night deliveries and truck traffic
- Limited bus service
- Late-night taxis and sports cars

### Traffic Volume Estimates

**Peak Hour (Morning Rush):**
- Main Arterial (Row 4): ~3,000-4,000 vehicles/hour
- Secondary Arterials (Rows 2,3,5,6): ~1,500-2,000 vehicles/hour each
- North-South Routes: ~1,000-1,500 vehicles/hour each
- **Total Network**: ~15,000-20,000 vehicles/hour peak
- **Buses**: ~100 buses active during rush hour
- **Total Simulation**: ~50,000-70,000 vehicle trips over 3 hours

**Original Network (for comparison):**
- Peak: ~500-800 vehicles/hour
- Total: ~3,000-5,000 vehicle trips

**Increase**: **10-15× more traffic volume**

### Continuous Flows
- Emergency vehicles all day (400-700s periods)
- Cyclists during daylight (120-150s periods)
- Local traffic on edge streets (low probability continuous)
- Column traffic on all 10 north-south corridors

## Setup Instructions

### Step 1: Generate the Network

Run the PowerShell script:
```powershell
cd simulation
.\generate_complex_network.ps1
```

Or run the netgenerate command directly:
```powershell
netgenerate `
    --grid `
    --grid.x-number=10 `
    --grid.y-number=8 `
    --grid.length=350 `
    --grid.attach-length=50 `
    --default.lanenumber=4 `
    --default.speed=16.67 `
    --turn-lanes=2 `
    --turn-lanes.length=30 `
    --tls.guess=true `
    --tls.cycle.time=90 `
    --tls.green.time=45 `
    --tls.yellow.time=4 `
    --tls.red.time=3 `
    --junctions.corner-detail=5 `
    --junctions.limit-turn-speed=5.5 `
    --lefthand=false `
    --output-file=complex_city.net.xml
```

### Step 2: Verify Files

You should have:
- ✅ `complex_city.net.xml` - Network file
- ✅ `complex_city.rou.xml` - Routes file (already created)
- ✅ `complex_city.sumocfg` - Configuration file (already created)

### Step 3: Run Simulation

#### GUI Mode (Visual):
```powershell
sumo-gui -c complex_city.sumocfg
```

#### Command Line Mode (Fast):
```powershell
sumo -c complex_city.sumocfg
```

#### With Python/TraCI:
```python
import traci
traci.start(["sumo", "-c", "simulation/complex_city.sumocfg"])
# Your simulation code here
traci.close()
```

## Key Differences from Original

| Feature | Original | Complex City | Increase |
|---------|----------|--------------|----------|
| Grid Size | 4×3 | 10×8 | 6.67× |
| Intersections | 12 | 80 | 6.67× |
| Edges | ~40 | ~360 | 9× |
| Routes | ~20 | ~150 | 7.5× |
| Vehicle Types | 5 | 15 | 3× |
| Lanes/Direction | 3 | 4 | 1.33× |
| Traffic Flows | ~30 | ~150 | 5× |
| Peak Traffic | 800/hr | 20,000/hr | 25× |
| Total Vehicles | 5,000 | 70,000 | 14× |
| Simulation Time | 3,600s | 10,800s | 3× |

## Performance Notes

⚠️ **This is a computationally intensive simulation!**

- Network is 6.67× larger
- Traffic volume is 14× higher
- Simulation is 3× longer
- Expected to be **~40-50× more computationally demanding**

**Recommendations:**
- Use a powerful computer
- Consider running without GUI for speed
- May want to reduce simulation end time for testing
- Monitor memory usage (expect 2-4 GB)
- First run may take 5-10 minutes to process

## Customization

### Adjust Traffic Volume
Edit probabilities in `complex_city.rou.xml`:
- Decrease all probability values to reduce congestion
- Increase period values to reduce vehicle frequency

### Change Simulation Duration
Edit `complex_city.sumocfg`:
```xml
<end value="7200"/>  <!-- Change from 10800 to 7200 for 2-hour sim -->
```

### Modify Network
Re-run netgenerate with different parameters:
- `--grid.x-number` and `--grid.y-number` for grid size
- `--grid.length` for block size
- `--default.lanenumber` for lanes per direction

## Visualization Tips

When running in SUMO-GUI:
1. Use View → Delay to slow down for observation
2. Enable Vehicle → Show Route to see paths
3. Use Locator → Junction to jump to specific intersections
4. Enable Statistics to see live vehicle counts
5. Color vehicles by type, speed, or waiting time

## Analysis Opportunities

This complex network is ideal for:
- **Congestion Analysis**: Multiple bottlenecks and traffic patterns
- **Route Optimization**: Compare many alternate routes
- **Priority Vehicle Testing**: Emergency and Olympic shuttles
- **Traffic Light Optimization**: 80 intersections to optimize
- **Multimodal Transport**: Cars, buses, trucks, bikes, motorcycles
- **Time-of-Day Patterns**: 5 distinct traffic periods
- **Network Resilience**: Test impact of blocked roads
- **Public Transport**: Complex bus and shuttle networks

Enjoy your complex city simulation! 🚗🚌🚑🏙️
