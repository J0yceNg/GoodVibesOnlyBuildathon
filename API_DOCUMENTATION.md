# FairLane API Documentation

## Base URL
```
http://localhost:8000
```

## WebSocket
```
ws://localhost:8000/ws
```

---

## REST API Endpoints

### Health & Status

#### `GET /health`
Get server health and detailed status information.

**Response:**
```json
{
  "status": "healthy",
  "connections": 2,
  "simulation": {
    "running": true,
    "paused": false,
    "current_step": 1234,
    "speed": 1.0
  },
  "config": {
    "ai_enabled": true,
    "priority_weights": {...},
    "detection_distance": 150,
    "timing": {...}
  }
}
```

#### `GET /api/simulation/status`
Get current simulation status.

**Response:**
```json
{
  "running": true,
  "paused": false,
  "current_step": 1234,
  "speed": 1.0,
  "connections": 2
}
```

---

### Simulation Control

#### `POST /api/simulation/start`
Start the simulation (from waiting state).

**Response:**
```json
{
  "success": true,
  "message": "Simulation started"
}
```

#### `POST /api/simulation/stop`
Stop the simulation completely.

**Response:**
```json
{
  "success": true,
  "message": "Stop signal sent"
}
```

#### `POST /api/simulation/pause`
Pause the running simulation.

**Response:**
```json
{
  "success": true,
  "message": "Simulation paused"
}
```

#### `POST /api/simulation/resume`
Resume a paused simulation.

**Response:**
```json
{
  "success": true,
  "message": "Simulation resumed"
}
```

#### `POST /api/simulation/restart`
Restart the simulation from the beginning.

**Response:**
```json
{
  "success": true,
  "message": "Restart signal sent"
}
```

#### `POST /api/simulation/speed`
Set simulation speed multiplier.

**Request Body:**
```json
{
  "speed": 2.0
}
```

**Parameters:**
- `speed` (float): Speed multiplier between 0.1 and 10.0

**Response:**
```json
{
  "success": true,
  "message": "Simulation speed set to 2.0x"
}
```

---

### Configuration

#### `GET /api/config`
Get all current configuration settings.

**Response:**
```json
{
  "ai_enabled": true,
  "priority_weights": {
    "emergency": 5.0,
    "accessible_vehicle": 4.0,
    "olympic_shuttle": 3.0,
    "regular_bus": 2.0,
    "car": 1.0
  },
  "detection_distance": 150,
  "timing": {
    "min_green": 15,
    "max_green": 60,
    "extension": 10
  }
}
```

#### `POST /api/config/ai`
Enable or disable AI predictions.

**Request Body:**
```json
{
  "enabled": true
}
```

**Response:**
```json
{
  "success": true,
  "message": "AI enabled"
}
```

#### `POST /api/config/detection-distance`
Set detection distance for priority vehicles.

**Request Body:**
```json
{
  "distance": 200
}
```

**Parameters:**
- `distance` (int): Distance in meters (50-500)

**Response:**
```json
{
  "success": true,
  "message": "Detection distance set to 200m"
}
```

#### `POST /api/config/timing`
Update traffic light timing parameters.

**Request Body:**
```json
{
  "min_green": 20,
  "max_green": 70,
  "extension": 15
}
```

**Parameters:**
- `min_green` (int, optional): Minimum green light duration in seconds (5-60)
- `max_green` (int, optional): Maximum green light duration in seconds (30-180)
- `extension` (int, optional): Extension time for priority vehicles in seconds (1-30)

**Response:**
```json
{
  "success": true,
  "message": "Timing parameters updated",
  "config": {...}
}
```

#### `POST /api/config/reset`
Reset all configuration to default values.

**Response:**
```json
{
  "success": true,
  "message": "Configuration reset to defaults",
  "config": {...}
}
```

---

## WebSocket Messages

### Client → Server

Currently, the WebSocket is primarily used for receiving data. Client messages can be added for future interactivity.

### Server → Client

#### Network Info (sent on connection)
```json
{
  "type": "network_info",
  "data": {
    "roads": [
      {
        "id": "E1",
        "lanes": [
          {
            "id": "E1_0",
            "index": 0,
            "coordinates": [[0.1, 0.2], [0.3, 0.4]],
            "width": 3.2,
            "speed": 13.89,
            "angle": 90.0
          }
        ],
        "from": "A",
        "to": "B",
        "num_lanes": 2
      }
    ],
    "junctions": [
      {
        "id": "B1",
        "x": 0.0,
        "y": 0.0,
        "type": "traffic_light"
      }
    ],
    "boundary": {
      "min_x": 0.0,
      "min_y": 0.0,
      "max_x": 1000.0,
      "max_y": 1000.0,
      "center_x": 500.0,
      "center_y": 500.0,
      "width": 1000.0,
      "height": 1000.0
    }
  }
}
```

