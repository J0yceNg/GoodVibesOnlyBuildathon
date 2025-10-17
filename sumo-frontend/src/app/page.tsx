'use client';

import { useEffect, useRef, useState, useCallback } from 'react';

// Types for simulation data
type Vehicle = {
  id: string;
  x: number;
  y: number;
  speed: number;
  angle: number;
  road_id: string;
  lane_id: string;
  waiting_time: number;
  co2: number;
  type: string;
};

type TrafficLight = {
  id: string;
  state: string;
  phase: number;
  next_switch: number;
  position?: { x: number; y: number };
  controlled_lanes?: Array<{
    signal_index: number;
    signal_state: string;
    angle: number;
  }>;
};

type SimulationStats = {
  total_vehicles: number;
  avg_wait_time: number;
  delayed_vehicles: number;
  delayed_percent: number;
  avg_co2: number;
  total_co2: number;
  collisions: number;
  by_type: {
    [key: string]: {
      count: number;
      avg_wait_time: number;
      avg_co2: number;
      avg_speed: number;
    };
  };
};

type Road = {
  id: string;
  lanes: Array<{
    id: string;
    index: number;
    coordinates: number[][];
    width: number;
    speed: number;
    angle: number;
  }>;
  from: string;
  to: string;
  num_lanes: number;
};

type NetworkData = {
  roads: Road[];
  junctions?: Array<{
    id: string;
    x: number;
    y: number;
    type: string;
  }>;
  boundary: {
    min_x: number;
    min_y: number;
    max_x: number;
    max_y: number;
    center_x: number;
    center_y: number;
    width: number;
    height: number;
  };
};

type NetworkInfo = {
  type: 'network_info';
  data: NetworkData;
};

type SimulationUpdate = {
  type: 'simulation_update';
  step: number;
  time: number;
  vehicles: Vehicle[];
  traffic_lights: TrafficLight[];
  stats: SimulationStats;
};

type MessageData = NetworkInfo | SimulationUpdate;

