# FairLane Controller + WebSocket Server Integration

## Summary

The functionality from `server.py` has been fully integrated into `fairlane_controller.py`, creating a unified system that combines AI-powered traffic signal control with real-time WebSocket broadcasting.

## Changes Made

### 1. Updated `shared_config.py`
Added a new `SimulationControl` class to manage simulation state:
- `is_simulation_running()` - Check if simulation is active
- `start_simulation()` - Start the simulation
- `stop_simulation()` - Signal simulation to stop
- `pause_simulation()` / `resume_simulation()` - Pause/resume control
- `restart_simulation()` - Restart the simulation
- `set_simulation_speed()` - Control simulation speed
- `update_current_step()` - Track current simulation step

Created global instance `sim_control` alongside existing `live_config`.

### 2. Enhanced `fairlane_controller.py`

#### Added Imports
- FastAPI, WebSocket, WebSocketDisconnect
- CORSMiddleware for frontend communication
- asyncio for async operations
- sumolib for network data processing

#### Added Classes and Functions
- **ConnectionManager**: Manages WebSocket connections and broadcasting
- **build_network_data()**: Extracts road/lane geometry from SUMO network file
- **normalize_position()**: Converts SUMO coordinates to normalized viewport coordinates
- **get_vehicle_data()**: Collects vehicle information for WebSocket transmission
- **get_traffic_light_state()**: Collects traffic light state with junction positions

#### Modified FairLaneController Class
- Added `network_data` and `boundary` attributes to store network geometry
- Converted `run_simulation()` to async method
- Integrated WebSocket broadcasting into simulation loop:
  - Sends network geometry on startup
  - Broadcasts vehicle positions, speeds, waiting times, CO2 emissions
  - Broadcasts traffic light states and phases
  - Sends cumulative statistics by vehicle type
  - Updates at 60 FPS for smooth visualization

#### Added FastAPI Endpoints
- **WebSocket `/ws`**: Real-time simulation data streaming
- **GET `/`**: API status and information
- **GET `/health`**: Health check with simulation status
- **Startup event**: Launches simulation as background task

#### Updated main() Function
Now supports three modes:
1. **GUI Mode** (default): `python fairlane_controller.py`
2. **No-GUI Mode**: `python fairlane_controller.py --no-gui`
3. **Server Mode**: `python fairlane_controller.py --server`

## How to Run

### Option 1: Standalone with GUI (Original Behavior)
```bash
python fairlane_controller.py
```
- Opens SUMO GUI
- Runs simulation with FairLane AI control
- No WebSocket broadcasting

### Option 2: Headless Simulation
```bash
python fairlane_controller.py --no-gui
```
- Runs without GUI for better performance
- Full FairLane AI control
- No WebSocket broadcasting

### Option 3: WebSocket Server Mode (New!)
```bash
python fairlane_controller.py --server
```
- Starts FastAPI server on port 8000
- Runs headless SUMO simulation
- Broadcasts real-time data via WebSocket
- Full FairLane AI control
- Can be controlled via dashboard

## WebSocket Data Format

### Network Info Message (sent on connect)
```json
{
  "type": "network_info",
  "data": {
    "roads": [...],
    "junctions": [...],
    "boundary": {...}
  }
}
```

### Simulation Update Message (sent each step)
```json
{
  "type": "simulation_update",
  "step": 123,
  "time": 61.5,
  "vehicles": [
    {
      "id": "vehicle_0",
      "x": 0.123,
      "y": -0.456,
      "speed": 12.5,
      "angle": 90.0,
      "road_id": "E1",
      "lane_id": "E1_0",
      "waiting_time": 0.0,
      "co2": 1234.56,
      "type": "car"
    }
  ],
  "traffic_lights": [
    {
      "id": "B1",
      "state": "GGGrrr",
      "phase": 0,
      "next_switch": 30.0,
      "position": {"x": 0.0, "y": 0.0},
      "controlled_lanes": [...]
    }
  ],
  "stats": {
    "total_vehicles": 45,
    "avg_wait_time": 5.2,
    "delayed_vehicles": 3,
    "delayed_percent": 6.7,
    "avg_co2": 1234.56,
    "total_co2": 55555.2,
    "collisions": 0,
    "signal_extensions": 12,
    "ai_preemptive_actions": 5,
    "by_type": {
      "car": {"count": 40, "avg_wait_time": 5.0, ...},
      "bus": {"count": 5, "avg_wait_time": 3.2, ...}
    }
  }
}
```

## Frontend Integration

Your Next.js frontend can connect to the WebSocket like this:

```typescript
const ws = new WebSocket('ws://localhost:8000/ws');

ws.onopen = () => {
  console.log('Connected to FairLane simulation');
};

ws.onmessage = (event) => {
  const message = JSON.parse(event.data);
  
  if (message.type === 'network_info') {
    // Initialize map with road network
    setupMap(message.data);
  } else if (message.type === 'simulation_update') {
    // Update vehicle positions and traffic lights
    updateVisualization(message);
  }
};
```

## Key Features Preserved

✅ **All FairLane AI features work**:
- Priority vehicle detection (emergency, accessible, Olympic shuttle, bus)
- AI congestion prediction
- Preemptive signal control
- Live configuration via `live_config`
- Simulation control via `sim_control`

✅ **All server.py features integrated**:
- Real-time WebSocket broadcasting
- Network geometry extraction
- Vehicle tracking
- Traffic light state monitoring
- Cumulative statistics
- CORS support for frontend

✅ **Enhanced capabilities**:
- FairLane statistics included in WebSocket data
- Signal extensions and AI actions visible to frontend
- Async architecture for better performance
- Unified codebase - easier to maintain

## Migration from server.py

The old `server.py` can now be **replaced** or **deprecated**:
- All functionality is in `fairlane_controller.py`
- Uses the same WebSocket protocol
- Compatible with existing frontend code
- Adds FairLane AI intelligence on top

## Next Steps

1. Test the server mode: `python fairlane_controller.py --server`
2. Connect your Next.js frontend to `ws://localhost:8000/ws`
3. Verify all visualization features work
4. Consider removing or archiving `server.py`
5. Update documentation to reference the new unified system

## Troubleshooting

**Issue**: Module not found errors
- **Solution**: Install dependencies: `pip install fastapi uvicorn websockets`

**Issue**: Port 8000 already in use
- **Solution**: Stop the old `server.py` or change the port in `uvicorn.run()`

**Issue**: SUMO not found
- **Solution**: Ensure SUMO is installed and in PATH

**Issue**: Network file not found
- **Solution**: Verify `olympic_corridor.net.xml` exists in the same directory