#### Simulation Update (sent each step)
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
      "controlled_lanes": [
        {
          "signal_index": 0,
          "signal_state": "G",
          "angle": 90.0
        }
      ]
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
      "car": {
        "count": 40,
        "avg_wait_time": 5.0,
        "avg_co2": 1200.0,
        "avg_speed": 10.5
      },
      "bus": {
        "count": 5,
        "avg_wait_time": 3.2,
        "avg_co2": 2500.0,
        "avg_speed": 8.0
      }
    }
  }
}
```

---

## Frontend Integration Example

### React/Next.js Example

```typescript
import { useEffect, useState } from 'react';

const API_BASE = 'http://localhost:8000';
const WS_URL = 'ws://localhost:8000/ws';

export function useSimulationControl() {
  const [status, setStatus] = useState({
    running: false,
    paused: false,
    current_step: 0,
    speed: 1.0
  });

  // Fetch status
  const fetchStatus = async () => {
    const res = await fetch(`${API_BASE}/api/simulation/status`);
    const data = await res.json();
    setStatus(data);
  };

  // Control functions
  const start = async () => {
    const res = await fetch(`${API_BASE}/api/simulation/start`, { method: 'POST' });
    const data = await res.json();
    if (data.success) await fetchStatus();
    return data;
  };

  const pause = async () => {
    const res = await fetch(`${API_BASE}/api/simulation/pause`, { method: 'POST' });
    const data = await res.json();
    if (data.success) await fetchStatus();
    return data;
  };

  const resume = async () => {
    const res = await fetch(`${API_BASE}/api/simulation/resume`, { method: 'POST' });
    const data = await res.json();
    if (data.success) await fetchStatus();
    return data;
  };

  const restart = async () => {
    const res = await fetch(`${API_BASE}/api/simulation/restart`, { method: 'POST' });
    const data = await res.json();
    if (data.success) await fetchStatus();
    return data;
  };

  const stop = async () => {
    const res = await fetch(`${API_BASE}/api/simulation/stop`, { method: 'POST' });
    const data = await res.json();
    if (data.success) await fetchStatus();
    return data;
  };

  const setSpeed = async (speed: number) => {
    const res = await fetch(`${API_BASE}/api/simulation/speed`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ speed })
    });
    const data = await res.json();
    if (data.success) await fetchStatus();
    return data;
  };

  useEffect(() => {
    fetchStatus();
    const interval = setInterval(fetchStatus, 2000);
    return () => clearInterval(interval);
  }, []);

  return { status, start, pause, resume, restart, stop, setSpeed };
}

// WebSocket hook
export function useSimulationWebSocket() {
  const [networkData, setNetworkData] = useState(null);
  const [simulationData, setSimulationData] = useState(null);

  useEffect(() => {
    const ws = new WebSocket(WS_URL);

    ws.onopen = () => {
      console.log('Connected to simulation');
    };

    ws.onmessage = (event) => {
      const message = JSON.parse(event.data);
      
      if (message.type === 'network_info') {
        setNetworkData(message.data);
      } else if (message.type === 'simulation_update') {
        setSimulationData(message);
      }
    };

    ws.onerror = (error) => {
      console.error('WebSocket error:', error);
    };

    ws.onclose = () => {
      console.log('Disconnected from simulation');
    };

    return () => ws.close();
  }, []);

  return { networkData, simulationData };
}
```

### Control Panel Component

```tsx
import { useSimulationControl } from './hooks';

export function SimulationControls() {
  const { status, start, pause, resume, restart, stop, setSpeed } = useSimulationControl();

  return (
    <div className="control-panel">
      <h3>Simulation Controls</h3>
      
      <div className="status">
        <p>Status: {status.running ? (status.paused ? 'Paused' : 'Running') : 'Stopped'}</p>
        <p>Step: {status.current_step}</p>
        <p>Speed: {status.speed}x</p>
      </div>

      <div className="buttons">
        <button onClick={start} disabled={status.running}>
          Start
        </button>
        <button onClick={pause} disabled={!status.running || status.paused}>
          Pause
        </button>
        <button onClick={resume} disabled={!status.paused}>
          Resume
        </button>
        <button onClick={restart}>
          Restart
        </button>
        <button onClick={stop} disabled={!status.running}>
          Stop
        </button>
      </div>

      <div className="speed-control">
        <label>Speed:</label>
        <input
          type="range"
          min="0.1"
          max="10"
          step="0.1"
          value={status.speed}
          onChange={(e) => setSpeed(parseFloat(e.target.value))}
        />
        <span>{status.speed}x</span>
      </div>
    </div>
  );
}
```

---

## Notes

- The simulation will wait for a START signal when running in server mode
- The network geometry is sent immediately on WebSocket connection, even before simulation starts
- Buttons should NOT be disabled when simulation isn't running - users can still interact with controls
- The "Initializing" message should only show while waiting for the initial network_info message
- Once network data is received, display the road network and show a "Start Simulation" button
