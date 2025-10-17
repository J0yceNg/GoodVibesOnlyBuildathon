# Quick Start Guide - AI Control Panel

## What Was Added

### 1. Purple Control Button (Top Center)
```
┌─────────────────────────┐
│  🤖 AI Controls ▶       │
└─────────────────────────┘
```
- Click to open/close the control panel

### 2. Control Panel Sections (When Opened)

#### A. AI Predictions Toggle
```
AI Predictions                 [ON/OFF Switch]
✅ AI predictions enabled
```

#### B. Priority Weights
```
Priority Weights
├─ Emergency          10.0  [====|    ]
├─ Accessible Vehicle  5.0  [==|      ]
├─ Olympic Shuttle     3.0  [=|       ]
├─ Regular Bus         2.0  [=|       ]
└─ Car                 1.0  [|        ]
                [Apply Priority Weights]
```

#### C. Detection Range
```
Detection Range
Distance (meters)           100
[=====|                        ]
           [Apply Detection Range]
```

#### D. Timing Parameters
```
Timing Parameters
├─ Min Green (seconds)    10  [==|       ]
├─ Max Green (seconds)    60  [====|     ]
└─ Extension (seconds)     5  [==|       ]
           [Apply Timing Parameters]
```

#### E. Action Buttons
```
┌─────────────────┬──────────────────┐
│ 🔄 Fetch Config │ ↺ Reset to Default│
└─────────────────┴──────────────────┘
```

## API Endpoints Integrated

| Action | Method | Endpoint | Purpose |
|--------|--------|----------|---------|
| Toggle AI | POST | `/api/control/ai` | Enable/disable AI predictions |
| Update Priorities | POST | `/api/control/priorities` | Change vehicle priority weights |
| Update Detection | POST | `/api/control/detection` | Change detection range |
| Update Timing | POST | `/api/control/timing` | Change timing parameters |
| Get Config | GET | `/api/config` | Fetch current configuration |
| Reset Config | POST | `/api/config/reset` | Reset to defaults |

## Quick Test (No API Required)

1. Start the frontend:
   ```powershell
   cd sumo-frontend
   bun dev
   ```

2. Open http://localhost:3000

3. Click the purple "🤖 AI Controls" button at the top

4. Interact with all the controls
   - You'll see error messages since the API isn't running yet
   - This is expected and shows the error handling works

## When API Is Ready

1. Update the API URL in `page.tsx` if needed (currently `http://localhost:8000`)

2. Start Dev C's API server on port 8000

3. Click "🔄 Fetch Config" to test connection

4. All controls should work and show success messages

## Control Panel Features

✨ **Features:**
- Real-time updates
- Visual feedback for all actions
- Error handling with user-friendly messages
- Sliders + number inputs for precise control
- Persistent UI state during session
- Smooth animations
- Matches existing dark theme

🎨 **Design:**
- Glass morphism effect
- Purple theme for AI/control elements
- Scrollable panel for smaller screens
- Responsive layout

## Default Values

These are the initial values shown in the UI:

```typescript
AI Enabled: false
Priorities: {
  emergency: 10.0,
  accessible_vehicle: 5.0,
  olympic_shuttle: 3.0,
  regular_bus: 2.0,
  car: 1.0
}
Detection Range: 100 meters
Timing: {
  min_green: 10 seconds,
  max_green: 60 seconds,
  extension: 5 seconds
}
```

These will be overwritten when you click "🔄 Fetch Config" and the API returns its current values.

## Troubleshooting

### "Error: Could not connect to API"
- The API server is not running
- Check the API URL configuration
- Verify CORS is enabled on the API

### Controls don't update
- Click the "Apply" button for each section
- Check the browser console for errors
- Verify the API is returning success responses

### Panel won't open
- Check browser console for JavaScript errors
- Ensure the frontend compiled successfully
- Try refreshing the page

## Next Integration Steps

1. ✅ Frontend controls are ready
2. ⏳ Wait for API server integration
3. ⏳ Test all endpoints together
4. ⏳ Add any additional features as needed
