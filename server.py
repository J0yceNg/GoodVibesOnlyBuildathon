import asyncio
import json
import os
from fastapi import FastAPI, WebSocket
import traci
import traci.constants as tc

app = FastAPI()

SUMO_BINARY = "sumo"  # or "sumo-gui" for visual mode
CONFIG_FILE = "simulation/simulation.sumocfg"

@app.on_event("startup")
async def startup_event():
    # Start SUMO simulation
    traci.start([SUMO_BINARY, "-c", CONFIG_FILE, "--start", "--quit-on-end"])

@app.on_event("shutdown")
async def shutdown_event():
    traci.close()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    print("Client connected")

    try:
        while traci.simulation.getMinExpectedNumber() > 0:
            traci.simulationStep()  # advance 1 step in SUMO
            vehicle_ids = traci.vehicle.getIDList()
            vehicles = []

            for vid in vehicle_ids:
                x, y = traci.vehicle.getPosition(vid)
                speed = traci.vehicle.getSpeed(vid)
                vehicles.append({
                    "id": vid,
                    "x": x,
                    "y": y,
                    "speed": speed
                })

            await websocket.send_text(json.dumps({"vehicles": vehicles}))
            await asyncio.sleep(0.5)  # control update rate

    except Exception as e:
        print("Error:", e)
    finally:
        traci.close()
        print("Simulation ended")
