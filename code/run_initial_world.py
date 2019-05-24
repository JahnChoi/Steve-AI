import sys
import time

try:
    from malmo import MalmoPython
except:
    import MalmoPython
import steve_agent
import json
import configparser
from ddqn import DQNAgent

config = configparser.ConfigParser()

# Create default Malmo objects:

agent_host = MalmoPython.AgentHost()
try:
    agent_host.parse(sys.argv)
except RuntimeError as e:
    print('ERROR:', e)
    print(agent_host.getUsage())
    exit(1)
if agent_host.receivedArgument("help"):
    print(agent_host.getUsage())
    exit(0)

with open('world.xml', 'r') as file:
    missionXML = file.read()

my_client_pool = MalmoPython.ClientPool()
my_client_pool.add(MalmoPython.ClientInfo('127.0.0.1', 10000))

EPISODES = 5000

state_size =  config.get('DEFAULT', 'STATE_SIZE')
action_size =  config.get('DEFAULT', 'ACTION_SIZE')
agent = DQNAgent(state_size, action_size)
done = False
batch_size = config.get('DEFAULT', 'BATCH_SIZE')

for repeat in range(EPISODES):
    my_mission = MalmoPython.MissionSpec(missionXML, True)
    my_mission_record = MalmoPython.MissionRecordSpec()

    # Attempt to start a mission:
    max_retries = 3
    for retry in range(max_retries):
        try:
            agent_host.startMission(my_mission, my_client_pool, my_mission_record, 0, "test")
            break
        except RuntimeError as e:
            if retry == max_retries - 1:
                print("Error starting mission:", e)
                exit(1)
            else:
                time.sleep(2)

    # Loop until mission starts:
    print("Waiting for the mission to start ", end=' ')
    world_state = agent_host.getWorldState()
    while not world_state.has_mission_begun:
        print(".", end="")
        time.sleep(2)
        world_state = agent_host.getWorldState()
        for error in world_state.errors:
            print("Error:", error.text)

    world_state_txt = world_state.observations[-1].text
    world_state_json = json.loads(world_state_txt)
    if len(world_state_json['entities']) > 2:
        # agent_host.sendCommand('chat /kill @e[type=Zombie,c=1]')
        agent_host.sendCommand('chat /kill @e[type=!minecraft:player]')

    print()
    print("Mission running ", end=' ')

    x = world_state_json['XPos']
    y = world_state_json['YPos']
    z = world_state_json['ZPos']
    agent_host.sendCommand('chat /summon zombie {} {} {}'.format(x+15, y, z))
    time.sleep(2)

    steve = steve_agent.Steve()
    # Loop until mission ends:

    # keep track if we've seeded the initial state
    have_initial_state = 0

    while world_state.is_mission_running:
        print(".", end="")
        time.sleep(0.1)
        world_state = agent_host.getWorldState()
        for error in world_state.errors:
            print("Error:", error.text)

        if world_state.number_of_observations_since_last_state > 0:
            msg = world_state.observations[-1].text
            ob = json.loads(msg)
            lock_on = steve.master_lock(ob, agent_host)

            # MAIN NN LOGIC
            # check if we've seeded initial state just for the first time
            if have_initial_state == 0:
                state = agent.get_state(ob)
                have_initial_state = 1

            action = agent.act(state)
            steve.perform_action(action) # send action to malmo
            reward = steve.get_reward(); # get reward
            next_state = steve.get_state(ob) # get next state
            done = False # mission is never one, keep done False
            reward = reward if not done else -10
            agent.remember(state, action, reward, next_state, done)
            state = next_state
            if done:
                agent.update_target_model()
                print("episode: {}/{}, score: {}, e: {:.2}"
                      .format(e, EPISODES, time, agent.epsilon))
                break
            if len(agent.memory) > batch_size:
                agent.replay(batch_size)
            # MAIN NN LOGIC

    print()
    print("Mission ended")
    # Mission has ended.
