from rl.env import SumoSignalEnv

# Define the SUMO cfg and lanes
cfg_path = "sumo/cfg/olympic.sumocfg"
tls_id = "tls_0"
lane_ids = ["lane_0", "lane_1", "lane_2", "lane_3"]

env = SumoSignalEnv(cfg_path, tls_id, lane_ids, decision_dt=5)

obs, _ = env.reset()
print("Initial observation:", obs)

# Run 10 simulation steps: alternate actions 0 and 1
for i in range(10):
    action = i % 2
    obs, reward, done, trunc, info = env.step(action)
    print(f"Step {i} | Action: {action} | Obs shape: {obs.shape} | Reward: {reward}")
    if done:
        print("Simulation ended early.")
        break

env.close()
print("Test complete.")