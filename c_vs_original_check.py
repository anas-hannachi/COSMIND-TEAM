# Run from repo root: python c_vs_original_check.py
# Compiles the C core, drives the ORIGINAL float simulator, and compares C decisions at every decision point.
# NOTE: truncates pending to 32 (the firmware bound). Needs tests/test_c_differential_fuzz.py ctypes structs.
import ctypes, tempfile, sys, collections
sys.path.insert(0,'.')
from tests.test_c_differential_fuzz import CContact, CTask, CState, CConfig, CDecision, _compile
from pmars_simulation.contract.from_sim import contract_state as _contract_state
from pmars_simulation.contract.from_sim import contract_task as _contract_task
from pmars_simulation.scenarios import build_simulation, generate_tasks, load_config
from pmars_simulation.contract.models import ContractConfig
names={0:"IDLE",1:"PROCESS",2:"STORE",3:"TRANSMIT"}
tmp=tempfile.mkdtemp(); core=_compile(tmp)
def run(sc, sch, seed, tot):
    cfg=load_config(sc); sim=build_simulation(sc,sch,seed,tasks=generate_tasks(cfg,seed))
    orig=sim.scheduler.decide; cc=ContractConfig()
    def wrap(snap,pending,s):
        st=_contract_state(s)
        ts=sorted((_contract_task(r) for r in pending), key=lambda t: (t.deadline_ms, -t.priority, -t.value_milli, t.id.encode()))[:32]
        cs=CState(st.now_ms,st.energy_mj,st.storage_used_bytes,st.storage_total_bytes,st.memory_available_bytes,
                  st.compute_capacity_milli,st.throttle_fraction_milli,st.processing_power_mw,st.transmit_power_mw,
                  st.idle_power_mw,st.drain_horizon_ms); cs.contact_count=len(st.contacts)
        for i,c in enumerate(st.contacts): cs.contacts[i]=CContact(*c)
        arr=(CTask*max(1,len(ts)))()
        for i,t in enumerate(ts):
            a=arr[i]; a.id=t.id.encode(); a.input_bytes=t.input_bytes; a.payload_bytes=t.payload_bytes or 0
            a.output_bytes_est=t.output_bytes_est; a.actual_output_bytes=-1; a.mem_req_bytes=t.mem_req_bytes
            a.demand_milli=t.demand_milli; a.base_proc_ms=t.base_proc_ms; a.priority=t.priority
            a.value_milli=t.value_milli; a.created_ms=t.created_ms; a.deadline_ms=t.deadline_ms; a.processed=int(t.processed)
        out=CDecision(); ccfg=CConfig(cc.store_horizon_ms,cc.urgent_slack_ms)
        assert core.pmars_decide(ctypes.byref(cs),arr,len(ts),ctypes.byref(ccfg),int(sch=="rule"),ctypes.byref(out))==0
        bounded_ids={t.id for t in ts}; feasible=s.feasible_pairs
        s.feasible_pairs=lambda: [pair for pair in feasible() if pair[0].task.id in bounded_ids]
        bounded_pending=[r for r in pending if r.task.id in bounded_ids]
        try: d=orig(snap,bounded_pending,s)
        finally: s.feasible_pairs=feasible
        tot["n"]+=1
        tot["act"][d.action.value]+=1
        if (names[out.action], out.task_id.decode() or None)!=(d.action.value,d.task_id): tot["bad"]+=1
        return d
    sim.scheduler.decide=wrap; sim.run(cfg["mission_duration_s"])
for sc in ("bench_normal","bench_burst","bench_low_energy","bench_poor_link","normal","thermal_burst_stress","low_energy"):
    for sch in ("edf","rule"):
        tot={"n":0,"bad":0,"act":collections.Counter()}
        for seed in (104,105): run(sc,sch,seed,tot)
        print(f"{sc:22s}{sch:5s} decisions={tot['n']:5d}  C-vs-ORIGINAL-float-sim mismatches={tot['bad']}  actions={dict(tot['act'])}")
