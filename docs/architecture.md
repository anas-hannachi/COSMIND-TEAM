# PMARS Phase 2 Architecture

## Session 1 objective

This session fixes the architecture before we write working code. The goal is not to optimize or implement behavior yet. The goal is to agree on what owns what, what data flows where, and where the scheduler boundary sits.

### What you need to understand

- A satellite is a digital twin with state, not a scheduler or mission planner.
- The scheduler is a decision function over a snapshot of state, not a mutating agent.
- The simulation advances time and updates world state deterministically.
- Tasks are data objects that move through the system and are evaluated by a queue + decision engine.

### What you need to build

- The repository structure for Phase 2.
- The architecture document.
- The conceptual contracts for the core objects.
- The data flow from task arrival to process/store/transmit decisions.

### Definition of Done

By the end of this session, you should be able to explain:

- which objects own state,
- which objects are mutable vs snapshot-like,
- how time advances,
- how a task moves from arrival to a decision,
- and why the scheduler cannot directly manipulate the satellite.

### Approximate time

4 hours, with the goal of getting the boundaries right before implementation starts.

---

## 1. Core architectural rule

The scheduler must not directly manipulate the satellite.

This is the key design constraint for the whole project.

Conceptually:

1. Tasks arrive.
2. Tasks enter a task queue.
3. A decision engine evaluates the queue and state snapshot.
4. The engine chooses an action: PROCESS, STORE, or TRANSMIT.
5. The action is applied to the satellite digital twin.
6. The satellite updates its internal state and emits a new snapshot.
7. The decision engine repeats with the new state.

This is a state-action-state feedback loop.

The reason is simple: the scheduler is reasoning over a representation of the system, while the satellite is the system model that evolves. If the scheduler mutates state directly, the system becomes impossible to reason about cleanly, and we lose the boundary between decision logic and environment dynamics.

---

## 2. Why this architecture matters

The simulation must remain:

- deterministic under a fixed seed,
- inspectable at any point in time,
- reusable across scheduler implementations,
- fair across algorithms,
- separable into environment dynamics vs decision logic.

If the scheduler directly changes the satellite state, then the scheduler is no longer a clean policy. It becomes a hidden side-effecting system. That makes baseline comparisons and scientific interpretation weaker.

---

## 3. System-level object model

The core relationship is:

- Task: a unit of work with metadata and constraints.
- TaskQueue: the ordered collection of pending tasks and scheduling-related operations.
- SatelliteState: a snapshot of the satellite at a time instant.
- Satellite: the digital twin that owns mutable, evolving system state.
- Simulation: the orchestrator that advances time, injects tasks, updates the environment, and evaluates actions.

The most important rule:

- Satellite owns mutable state.
- SatelliteState is a stable view or snapshot of that state.
- TaskQueue owns task ordering and task visibility.
- Simulation owns time and coordination.
- Scheduler is an external policy that consumes state and returns an action decision.

---

## 4. Component contracts

## 4.1 Task

### What it owns

A Task owns the task identity and the task's mission-level and execution-level metadata.

### Data it contains

- id
- type
- input_size_mb
- processing_demand
- base_processing_time_s
- processing_energy_estimate_j
- processed_output_mb
- priority
- mission_value
- deadline_s
- created_at_s
- freshness_decay

Optional but often useful later:

- status
- assigned_action
- queued_at
- accepted_at
- started_at
- completed_at
- source
- metadata

### Who can read it

- TaskQueue
- Simulation
- Scheduler
- Debug/logging layers

### Who can modify it

- Task itself during validation or mutation of internal metadata
- TaskQueue may move it or update its queue metadata
- The simulation may update lifecycle status

### What it returns

- A task instance with valid fields
- Optional summary or serialization for logs
- Optional derived values such as urgency or slack

### What it should NOT know about

- Satellite internals
- Resource availability details
- Scheduling policy choice
- Simulation time progression beyond timestamps it already contains

### Responsibility boundary

Task is a data carrier and validation object. It should not decide whether it is processed, stored, or transmitted. It should not model energy or hardware behavior.

### Design principle

Task should behave like a value-like object with strong invariants. It should be easy to compare, serialize, and audit.

---

## 4.2 TaskQueue

### What it owns

TaskQueue owns the pending work list and ordering logic for tasks that have not yet been acted upon.

### Data it contains

- a collection of pending tasks
- ordering policy or priority ordering metadata
- task arrival timestamps
- queue length metrics
- backlog status
- optional ready/not-ready filtering

### Who can read it

- Scheduler
- Simulation
- Monitoring or metrics code

### Who can modify it

- Simulation when tasks are added
- TaskQueue when tasks are removed, reordered, or marked as started
- Optional queue policy logic if you choose to embed ordering rules inside the queue

### What it returns

- current pending tasks
- queue snapshot
- selected tasks for evaluation
- counts such as queue size, urgent count, backlog

### What it should NOT know about

- Satellite thermal state
- Battery state
- Communication windows
- Real decision policy beyond queue ordering concerns

### Responsibility boundary

