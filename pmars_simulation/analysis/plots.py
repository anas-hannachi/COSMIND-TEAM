import csv
from pathlib import Path
def generate(results_path="results/raw_results.csv", output="results/figures"):
 out=Path(output); out.mkdir(parents=True,exist_ok=True)
 with open(results_path,newline="") as f: rows=list(csv.DictReader(f))
 for metric in ("total_mission_value_completed","task_completion_rate","critical_task_completion_rate","mission_efficiency","deadline_miss_rate","average_latency_s"):
  values={}
  for row in rows: values.setdefault((row["scenario"],row["scheduler"]),[]).append(float(row[metric]))
  means={k:sum(v)/len(v) for k,v in values.items()}; top=max(means.values()) or 1
  bars="".join(f'<rect x="{20+i*35}" y="{180-150*v/top}" width="25" height="{150*v/top}" fill="#2563eb"/><text x="{20+i*35}" y="195" font-size="7">{s[:3]}-{q[:3]}</text>' for i,((s,q),v) in enumerate(means.items()))
  (out/f"{metric}.svg").write_text(f'<svg xmlns="http://www.w3.org/2000/svg" width="900" height="220"><text x="10" y="15">{metric} (mean)</text><line x1="10" y1="180" x2="880" y2="180" stroke="black"/>{bars}</svg>')
 (out/"architecture.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg" width="900" height="180"><text x="20" y="30">Tasks → Digital Twin (energy / compute / thermal / storage / contact / freshness) → Scheduler → PROCESS / STORE / TRANSMIT → Metrics → Results</text><rect x="20" y="55" width="120" height="50" fill="#bfdbfe"/><rect x="200" y="55" width="210" height="50" fill="#bbf7d0"/><rect x="470" y="55" width="120" height="50" fill="#fde68a"/><rect x="650" y="55" width="120" height="50" fill="#ddd6fe"/></svg>')
 (out/"contact_and_sunlight.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg" width="900" height="180"><text x="20" y="20">Example contact bandwidth and sunlight/eclipse timeline (simulation assumptions)</text><path d="M20 130 L120 130 L120 60 L240 30 L360 130 L470 130 L470 90 L610 40 L720 130" fill="none" stroke="#2563eb"/><rect x="20" y="145" width="180" height="15" fill="#facc15"/><rect x="200" y="145" width="180" height="15" fill="#475569"/><rect x="380" y="145" width="180" height="15" fill="#facc15"/></svg>')
 (out/"predictive_sequence.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg" width="900" height="120"><text x="20" y="30">Illustrative predictive plan: STORE → PROCESS after favourable energy → TRANSMIT in contact</text><path d="M40 70 H250 M300 70 H510 M560 70 H770" stroke="black"/><text x="65" y="60">STORE</text><text x="330" y="60">PROCESS</text><text x="600" y="60">TRANSMIT</text></svg>')
