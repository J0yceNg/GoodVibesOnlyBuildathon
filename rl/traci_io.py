from rl.env import SumoSignalEnv
env = SumoSignalEnv("sumo/cfg/olympic.sumocfg", "tls_0", ["lane_0","lane_1","lane_2","lane_3"])
obs, _ = env.reset()
for _ in range(6):
    obs, r, term, trunc, info = env.step(0)
    print(obs.shape, r, term)
    if term: break
env.close()