TaskQueue decides how tasks are organized and visible. It does not decide which action a task should take. That is the scheduler's job.

### Design principle

A queue is a structure, not a decision maker. It should be deterministic and transparent.

---

## 4.3 SatelliteState

### What it owns

SatelliteState owns a frozen, time-stamped snapshot of the entire satellite system at a point in time.

### Data it contains

This is the official Phase 2 state definition that should be captured in a structured way:

- time
- energy
- battery
- solar_power
- compute_availability
- memory
- temperature
- storage
- communication/contact information
- queue_length
- critical_task_count

In practice, the state may include more detail than the minimal official definition, but the snapshot should remain conceptually coherent and time-stamped.

### Who can read it

- Scheduler
- Simulation
- Metrics/logging
- Analysis code

### Who can modify it

- Typically no one directly after creation
- It may be replaced by a new snapshot object, not mutated in place

### What it returns

- A stable snapshot for policy evaluation
- Derived values such as projected remaining energy, expected load, or link quality

### What it should NOT know about

- Business rules for choosing PROCESS vs STORE vs TRANSMIT
- Task-specific mission priorities beyond what is in the snapshot
- Whether a scheduler will choose a particular action

### Responsibility boundary

SatelliteState is a read-only observation layer. It reflects the system at a time instant.

### Design principle

If a policy needs to make a decision, it should look at a state snapshot, not mutate the live system.

---

## 4.4 Satellite

### What it owns

Satellite owns the mutable digital twin of the spacecraft. It is the system model that changes over time as events occur.

### Data it contains

- current time
- energy model state
- compute state
- thermal state
- communication state
- storage state
- mission/task state summary
- event logs or event state if the implementation later needs them

### Who can read it

- Simulation
- Diagnostics
- Metrics layers
- schedulers only via a snapshot or state export

### Who can modify it

- Simulation
- Environment models
- Action handlers that apply PROCESS/STORE/TRANSMIT outcomes

### What it returns

- current state snapshot
- updated state after an action or time progression
- derived metrics or warnings

### What it should NOT know about

- The scheduler's algorithms
- Specific mission heuristics
- Hard-coded preferences for one policy over another
- Task selection rules beyond the actions it is asked to execute

### Responsibility boundary

The satellite is the system model. It executes commands, evolves under time, and exposes a consistent state representation. It does not decide policy.

### Design principle

Satellite should be a stateful engine, not an optimizer.

---

## 4.5 Simulation

### What it owns

Simulation owns the orchestration of the model over time.

### Data it contains

- current simulation time
- random seed
- task generator or scenario definition
- list of active simulation objects
- event loop or time-stepping logic
- scheduler reference
- environment parameters
- experiment configuration

### Who can read it

- Experiment runners
- Logging/analysis
- Scheduler indirectly through state snapshot

### Who can modify it

- Time progression
- Task injection
- Simulation event scheduling
- Environment updates
- Satellite state transitions

### What it returns

- final simulation result or log stream
- state histories over time
- metrics and outcomes

### What it should NOT know about

- It should not encode the scheduler's exact policy logic
- It should not contain hard-coded mission choice bias
- It should not silently rewrite state without recording the action that caused it

### Responsibility boundary

Simulation is the conductor. It advances the model and ensures the state-action-state loop occurs correctly.

### Design principle

Simulation should coordinate, not decide mission priorities.

---

## 5. Data flow: from task to action

The most important data flow is:

1. New tasks are created or injected into the system.
2. They enter the TaskQueue.
3. The simulation collects the current satellite state snapshot.
4. The decision engine receives a clean state snapshot plus the queue.
5. The scheduler returns an action choice.
6. The simulation or action layer applies the chosen action to Satellite.
7. Satellite updates its internal mutable state.
8. A new SatelliteState snapshot is emitted.
9. The decision engine repeats with the updated state.

A simple conceptual flow is:

Task -> TaskQueue -> Decision Engine -> Action -> Satellite -> New State Snapshot -> Decision Engine

This loop is essential. If we skip the snapshot/reaction boundary, we are no longer building a clean digital twin.

---

## 6. Relationship between objects

### Satellite

- owns live mutable state
- evolves with time and events
- exposes snapshots
- accepts actions or commands

### SatelliteState

- is a read-only representation of Satellite at a moment in time
- is safe to pass into scheduling logic
- should be easy to serialize and compare

### Task

- is a unit of work with mission and processing metadata
- is independent of hardware state
- is not responsible for simulation dynamics

### TaskQueue

- holds outstanding work
- provides ordered access for decision logic
- separates queue management from action selection

### Simulation

- runs the discrete-event timeline
- injects tasks and updates time
- calls into the satellite and decision engine
- records outcomes and metrics

---

## 7. Mutable vs snapshot objects

### Mutable objects

These should change over time:

- Satellite
- TaskQueue, if it is a live queue that changes as tasks are admitted or removed
- Simulation clock and event state
- Energy, compute, thermal, storage, and communication models if implemented as live state containers

### Snapshot/value objects

These should be stable views or value representations:

