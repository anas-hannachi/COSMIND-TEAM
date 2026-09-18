from pmars_simulation.actions import Action
from pmars_simulation.core.task import Task
from pmars_simulation.environment.communication import CommunicationModel, ContactWindow
from pmars_simulation.scenarios import build_simulation

def test_task_value_decays_and_validates():
    t=Task("a","science",1,1,2,3,.5,1,10,30,0,.1)
    assert t.value_at(10) < t.mission_value

def test_communication_rejects_contact_overrun():
    c=CommunicationModel((ContactWindow(10,20,1,1,100),))
    assert c.feasible(1,19) is False
    assert c.transfer_time(1,10) == 8.1

def test_three_actions_change_state():
    sim=build_simulation("normal","rule",1)
    sim.run(250)
    actions={row["action"] for row in sim.history}
    assert Action.STORE.value in actions
    assert sim.satellite.time_s >= 250
    assert sim.energy_consumed_j > 0

def test_seed_reproducibility():
    a=build_simulation("normal","predictive",7); b=build_simulation("normal","predictive",7)
    assert a.run(300) == b.run(300)

def test_all_scenarios_run():
    for name in ("normal","low_energy","poor_link","task_burst","critical"):
        sim=build_simulation(name,"greedy",3); assert sim.run(100)
