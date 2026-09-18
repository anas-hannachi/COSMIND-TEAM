from __future__ import annotations
import argparse, csv
from pathlib import Path
from .metrics import calculate
from ..scenarios import build_simulation
def run(scenarios=("normal","low_energy","poor_link","task_burst","critical"), schedulers=("random","rule","greedy","predictive"), seeds=range(10), output="results"):
    rows=[]
    for scenario in scenarios:
      for scheduler in schedulers:
       for seed in seeds:
        sim=build_simulation(scenario,scheduler,seed); sim.run(3600); rows.append({"scenario":scenario,"scheduler":scheduler,"seed":seed,**calculate(sim)})
    out=Path(output); out.mkdir(parents=True,exist_ok=True)
    with (out / "raw_results.csv").open("w", newline="") as f:
        writer=csv.DictWriter(f, fieldnames=rows[0].keys()); writer.writeheader(); writer.writerows(rows)
    return rows
if __name__ == "__main__":
 p=argparse.ArgumentParser(); p.add_argument("--seeds",type=int,default=10); p.add_argument("--output",default="results"); a=p.parse_args(); run(seeds=range(a.seeds),output=a.output)