- SatelliteState
- Task in its immutable or strongly validated form
- Derived metric tuples or event records

This distinction matters because the scheduler needs a safe, consistent view of the system. It should not be reading a live mutable object that changes underneath it during evaluation.

### Rule of thumb

If an object is passed to the scheduler, prefer a snapshot or copy rather than a live object reference.

---

## 8. Simulation time concept

The system is a discrete-event simulation. That means time advances in steps determined by events and state transitions, not continuously.

### Core idea

- The system has a simulation clock.
- Time is not wall-clock time; it is logical time.
- Events happen at specific simulation timestamps.
- State changes are observed at those timestamps.

Examples:

- a task arrives at t = 12.0 s
- a communication contact opens at t = 100.0 s
- a task is processed between t = 120.0 s and t = 130.0 s
- energy draw is computed over the duration of that action

### Why this matters

Discrete time gives us:

- deterministic behavior when seeded properly,
- reproducibility across runs,
- clean logging of state transitions,
- the ability to compare different scheduler policies under the same scenario.

### Important rule

The simulation clock belongs to the simulation. The scheduler should reason about the state as of a time value, but it should not own or mutate the clock directly.

---

## 9. Responsibilities and non-responsibilities

### Satellite must own

- the live system state
- action application semantics
- state propagation over time
- the digital twin model

### Satellite must not own

- policy selection logic
- task prioritization heuristics
- static mission strategy beyond the model itself

### Simulation must own

- scenario execution
- time progression
- task injection
- action orchestration
- logging and data collection

### Simulation must not own

- a hidden decision policy that bypasses the scheduler
- direct tactical manipulation of task selection outside the declared loop

### TaskQueue must own

- queue state and ordering
- visibility into pending work

### TaskQueue must not own

- the final decision to process/store/transmit
- the physics of energy or communication

### Scheduler must own

- decision policy
- scoring or comparison logic
- selection of the next action

### Scheduler must not own

- mutable satellite state
- event execution logic
- direct mutation of environment models

---

## 10. Validation and invariants to decide now

Some invariants should be defined early, even if implementation occurs later. These are useful contract-level rules.

Examples:

- energy cannot be negative
- battery cannot exceed capacity
- storage cannot exceed capacity
- temperature should remain within sensible bounds
- task IDs must be unique
- task sizes cannot be negative
- deadlines should be valid
- priority should have a consistent interpretation
- mission value should be valid for the intended task type

These are not policy rules. They are system safety and consistency assumptions.

---

## 11. Recommended directory structure

The repository structure should remain close to the project plan:

- pmars-simulation/
  - core/
    - satellite.py
    - task.py
    - task_queue.py
    - simulation.py
  - environment/
    - energy.py
    - communication.py
    - storage.py
    - compute.py
    - thermal.py
  - schedulers/
    - random_scheduler.py
    - rule_scheduler.py
    - greedy_scheduler.py
    - predictive_scheduler.py
  - scenarios/
    - normal.yaml
    - low_energy.yaml
    - poor_link.yaml
    - task_burst.yaml
    - critical.yaml
  - experiments/
    - runner.py
    - metrics.py
    - results/
  - analysis/
    - statistics.py
    - plots.py
  - tests/

This structure reflects a clean separation between:

- model state,
- policy logic,
- environmental dynamics,
- scenarios,
- analysis,
- and experimental comparison.

---

## 12. Architectural questions to answer before implementation

Before we move to code, these are the key questions to answer and defend:

1. Should Task be immutable after creation, or is status tracking okay?
2. Should SatelliteState be a dataclass, a Pydantic model, or a lightweight pure Python container?
3. Should TaskQueue own ordering logic or be a simple container with a separate policy layer?
4. Should Simulation own task arrival generation or should a separate scenario generator do it?
5. When the scheduler receives a snapshot, should it receive the full SatelliteState or a filtered subset?
6. Should action execution be part of Satellite, part of Simulation, or a separate action layer?

These are not arbitrary choices. They affect correctness and testability.

---

## 13. Decision to freeze for Session 1

The architecture we will carry forward is:

- task and queue are domain objects,
- satellite is the mutable system model,
- satellite state is a frozen snapshot,
- simulation is the orchestrator,
- scheduler is a pure decision policy over state.

This is the simplest architecture that preserves the state-action-state loop and keeps scientific comparison fair.

---

## 14. Final architectural summary

The simulator should behave like this:

- Task arrives.
- Task enters queue.
- System snapshot is materialized.
- Policy decides what to do.
- Action is applied to the satellite.
- New state is observed.
- Loop repeats.

This is the core design. Everything else in Phase 2 should be built around this principle.

---

## 15. What to do next

Before any Python implementation, make sure you can explain these five statements without reading the document:

1. The scheduler never directly mutates the satellite.
2. SatelliteState is a time-stamped observation, not the live system.
3. TaskQueue is not the decision maker.
4. Simulation advances time and coordinates the loop.
5. The system is a state-action-state feedback engine.

If you can explain those clearly, we are ready for Session 2, where we start implementing the Python domain models.