export default function SUMODashboard() {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const [connected, setConnected] = useState(false);
  const [networkData, setNetworkData] = useState<NetworkData | null>(null);
  const [simData, setSimData] = useState<SimulationUpdate | null>(null);
  const [hoveredVehicle, setHoveredVehicle] = useState<Vehicle | null>(null);
  const [mousePos, setMousePos] = useState({ x: 0, y: 0 });
  const wsRef = useRef<WebSocket | null>(null);
  const animationFrameRef = useRef<number | null>(null);
  
  // Simulation Control State
  const [simulationRunning, setSimulationRunning] = useState(false);
  const [simulationPaused, setSimulationPaused] = useState(false);
  
  // Control Panel State
  const [showControls, setShowControls] = useState(false);
  const [aiEnabled, setAiEnabled] = useState(false);
  const [priorities, setPriorities] = useState({
    emergency: 10.0,
    accessible_vehicle: 5.0,
    olympic_shuttle: 3.0,
    regular_bus: 2.0,
    car: 1.0
  });
  const [detectionRange, setDetectionRange] = useState(100);
  const [timing, setTiming] = useState({
    min_green: 10,
    max_green: 60,
    extension: 5
  });
  const [apiStatus, setApiStatus] = useState<string>('');
  
  // Canvas drawing parameters
  const scale = useRef(1);
  const offset = useRef({ x: 0, y: 0 });
  const isDragging = useRef(false);
  const dragStart = useRef({ x: 0, y: 0 });
  const canvasDimensions = useRef({ width: 0, height: 0 }); // CSS pixel dimensions
  
  // Vehicle angle tracking for smooth rotation
  const vehicleAngles = useRef<Map<string, number>>(new Map());

  // API Control Functions
  const startSimulation = async () => {
    try {
      const response = await fetch('http://localhost:8000/simulation/start', {
        method: 'POST'
      });
      const data = await response.json();
      setApiStatus(data.message);
      setSimulationRunning(true);
      setSimulationPaused(false);
    } catch (error) {
      console.error('Failed to start simulation:', error);
      setApiStatus('Failed to start simulation');
    }
  };

  const stopSimulation = async () => {
    try {
      const response = await fetch('http://localhost:8000/simulation/stop', {
        method: 'POST'
      });
      const data = await response.json();
      setApiStatus(data.message);
      setSimulationRunning(false);
      setSimulationPaused(false);
    } catch (error) {
      console.error('Failed to stop simulation:', error);
      setApiStatus('Failed to stop simulation');
    }
  };

  const pauseSimulation = async () => {
    try {
      const response = await fetch('http://localhost:8000/simulation/pause', {
        method: 'POST'
      });
      const data = await response.json();
      setApiStatus(data.message);
      setSimulationPaused(true);
    } catch (error) {
      console.error('Failed to pause simulation:', error);
      setApiStatus('Failed to pause simulation');
    }
  };

  const resumeSimulation = async () => {
    try {
      const response = await fetch('http://localhost:8000/simulation/resume', {
        method: 'POST'
      });
      const data = await response.json();
      setApiStatus(data.message);
      setSimulationPaused(false);
    } catch (error) {
      console.error('Failed to resume simulation:', error);
      setApiStatus('Failed to resume simulation');
    }
  };

  const restartSimulation = async () => {
    try {
      const response = await fetch('http://localhost:8000/simulation/restart', {
        method: 'POST'
      });
      const data = await response.json();
      setApiStatus(data.message);
      setSimulationRunning(true);
      setSimulationPaused(false);
    } catch (error) {
      console.error('Failed to restart simulation:', error);
      setApiStatus('Failed to restart simulation');
    }
  };

  // Convert normalized coordinates to canvas coordinates
  const toCanvasCoords = useCallback((x: number, y: number) => {
    const { width, height } = canvasDimensions.current;
    const centerX = width / 2;
    const centerY = height / 2;
    const viewScale = Math.min(width, height) * 0.4 * scale.current;
    
    return {
      x: centerX + x * viewScale + offset.current.x,
      y: centerY - y * viewScale + offset.current.y // Flip Y axis
    };
  }, []);

  // Convert world distance (in normalized units) to canvas pixels
  const worldToCanvasScale = useCallback(() => {
    const { width, height } = canvasDimensions.current;
    return Math.min(width, height) * 0.4 * scale.current;
  }, []);
  
  // Normalize angle difference to ensure shortest rotation path
  const normalizeAngle = useCallback((vehicleId: string, newAngle: number): number => {
    const prevAngle = vehicleAngles.current.get(vehicleId);
    
    if (prevAngle === undefined) {
      // First time seeing this vehicle, just store the angle
      vehicleAngles.current.set(vehicleId, newAngle);
      return newAngle;
    }
    
    // Calculate the difference between new and previous angle
    let diff = newAngle - prevAngle;
    
    // Normalize the difference to -180 to 180 range
    while (diff > 180) diff -= 360;
    while (diff < -180) diff += 360;
    
    // Calculate the normalized angle by adding the shortest difference
    const normalizedAngle = prevAngle + diff;
    
    // Store the normalized angle for next frame
    vehicleAngles.current.set(vehicleId, normalizedAngle);
    
    return normalizedAngle;
  }, []);

  // Convert canvas coordinates back to normalized coordinates
  const fromCanvasCoords = useCallback((canvasX: number, canvasY: number) => {
    const { width, height } = canvasDimensions.current;
    const centerX = width / 2;
    const centerY = height / 2;
    const viewScale = Math.min(width, height) * 0.4 * scale.current;
    
    return {
      x: (canvasX - centerX - offset.current.x) / viewScale,
      y: -(canvasY - centerY - offset.current.y) / viewScale
    };
  }, []);

  // Draw the simulation
  const draw = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const { width, height } = canvasDimensions.current;

    // Clear canvas
    ctx.fillStyle = '#0b1020';
    ctx.fillRect(0, 0, width, height);

    // Draw roads with multi-lane grouping
    if (networkData) {
      console.log(`🎨 Drawing ${networkData.roads.length} roads with boundary:`, networkData.boundary);
      
      let lanesDrawn = 0;
      const canvasScale = worldToCanvasScale();
      
      // Calculate meters to normalized coordinate conversion
      const worldScale = Math.max(networkData.boundary.width, networkData.boundary.height);
      const metersToNormalized = 2.0 / worldScale; // Convert meters to normalized [-1,1] range
      
      // Draw junctions first (so roads appear on top)
      const junctions = new Map<string, {x: number, y: number, connections: string[]}>();
      
      // Use accurate junction positions from network data (SUMO node coordinates)
      if (networkData.junctions) {
        networkData.junctions.forEach(junction => {
          junctions.set(junction.id, {x: junction.x, y: junction.y, connections: []});
        });
      }
      
      // If no junction data, fall back to traffic light positions
      if (junctions.size === 0 && simData?.traffic_lights) {
        simData.traffic_lights.forEach(tl => {
          if (tl.position) {
            junctions.set(tl.id, {x: tl.position.x, y: tl.position.y, connections: []});
          }
        });
      }
      
      // Collect connected roads for each junction
      networkData.roads.forEach(road => {
        if (road.lanes && road.lanes.length > 0) {
          // Track connections for each junction
          if (junctions.has(road.from)) {
            junctions.get(road.from)!.connections.push(road.id);
          }
          
          if (junctions.has(road.to)) {
            junctions.get(road.to)!.connections.push(road.id);
          }
        }
      });

      // Draw intersection areas for all junctions
      console.log(`📍 Drawing ${junctions.size} junctions`);
      const tlIds = new Set(simData?.traffic_lights?.map(tl => tl.id) || []);
      
      junctions.forEach((junctionData, junctionId) => {
        const pos = toCanvasCoords(junctionData.x, junctionData.y);
        const isTrafficLight = tlIds.has(junctionId);
        const connectionCount = junctionData.connections.length;
        
        // Calculate road widths and angles for connected roads
        const roadAngles: number[] = [];
        const roadWidths: number[] = [];
        const roadsByAngle = new Map<number, number>(); // angle bucket -> maximum width from single side
        
        junctionData.connections.forEach(roadId => {
          const road = networkData.roads.find(r => r.id === roadId);
          if (road && road.lanes.length > 0) {
            const angle = road.lanes[0].angle;
            roadAngles.push(angle);
            
            // Calculate total road width (sum of all lane widths)
            const totalWidth = road.lanes.reduce((sum, lane) => sum + lane.width, 0);
            roadWidths.push(totalWidth);
            
            // Group by angle (rounded to nearest 45 degrees for N/S/E/W)
            // Use MAX width from any single road in that direction (not sum)
            const angleKey = Math.round(angle / 45) * 45;
            roadsByAngle.set(angleKey, Math.max(roadsByAngle.get(angleKey) || 0, totalWidth));
          }
        });
        
        // Calculate junction dimensions based on road widths
        // Convert meters to canvas pixels
        const worldScale = Math.max(networkData.boundary.width, networkData.boundary.height);
        const metersToNormalized = 2.0 / worldScale;
        const canvasScale = worldToCanvasScale();
        
        // Get widths in different directions
        let horizontalWidth = 0;
        let verticalWidth = 0;
        
        roadsByAngle.forEach((width, angle) => {
          // Normalize angle to 0-360
          const normalizedAngle = ((angle % 360) + 360) % 360;
          
          // Horizontal roads (East-West): angles around 0/180/360
          if (normalizedAngle < 45 || normalizedAngle > 315 || (normalizedAngle > 135 && normalizedAngle < 225)) {
            horizontalWidth = Math.max(horizontalWidth, width);
          }
          
          // Vertical roads (North-South): angles around 90/270
          if ((normalizedAngle > 45 && normalizedAngle < 135) || (normalizedAngle > 225 && normalizedAngle < 315)) {
            verticalWidth = Math.max(verticalWidth, width);
          }
        });
        
        // Default minimum size if no width calculated
        if (horizontalWidth === 0 && verticalWidth === 0) {
          horizontalWidth = 10; // meters
          verticalWidth = 10; // meters
        }
        if (horizontalWidth === 0) horizontalWidth = verticalWidth;
        if (verticalWidth === 0) verticalWidth = horizontalWidth;
        
        // Convert to canvas pixels with slight expansion for junction area
        const junctionWidthH = (horizontalWidth * metersToNormalized * canvasScale) * 2.6;
        const junctionWidthV = (verticalWidth * metersToNormalized * canvasScale) * 2.6;
        
        // Draw junction shape based on number of connections
        // Use same color as roads (medium gray for arterials)
        ctx.fillStyle = '#374151';
        
        if (connectionCount <= 2) {
          // Line junction (2 roads or dead end)
          const angle = roadAngles.length > 0 ? (roadAngles[0] * Math.PI / 180) : 0;
          const width = Math.max(junctionWidthH, junctionWidthV);
          ctx.save();
          ctx.translate(pos.x, pos.y);
          ctx.rotate(angle);
          ctx.fillRect(-width * 0.5, -width * 0.4, width, width * 0.8);
          ctx.restore();
        } else if (connectionCount === 3) {
          // T-shaped junction
          ctx.save();
          ctx.translate(pos.x, pos.y);
          
          // Determine T orientation based on road angles
          const avgAngle = roadAngles.reduce((sum, a) => sum + a, 0) / roadAngles.length;
          ctx.rotate(avgAngle * Math.PI / 180);
          
          // Horizontal bar of T (matches horizontal road width)
          ctx.fillRect(-junctionWidthH * 0.5, -junctionWidthV * 0.4, junctionWidthH, junctionWidthV * 0.8);
          // Vertical stem of T (matches vertical road width)
          ctx.fillRect(-junctionWidthV * 0.4, -junctionWidthV * 0.4, junctionWidthV * 0.8, junctionWidthH * 0.6);
          ctx.restore();
        } else {
          // Cross junction (4+ roads)
          ctx.save();
          ctx.translate(pos.x, pos.y);
          // Draw cross shape matching road widths
          // Horizontal bar
          ctx.fillRect(-junctionWidthH * 0.5, -junctionWidthV * 0.4, junctionWidthH, junctionWidthV * 0.8);
          // Vertical bar
          ctx.fillRect(-junctionWidthV * 0.4, -junctionWidthH * 0.5, junctionWidthV * 0.8, junctionWidthH);
          ctx.restore();
        }
        
        ctx.shadowBlur = 0;
        
        // Draw crosswalks for traffic light intersections
        if (isTrafficLight && connectionCount >= 3) {
          ctx.strokeStyle = '#f3f4f6';
          ctx.lineWidth = 1.5 * scale.current;
          ctx.setLineDash([2 * scale.current, 2 * scale.current]);
          
          // Draw crosswalks on each approach, positioned based on junction width
          const crosswalkDistH = junctionWidthH * 0.65; // Distance for horizontal crosswalks
          const crosswalkDistV = junctionWidthV * 0.65; // Distance for vertical crosswalks
          const crosswalkWidthH = Math.min(junctionWidthH * 0.8, 12 * scale.current); // Width matches road
          const crosswalkWidthV = Math.min(junctionWidthV * 0.8, 12 * scale.current);
          
          // Draw crosswalks at 4 cardinal directions
          // North (horizontal crosswalk)
          ctx.beginPath();
          ctx.moveTo(pos.x - crosswalkWidthH/2, pos.y - crosswalkDistV);
          ctx.lineTo(pos.x + crosswalkWidthH/2, pos.y - crosswalkDistV);
          ctx.stroke();
          
          // South (horizontal crosswalk)
          ctx.beginPath();
          ctx.moveTo(pos.x - crosswalkWidthH/2, pos.y + crosswalkDistV);
          ctx.lineTo(pos.x + crosswalkWidthH/2, pos.y + crosswalkDistV);
          ctx.stroke();
          
          // East (vertical crosswalk)
          ctx.beginPath();
          ctx.moveTo(pos.x + crosswalkDistH, pos.y - crosswalkWidthV/2);
          ctx.lineTo(pos.x + crosswalkDistH, pos.y + crosswalkWidthV/2);
          ctx.stroke();
          
          // West (vertical crosswalk)
          ctx.beginPath();
          ctx.moveTo(pos.x - crosswalkDistH, pos.y - crosswalkWidthV/2);
          ctx.lineTo(pos.x - crosswalkDistH, pos.y + crosswalkWidthV/2);
          ctx.stroke();
          
          ctx.setLineDash([]);
        }
      });
      
      // Draw each lane individually with proper width
      networkData.roads.forEach((road, roadIdx) => {
        if (!road.lanes || road.lanes.length === 0) {
          console.warn(`⚠️ Road ${road.id} has no lanes`);
          return;
        }

        road.lanes.forEach((lane) => {
          if (lane.coordinates.length < 2) {
            console.warn(`⚠️ Lane ${lane.id} has insufficient coordinates`);
            return;
          }
          lanesDrawn++;

          // Calculate lane properties
          const speedKmh = lane.speed * 3.6;
          let baseColor: string;
          
          if (speedKmh > 60) {
            baseColor = '#2d3748'; // Dark gray for highways
          } else if (speedKmh > 40) {
            baseColor = '#374151'; // Medium gray for arterials  
          } else {
            baseColor = '#4b5563'; // Light gray for local streets
          }

          // Convert lane width from meters to canvas pixels
          // lane.width is in meters, convert to normalized units then to canvas pixels
          const laneWidthNormalized = lane.width * metersToNormalized;
          const laneWidthCanvas = laneWidthNormalized * canvasScale;

          // Draw lane surface
          ctx.strokeStyle = baseColor;
          ctx.lineWidth = laneWidthCanvas;
          ctx.lineCap = 'round';
          ctx.lineJoin = 'round';

          ctx.beginPath();
          lane.coordinates.forEach((coord, idx) => {
            const pos = toCanvasCoords(coord[0], coord[1]);
            if (idx === 0) {
              ctx.moveTo(pos.x, pos.y);
            } else {
              ctx.lineTo(pos.x, pos.y);
            }
          });
          ctx.stroke();
        });
      });

      // Second pass: Draw lane markings (dashed white for same direction, double yellow for opposite)
      networkData.roads.forEach((road, roadIdx) => {
        if (!road.lanes || road.lanes.length < 2) return;

        // Draw markings between adjacent lanes
        for (let i = 0; i < road.lanes.length - 1; i++) {
          const lane1 = road.lanes[i];
          const lane2 = road.lanes[i + 1];
          
          if (!lane1.coordinates || !lane2.coordinates || 
              lane1.coordinates.length < 2 || lane2.coordinates.length < 2) continue;

          // Calculate angle difference to determine if lanes are going opposite directions
          // Normalize angle difference to 0-180 range
          let angleDiff = Math.abs(lane1.angle - lane2.angle);
          if (angleDiff > 180) angleDiff = 360 - angleDiff;
          
          // Lanes are opposite if angle difference is close to 180 degrees (within 45 degree tolerance)
          const isOppositeDirection = angleDiff > 135 && angleDiff < 225;

          // Calculate positions between the two lane centerlines
          const minLength = Math.min(lane1.coordinates.length, lane2.coordinates.length);
          
          // Scale line widths with zoom
          const baseLineWidth = 0.3 * scale.current;
          const dashLength = 2 * scale.current;
          const gapLength = 4 * scale.current;
          
          if (isOppositeDirection) {
            // Double yellow line for opposite directions
            ctx.strokeStyle = '#fbbf24'; // Yellow
            ctx.lineWidth = baseLineWidth;
            ctx.setLineDash([]);
            ctx.lineCap = 'butt';

            // Offset in normalized coordinates (small value)
            const offsetNorm = 0.002;

            // Draw first yellow line (offset left)
            ctx.beginPath();
            for (let j = 0; j < minLength; j++) {
              const coord1 = lane1.coordinates[j];
              const coord2 = lane2.coordinates[j];
              const midX = (coord1[0] + coord2[0]) / 2 - offsetNorm;
              const midY = (coord1[1] + coord2[1]) / 2 - offsetNorm;
              const pos = toCanvasCoords(midX, midY);
              if (j === 0) {
                ctx.moveTo(pos.x, pos.y);
              } else {
                ctx.lineTo(pos.x, pos.y);
              }
            }
            ctx.stroke();

            // Draw second yellow line (offset right)
            ctx.beginPath();
            for (let j = 0; j < minLength; j++) {
              const coord1 = lane1.coordinates[j];
              const coord2 = lane2.coordinates[j];
              const midX = (coord1[0] + coord2[0]) / 2 + offsetNorm;
              const midY = (coord1[1] + coord2[1]) / 2 + offsetNorm;
              const pos = toCanvasCoords(midX, midY);
              if (j === 0) {
                ctx.moveTo(pos.x, pos.y);
              } else {
                ctx.lineTo(pos.x, pos.y);
              }
            }
            ctx.stroke();
          } else {
            // Dashed white line for same direction
            ctx.strokeStyle = '#ffffff';
            ctx.lineWidth = baseLineWidth;
            ctx.setLineDash([dashLength, gapLength]);
            ctx.lineCap = 'butt';

            ctx.beginPath();
            for (let j = 0; j < minLength; j++) {
              const coord1 = lane1.coordinates[j];
              const coord2 = lane2.coordinates[j];
              const midX = (coord1[0] + coord2[0]) / 2;
              const midY = (coord1[1] + coord2[1]) / 2;
              const pos = toCanvasCoords(midX, midY);
              if (j === 0) {
                ctx.moveTo(pos.x, pos.y);
              } else {
                ctx.lineTo(pos.x, pos.y);
              }
            }
            ctx.stroke();
          }
        }
        ctx.setLineDash([]); // Reset to solid line
      });
      
      if (lanesDrawn === 0) {
        console.error('❌ No lanes were drawn!');
        // Draw error indicator
        ctx.fillStyle = '#ef4444';
        ctx.font = 'bold 24px monospace';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText('⚠️ No lanes rendered', width / 2, height / 2);
        ctx.font = '16px monospace';
        ctx.fillText(`Roads: ${networkData.roads.length}`, width / 2, height / 2 + 30);
      } else {
        console.log(`✅ Successfully drew ${lanesDrawn} lanes`);
      }
    } else {
      // No network data yet
      ctx.fillStyle = '#fbbf24';
      ctx.font = 'bold 24px monospace';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText('⏳ Loading network data...', width / 2, height / 2);
    }

    // Draw traffic lights at junctions
    if (simData?.traffic_lights) {
      simData.traffic_lights.forEach(tl => {
        if (!tl.position) return;

        const pos = toCanvasCoords(tl.position.x, tl.position.y);
        
        ctx.save();
        ctx.translate(pos.x, pos.y);
        
        // Draw central junction circle
        ctx.fillStyle = '#1f2937';
        ctx.beginPath();
        ctx.arc(0, 0, 5 * scale.current, 0, Math.PI * 2);
        ctx.fill();
        ctx.strokeStyle = '#374151';
        ctx.lineWidth = 1 * scale.current;
        ctx.stroke();
        
        // Draw individual signal indicators based on actual controlled lane directions
        if (tl.controlled_lanes && tl.controlled_lanes.length > 0) {
          const circleRadius = 3.5 * scale.current; // Radius of each signal circle
          const circleDistance = 8 * scale.current; // Distance from center (reduced for closer positioning)
          
          tl.controlled_lanes.forEach((lane) => {
            // Use the actual angle from the lane direction
            // Convert to radians and adjust (SUMO angles: 0=East, 90=North, 180=West, 270=South)
            // We need to rotate by 90 degrees to align properly (SUMO 0° = East, Canvas 0° = Right)
            const angle = (lane.angle - 90) * Math.PI / 180;
            
            // Determine color based on signal character
            let color: string;
            
            switch (lane.signal_state.toLowerCase()) {
              case 'g':
                color = '#10b981'; // green
                break;
              case 'y':
                color = '#fbbf24'; // yellow
                break;
              case 'r':
                color = '#ef4444'; // red
                break;
              case 'o':
                color = '#f97316'; // orange (off-blink)
                break;
              default:
                color = '#6b7280'; // gray (unknown/off)
            }
            
            ctx.save();
            ctx.rotate(angle);
            
            // Calculate circle position (pointing outward from junction)
            const circleY = circleDistance;
            
            // Draw glow
            ctx.shadowBlur = 6 * scale.current;
            ctx.shadowColor = color;
            
            // Draw the circle
            ctx.fillStyle = color;
            ctx.beginPath();
            ctx.arc(0, circleY, circleRadius, 0, Math.PI * 2);
            ctx.fill();
            
            // Draw border for definition
            ctx.shadowBlur = 0;
            ctx.strokeStyle = '#ffffff';
            ctx.lineWidth = 0.8 * scale.current;
            ctx.beginPath();
            ctx.arc(0, circleY, circleRadius, 0, Math.PI * 2);
            ctx.stroke();
            
            ctx.restore();
          });
        }
        
        // Draw junction ID label if there are few traffic lights (less clutter)
        if (simData.traffic_lights.length <= 8) {
          ctx.fillStyle = '#e5e7eb';
          ctx.font = `bold ${8 * scale.current}px monospace`;
          ctx.textAlign = 'center';
          ctx.textBaseline = 'middle';
          ctx.shadowBlur = 3 * scale.current;
          ctx.shadowColor = '#000000';
          ctx.fillText(tl.id, 0, 24 * scale.current);
          ctx.shadowBlur = 0;
        }
        
        ctx.restore();
      });
    }

    // Draw vehicles with enhanced rendering
    if (simData?.vehicles) {
      simData.vehicles.forEach(vehicle => {
        const pos = toCanvasCoords(vehicle.x, vehicle.y);
        const color = getVehicleColorByType(vehicle.type);
        
        // Determine vehicle size based on type (scale with zoom)
        let length = 4 * scale.current, width = 2 * scale.current;
        if (vehicle.type === 'regular_bus' || vehicle.type === 'olympic_shuttle' || vehicle.type === 'accessible_vehicle') {
          length = 6 * scale.current;
          width = 2 * scale.current;
        } else if (vehicle.type === 'emergency') {
          length = 5 * scale.current;
          width = 2 * scale.current;
        }

        ctx.save();
        ctx.translate(pos.x, pos.y);
        // SUMO angle: 0° = North, 90° = East, 180° = South, 270° = West
        // Canvas angle: 0° = East (right), 90° = South (down), 180° = West (left), 270° = North (up)
        // Convert SUMO angle to canvas angle: canvas_angle = 90° - sumo_angle
        // Use normalized angle to ensure smooth rotation without flipping
        const sumoAngle = vehicle.angle;
        const normalizedSumoAngle = normalizeAngle(vehicle.id, sumoAngle);
        const canvasAngle = (90 - normalizedSumoAngle) * Math.PI / 180;
        ctx.rotate(canvasAngle);

        // Draw shadow
        ctx.fillStyle = 'rgba(0, 0, 0, 0.3)';
        ctx.fillRect(-length/2 + scale.current, -width/2 + scale.current, length, width);

        // Draw vehicle body
        ctx.fillStyle = color;
        ctx.strokeStyle = '#1f2937';
        ctx.lineWidth = 0.8 * scale.current;
        ctx.fillRect(-length/2, -width/2, length, width);
        ctx.strokeRect(-length/2, -width/2, length, width);

        // Add vehicle details
        // Windshield
        ctx.fillStyle = '#60a5fa';
        ctx.fillRect(length/2 - 4 * scale.current, -width/2 + scale.current, 3 * scale.current, width - 2 * scale.current);
        
        // Highlight for 3D effect
        const gradient = ctx.createLinearGradient(0, -width/2, 0, width/2);
        gradient.addColorStop(0, 'rgba(255, 255, 255, 0.3)');
        gradient.addColorStop(0.5, 'rgba(255, 255, 255, 0)');
        gradient.addColorStop(1, 'rgba(0, 0, 0, 0.2)');
        ctx.fillStyle = gradient;
        ctx.fillRect(-length/2, -width/2, length, width);

        // Emergency vehicle lights
        if (vehicle.type === 'emergency' && vehicle.speed > 0.5) {
          const frame = Math.floor(Date.now() / 200) % 2;
          ctx.fillStyle = frame === 0 ? '#ef4444' : '#3b82f6';
          ctx.shadowBlur = 10 * scale.current;
          ctx.shadowColor = ctx.fillStyle;
          ctx.beginPath();
          ctx.arc(-length/4, 0, 2 * scale.current, 0, Math.PI * 2);
          ctx.fill();
          ctx.shadowBlur = 0;
        }

        // Olympic shuttle indicator
        if (vehicle.type === 'olympic_shuttle') {
          ctx.fillStyle = '#fbbf24';
          ctx.font = `bold ${6 * scale.current}px Arial`;
          ctx.textAlign = 'center';
          ctx.textBaseline = 'middle';
          ctx.fillText('O', 0, 0);
        }

        // Highlight hovered vehicle
        if (hoveredVehicle?.id === vehicle.id) {
          ctx.strokeStyle = '#ffffff';
          ctx.lineWidth = 2 * scale.current;
          ctx.shadowBlur = 8 * scale.current;
          ctx.shadowColor = '#ffffff';
          ctx.strokeRect(-length/2 - 2 * scale.current, -width/2 - 2 * scale.current, 
                         length + 4 * scale.current, width + 4 * scale.current);
          ctx.shadowBlur = 0;
        }

        ctx.restore();
      });
    }
  }, [networkData, simData, hoveredVehicle, toCanvasCoords, normalizeAngle]);

  // Animation loop
  useEffect(() => {
    const animate = () => {
      draw();
      animationFrameRef.current = requestAnimationFrame(animate);
    };
    animate();

    return () => {
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current);
      }
    };
  }, [draw]);

  // Handle canvas resize
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const resizeCanvas = () => {
      const dpr = window.devicePixelRatio || 1;
      const rect = canvas.getBoundingClientRect();
      
      // Store CSS pixel dimensions
      canvasDimensions.current = { width: rect.width, height: rect.height };
      
      // Set physical pixel dimensions
      canvas.width = rect.width * dpr;
      canvas.height = rect.height * dpr;
      
      const ctx = canvas.getContext('2d');
      if (ctx) {
        // Scale context to use CSS pixels for drawing
        ctx.scale(dpr, dpr);
        
        // Set canvas display size
        canvas.style.width = `${rect.width}px`;
        canvas.style.height = `${rect.height}px`;
      }
    };

    resizeCanvas();
    window.addEventListener('resize', resizeCanvas);

    return () => window.removeEventListener('resize', resizeCanvas);
  }, []);

  // Mouse interaction handlers
  const handleMouseDown = (e: React.MouseEvent<HTMLCanvasElement>) => {
    isDragging.current = true;
    dragStart.current = { x: e.clientX, y: e.clientY };
  };

  const handleMouseMove = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const rect = canvas.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    setMousePos({ x: e.clientX, y: e.clientY });

    if (isDragging.current) {
      const dx = e.clientX - dragStart.current.x;
      const dy = e.clientY - dragStart.current.y;
      offset.current.x += dx;
      offset.current.y += dy;
      dragStart.current = { x: e.clientX, y: e.clientY };
    } else {
      // Check for vehicle hover
      const worldPos = fromCanvasCoords(x, y);
      let found: Vehicle | null = null;

      if (simData?.vehicles) {
        for (const vehicle of simData.vehicles) {
          const dx = vehicle.x - worldPos.x;
          const dy = vehicle.y - worldPos.y;
          const distance = Math.sqrt(dx * dx + dy * dy);
          
          if (distance < 0.02) {
            found = vehicle;
            break;
          }
        }
      }

      setHoveredVehicle(found);
    }
  };

  const handleMouseUp = () => {
    isDragging.current = false;
  };

  const handleWheel = (e: React.WheelEvent<HTMLCanvasElement>) => {
    e.preventDefault();
    const delta = e.deltaY > 0 ? 0.9 : 1.1;
    scale.current = Math.max(0.5, Math.min(5, scale.current * delta));
  };

  // WebSocket connection
  useEffect(() => {
    console.log('🔌 Attempting WebSocket connection to ws://localhost:8000/ws');
    const ws = new WebSocket('ws://localhost:8000/ws');
    wsRef.current = ws;

    ws.onopen = () => {
      setConnected(true);
      console.log('✅ WebSocket connected successfully');
    };

    ws.onmessage = (event: MessageEvent<string>) => {
      console.log('📨 Received message:', event.data.substring(0, 200) + '...');
      
      try {
        const data: MessageData = JSON.parse(event.data);
        console.log('📦 Parsed message type:', data.type);
        
        if (data.type === 'network_info') {
          console.log('🗺️ Network info received!');
          console.log('📍 Roads count:', data.data.roads.length);
          console.log('📍 First road sample:', JSON.stringify(data.data.roads[0], null, 2));
          console.log('📍 Network boundary:', data.data.boundary);
          setNetworkData(data.data);
        } else if (data.type === 'simulation_update') {
          console.log('🚗 Simulation update received');
          setSimData(data);
        } else {
          console.warn('⚠️ Unknown message type:', (data as any).type);
        }
      } catch (error) {
        console.error('❌ Error parsing message:', error);
        console.error('Raw message:', event.data);
      }
    };

    ws.onerror = (error) => {
      console.error('❌ WebSocket error:', error);
      console.error('❌ Connection state:', ws.readyState);
    };

    ws.onclose = (event) => {
      setConnected(false);
      console.log('❌ WebSocket disconnected');
      console.log('Close code:', event.code, 'Reason:', event.reason);
      // Attempt reconnection
      setTimeout(() => {
        if (wsRef.current?.readyState === WebSocket.CLOSED) {
          window.location.reload();
        }
      }, 3000);
    };

    return () => {
      ws.close();
    };
  }, []);

  // Helper functions
  const getVehicleColorByType = (type: string): string => {
    switch (type) {
      case 'car':
        return '#3b82f6'; // Blue for cars
      case 'regular_bus':
        return '#10b981'; // Green for regular buses
      case 'olympic_shuttle':
        return '#fbbf24'; // Gold for Olympic shuttles
      case 'accessible_vehicle':
        return '#06b6d4'; // Cyan for accessible vehicles
      case 'emergency':
        return '#ef4444'; // Red for emergency vehicles
      default:
        return '#9ca3af'; // Gray for unknown
    }
  };

  const getVehicleColor = (speed: number): string => {
    if (speed < 1) return '#ef4444'; // Red for stopped
    if (speed < 5) return '#f59e0b'; // Orange for slow
    if (speed < 10) return '#eab308'; // Yellow for moderate
    return '#10b981'; // Green for fast
  };

  const getTrafficLightColor = (state: string): string => {
    if (state.includes('r') || state.includes('R')) return '#ef4444';
    if (state.includes('y')) return '#fbbf24';
    if (state.includes('g') || state.includes('G')) return '#10b981';
    return '#6b7280';
  };

  const formatTime = (seconds: number): string => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  // API Functions (assuming the API runs on the same host but port 8000)
  const API_BASE_URL = 'http://localhost:8000';

  const toggleAI = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/control/ai`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ enabled: !aiEnabled })
      });
      const data = await response.json();
      if (data.success) {
        setAiEnabled(data.ai_enabled);
        setApiStatus('AI mode updated successfully');
        setTimeout(() => setApiStatus(''), 3000);
      }
    } catch (error) {
      setApiStatus('Error: Could not connect to API');
      setTimeout(() => setApiStatus(''), 3000);
    }
  };

  const updatePriorities = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/control/priorities`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(priorities)
      });
      const data = await response.json();
      if (data.success) {
        setApiStatus('Priorities updated successfully');
        setTimeout(() => setApiStatus(''), 3000);
      }
    } catch (error) {
      setApiStatus('Error: Could not update priorities');
      setTimeout(() => setApiStatus(''), 3000);
    }
  };

  const updateDetection = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/control/detection`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ distance: detectionRange })
      });
      const data = await response.json();
      if (data.success) {
        setApiStatus('Detection range updated successfully');
        setTimeout(() => setApiStatus(''), 3000);
      }
    } catch (error) {
      setApiStatus('Error: Could not update detection range');
      setTimeout(() => setApiStatus(''), 3000);
    }
  };

  const updateTiming = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/control/timing`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(timing)
      });
      const data = await response.json();
      if (data.success) {
        setApiStatus('Timing parameters updated successfully');
        setTimeout(() => setApiStatus(''), 3000);
      }
    } catch (error) {
      setApiStatus('Error: Could not update timing');
      setTimeout(() => setApiStatus(''), 3000);
    }
  };

  const fetchConfig = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/config`);
      const data = await response.json();
      // Update local state with fetched config
      setAiEnabled(data.ai_enabled || false);
      if (data.priority_weights) setPriorities(data.priority_weights);
      if (data.detection_distance) setDetectionRange(data.detection_distance);
      if (data.timing) setTiming(data.timing);
      setApiStatus('Configuration loaded successfully');
      setTimeout(() => setApiStatus(''), 3000);
    } catch (error) {
      setApiStatus('Error: Could not fetch configuration');
      setTimeout(() => setApiStatus(''), 3000);
    }
  };

  const resetConfig = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/config/reset`, {
        method: 'POST'
      });
      const data = await response.json();
      if (data.success && data.config) {
        // Update local state with reset values
        setAiEnabled(data.config.ai_enabled || false);
        if (data.config.priority_weights) setPriorities(data.config.priority_weights);
        if (data.config.detection_distance) setDetectionRange(data.config.detection_distance);
        if (data.config.timing) setTiming(data.config.timing);
        setApiStatus('Configuration reset to defaults');
        setTimeout(() => setApiStatus(''), 3000);
      }
    } catch (error) {
      setApiStatus('Error: Could not reset configuration');
      setTimeout(() => setApiStatus(''), 3000);
    }
  };

  return (
    <div className="relative w-full h-screen bg-gray-900 overflow-hidden">
      {/* Canvas */}
      <canvas
        ref={canvasRef}
        className="absolute inset-0 w-full h-full cursor-move"
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseUp}
        onWheel={handleWheel}
      />

      {/* Connection Status */}
      <div className="absolute top-4 left-4 z-10">
        <div className="bg-gray-900 bg-opacity-95 backdrop-blur-md rounded-xl px-4 py-2.5 border border-gray-700 shadow-xl">
          <div className="flex items-center gap-3">
            <div className="relative">
              <div className={`w-3 h-3 rounded-full ${connected ? 'bg-emerald-500' : 'bg-red-500'}`}></div>
              {connected && (
                <div className="absolute inset-0 w-3 h-3 rounded-full bg-emerald-500 animate-ping opacity-75"></div>
              )}
            </div>
            <span className="text-white text-sm font-semibold tracking-wide">
              {connected ? 'LIVE' : 'OFFLINE'}
            </span>
          </div>
        </div>
      </div>

      {/* Statistics Panel */}
      {simData && (
        <div className="absolute top-4 right-4 z-10 w-80">
          <div className="bg-gray-900 bg-opacity-95 backdrop-blur-md rounded-xl p-5 border border-gray-700 shadow-2xl">
            {/* Header */}
            <div className="flex items-center justify-between mb-4 pb-3 border-b border-gray-700">
              <h2 className="text-white font-bold text-lg tracking-wide">Simulation Stats</h2>
              <div className="text-cyan-400 font-mono text-sm">{formatTime(simData.time)}</div>
            </div>
            
            {/* Stats Grid */}
            <div className="grid grid-cols-2 gap-3 mb-4">
              <StatCard label="Current Vehicles" value={simData.stats.total_vehicles} color="text-emerald-400" icon="🚗" />
              <StatCard label="Avg Wait (s)" value={simData.stats.avg_wait_time} color="text-yellow-400" icon="⏱️" />
              <StatCard label="Currently Delayed" value={`${simData.stats.delayed_vehicles}`} color="text-orange-400" icon="🚦" />
              <StatCard label="Avg Delay %" value={`${simData.stats.delayed_percent}%`} color="text-red-400" icon="⚠️" />
            </div>
            
            {/* Environmental Impact */}
            <div className="mb-4 p-3 bg-gray-800 bg-opacity-50 rounded-lg border border-gray-700">
              <h3 className="text-gray-300 text-xs font-semibold mb-2 uppercase tracking-wide">Environmental Impact</h3>
              <div className="flex items-center justify-between">
                <span className="text-gray-400 text-sm">Avg CO₂ Emissions</span>
                <span className="text-cyan-400 font-mono font-bold text-lg">{simData.stats.avg_co2.toFixed(1)} mg/veh</span>
              </div>
              <div className="flex items-center justify-between mt-2">
                <span className="text-gray-400 text-sm">Total CO₂</span>
                <span className="text-cyan-300 font-mono text-sm">{(simData.stats.total_co2 / 1000).toFixed(2)} g</span>
              </div>
            </div>

            {/* Vehicle Type Breakdown */}
            {Object.keys(simData.stats.by_type).length > 0 && (
              <div className="mb-4 p-3 bg-gray-800 bg-opacity-50 rounded-lg border border-gray-700">
                <h3 className="text-gray-300 text-xs font-semibold mb-2 uppercase tracking-wide">Cumulative Averages by Type</h3>
                <div className="space-y-2">
                  {Object.entries(simData.stats.by_type).map(([type, data]) => (
                    <div key={type} className="flex items-center justify-between text-sm">
                      <span className="text-gray-300 font-medium capitalize">{type}</span>
                      <div className="flex gap-3 font-mono">
                        <span className="text-emerald-400">×{data.count}</span>
                        <span className="text-yellow-400">⏱️{data.avg_wait_time}s</span>
                        <span className="text-blue-400">🏃{data.avg_speed.toFixed(1)}m/s</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Collision Alert */}
            {simData.stats.collisions > 0 && (
              <div className="p-3 bg-red-500 bg-opacity-20 border border-red-500 rounded-lg">
                <div className="flex items-center gap-2 text-red-400 font-bold">
                  <span className="text-lg">⚠️</span>
                  <span>Collisions: {simData.stats.collisions}</span>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Vehicle Tooltip */}
      {hoveredVehicle && (
        <div
          className="absolute z-20 pointer-events-none"
          style={{
            left: mousePos.x + 15,
            top: mousePos.y + 15,
          }}
        >
          <div className="bg-gray-800 p-3 rounded-lg text-sm shadow-2xl border border-cyan-500">
            <div className="font-bold text-cyan-400 mb-2">Vehicle {hoveredVehicle.id}</div>
            <div className="space-y-1 text-gray-300">
              <div><span className="text-gray-400">Type:</span> <span className="capitalize">{hoveredVehicle.type.replace('_', ' ')}</span></div>
              <div><span className="text-gray-400">Speed:</span> {hoveredVehicle.speed.toFixed(2)} m/s</div>
              <div><span className="text-gray-400">Road:</span> {hoveredVehicle.road_id}</div>
              <div><span className="text-gray-400">Lane:</span> {hoveredVehicle.lane_id}</div>
              <div><span className="text-gray-400">Waiting:</span> {hoveredVehicle.waiting_time.toFixed(1)}s</div>
              <div><span className="text-gray-400">CO₂:</span> {hoveredVehicle.co2.toFixed(2)} mg/s</div>
            </div>
          </div>
        </div>
      )}

      {/* Zoom Controls */}
      <div className="absolute bottom-4 right-4 z-10">
        <div className="bg-gray-900 bg-opacity-95 backdrop-blur-md rounded-xl border border-gray-700 shadow-xl overflow-hidden">
          <button
            onClick={() => {
              scale.current = Math.min(scale.current * 1.3, 5);
            }}
            className="w-12 h-12 flex items-center justify-center text-white hover:bg-gray-800 transition-colors border-b border-gray-700"
          >
            <span className="text-xl font-bold">+</span>
          </button>
          <div className="w-12 h-12 flex items-center justify-center text-gray-400 text-xs border-b border-gray-700">
            {scale.current.toFixed(1)}x
          </div>
          <button
            onClick={() => {
              scale.current = Math.max(scale.current / 1.3, 0.3);
            }}
            className="w-12 h-12 flex items-center justify-center text-white hover:bg-gray-800 transition-colors border-b border-gray-700"
          >
            <span className="text-xl font-bold">−</span>
          </button>
          <button
            onClick={() => {
              scale.current = 1;
              offset.current = { x: 0, y: 0 };
            }}
            className="w-12 h-12 flex items-center justify-center text-white hover:bg-gray-800 transition-colors"
            title="Reset view"
          >
            <span className="text-lg">🎯</span>
          </button>
        </div>
      </div>

      {/* Vehicle Type Legend */}
      <div className="absolute bottom-4 left-4 z-10">
        <div className="bg-gray-900 bg-opacity-95 backdrop-blur-md rounded-xl px-4 py-3 border border-gray-700 shadow-xl mb-2">
          <h3 className="text-gray-400 text-xs font-semibold uppercase tracking-wider mb-2">Vehicle Types</h3>
          <div className="space-y-1.5">
            <div className="flex items-center gap-2">
              <div className="w-4 h-4 rounded" style={{backgroundColor: '#3b82f6'}}></div>
              <span className="text-gray-300 text-xs">Car</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-4 h-4 rounded" style={{backgroundColor: '#10b981'}}></div>
              <span className="text-gray-300 text-xs">Regular Bus</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-4 h-4 rounded" style={{backgroundColor: '#fbbf24'}}></div>
              <span className="text-gray-300 text-xs">Olympic Shuttle</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-4 h-4 rounded" style={{backgroundColor: '#06b6d4'}}></div>
              <span className="text-gray-300 text-xs">Accessible</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-4 h-4 rounded" style={{backgroundColor: '#ef4444'}}></div>
              <span className="text-gray-300 text-xs">Emergency</span>
            </div>
          </div>
        </div>
        <div className="bg-gray-900 bg-opacity-95 backdrop-blur-md rounded-xl px-4 py-3 border border-gray-700 shadow-xl">
          <div className="text-gray-400 text-xs space-y-1">
            <div><span className="text-white">🖱️ Drag:</span> Pan view</div>
            <div><span className="text-white">🔍 Scroll:</span> Zoom in/out</div>
            <div><span className="text-white">👆 Hover:</span> Vehicle info</div>
          </div>
        </div>
      </div>

      {/* Top Center Controls */}
      <div className="absolute top-4 left-1/2 transform -translate-x-1/2 z-10 flex gap-3">
        {/* Simulation Controls - Always Visible */}
        {simData && (
          <div className="bg-gray-900 bg-opacity-95 backdrop-blur-md rounded-xl border border-gray-700 shadow-xl flex items-center gap-2 px-3 py-2">
            {!simulationPaused ? (
              <button
                onClick={pauseSimulation}
                className="bg-yellow-600 hover:bg-yellow-700 text-white px-4 py-1.5 rounded-lg transition-colors font-medium text-sm"
                title="Pause Simulation"
              >
                ⏸️ Pause
              </button>
            ) : (
              <button
                onClick={resumeSimulation}
                className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-1.5 rounded-lg transition-colors font-medium text-sm"
                title="Resume Simulation"
              >
                ▶️ Resume
              </button>
            )}
            <button
              onClick={restartSimulation}
              className="bg-orange-600 hover:bg-orange-700 text-white px-4 py-1.5 rounded-lg transition-colors font-medium text-sm"
              title="Restart Simulation"
            >
              🔄 Restart
            </button>
            <button
              onClick={stopSimulation}
              className="bg-red-600 hover:bg-red-700 text-white px-4 py-1.5 rounded-lg transition-colors font-medium text-sm"
              title="Stop Simulation"
            >
              ⏹️ Stop
            </button>
          </div>
        )}
        
        {/* AI Control Panel Toggle */}
        <button
          onClick={() => setShowControls(!showControls)}
          className="bg-purple-600 hover:bg-purple-700 text-white px-6 py-2.5 rounded-xl border border-purple-500 shadow-xl transition-all font-semibold flex items-center gap-2"
        >
          <span>🤖</span>
          <span>AI Controls</span>
          <span className="text-xs opacity-75">{showControls ? '▼' : '▶'}</span>
        </button>
      </div>

      {/* Control Panel Modal */}
      {showControls && (
        <div className="absolute top-20 left-1/2 transform -translate-x-1/2 z-20 w-[600px] max-h-[calc(100vh-120px)] overflow-y-auto">
          <div className="bg-gray-900 bg-opacity-98 backdrop-blur-md rounded-xl p-6 border border-purple-500 shadow-2xl">
            {/* Header */}
            <div className="flex items-center justify-between mb-6 pb-4 border-b border-gray-700">
              <h2 className="text-white font-bold text-xl flex items-center gap-2">
                <span>🤖</span>
                <span>Traffic Control System</span>
              </h2>
              <button
                onClick={() => setShowControls(false)}
                className="text-gray-400 hover:text-white text-2xl"
              >
                ×
              </button>
            </div>

            {/* Status Message */}
            {apiStatus && (
              <div className={`mb-4 p-3 rounded-lg ${
                apiStatus.includes('Error') 
                  ? 'bg-red-900 bg-opacity-50 border border-red-500 text-red-300'
                  : 'bg-green-900 bg-opacity-50 border border-green-500 text-green-300'
              }`}>
                {apiStatus}
              </div>
            )}

            {/* AI Toggle */}
            <div className="mb-6 p-4 bg-gray-800 bg-opacity-50 rounded-lg border border-gray-700">
              <div className="flex items-center justify-between mb-2">
                <h3 className="text-white font-semibold text-lg">AI Predictions</h3>
                <button
                  onClick={toggleAI}
                  className={`relative w-14 h-7 rounded-full transition-colors ${
                    aiEnabled ? 'bg-green-500' : 'bg-gray-600'
                  }`}
                >
                  <div className={`absolute top-0.5 left-0.5 w-6 h-6 bg-white rounded-full transition-transform ${
                    aiEnabled ? 'transform translate-x-7' : ''
                  }`}></div>
                </button>
              </div>
              <p className="text-gray-400 text-sm">
                {aiEnabled ? '✅ AI predictions enabled' : '⚠️ Using traditional timing'}
              </p>
            </div>

            {/* Priority Weights */}
            <div className="mb-6 p-4 bg-gray-800 bg-opacity-50 rounded-lg border border-gray-700">
              <h3 className="text-white font-semibold text-lg mb-4">Priority Weights</h3>
              <div className="space-y-3">
                {Object.entries(priorities).map(([key, value]) => (
                  <div key={key}>
                    <div className="flex items-center justify-between mb-1">
                      <label className="text-gray-300 text-sm capitalize">
                        {key.replace('_', ' ')}
                      </label>
                      <input
                        type="number"
                        value={value}
                        onChange={(e) => setPriorities({...priorities, [key]: parseFloat(e.target.value) || 0})}
                        className="w-20 px-2 py-1 bg-gray-700 text-white rounded border border-gray-600 text-sm"
                        step="0.1"
                      />
                    </div>
                    <input
                      type="range"
                      min="0"
                      max="20"
                      step="0.1"
                      value={value}
                      onChange={(e) => setPriorities({...priorities, [key]: parseFloat(e.target.value)})}
                      className="w-full"
                    />
                  </div>
                ))}
              </div>
              <button
                onClick={updatePriorities}
                className="mt-4 w-full bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg transition-colors font-medium"
              >
                Apply Priority Weights
              </button>
            </div>

            {/* Detection Range */}
            <div className="mb-6 p-4 bg-gray-800 bg-opacity-50 rounded-lg border border-gray-700">
              <h3 className="text-white font-semibold text-lg mb-4">Detection Range</h3>
              <div className="flex items-center justify-between mb-2">
                <label className="text-gray-300 text-sm">Distance (meters)</label>
                <input
                  type="number"
                  value={detectionRange}
                  onChange={(e) => setDetectionRange(parseInt(e.target.value) || 0)}
                  className="w-24 px-2 py-1 bg-gray-700 text-white rounded border border-gray-600"
                />
              </div>
              <input
                type="range"
                min="50"
                max="500"
                step="10"
                value={detectionRange}
                onChange={(e) => setDetectionRange(parseInt(e.target.value))}
                className="w-full mb-4"
              />
              <button
                onClick={updateDetection}
                className="w-full bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg transition-colors font-medium"
              >
                Apply Detection Range
              </button>
            </div>

            {/* Timing Parameters */}
            <div className="mb-6 p-4 bg-gray-800 bg-opacity-50 rounded-lg border border-gray-700">
              <h3 className="text-white font-semibold text-lg mb-4">Timing Parameters</h3>
              <div className="space-y-3">
                <div>
                  <div className="flex items-center justify-between mb-1">
                    <label className="text-gray-300 text-sm">Min Green (seconds)</label>
                    <input
                      type="number"
                      value={timing.min_green}
                      onChange={(e) => setTiming({...timing, min_green: parseInt(e.target.value) || 0})}
                      className="w-20 px-2 py-1 bg-gray-700 text-white rounded border border-gray-600 text-sm"
                    />
                  </div>
                  <input
                    type="range"
                    min="5"
                    max="30"
                    value={timing.min_green}
                    onChange={(e) => setTiming({...timing, min_green: parseInt(e.target.value)})}
                    className="w-full"
                  />
                </div>
                <div>
                  <div className="flex items-center justify-between mb-1">
                    <label className="text-gray-300 text-sm">Max Green (seconds)</label>
                    <input
                      type="number"
                      value={timing.max_green}
                      onChange={(e) => setTiming({...timing, max_green: parseInt(e.target.value) || 0})}
                      className="w-20 px-2 py-1 bg-gray-700 text-white rounded border border-gray-600 text-sm"
                    />
                  </div>
                  <input
                    type="range"
                    min="30"
                    max="120"
                    value={timing.max_green}
                    onChange={(e) => setTiming({...timing, max_green: parseInt(e.target.value)})}
                    className="w-full"
                  />
                </div>
                <div>
                  <div className="flex items-center justify-between mb-1">
                    <label className="text-gray-300 text-sm">Extension (seconds)</label>
                    <input
                      type="number"
                      value={timing.extension}
                      onChange={(e) => setTiming({...timing, extension: parseInt(e.target.value) || 0})}
                      className="w-20 px-2 py-1 bg-gray-700 text-white rounded border border-gray-600 text-sm"
                    />
                  </div>
                  <input
                    type="range"
                    min="1"
                    max="20"
                    value={timing.extension}
                    onChange={(e) => setTiming({...timing, extension: parseInt(e.target.value)})}
                    className="w-full"
                  />
                </div>
              </div>
              <button
                onClick={updateTiming}
                className="mt-4 w-full bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg transition-colors font-medium"
              >
                Apply Timing Parameters
              </button>
            </div>

            {/* Action Buttons */}
            <div className="grid grid-cols-2 gap-3">
              <button
                onClick={fetchConfig}
                className="bg-cyan-600 hover:bg-cyan-700 text-white px-4 py-2.5 rounded-lg transition-colors font-medium"
              >
                🔄 Fetch Config
              </button>
              <button
                onClick={resetConfig}
                className="bg-orange-600 hover:bg-orange-700 text-white px-4 py-2.5 rounded-lg transition-colors font-medium"
              >
                ↺ Reset to Default
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Loading State / Simulation Control */}
      {!simData && connected && (
        <div className="absolute inset-0 flex items-center justify-center z-20 bg-gray-900 bg-opacity-80 backdrop-blur-sm">
          <div className="bg-gray-800 rounded-xl p-8 border border-cyan-500 shadow-2xl max-w-md">
            <div className="flex flex-col items-center gap-6">
              {networkData && (
                <div className="text-green-400 text-sm">
                  ✓ Network loaded ({networkData.roads.length} roads)
                </div>
              )}
              
              {!simulationRunning ? (
                <>
                  <div className="text-cyan-400 text-xl font-bold">Simulation Ready</div>
                  <div className="text-gray-400 text-sm text-center">
                    Press start to begin the traffic simulation
                  </div>
                  <button
                    onClick={startSimulation}
                    className="bg-green-600 hover:bg-green-700 text-white px-8 py-3 rounded-lg transition-colors font-bold text-lg shadow-lg"
                  >
                    ▶️ Start Simulation
                  </button>
                </>
              ) : (
                <>
                  <div className="w-16 h-16 border-4 border-cyan-500 border-t-transparent rounded-full animate-spin"></div>
                  <div className="text-cyan-400 text-xl font-bold">
                    {simulationPaused ? 'Simulation Paused' : 'Starting Simulation'}
                  </div>
                  <div className="text-gray-400 text-sm">
                    {simulationPaused ? 'Press resume to continue...' : 'Waiting for SUMO data...'}
                  </div>
                  
                  <div className="flex gap-3 mt-2">
                    {simulationPaused ? (
                      <button
                        onClick={resumeSimulation}
                        className="bg-blue-600 hover:bg-blue-700 text-white px-6 py-2 rounded-lg transition-colors font-medium"
                      >
                        ▶️ Resume
                      </button>
                    ) : (
                      <button
                        onClick={pauseSimulation}
                        className="bg-yellow-600 hover:bg-yellow-700 text-white px-6 py-2 rounded-lg transition-colors font-medium"
                      >
                        ⏸️ Pause
                      </button>
                    )}
                    <button
                      onClick={restartSimulation}
                      className="bg-orange-600 hover:bg-orange-700 text-white px-6 py-2 rounded-lg transition-colors font-medium"
                    >
                      🔄 Restart
                    </button>
                    <button
                      onClick={stopSimulation}
                      className="bg-red-600 hover:bg-red-700 text-white px-6 py-2 rounded-lg transition-colors font-medium"
                    >
                      ⏹️ Stop
                    </button>
                  </div>
                </>
              )}
              
              {apiStatus && (
                <div className="text-gray-300 text-sm mt-2 px-4 py-2 bg-gray-700 rounded">
                  {apiStatus}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Disconnected Overlay */}
      {!connected && (
        <div className="absolute inset-0 flex items-center justify-center z-20 bg-gray-900 bg-opacity-80 backdrop-blur-sm">
          <div className="bg-gray-800 rounded-xl p-8 border border-red-500 shadow-2xl">
            <div className="flex flex-col items-center gap-4">
              <div className="text-red-400 text-6xl">⚠️</div>
              <div className="text-red-400 text-xl font-bold">Connection Lost</div>
              <div className="text-gray-400 text-sm">Attempting to reconnect...</div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// Helper Components
function StatCard({ label, value, color, icon }: { label: string; value: number | string; color: string; icon: string }) {
  return (
    <div className="bg-gray-800 bg-opacity-50 rounded-lg p-3">
      <div className="flex items-center justify-between mb-1">
        <span className="text-gray-400 text-xs">{label}</span>
        <span className="text-lg">{icon}</span>
      </div>
      <div className={`${color} font-mono font-bold text-2xl`}>{value}</div>
    </div>
  );
}

function LegendItem({ color, label }: { color: string; label: string }) {
  return (
    <div className="flex items-center gap-2">
      <div 
        className="w-4 h-4 rounded-full border-2 border-white shadow-lg" 
        style={{ background: color, boxShadow: `0 0 10px ${color}` }}
      ></div>
      <span className="text-gray-300 text-xs">{label}</span>
    </div>
  );
}
