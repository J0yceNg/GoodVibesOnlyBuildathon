# Frontend Simulation Control - Quick Start Guide

## What Changed

The frontend now has full control over the simulation lifecycle:

### 1. **Initial Screen** (Before Start)
When you open the app, you'll see:
- "Simulation Ready" message
- ✅ Network loaded confirmation
- **START button** to begin simulation

### 2. **Running Screen** (During Simulation)
Once started, you get:
- Live vehicle visualization
- **Top control bar** with:
  - ⏸️ **Pause/Resume** button
  - 🔄 **Restart** button  
  - ⏹️ **Stop** button
- Real-time statistics panel
- AI Controls panel

### 3. **Paused Screen**
When paused:
- Simulation stops updating
- "Simulation Paused" message
- **Resume** button to continue
- All control buttons still work

## API Endpoints Used

The frontend calls these endpoints:

```
POST http://localhost:8000/simulation/start    - Start simulation
POST http://localhost:8000/simulation/stop     - Stop simulation
POST http://localhost:8000/simulation/pause    - Pause simulation
POST http://localhost:8000/simulation/resume   - Resume simulation
POST http://localhost:8000/simulation/restart  - Restart simulation
```

## How to Test

1. **Start Backend:**
   ```bash
   python fairlane_controller.py --server
   ```

2. **Start Frontend:**
   ```bash
   cd sumo-frontend
   bun run dev
   ```

3. **Open Browser:**
   - Go to http://localhost:3000
   - You should see "Simulation Ready" screen
   - Click **START** button
   - Watch vehicles appear and move!

## Key Features

✅ **User has full control** - Never locked out of buttons  
✅ **Blank network visible** - Can see roads before starting  
✅ **Pause/Resume** - Stop and continue simulation  
✅ **Restart** - Reset simulation from beginning  
✅ **Stop** - End simulation and return to start screen  
✅ **Status messages** - Clear feedback on actions  

## User Flow

```
Open App
  ↓
See Network (roads visible)
  ↓
Press START
  ↓
Simulation Runs
  ├→ Press PAUSE (anytime)
  │   ↓
  │   Press RESUME
  │   ↓
  │   Continue
  ├→ Press RESTART (anytime)
  │   ↓
  │   Simulation restarts
  └→ Press STOP (anytime)
      ↓
      Return to START screen
```

## Troubleshooting

**"Waiting for SUMO data" forever:**
- Make sure backend is running
- Check backend terminal for errors
- Press START button on frontend

**Buttons not working:**
- Check browser console for errors
- Verify API endpoints are reachable
- Check network tab in dev tools

**No vehicles appearing:**
- Simulation may need a few seconds to spawn vehicles
- Check if simulation is actually running (not paused)
- Look at backend terminal for TraCI errors
