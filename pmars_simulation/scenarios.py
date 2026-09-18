from __future__ import annotations
import random
from pathlib import Path
import yaml
from .core.task import Task
from .core.satellite import Satellite
from .core.simulation import Simulation
from .environment import EnergyModel, ComputeModel, ThermalModel, StorageModel, CommunicationModel, ContactWindow
from .schedulers import RandomScheduler, RuleScheduler, GreedyScheduler, PredictiveScheduler

ROOT=Path(__file__).resolve().parent.parent
def load_config(name: str) -> dict:
    with (ROOT / "scenarios" / f"{name}.yaml").open() as f: return yaml.safe_load(f)
def generate_tasks(config: dict, seed: int) -> list[Task]:
    rng=random.Random(seed); t=0.; out=[]; duration=config["mission_duration_s"]; w=config["workload"]
    kinds=[("telemetry",3,1,.2,.10), ("earth_image",40,5,.7,.03), ("emergency",12,9,.9,.80), ("science_image",80,4,.5,.005)]
    while t < duration:
        t += rng.uniform(*w["interarrival_s"])
        if t >= duration: break
        typ,size,priority,ratio,decay=rng.choice(kinds)
        critical=rng.random()<w["critical_probability"]
        if critical: typ,priority,decay="emergency",9,.80
        size*=rng.uniform(.7,1.3); base=max(2,size*.25); deadline=t+rng.uniform(*w["deadline_s"])
        out.append(Task(f"{seed}-{len(out)}",typ,size,size/10,base,45*base,size*ratio,priority,size*priority,deadline,t,decay))
    return out
def build_simulation(name: str, scheduler_name: str, seed: int) -> Simulation:
    c=load_config(name); e=c["energy"]; contacts=tuple(ContactWindow(**x) for x in c["contacts"])
    sched={"random":RandomScheduler(seed),"rule":RuleScheduler(),"greedy":GreedyScheduler(),"predictive":PredictiveScheduler()}[scheduler_name]
    return Simulation(Satellite(e["initial_energy_j"],e["capacity_j"],4096,c["storage_mb"]),EnergyModel(**{k:v for k,v in e.items() if k not in {"initial_energy_j"}}),ComputeModel(),ThermalModel(),StorageModel(c["storage_mb"]),CommunicationModel(contacts),sched,seed,c["sunlight_s"],c["eclipse_s"],generate_tasks(c,seed))
