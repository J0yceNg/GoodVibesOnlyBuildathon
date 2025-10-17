#!/usr/bin/env python3
"""
FairLane - Dynamic Transit Lane Optimizer
AI-powered traffic signal priority system for Olympic corridor
"""

import traci
import sys
import time
import asyncio
from collections import defaultdict
from datetime import datetime, timedelta
from shared_config import live_config
from fairlane.prediction.predictor import TrafficPredictor  
from fairlane.rl.agent import RLAgent                      


class FairLaneController:
    """
    Traffic signal controller with LIVE CONTROLS
    """
    def __init__(self, policy_mode: str = "ensemble", rl_ckpt: str | None = None):
        # Traffic light IDs
        self.traffic_lights = []
        self.stats = {
            'total_vehicles': 0,
            'priority_vehicles_served': defaultdict(int),
            'avg_waiting_time': defaultdict(list),
            'signal_extensions': 0,
            'ai_preemptive_actions': 0,
            'predictions_made': 0,
            'high_congestion_prevented': 0
        }
        
        # Callback for broadcasting updates (set by server)
        self.broadcast_callback = None

        # === Prediction model (Adapter) ===
        try:
            self.predictor = TrafficPredictor(model_path="traffic_predictor_model.pkl")
            self.use_prediction = True
            print("✓ AI Prediction Model loaded successfully")
        except Exception as e:
            self.predictor = None
            self.use_prediction = False
            print(f"⚠ Running without AI prediction model: {e}")

        # === RL Agent ===
        self.policy_mode = policy_mode              # "rules_only" | "rl_only" | "ensemble"
        try:
            self.rl_agent = RLAgent(checkpoint=rl_ckpt, use_flags=True)
            print("✓ RL Agent loaded")
        except Exception as e:
            # Safe fallback: disable RL if loading fails
            self.rl_agent = None
            if self.policy_mode != "rules_only":
                print(f"⚠ RL unavailable ({e}); falling back to rules_only")
                self.policy_mode = "rules_only"

        # Ensemble voting weights
        self._w_A = 2.0          # predictor vote
        self._w_B = 3.0          # RL vote
        self._w_PRIORITY = 10.0  # hard override

        self.simulation_start_time = datetime(2025, 10, 17, 8, 0, 0)
        self.prediction_history = []

    def get_vehicle_type(self, vehicle_id):
        """Get the type of vehicle for priority calculation"""
        try:
            vtype = traci.vehicle.getTypeID(vehicle_id)
            return vtype
        except:
            return 'car'
    
    def get_priority_score(self, vehicle_id):
        """Calculate priority score for a vehicle - NOW USES LIVE CONFIG"""
        vtype = self.get_vehicle_type(vehicle_id)
        return live_config.get_priority_weight(vtype)  # CHANGED: Read from config
    
    def get_current_datetime(self, simulation_step):
        """Convert simulation step (seconds) to datetime"""
        return self.simulation_start_time + timedelta(seconds=simulation_step)
    
    def get_vehicle_count_at_intersection(self, tl_id):
        """Count vehicles approaching this traffic light"""
        controlled_lanes = traci.trafficlight.getControlledLanes(tl_id)
        total_vehicles = 0
        
        for lane in set(controlled_lanes):
            try:
                total_vehicles += traci.lane.getLastStepVehicleNumber(lane)
            except:
                continue
        
        return total_vehicles

    def predict_congestion_at_intersection(self, tl_id, step):
        if not live_config.is_ai_enabled() or not self.use_prediction or self.predictor is None:
            return None, None
        try:
            current_time = self.get_current_datetime(step)
            vehicle_count = self.get_vehicle_count_at_intersection(tl_id)
            pred = self.predictor.predict_congestion(
                tl_id, step, horizon_s=900,
                context={"current_time": current_time, "vehicle_count": vehicle_count}
            )
            print(f"[DEBUG] {tl_id} step {step} predicted:", pred)  
            
            prob = float(pred.get("congestion_prob", 0.0))
            if   prob >= 0.70: level = "SEVERE"
            elif prob >= 0.55: level = "HEAVY"
            elif prob >= 0.30: level = "MEDIUM"
            else:              level = "LOW"

            self.prediction_history.append({
                'step': step, 'time': current_time, 'intersection': tl_id,
                'prediction': prob, 'level': level, 'vehicle_count': vehicle_count
            })
            self.stats['predictions_made'] += 1
            return prob, level
        except Exception as e:
            print(f"[{tl_id}] Prediction error: {e}")
            return None, None

    def detect_priority_vehicles(self, tl_id):
        """
        Detect priority vehicles - NOW USES LIVE DETECTION DISTANCE
        """
        controlled_lanes = traci.trafficlight.getControlledLanes(tl_id)
        
        priority_vehicles = []
        max_priority = 0
        vehicle_types = []
        
        # Get detection distance from live config
        detection_distance = live_config.get_detection_distance()
        
        for lane in set(controlled_lanes):
            vehicles_on_lane = traci.lane.getLastStepVehicleIDs(lane)
            
            for veh_id in vehicles_on_lane:
                try:
                    pos = traci.vehicle.getLanePosition(veh_id)
                    lane_length = traci.lane.getLength(lane)
                    distance_to_light = lane_length - pos
                    
                    # CHANGED: Use live config detection distance
                    if distance_to_light <= detection_distance:
                        priority = self.get_priority_score(veh_id)
                        vtype = self.get_vehicle_type(veh_id)
                        
                        if priority > 1.0:
                            priority_vehicles.append((veh_id, priority, vtype))
                            max_priority = max(max_priority, priority)
                            vehicle_types.append(vtype)
                            
                except traci.exceptions.TraCIException:
                    continue
        
        has_priority = len(priority_vehicles) > 0
        return has_priority, max_priority, vehicle_types
    
    def control_signal(self, tl_id, current_phase, time_in_phase, step):
        """
        AI-Enhanced signal control with optional RL/ensemble.
        """

        # --- Priority vehicle detection (your existing logic) ---
        has_priority, priority_score, vehicle_types = self.detect_priority_vehicles(tl_id)

        # --- Prediction (adapter) ---
        predicted_congestion, congestion_level = self.predict_congestion_at_intersection(tl_id, step)
        if predicted_congestion is not None and step % 300 == 0:
            print(f"[AI PREDICTION] {tl_id}: {congestion_level} in 15min ({predicted_congestion:.2f})")

        # --- Your rule-based decision (kept as-is) ---
        should_extend = False
        decision_reason = None
        max_green_time = live_config.get_max_green_time()

        # Priority rule
        if has_priority:
            if 'emergency' in vehicle_types:
                print(f"[{tl_id}] EMERGENCY vehicle detected - extending green")
                self.stats['priority_vehicles_served']['emergency'] += 1
                self.stats['signal_extensions'] += 1
                should_extend = True
                decision_reason = "emergency_vehicle"

            elif 'accessible_vehicle' in vehicle_types:
                print(f"[{tl_id}] ACCESSIBLE vehicle detected - extending green")
                self.stats['priority_vehicles_served']['accessible_vehicle'] += 1
                self.stats['signal_extensions'] += 1
                should_extend = True
                decision_reason = "accessible_vehicle"

            elif 'olympic_shuttle' in vehicle_types:
                print(f"[{tl_id}] OLYMPIC shuttle detected - extending green")
                self.stats['priority_vehicles_served']['olympic_shuttle'] += 1
                self.stats['signal_extensions'] += 1
                should_extend = True
                decision_reason = "olympic_shuttle"

            elif 'regular_bus' in vehicle_types:
                if time_in_phase < max_green_time:
                    print(f"[{tl_id}] Bus detected - extending green")
                    self.stats['priority_vehicles_served']['regular_bus'] += 1
                    self.stats['signal_extensions'] += 1
                    should_extend = True
                    decision_reason = "regular_bus"

        # Predictor rule
        if not should_extend and predicted_congestion is not None:
            SEVERE_THRESHOLD = 0.70
            HEAVY_THRESHOLD = 0.55

            if predicted_congestion >= SEVERE_THRESHOLD:
                vehicle_count = self.get_vehicle_count_at_intersection(tl_id)
                print(f"[{tl_id}] 🤖 AI ALERT: Severe congestion predicted!")
                print(f"    Current: {vehicle_count} vehicles")
                print(f"    Forecast: {predicted_congestion:.2f} congestion level")
                print(f"    Action: Extending green phase preemptively")
                should_extend = True
                decision_reason = "ai_severe_prediction"
                self.stats['ai_preemptive_actions'] += 1
                self.stats['high_congestion_prevented'] += 1

            elif predicted_congestion >= HEAVY_THRESHOLD and time_in_phase < max_green_time - 10:
                vehicle_count = self.get_vehicle_count_at_intersection(tl_id)
                print(f"[{tl_id}] 🤖 AI: HEAVY congestion predicted ({predicted_congestion:.2f}) - minor extension")
                print(f"    Current vehicles: {vehicle_count}")
                should_extend = True
                decision_reason = "ai_heavy_prediction"
                self.stats['ai_preemptive_actions'] += 1

        # --- RL + Ensemble ---
        # Build RL state
        live_state = self._collect_live_state(tl_id, current_phase, time_in_phase, step, has_priority, vehicle_types)
        pred_prob = predicted_congestion if predicted_congestion is not None else 0.0
        rl_input = {
            **live_state,
            "pred_cong_prob": pred_prob,
            "pred_conf": 0.9 if predicted_congestion is not None else 0.0,
            "suggested_hold_s": 10.0 if pred_prob > 0.8 else 0.0
        }

        rl_action = {"action": "normal", "hold_s": 0.0, "policy_id": "none"}
        if self.rl_agent is not None:
            try:
                rl_action = self.rl_agent.get_action(rl_input)
            except Exception as e:
                print(f"[{tl_id}] RL error: {e}")

        # Priority override (hard)
        hard_override = self._priority_override(has_priority, vehicle_types)

        # Policy selection
        final_action = "normal"
        hold_s = rl_action.get("hold_s", 0.0)

        if self.policy_mode == "rules_only":
            final_action = "extend" if should_extend else "normal"

        elif self.policy_mode == "rl_only":
            final_action = rl_action["action"]

        else:  # ensemble
            votes = {"extend": 0.0, "shorten": 0.0, "switch": 0.0, "hold": 0.0, "normal": 0.0}
            # A's vote (predictor)
            if pred_prob > 0.8:
                votes["extend"] += self._w_A
            elif pred_prob < 0.2:
                votes["normal"] += self._w_A
            # Rule decision contributes as a soft vote too
            if should_extend:
                votes["extend"] += self._w_A

            # B's vote (RL)
            votes[rl_action["action"]] += self._w_B

            # Priority override
            if hard_override:
                votes[hard_override] += self._w_PRIORITY

            final_action = max(votes, key=votes.get)

            # default hold seconds when extending
            if final_action == "extend" and hold_s <= 0.0:
                hold_s = 10.0 if pred_prob > 0.8 else 5.0

        # --- Logging (keeps your existing decision list) ---
        if not hasattr(self, 'decision_log'):
            self.decision_log = []
        self.decision_log.append({
            'step': step,
            'intersection': tl_id,
            'reason': decision_reason or "none",
            'prediction': predicted_congestion,
            'had_priority': has_priority,
            'rl_action': rl_action.get("action"),
            'final_action': final_action
        })

        # Return a boolean to the caller (extend or not) to minimize changes where you apply it
        return final_action in ("extend", "hold")
    
    def _collect_live_state(self, tl_id: str, current_phase: int, time_in_phase: int, step: int,
                        had_priority: bool, vehicle_types: list[str]) -> dict:
        """Build a consistent snapshot of live features for RL."""
        queues = {}   # If you have lane-wise queues, fill them; else keep totals only.
        try:
            controlled_lanes = traci.trafficlight.getControlledLanes(tl_id)
            for ln in set(controlled_lanes):
                queues[ln] = traci.lane.getLastStepVehicleNumber(ln)
        except:
            pass

        vmix = defaultdict(int)
        for vt in vehicle_types:
            vmix[vt] += 1

        return {
            "tl_id": tl_id,
            "phase": current_phase,
            "time_in_phase": time_in_phase,
            "q_total": sum(queues.values()) if queues else self.get_vehicle_count_at_intersection(tl_id),
            "vehicle_mix": dict(vmix),
            "flag_emerg": int('emergency' in vehicle_types),
            "flag_access": int('accessible_vehicle' in vehicle_types),
            "flag_olympic": int('olympic_shuttle' in vehicle_types),
            "is_rush_hour": int(self._is_rush_hour(step)) if hasattr(self, "_is_rush_hour") else 0
        }

    def _priority_override(self, had_priority: bool, vehicle_types: list[str]) -> str | None:
        """Hard safety rule: emergency/accessible forces extend."""
        if not had_priority:
            return None
        if 'emergency' in vehicle_types or 'accessible_vehicle' in vehicle_types:
            return "extend"
        return None

    def run_simulation(self, gui=True, api_mode=False):
        """
        Main simulation loop with start/stop/restart control
        """
        
        sumoBinary = "sumo-gui" if gui else "sumo"
        # Add --step-length 0 for maximum speed, --delay 0 for no GUI delay
        sumoCmd = [sumoBinary, "-c", "olympic_corridor.sumocfg", 
                   "--step-length", "1",  # Smaller time steps = faster progression
                   "--delay", "0"]  # No delay between steps in GUI
        
        if not gui:
            # When running without GUI, add --no-step-log for even faster execution
            sumoCmd.extend(["--no-step-log", "true"])
        
        print("=" * 60)
        print("FairLane Dynamic Transit Lane Optimizer")
        print("🎮 LIVE CONTROL MODE ENABLED")
        print("⚡ MAXIMUM SPEED MODE")
        print("=" * 60)
        
        if api_mode:
            print("\n⏳ Waiting for START signal from dashboard...")
            print("   Dashboard can start simulation via POST /api/simulation/start")
            
            # Wait for start signal
            while not live_config.is_simulation_running():
                time.sleep(0.5)
                if live_config.should_simulation_stop():
                    print("❌ Simulation cancelled before start")
                    return
            
            print("✓ START signal received!")
        else:
            # Auto-start if not in API mode
            live_config.start_simulation()
        
        # Start SUMO
        traci.start(sumoCmd)
        self.traffic_lights = traci.trafficlight.getIDList()
        
        print(f"\nMonitoring {len(self.traffic_lights)} intersections")
        
        config = live_config.get_all_config()
        print("\nCurrent Configuration:")
        print(f"  AI Enabled: {config['ai_enabled']}")
        print(f"  Detection Range: {config['detection_distance']}m")
        print(f"  Min/Max Green: {config['timing']['min_green']}/{config['timing']['max_green']}s")
        print("\n" + "=" * 60 + "\n")
        
        tl_phase_start = {tl: 0 for tl in self.traffic_lights}
        step = 0
        
        try:
            while traci.simulation.getMinExpectedNumber() > 0:
                # Check for stop signal
                if live_config.should_simulation_stop():
                    print("\n🛑 STOP signal received - terminating simulation")
                    break
                
                # Check for restart signal
                if live_config.should_simulation_restart():
                    print("\n🔄 RESTART signal received")
                    traci.close()
                    time.sleep(1)
                    # Restart will be handled by wrapper
                    break
                
                # Handle pause
                while live_config.is_simulation_paused():
                    print("⏸️  Simulation paused...", end='\r')
                    time.sleep(0.5)
                    if live_config.should_simulation_stop():
                        break
                
                if live_config.should_simulation_stop():
                    break
                
                # No artificial delays - run at maximum speed
                # Speed control removed for fastest execution
                
                # Normal simulation step
                traci.simulationStep()
                step += 1
                
                # Update current step in config
                live_config.update_current_step(step)
                
                self.stats['total_vehicles'] = traci.vehicle.getIDCount()
                
                # Control each traffic light
                for tl_id in self.traffic_lights:
                    try:
                        current_phase = traci.trafficlight.getPhase(tl_id)
                        time_in_phase = step - tl_phase_start[tl_id]
                        
                        should_extend = self.control_signal(tl_id, current_phase, time_in_phase, step)
                        
                        min_green_time = live_config.get_min_green_time()
                        extension_time = live_config.get_extension_time()
                        
                        if should_extend and time_in_phase >= min_green_time:
                            programs = traci.trafficlight.getAllProgramLogics(tl_id)
                            if programs:
                                current_program = programs[0]
                                phases = list(current_program.phases)
                                
                                if current_phase < len(phases):
                                    phases[current_phase] = traci.trafficlight.Phase(
                                        phases[current_phase].duration + extension_time,
                                        phases[current_phase].state,
                                        phases[current_phase].minDur,
                                        phases[current_phase].maxDur
                                    )
                                    
                                    logic = traci.trafficlight.Logic(
                                        current_program.programID,
                                        current_program.type,
                                        current_program.currentPhaseIndex,
                                        phases
                                    )
                                    traci.trafficlight.setProgramLogic(tl_id, logic)
                        
                        new_phase = traci.trafficlight.getPhase(tl_id)
                        if new_phase != current_phase:
                            tl_phase_start[tl_id] = step
                            
                    except traci.exceptions.TraCIException:
                        continue
                
                # Broadcast updates to WebSocket clients (works in both API and auto-start mode)
                # Broadcasting every step for smooth real-time visualization
                if self.broadcast_callback:
                    try:
                        asyncio.run(self.broadcast_callback())
                    except Exception as e:
                        pass  # Silently fail if broadcast unavailable
                
                if step % 300 == 0:
                    self.print_statistics(step)
        
        finally:
            print("\n" + "=" * 60)
            print("Simulation Complete")
            print("=" * 60)
            self.print_final_statistics()
            traci.close()
            live_config.mark_simulation_stopped()
    
    def print_statistics(self, step):
        """Print current statistics"""
        print(f"\n--- Time: {step}s ({step//60} minutes) ---")
        print(f"Total vehicles in simulation: {self.stats['total_vehicles']}")
        print(f"Signal extensions: {self.stats['signal_extensions']}")
        
        # Show live config status
        print(f"AI Status: {'ENABLED' if live_config.is_ai_enabled() else 'DISABLED'}")
        
        if live_config.is_ai_enabled():
            print(f"AI predictions made: {self.stats['predictions_made']}")
            print(f"AI preemptive actions: {self.stats['ai_preemptive_actions']}")
        
        print("Priority vehicles served:")
        for vtype, count in self.stats['priority_vehicles_served'].items():
            weight = live_config.get_priority_weight(vtype)
            print(f"  {vtype}: {count} (weight: {weight}x)")
    
    # ... rest of your methods (print_final_statistics, save_prediction_data) remain the same ...

def main():
    """Main entry point with restart loop"""
    gui = True
    api_mode = False
    policy = "ensemble"
    rl_ckpt = None

    # Simple CLI
    #   --no-gui
    #   --api
    #   --policy {rules_only|rl_only|ensemble}
    #   --rl-ckpt path/to/checkpoint.pt
    args = sys.argv[1:]
    i = 0
    while i < len(args):
        a = args[i]
        if a == "--no-gui":
            gui = False
        elif a == "--api":
            api_mode = True
            print("🌐 API Mode: Simulation controlled by dashboard")
        elif a == "--policy" and i + 1 < len(args):
            policy = args[i+1]; i += 1
        elif a == "--rl-ckpt" and i + 1 < len(args):
            rl_ckpt = args[i+1]; i += 1
        i += 1

    while True:
        controller = FairLaneController(policy_mode=policy, rl_ckpt=rl_ckpt)
        controller.run_simulation(gui=gui, api_mode=api_mode)

        # Check if restart was requested
        if not live_config.should_simulation_restart():
            break

        print("\n🔄 Restarting simulation in 3 seconds...")
        live_config.should_restart = False  # Reset flag
        time.sleep(3)

    print("👋 FairLane terminated")

if __name__ == "__main__":
    main()