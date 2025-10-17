"use client";
import { useEffect, useState } from "react";

export default function Home() {
  const [vehicles, setVehicles] = useState<any[]>([]);

  useEffect(() => {
    const ws = new WebSocket("ws://localhost:8000/ws");
    ws.onmessage = (msg) => {
      const data = JSON.parse(msg.data);
      setVehicles(data.vehicles);
    };
    return () => ws.close();
  }, []);

  return (
    <main style={{ padding: "2rem", fontFamily: "sans-serif" }}>
      <h1>SUMO Simulation Data</h1>
      <ul>
        {vehicles.map((v) => (
          <li key={v.id}>
            🚗 {v.id} — x: {v.x.toFixed(1)}, y: {v.y.toFixed(1)}, speed:{" "}
            {v.speed.toFixed(2)}
          </li>
        ))}
      </ul>
    </main>
  );
}
