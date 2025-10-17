# AI Control Panel Integration

## Overview
I've added a comprehensive AI Control Panel to your SUMO frontend that integrates with Dev C's FastAPI server endpoints. The panel allows real-time control of traffic light AI parameters without modifying your existing server.

## Features Added

### 1. **AI Toggle Button**
- Enable/disable AI predictions with a visual toggle switch
- Endpoint: `POST /api/control/ai`
- Shows current state (AI enabled or using traditional timing)

### 2. **Priority Weights Configuration**
- Adjust priority weights for each vehicle type:
  - Emergency vehicles
  - Accessible vehicles
  - Olympic shuttles
  - Regular buses
  - Cars
- Each weight has:
  - Range slider (0-20)
  - Number input for precise control
  - Visual feedback
- Endpoint: `POST /api/control/priorities`

### 3. **Detection Range Control**
- Adjust vehicle detection distance (50-500 meters)
- Visual slider with numeric input
- Endpoint: `POST /api/control/detection`

### 4. **Timing Parameters**
- Configure three timing parameters:
  - Min Green Time (5-30 seconds)
  - Max Green Time (30-120 seconds)
  - Extension Time (1-20 seconds)
- Each with slider and numeric input
- Endpoint: `POST /api/control/timing`

### 5. **Configuration Management**
- **Fetch Config**: Load current configuration from server
  - Endpoint: `GET /api/config`
  - Updates all UI controls with server values
- **Reset to Default**: Reset all parameters to defaults
  - Endpoint: `POST /api/config/reset`
  - Automatically updates UI after reset

## UI Components

### Main Control Button
- Located at the top center of the screen
- Purple button with 🤖 emoji
- Click to toggle control panel visibility

### Control Panel Modal
- Scrollable panel (600px wide)
- Dark theme matching existing UI
- Contains all configuration sections
- Status messages for API responses (success/error)

## API Configuration

### API Base URL
The frontend is currently configured to connect to:
```typescript
const API_BASE_URL = 'http://localhost:8000';
```

**Important**: Update this URL when integrating with your actual API server. You may need to:
- Change the port if your API runs on a different port
- Update the hostname for production deployments
- Configure CORS on your API server to allow requests from the frontend

## How to Use

1. **Start the Frontend**:
   ```bash
   cd sumo-frontend
   bun dev
   ```

2. **Start the API Server** (when ready):
   ```bash
   # Dev C's API server on port 8000
   python api.py
   ```

3. **Open the Control Panel**:
   - Click the "🤖 AI Controls" button at the top center
   - The panel will slide down

4. **Configure Parameters**:
   - Toggle AI on/off
   - Adjust sliders or enter numeric values
   - Click "Apply" buttons for each section

5. **Manage Configuration**:
   - Click "🔄 Fetch Config" to load current settings
   - Click "↺ Reset to Default" to restore defaults

## API Integration Notes

### Error Handling
- All API calls include try/catch error handling
- Status messages appear for 3 seconds after each action
- Green background = Success
- Red background = Error

### Request Format
All POST requests send JSON data matching the Pydantic models:

```typescript
// AI Toggle
{ enabled: boolean }

// Priority Weights
{ 
  emergency?: number,
  accessible_vehicle?: number,
  olympic_shuttle?: number,
  regular_bus?: number,
  car?: number 
}

// Detection Range
{ distance: number }

// Timing Parameters
{ 
  min_green?: number,
  max_green?: number,
  extension?: number 
}
```

### CORS Configuration
When you integrate with the actual API server, ensure CORS is configured:

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Your frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

## UI Styling

The control panel matches your existing dark theme:
- Background: `bg-gray-900` with 98% opacity
- Borders: Purple (`border-purple-500`) for AI theme
- Buttons: 
  - Blue for apply actions
  - Cyan for fetch
  - Orange for reset
  - Purple for main toggle
- Backdrop blur for glass morphism effect

## State Management

All control states are managed locally:
- `aiEnabled`: boolean
- `priorities`: object with 5 vehicle type weights
- `detectionRange`: number (meters)
- `timing`: object with min_green, max_green, extension
- `apiStatus`: string for status messages
- `showControls`: boolean for panel visibility

## Next Steps

1. **API Integration**: When Dev C's server is ready, test all endpoints
2. **Port Configuration**: Update API_BASE_URL if needed
3. **Real-time Updates**: Consider adding WebSocket support for live config updates
4. **Persistence**: Add local storage to remember user preferences
5. **Validation**: Add more robust input validation if needed

## Testing

To test the UI without the API:
1. The control panel will show error messages if the API is unavailable
2. All UI interactions work independently
3. Error messages indicate connection issues

When the API is available:
1. Click "🔄 Fetch Config" to verify connection
2. Toggle AI and check the response
3. Update each parameter section individually
4. Test the reset functionality

## File Changes

**Modified**: `sumo-frontend/src/app/page.tsx`
- Added state variables for control panel
- Added API call functions (7 new functions)
- Added control panel UI components
- No changes to existing visualization code
