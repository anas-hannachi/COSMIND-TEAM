import csv, statistics, math
from collections import defaultdict
def summarize(results_path: str) -> list[dict]:
    groups=defaultdict(list)
    with open(results_path, newline="") as f:
        for row in csv.DictReader(f): groups[(row["scenario"],row["scheduler"])].append(row)
    output=[]
    for (scenario,scheduler), rows in groups.items():
        numeric=[k for k in rows[0] if k not in {"scenario","scheduler","seed"}]
        result={"scenario":scenario,"scheduler":scheduler,"sample_count":len(rows)}
        for key in numeric:
            vals=[float(r[key]) for r in rows]; result[f"{key}_mean"]=statistics.mean(vals); result[f"{key}_std"]=statistics.stdev(vals) if len(vals)>1 else 0.
            result[f"{key}_ci95"] = 1.96 * result[f"{key}_std"] / math.sqrt(len(vals)) if len(vals) > 1 else 0.
        output.append(result)
    return output
