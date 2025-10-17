# save as verify_obs_actions.py in lovelyHackathon/
import gymnasium as gym
import sumo_rl
import traci

ENV_KW = dict(
    net_file='local_sumo/net/mini.net.xml',
    route_file='local_sumo/routes/mini.rou.xml',
    use_gui=False,
    num_seconds=120,
    delta_time=5,   # one RL decision every 5s
)

def phase_info(tls_id):
    p = traci.trafficlight.getPhase(tls_id)  # numeric phase (includes yellow steps)
    t_now = traci.simulation.getTime()
    t_next = traci.trafficlight.getNextSwitch(tls_id)
    rem = max(0.0, t_next - t_now)
    return p, rem

env = gym.make('sumo-rl-v0', **ENV_KW)
obs, info = env.reset()
print("Initial obs shape:", getattr(obs, "shape", type(obs)))
tls_ids = traci.trafficlight.getIDList()
assert tls_ids, "No traffic signals found in this net. Rebuild the net with a TLS."
tls = tls_ids[0]
print("TLS IDs:", tls_ids)
print("Action space:", env.action_space)

print("Initial phase:", phase_info(tls))
# Add this tiny print to the top of the loop if you want to see the obs evolve:
print("Obs min/max:", float(obs.min()), float(obs.max()))

# Try 'extend': take the SAME action twice
a_extend = 0
for i in range(2):
    obs, r, term, trunc, inf = env.step(a_extend)
    print(f"[extend] step {i} action={a_extend} -> phase={phase_info(tls)}, reward={r}, term={term}")
    if term or trunc:
        break

# Try 'switch': pick a different action index
if hasattr(env.action_space, "n"):
    a_switch = (a_extend + 1) % env.action_space.n
else:
    a_switch = 1  # fallback

obs, r, term, trunc, inf = env.step(a_switch)
print(f"[switch] action={a_switch} -> phase={phase_info(tls)}, reward={r}, term={term}")

env.close()
print("Done.")