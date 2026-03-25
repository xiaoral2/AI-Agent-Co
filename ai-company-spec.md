**Canonical:** This file (**English**) is authoritative for normative wording; [ai-company-spec.zh.md](./ai-company-spec.zh.md) is a synchronized translation—on conflict, prefer English.

**Language:** English. 简体中文见 [ai-company-spec.zh.md](./ai-company-spec.zh.md)（章节编号一致，便于对照）。

⸻

1. Goal

North star (aligned with [TokenFly](https://tokenfly.ai/))

Open-source reference implementation: [TokenFlyAI/Agentic_System](https://github.com/TokenFlyAI/Agentic_System) (SAS — Solar Agentic System). It is a Python framework for **persistent agents that focus on one target**: everything-as-`Tool`, `AgentV3` with LLM-planned **DAG** tool runs, **generator-based** execution (stream / pause / resume), and a **three-layer context** (local / parent / global). Upstream also has coordinator / multi-agent **demos**, but the **default product story** is closer to **one powerful operative** (or one coordinator agent) driving a session—not a **company operating system** with governance, staffing, and multi-function org chart. **This document is strictly broader** (§2.3): it **subsumes** those runtime ideas (§6.3–§6.7, §2.1) and adds a **company layer** on top. SAS remains an optional **engine** to integrate, not the ceiling of the design.

The longer-term direction is **long-running, harnessed agent infrastructure**: agents that persist across restarts, keep a stable target over long horizons, and receive **continuous corrective signals** from an environment (constraints, consequences, human/authority correction, and structured pressure)—not only single-shot prompt/response. TokenFly frames this as agent runtime (TAS-style), a world engine that “pushes back” (TWE-style), and a harness where they meet (AIverse-style); this document does not require adopting their stack, but the **product intuition is the same**.

**Harness here is mandatory, not optional:** the same *job* as upstream [Agentic_System](https://github.com/TokenFlyAI/Agentic_System) / [TokenFly](https://tokenfly.ai/) narratives—**keep focus on the mission over long runs**—is delivered through **checkpoints**, **three-layer context**, **test/review/retry loops**, **CEO authority** (`escalate`, replan), and (later) richer environment signals (§13). This repo **also** requires a **company-shaped control plane** (§2.3–§2.4) so you can **grow capacity and functions** without losing that focus.

**Design pressure (normative intent):** the hard problem is **not** only “make an LLM output text”—it is **operating the org correctly** while **not wasting** tokens, wall-clock, or money. That requires **machine-validated** handoffs from **planning → execution** (**§2.5.1a**), **typed failures with recovery** (**§4.4**), **budgets** (**§17.2**), and **honest scheduling** when tasks differ in urgency (**§6.4**, **§3.2**). If you want **reward-like** or **peer-pressure** shaping beyond raw pass/fail, **§2.5.10** defines how to do it **without** bypassing policy.

**CEO mission, scalable enterprise shape:** you are the only human **CEO**; every AI role exists to **execute your approved missions** (projects / goals). Target **multi-project, multi-division organizational ambition without tying to headcount**: many **projects**, many **divisions / role types** over time, elastic **worker pools**, clear governance—implemented incrementally (MVP starts with four role types) but **never** architecturally capped at “one super-agent.” **Assistant** staffs and schedules against **your** priorities (§2.2). This spec does **not** cover business, finance, or people HR; it covers **how work gets aligned and scaled** under one CEO.

What this spec defines **now** is a deliberate **MVP slice** for the *product loop*, **plus** a **SAS-aligned runtime layer** (§6.3–§6.7): same scope as before for roles and CEO gate, but **not** a throwaway script—Tool contracts, DAG-correct scheduling, persisted session, and three-layer context are **required** so behavior matches [Agentic_System](https://github.com/TokenFlyAI/Agentic_System) closely enough to integrate or swap later. §13 keeps *optional* product extras (UI, RAG, git PRs, multi-pool scaling).

Build an autonomous multi-agent system that can:
	•	Take a natural language software request
	•	Generate a plan
	•	Write code
	•	Write tests
	•	Run tests
	•	Debug and fix issues automatically
	•	Minimize human intervention (CEO only approves plan)
	•	**One human (CEO)** sets missions; the org **rallies on your tasks**; **Assistant** scales the AI **worker pool** so one person can run a **growing** firm, not a fixed squad (§2.2, §2.4).

⸻

2. High-Level Architecture

Roles
	•	CEO (Human)
	•	Provides high-level goal and **mission priority** (what “the company” optimizes for)
	•	Approves plan
	•	Makes tradeoff decisions
	•	Orchestrator (**Secretary / Assistant** — see **§2.2**)
	•	Manages entire workflow
	•	Creates project + tasks
	•	**Provisions and scales workers on demand** (pool grows/shrinks with workload and policy—§2.2, §6.4)
	•	Assigns tasks to workers (reuse idle workers or spin up new logical workers)
	•	Tracks status
	•	Handles retry loop and **failure routing** (**§4.4**)
	•	Workers (AI Agents)
	•	Planner
	•	Coder
	•	Tester
	•	Reviewer

2.1 Mapping to TokenFly Agentic_System (SAS)

This spec’s roles map to [Agentic_System](https://github.com/TokenFlyAI/Agentic_System) concepts so MVP and long-term evolution stay aligned.

	•	Orchestrator — Drives the session: CEO gate, task lifecycle, retries, and **worker pool lifecycle** (§2.2). Implement as a **thin Python loop** that calls SAS (`SASClient` / executor) **or** mirrors the same boundaries (scheduler + tool invocations + pool registry).
	•	Planner / Coder / Tester / Reviewer — Each is a **`Tool`** with **`execute` → `Result`** (**§6.3**). **Default profile:** LLM + prompts + structured I/O. **Coder** **may** use a **terminal-agent adapter** (e.g. **Claude Code**, other CLI coding agents) instead of chat-completion + `write_file` only — **§13**. Optional **Architect** — **§13** / **§5.5**. Later, any role can become a nested **`AgentV3`** with its own tool list (SAS pattern: agents compose as tools).
	•	File read/write + pytest — **Concrete `Tool` implementations** (same idea as SAS demo file / subprocess tools), scoped to `/workspace/` (§9).
	•	Task list — Orchestrator uses a **DAG-correct scheduler** (§6.4); **parallel** execution of independent tasks is optional (serial execution is OK if order respects `depends_on`).
	•	Memory / long runs — **Three-layer context** (§6.5) + **persistence / checkpoints** (§6.6) are required; not optional “later bridge.”
	•	CEO approval — **Harness / human gate** outside SAS’s stock loop; orchestrator blocks execution until approved or replanned.
	•	**Long-term focus (harness)** — same *purpose* as TokenFly/SAS: avoid drift across sessions. Here, harness signals include **pytest/reviewer**, **checkpoints**, **context layers**, and **CEO escalation**; expand toward TWE-style environment tools in §13.

**Reference framework internal layout (informative):** Stacks in this family are usually **layered**, not one monolith. Typical pieces (names vary by fork): **service / API** — requests enter through a handler; a client streams results; protocol types separate wire format from execution. **Persistence** — session or turn state is stored durably so runs survive restarts. **Configuration** — tools and agents are declared declaratively (e.g. YAML): named entries, I/O schemas, which child tools each node may call. **Registry** — logical names resolve to implementations (file, shell, and other backends). **Execution engine** — a scheduler walks a **DAG** of tool calls; branches may run concurrently; steps are often **generator-shaped** (emit a plan, block, then resume with results). **Tool model** — atomic tools and **LLM agents** share one abstraction; **nested agents** are invoked as tools. **Composition pattern** — a **coordinator-style** agent delegates to **specialist** sub-agents (each specialist is a tool with its own tool list); **skill** modules swap tool subsets at runtime. XR-AI-Co keeps **CEO + Assistant** as the **governance and staffing layer above** this substrate; **Planner / Coder / Tester / Reviewer** align with **specialists**; **Assistant** owns sequencing, pool policy, and **CEO-side gates** that a **coordinator-style agent inside the reference stack** does not subsume.

**Integration stance (pick one, document in repo README when coding):**

	•	**Integrate SAS** — Depend on [TokenFlyAI/Agentic_System](https://github.com/TokenFlyAI/Agentic_System) (git submodule or install from Git). Register XR tools in a **tool registry**, define **YAML** agent(s) for planner vs workers or one coordinator agent; reuse DAG executor where possible.
	•	**Mirror SAS** — No upstream dependency; still use **Tool-shaped** modules, clear **I/O schemas**, and a **small dependency-aware scheduler** so swapping in SAS later is mostly wiring.

2.2 One human, elastic team (Secretary / Assistant)

Only the **CEO** is human. **Assistant (Orchestrator)** is the **single control plane** for every AI worker. Treat it as more than a **pool counter**: it is the **execution manager** (DAG, retries, failure policy **§4.4**, checkpoints), **HR** (provision / idle / retire workers, caps, safe parallelism §6.4), and **light PM toward the CEO** (status summaries, blockers, progress). **Policy-driven** behavior **must** follow **§2.5.3** (config), not opaque model decisions. For **requirements clarification** before planning, see **§2.5.6** (recommended PM pass)—distinct from status summaries here.

It may **add, idle, reuse, or retire** worker instances **when the job needs it**—e.g. more **parallel** runnable tasks (§6.4, §13), a **burst** of test/review work, or **separate** coders on disjoint file areas. Headcount is **not** fixed at four role types; those are **role types** (plus optional **Architect** §13). The CEO still approves the plan once; after that, **Assistant** runs the team so **one person** can steer the whole crew without manually spawning each bot.

**Secretary responsibilities (normative intent):**

	•	**Dynamic scale** — match **ready tasks** and **role** demand to worker instances within caps (§2.2 bullets below, §6.4).
	•	**Task breakdown support** — materialize Planner JSON into **§3.2** tasks; **may** split oversized descriptions or suggest extra `depends_on` / subtasks **before** CEO approve (policy-defined); **must not** bypass CEO gate on material plan changes (§4 Step 3, §17.3).
	•	**CEO-facing progress** — maintain **parent** / **global** snapshots the CLI or UI can render: which tasks are `done` / `in_progress` / blocked, last failure summary, **`retry_count`** highlights—so the CEO sees **how the run is doing**, not only final pass/fail. On **escalate** / **blocked**, render the **executive report** and **choices** in **§7.2**.

Design rules:

	•	**Demand-driven** — pool size follows **ready tasks**, **role** needs, and configurable **caps** (max concurrent coders, etc.), not a static table.
	•	**CPU-aware default for code** — **per orchestrator process**, at most **two** **`code`-type tasks** (or **`coder`** workers in `busy` on code work) may run **at the same time** unless configuration explicitly changes this. Assistant **queues** additional ready code tasks until a slot frees. Rationale: LLM + tooling is CPU/IO heavy; capping avoids saturating a laptop when parallelism is enabled. Operators may set `1` for weaker machines or raise the cap only **deliberately**.
	•	**Host metrics & effective caps (recommended)** — On session start, record a **host snapshot** in **global or parent context** (§6.5): at minimum **logical CPU count** (e.g. `os.cpu_count()`); optionally **installed / available memory** if cheap to read. Implementations **may** derive a **`host_ceiling`** for concurrent code work from that snapshot (e.g. `max(1, min(cpu_count // 2, 4))`—**illustrative only**; choose a conservative formula and document it). The **effective** concurrent code limit is then **`min(operator_configured_max_concurrent_code_tasks, host_ceiling)`** when **`clamp_code_tasks_to_host: true`** (§14); otherwise the configured cap applies as today. **Do not** auto-raise above the operator’s configured cap from host data alone—only **clamp down** to protect the machine. If no clamp flag, still **log** CPU/memory at start for supportability.
	•	**Multi-terminal / multi-session** — you may run **several** orchestrator instances (e.g. one terminal per project) with **separate** `state/` / session ids. **Each process** enforces its **own** code cap (default 2); **total** load is **multiplicative**—if three terminals each run two coders, the OS may see up to six concurrent code paths; **that is acceptable** only if the operator accepts the cost; otherwise lower caps per session or stagger runs.
	•	**Safe parallelism** — more workers **must not** violate §6.4 workspace / same-file conflict rules; Assistant may **serialize** conflicting tasks even if the pool could run more.
	•	**Repo–worker affinity** — default **one `coder` ↔ one git repo** (§3.3); parallel coders imply **multiple repos** or **documented §9.2** isolation, not silent shared-HEAD contention.
	•	**Observable** — parent context (§6.5) should list **active workers** and assignments so the CEO (or logs) can see who is doing what.

2.3 Company-grade scope vs [Agentic_System](https://github.com/TokenFlyAI/Agentic_System) (superset)

**How to read SAS:** treat it as a **strong single-agent / single-session runtime** (plus composable tools and optional nested agents). That is excellent **machinery**, but it does **not** prescribe **who is CEO**, **who runs the floor**, **how plans are approved**, **how QA and review are separate functions**, or **how headcount scales**—those are **organizational** choices. Your intuition that SAS feels more like **“单兵（或单核 agent）打穿一个目标”** matches its README emphasis on **one target, one AgentV3 loop** and DAG **inside** that agent—not a full **firm**.

**What this spec adds (company-level, more extensible):**

| Layer | SAS (typical use) | XR-AI-Co (this spec) |
| ----- | ----------------- | -------------------- |
| **Governance** | Implicit (user prompt) | **CEO** human gate, tradeoffs, plan approval |
| **Operations** | Agent + executor | **Assistant** — task portfolio, worker pool, retries, `escalate`, checkpoints |
| **Org / roles** | Tools + optional sub-agents | Fixed **role types** (Planner / Coder / Tester / Reviewer) + **elastic worker instances**; optional **Architect** §13 |
| **Work breakdown** | LLM plans tool DAG per turn | **Project / Task** entities, `depends_on`, CEO-visible plan |
| **Factory floor** | Repo / cwd in demos | **`/workspace/`** + file + pytest tools as **environment** |
| **Harness (long-term focus)** | Persistence, context, env feedback—keep one target from drifting | **Same anti-drift intent**, **org-wrapped:** test → review → retry → CEO / `escalate`, checkpoints, context (§6.5–§6.7), plus roadmap to TWE-style “world” signals (§13) |
| **Future org** | New tools / skills | **§13** — new **divisions** (role types), **multi-project** CEO portfolio, distributed fleet, RAG, UI, git, TWE-style signals |

**Superset claim (precise):** anything SAS does at the **runtime** level (Tool contract, DAG execution, context layers, persistence, YAML-configurable agents) is **either required here** (§6.3–§6.7) or **admitted via integration** (§2.1, §14). This spec **adds** a **corporate control plane** that a raw agent framework does not model—so the system can grow into **more divisions and policies** without collapsing back to “one chatty super-agent.”

**When integrating SAS:** use it as **executor / AgentV3 substrate** under **Assistant**; do **not** delete the **company** boundaries—CEO approval, worker pool registry, and org-visible state remain **first-class** in this repo.

2.4 CEO-centric mission & scalable enterprise shape

**Alignment to your mission:** all AI workers and future **divisions** exist to advance **CEO-approved goals**. There is no separate “side agenda”; tradeoffs surface to **you** (or through policies you set in config). **Assistant** is the **staffing and routing layer**—analogous to **COO / Chief of Staff**—allocating parallel capacity, sequencing dependencies, and preserving **harness** so the org does not lose the thread over long runs.

**Enterprise *topology*, not literal headcount:** the **architectural** target is a **multi-division firm**: many **projects**, expandable **role types** (§13), elastic **worker pools** (§2.2), and visible **portfolio** state—not a single chat thread. MVP ships a **small** org chart (four role types) on purpose; the spec **forbids** designing a hard ceiling that would prevent adding **security, design, docs, SRE**, etc., as first-class departments later. **No** finance, payroll, or corporate law in scope; **yes** to **org growth, mission focus, and operational support for one CEO**.

2.5 Core stability layers (normative cross-cutting)

These layers **prevent** “DAG + retry” from becoming **implicit** coordination: every role needs **contracts**, **artifacts** with **lineage**, **policies**, explicit **lifecycle**, **task closure** (**who** sets `done`), **decision logs**, **typed failures**, **accumulated knowledge** (short- and long-term), (when you want low-touch CEO input) a **requirements / clarification pass**, and—when you want human-org-like **shaping**—an explicit stance on **motivation / peer cues** vs pure mechanics (**§2.5.10**).

**2.5.1 Task specification layer**

Every **materialized** task (**§3.2**, **§4.3**, **§10.2 Mode 1**) **must** carry a **TaskSpec**—either **flat fields** on the Task JSON or a nested **`task_spec`** object—so **Coder**, **Tester**, and **Reviewer** share one **contract**, not guesswork:

| Field | Required (Mode 1) | Type | Role |
| ----- | ----------------- | ---- | ---- |
| **`input`** | yes | string | What this task **starts from** (upstream task ids, file globs, or a short “given …” statement). |
| **`output`** | yes | string | What **done** **means** as a **deliverable** (paths, APIs, behaviors)—not vague “implement feature.” |
| **`constraints`** | yes | string \| string[] | Hard limits (language, libs, style, perf, security)—empty array **only** if CEO explicitly waives (document in README). |
| **`acceptance_criteria`** | yes | string \| string[] | **Observable** checks (e.g. “`pytest tests/test_x.py` green”, “public `foo()` matches …”). |
| **`test_plan`** | yes | string | **Human-readable** verification narrative: **scope** (files / markers), **command** if not default pytest, and **what** constitutes pass/fail—**CEO** and **Reviewer** read this. |
| **`verification`** | yes when **`type: test`** (Mode 1) | object | **Machine-enforceable** pytest spec for the **Execution Tool**—**§2.5.1a**. **Optional** on **`type: code`** (often the sibling **`test`** task carries **`verification`**). |

**Planner** **must** populate **`input` / `output` / `constraints` / `acceptance_criteria` / `test_plan`** for **each** task, and **`verification`** for **every `test`** task, before CEO **APPROVE** (CEO **may** edit via replan). Downstream tools **must** receive them via **§6.5.2** / **§6.5.3** inside validated JSON (**§3.2**).

**2.5.1a Planning → execution contract (machine-enforceable)**

**Problem addressed:** **TaskSpec** fields that are **only** prose are **not** an **interface** the orchestrator can **enforce**—the gap between **Planner JSON** and **pytest** must be **structured**, not “hope the model understood `test_plan`.”

**Normative (§10.2 Mode 1):**

	•	The **authoritative** plan is still **JSON** tasks (**§4.3**). **Before** CEO **APPROVE** (or immediately after Planner emit, per implementation), the orchestrator **must** **`validate`** every task against a **fixed JSON Schema** (or equivalent: Pydantic / `jsonschema`) **shipped or referenced in-repo** (**§14**—e.g. `schemas/task.v1.json`). **Invalid plans do not reach execution.**
	•	Each task with **`type: test`** **must** include **`verification`**, a **JSON object** the **Execution Tool** can run **without** NL parsing:

| Field | Required | Type | Notes |
| ----- | -------- | ---- | ----- |
| **`kind`** | yes | string | MVP: **`pytest`** only (extend in §13). |
| **`paths`** | yes | string[] | Paths **relative to `/workspace/`** (or `repo_root`—document); passed as pytest **file args** or `-k`/marker **only** if **`kind`** defines how—document mapping. |
| **`extra_args`** | no | string[] | Extra argv for pytest (e.g. `-m`, `-q`); **must not** bypass **§9.1** (no arbitrary shell from model text). |

	•	**`test_plan`** (string) on **`test`** tasks **must** **describe** the same run as **`verification`** (for humans); **mismatch** is a **Planner bug**—Reviewer **may** flag **`requirement_mismatch`**.
	•	**Task closure** (**§2.5.7**) for **`test`** tasks: **default** gate is **Execution Tool** success on **`verification`** (not “model says OK”).

**2.5.2 Artifact system**

Workers **do not** “coordinate by vibes.” **Communication** across steps is **via artifacts**—paths, structured blobs, and registry references—recorded in **`ToolResult.artifacts`** (**§6.3.1**), checkpoints (**§6.6**), and **global** / **parent** (**§6.5.1**).

**Normative artifact kinds (minimum vocabulary):**

| Kind | Typical carrier | Notes |
| ---- | ----------------- | ----- |
| **code** | `/workspace/` paths | Source the **Coder** produced or changed. |
| **tests** | `/workspace/` paths | **Tester** output. |
| **logs** | Execution Tool **`logs`**, pytest JSON in **`last_pytest`** | Objective failure evidence. |
| **review_report** | Reviewer **`payload`** / persisted **`last_reviewer_feedback`** (structured **recommended**) | **Not** only prose—**should** align with **§5.4** checklist dimensions. |
| **metrics** (optional) | `payload` or global | e.g. coverage %, timing—**recommended** when available; **not** required for bare MVP. |

**2.5.3 Policy layer**

**Assistant** decisions (**retry**, **scale**, **parallelism**, **failure routing**, **which runnable task runs next**, **time / SLA reactions**) **must** follow **declared policies** in **config** (YAML/TOML/JSON—**§14**), **not** ad-hoc model whim. Minimum **named** policy blocks implementations **should** expose (fields map to existing sections):

| Policy | Governs | Spec anchor |
| ------ | ------- | ----------- |
| **`scheduler_policy`** | **Scheduling decision rules:** how the ready set maps to **next task** and **parallel batch** (binding to **§6.4** ordering, tie-breaks, serial vs parallel when multiple tasks are runnable—**must** remain **deterministic** unless README documents a **seeded** fair-share variant) | **§6.4** |
| **`retry_policy`** | `max_retries`, when Reviewer is mandatory, backoff | **§4.1**, **§4.4**, **§7** |
| **`scaling_policy`** | worker provision / retire, idle behavior, **caps** (no unbounded spawn) | **§2.2**, **§6.4** |
| **`failure_policy`** | taxonomy routing, escalate vs blocked | **§4.4**, **§7.2** |
| **`parallelism_policy`** | max concurrent `code`, serialization vs overlap, **§9.4** | **§2.2**, **§6.4**, **§9.4** |
| **`budget_policy`** | token/cost/retry ceilings, hard-stop behavior | **§17.2** |
| **`sla_policy`** | overdue **`deadline`** handling (**warn** / **escalate** / **continue**) **and** **inputs** to **SLA-driven** **`effective_priority_rank`** (**§2.5.3a**, **§6.4**) | **§6.4**, **§3.2** |

README **must** point to the **authoritative** config keys or state that defaults match the spec tables.

**2.5.3a Policy composition and conflicts (normative)**

**Problem addressed:** naming **`retry_policy`**, **`budget_policy`**, **`scheduler_policy`**, etc. supplies **definitions**; it does **not** by itself define **how** they **compose** when they **disagree**. Without a **decision layer**, cases like “**high** `priority` but **over budget** vs **low** `priority` but **budget OK**” have **no** specified **next dispatch**.

**Definition vs composition:** policy **blocks** are **definitions**. **Composition** is the **ordered evaluation** Assistant **must** implement so each dispatch is **reproducible** and **auditable** (**§2.5.9**).

**Minimum composition stack** (later layers apply only to outcomes allowed by earlier layers):

1. **Hard gates — spend and safety** — **`budget_policy`** / **`Budget`** (**§17.2**): before **starting** or **continuing** work that **increments** token/cost/retry budgets, check **`budget_counters`**. If the **next** budgeted unit of work would **violate** limits, that task is **not eligible for that dispatch**—**even** if its stored **`Task.priority`** is **`urgent`**. **No** model-text override of limits.
2. **Structural eligibility** — DAG **`depends_on`**, **`plan_revision_id`** vs **`approved_plan_revision_id`** (**§17.3**), and project/task states that forbid run (**§4.2**).
3. **Failure routing** — **`failure_policy`** + **`failure_type`** (**§4.4**) for retries, replan, escalate.
4. **Scheduler** — among tasks **eligible** after (1)–(3) for the **current** decision, apply **`scheduler_policy`** bound to **§6.4** (ordering, parallelism).

**Normative conflict (priority vs budget):** **Budget eligibility** is evaluated **before** **priority / deadline ordering**. Example: task **A** has **`high`** `priority` but the **next** LLM call would exceed **`max_tokens_per_session`**; task **B** has **`low`** `priority` and fits **Budget** — Assistant **must not** dispatch that LLM step to **A**; **may** dispatch **B** if **B** passes (1)–(3). If **no** task can proceed without violating **`Budget`**, follow **§17.2** (**`escalate()`** / **`blocked`**). README **must** document any **CEO / policy** exception path.

**SLA feedback into scheduling (normative):** **`sla_policy`** **must** influence **§6.4** on **every** scheduling tick: when **`Task.deadline`** is set, Assistant **must** compute **`effective_priority_rank`** (or an equivalent documented sort key) from **stored** **`Task.priority`** **plus** **time-to-deadline** per thresholds in **`scheduler_policy`** and/or **`sla_policy`** (e.g. “within **T** seconds of **`deadline`**, treat as at least **`high`**”). **Urgency for that task must not decrease** as **`deadline`** approaches (monotonic toward **`urgent`** cap unless the CEO or replan changes the task). **`DecisionLog`** **should** record **`sla_priority_boost`** when a bump applies.

**Multi-criteria scheduling (normative binding, not ad-hoc splicing):** a **lexicographic** sort (**effective rank** → **`deadline`** → **`Task.id`**) is a **valid** default binding. Implementations **may** instead publish a **documented** scalar or tuple (e.g. combining **effective** priority, **deadline**, optional **estimated cost to complete**, optional **retry pressure** from **`retry_count`**) **provided** the function is **deterministic**, **versioned** in **`scheduler_policy`**, and disputes are traceable via **`DecisionLog`** (**§2.5.9**).

**2.5.4 Task lifecycle vocabulary (workflow state machine)**

**Canonical** `Task.status` strings remain **§16** / **§4.1**. For **documentation**, product UI, or external runbooks, the following **map one-to-one**:

| Informal | Canonical `Task.status` (§16) |
| -------- | ------------------------------- |
| **pending** | `todo` |
| **running** | `in_progress` |
| **blocked** | `blocked` (optional on Task) **or** `Project.status: blocked` |
| **failed** | `failed` |
| **success** | `done` |

**Optional `needs_review` (§16):** implementations **may** insert **`needs_review`** **after** a worker pass and **before** **`done`** when **Reviewer** is an explicit **quality gate** on the **success path**; transitions **must** be **documented** and **checkpointed**. If unused, keep **Reviewer** on the **failure / retry path** per **§4.1** / **§4.4** and map “running review” to **`in_progress`**.

**2.5.5 Knowledge layer (short-term vs global learning loop)**

**Short-term memory (already required):** **§6.5** context layers + **§6.6** checkpoints hold **this session’s** state—enough to **resume**, **retry**, and **debug**, but **not** automatically **cross-run** learning.

**Global / long-term loop (recommended — true org memory):** the system **should** accumulate a **durable knowledge slice** (persisted **`knowledge_base`** under `state/` or a separate store—**§6.5.1**) updated **across** runs and missions so the org **does not** “re-hit the same bug forever”:

	•	**failed_attempts** — short **structured** entries (task id, **`failure_type`** §4.4, fix that worked)—**redacts** secrets.
	•	**common_bugs** — recurring failure patterns from **Reviewer** / pytest.
	•	**patterns** — repo-specific conventions the org **should** reuse.
	•	**best_practices** — CEO- or Reviewer-approved **do / don’t** lines.

**Injection:** **§6.5.3** **should** include a **trimmed** knowledge digest for **Planner** and **Coder** on **retry** or **new** tasks in the **same** project when present—**document** caps in README. **Optional §13:** embeddings or shared org store beyond this **minimum** slice. **Not** required for **§10.2 Mode 0** spikes.

**2.5.6 PM role & clarification loop (recommended — requirements clarification)**

When the product goal is **“CEO types little; the org fills gaps,”** a **clarification loop** **before** **Planner** materializes the **authoritative** task JSON **is strongly recommended**. **Anti-pattern:** a **vague** CEO goal (e.g. “build me a system”) goes **straight** to **Planner-only** decomposition—**high risk of wrong scope** unless the CEO already supplied a **complete** charter.

**Clarification loop (normative when enabled):** elicit **scope**, **constraints**, **success signals**, and **open questions**; persist **Q&A or summary** into **`requirements_summary`** / **global** (**§3.1**, **§6.5.1**); **only then** invoke **Planner**. Implement as **`Worker.role: pm`**, a **named Tool** chain, or **Assistant** pre-flight—**register** in README. **Not** the same as **§2.2** “light PM toward CEO” (status summaries). **Bare MVP** **may** omit it **only** if the CEO supplies **complete** goals; **document** that choice.

**2.5.7 Task closure — who marks a task “done” (normative)**

**TaskSpec** (**§2.5.1**) states **what** “done” **means**; **closure** defines **who** **authoritatively** transitions **`Task.status` → `done`**.

| Situation | **Authority** | **Mechanism** |
| --------- | --------------- | ------------- |
| Default **`code`** / **`test`** task, **no** **`needs_review`** gate | **Assistant** only | After **Tool** **`success: true`** **and**—for **`test`**—**Execution Tool** green on **`verification`** (**§2.5.1a**, §6.2.1), Assistant sets **`done`** and **checkpoints** (**§6.6**). **Models** **do not** self-declare done without orchestrator. |
| **`needs_review`** enabled (**§2.5.4**) | **Assistant** after **Reviewer** | Worker success → **`needs_review`** → Reviewer **`review_report`** **pass** → Assistant sets **`done`**. |
| **Git milestone** (**§9.3**) | **Complements** closure, **does not replace** it | **Commit** (or snapshot tag) **after** green tests documents **lineage**; **`done`** is still an orchestrator **state** transition. |
| **CEO override** | **CEO / operator** | **Documented** “accept risk” / **skip** path **only** if **explicit** in README and **logged** to **§2.5.9** `DecisionLog`. |

**Forbidden:** a **Coder** or **Tester** **Tool** setting **`Task.status`** directly; **only** the orchestrator (**§4.1**).

**2.5.8 Artifact lineage (version control / “who matches whom”)**

Artifacts (**§2.5.2**) **evolve** across attempts and tasks. Implementations **must** bind **code**, **tests**, and **logs** so operators can answer: **“this test run validated which code revision?”**

**Minimum lineage (Mode 1):**

	•	Every **ToolResult** **should** record **`task_id`**, **`plan_revision_id`**, and **`retry_count`** / **attempt** id in **`payload`** or parallel **parent** fields when not inferable from context.
	•	**`last_pytest`** (**§6.5.1**) **must** reference the **same** **`task_id`** (and attempt) as the **`test`** task that invoked the Execution Tool.
	•	When using **git** (**§9.2**), **tie** task-boundary commits to **`task_id`** + attempt (commit message, tag, or **checkpoint** field storing **`commit_sha`**). **§9.3** ordering still applies.
	•	**DAG handoff:** for **`test`** depending on **`code`**, **document** whether **tests** are expected to track **latest** workspace HEAD after upstream **`done`** or a **named** revision—**no** silent mismatch.

**2.5.9 Decision log & Assistant interpretability (normative)**

**Problem addressed:** **Assistant** scales, retries, and routes (**§2.2**, **§4.4**)—without **recorded reasons**, operators see **random retry**, **infinite loops**, or **parallel explosion** as **opaque**.

**Policy + proof:** every **material** Assistant decision **must** be **derivable** from **§2.5.3** policy definitions + **§2.5.3a** **composition order** + **§4.4** **`failure_type`** + **task state**—**not** free-form model whim. When a decision **is** LLM-suggested, the orchestrator **still** **commits** only after **policy** allows the transition and **logs** the **policy rule id** or **reason code**.

**`DecisionLog` (append-only per session, checkpointed — §6.6):** ordered entries, each **at least**:

```yaml
- decision: spawn_worker   # e.g. spawn_worker | retire_worker | schedule_task | retry_route | escalate | parallel_schedule
  reason: policy_max_code_slots  # short stable token; may reference failure_policy / retry_policy key
  context:
    task_id: T2
    failure_type: test_failure   # when applicable — §4.4
    retry_count: 1
```

**Observability:** **§6.7** — stream or tail **`DecisionLog`** with phase transitions so **“what is the system doing?”** is answerable from **logs + checkpoint**, not guesswork.

**2.5.10 Motivation, “peer pressure,” and rewards (informative + guardrails)**

**Problem addressed:** real orgs use **social cues**, **reputational pressure**, and **incentives**. This spec is **mechanistic** first; without naming this layer, teams either **omit** human-like shaping or **smuggle** it through prompts in ways that **fight** policy.

**Already-built “pressure” (Mode 1 — no extra reward engine):** the harness **already** supplies **consequences** that act like **organizational pressure**: **pytest** / Execution Tool outcomes (**§6.2.1**), **Reviewer** structured feedback (**§5.4**), **bounded retries** and **`retry_count`** visibility (**§4.1**), **budget** hard stops (**§17.2**), **SLA-driven** scheduling urgency (**§2.5.3a**, **§6.4**), **CEO** approval and **`escalate()`** (**§7.2**), and **auditable** **`DecisionLog`** (**§2.5.9**). Treat these as the **default** substitute for ad-hoc “peer pressure” copy.

**Optional explicit peer / comparative shaping (recommended pattern, not Mode 1–required):** when **parallel** lanes or **multi-task** projects exist, implementations **may** inject **orchestrator-factual** summaries into **§6.5.2** / **§6.5.3** (e.g. **Block B — Parent**): anonymized or **task-id-labeled** **signals** such as “lanes with **green** tests vs **open** retries,” **time-to-first-green**, or **shared** **`knowledge_base`** lines (**§2.5.5**) that encode **“what the org already learned.”** **Reviewer** **may** cite **patterns** from **`knowledge_base`** so **Coder** sees **cross-task** norms—**not** personal attacks, **not** unverifiable claims.

**Normative guardrails (when you add motivational text or metrics):**

	•	**Policy wins** — motivational framing is **untrusted content** for **safety / budget / tools** (**§17.4**). It **must not** override **allowlists**, **paths**, **`Budget`**, or **CEO** authority.
	•	**No hidden reward channel** — **RL** scalars, **learned** reward models, or **payout** logic **outside** **`ToolResult`**, **§2.5.3**, and **`DecisionLog`** are **out of scope** for **§10.2 Mode 1**. If promoted from **§13**, they **must** remain **auditable** and **subordinate** to **budget** and **failure** policies.
	•	**Honest signals** — peer-style metrics **should** trace to **checkpoints** / **logs** (same spirit as **§2.5.8** lineage); **do not** fabricate comparisons the harness did not compute.

⸻

3. Core Entities (Must Implement)

3.1 Project

```json
{
  "id": "P1",
  "goal": "Build rate limiter",
  "status": "planning",
  "tasks": []
}
```

**Requirements summary (Planner):** the **requirements summary** from §4 Step 2 is **not** stored inside `tasks[]`. Persist it under **global context** (§6.5), and/or as an optional top-level field on `Project` (e.g. `requirements_summary`: string). Checkpoint it with the project (§6.6).

**Plan revisions (normative — detail §17.3):** each materialized plan has a monotonic **`plan_revision_id`** (string: UUID or incrementing id per project). After CEO **APPROVE**, persist **`approved_plan_revision_id`** and **only execute tasks** tied to that revision. Replanning or CEO **modifications** allocate a **new** `plan_revision_id` and clear prior approval until CEO approves again.

3.2 Task

**Text at the boundary, structured inside (normative):** the **CEO** and **user** enter missions and feedback as **natural-language text** (UTF-8 strings). The **Planner** turns goals into **`requirements_summary`** (text) and a **task list** whose human-facing fields—especially **`description`**, **`acceptance_criteria`**, **`design_notes`**—are **text**. **Downstream tools** **must** receive those strings **inside** validated **JSON** tool inputs (**§6.3**), not as an undocumented blob. **IDs**, **`depends_on`**, **`status`**, **`type`**, and **`plan_revision_id`** are **always** structured scalars or arrays—never ambiguous freeform at persistence boundaries.

Field values **must** match **§16** (e.g. `status`, `type`). Each task **must** carry **`plan_revision_id`** matching the project plan it was created under (§17.3). **Task.type** (DAG work unit) is **not** the same as **Worker.role** — see **§17.5**.

**Task schema (normative — “what a Task looks like”):** full **TaskSpec** contract **§2.5.1**; fields below are the **persistence** shape.

| Field | Required | Type | Notes |
| ----- | -------- | ---- | ----- |
| **`id`** | yes | string | Stable unique id within project (e.g. `T1`). |
| **`type`** | yes | string | **`code`** \| **`test`** (+ §13 extensions). |
| **`description`** | yes | string | **Text**; primary handoff to workers. |
| **`status`** | yes | string | §16 (`todo`, `in_progress`, …). |
| **`depends_on`** | yes | string[] | Task ids; DAG edges; may be `[]`. |
| **`owner`** | no | string \| null | **`Worker.id`** when bound. |
| **`retry_count`** | yes | number | Integer ≥ 0. |
| **`plan_revision_id`** | yes | string | §17.3. |
| **`input`** | Mode 1 yes | string | TaskSpec — **§2.5.1**. |
| **`output`** | Mode 1 yes | string | TaskSpec — **§2.5.1**. |
| **`constraints`** | Mode 1 yes | string \| string[] | TaskSpec — **§2.5.1**. |
| **`acceptance_criteria`** | Mode 1 yes | string \| string[] | TaskSpec — **§2.5.1** (observable). |
| **`test_plan`** | Mode 1 yes | string | TaskSpec — **§2.5.1** (human narrative; must align with **`verification`**). |
| **`verification`** | Mode 1 yes if **`type: test`** | object | **§2.5.1a** — machine-enforceable pytest; **omit** on **`code`** if sibling **`test`** task owns verification—**document** schema. |
| **`priority`** | no | string | §16 — **`low`** \| **`normal`** \| **`high`** \| **`urgent`**; persisted Planner field—**§6.4** uses **`effective_priority_rank`** (**§2.5.3a**) when **`deadline`** / SLA applies, not this value alone. |
| **`deadline`** | no | string | ISO 8601 **datetime** (UTC or offset documented); **SLA** hint—**§6.4**. |
| **`path_hints`** | no | string[] | Paths under `/workspace/`. |
| **`design_notes`** | no | string | Text; §4.3. |

```json
{
  "id": "T1",
  "type": "code",
  "description": "Implement rate limiter class",
  "status": "todo",
  "depends_on": [],
  "owner": null,
  "retry_count": 0,
  "plan_revision_id": "rev-001",
  "priority": "normal",
  "input": "Empty module; requirements_summary in global",
  "output": "src/ratelimit.py with TokenBucket class",
  "constraints": ["Python 3.11+", "no external deps"],
  "acceptance_criteria": ["public API documented in docstrings"],
  "test_plan": "Sibling task T2 runs pytest tests/test_ratelimit.py"
}
```

**`type: test`** example (same plan—**`verification`** required):

```json
{
  "id": "T2",
  "type": "test",
  "description": "Unit tests for rate limiter",
  "status": "todo",
  "depends_on": ["T1"],
  "owner": null,
  "retry_count": 0,
  "plan_revision_id": "rev-001",
  "priority": "normal",
  "input": "T1 deliverables in workspace",
  "output": "tests/test_ratelimit.py green",
  "constraints": ["pytest only under /workspace/"],
  "acceptance_criteria": ["pytest tests/test_ratelimit.py passes"],
  "test_plan": "pytest tests/test_ratelimit.py from /workspace/",
  "verification": {
    "kind": "pytest",
    "paths": ["tests/test_ratelimit.py"],
    "extra_args": []
  }
}
```

`plan_revision_id` must align with **§17.3** and the project’s approved revision before execution.

**Optional handoff fields (Planner — §4.3):** implementations **should** persist **`path_hints`** and **`design_notes`** on the task record when present so checkpoints and tool inputs stay aligned. **§2.5.1** TaskSpec fields **`input` … `test_plan`** are **required** for **§10.2 Mode 1** **every** task; **`verification`** is **required** for **every `type: test`** task (**§2.5.1a**).

3.2.1 Task execution unit — scheduling vs tool granularity (normative)

**Problem addressed:** “**Coder task**” spans **many** internal LLM turns; the **scheduler** must know what **one assignment** means.

**Definitions:**

	•	**Task (DAG node)** — the **§3.2** record; **scheduling** selects **whole Tasks**, not arbitrary sub-steps.
	•	**Dispatch unit** — one **`todo`** Task moved to **`in_progress`** and bound to one **`Worker`** (**§6.4.1**) until the orchestrator **closes** that attempt (**§4.1.1**).
	•	**Tool execution slice** — one or more **`execute`** calls **inside** a role Tool (e.g. multiple LLM rounds in one **Coder** `execute`) **without** orchestrator-visible **`Task.status`** change—**implementation-internal** unless you expose sub-steps in **§6.7** streams.

**Normative:** the **Orchestrator** **schedules at Task grain**; **Workers** implement **Task-level** **`execute(task, context)`** (**§6.3**) that **may** be multi-step internally. **Do not** split one **§3.2** Task across **two** concurrent **`in_progress`** rows for the same **`id`**.

3.3 Worker

Many **Worker** rows may exist at runtime; **Assistant** creates or retires them as needed. `id` must be unique (e.g. `coder_2`, `tester_1`). `role` is one of the role types under Workers above (or future extended roles if registered as Tools).

```json
{
  "id": "coder_1",
  "role": "coder",
  "status": "idle",
  "repo_root": "."
}
```

**`repo_root` (optional, recommended for `coder`):** path **relative to `/workspace/`** pointing at the **single git repository root** this worker “owns” for concurrent-write policy (`.` = workspace root). Persist in checkpoints (§6.6) when used.

**Repo–worker affinity (normative default):** treat **one logical `coder` worker ↔ one repository** (one **`.git`** root). **Do not** run two **`coder`** workers against the **same** repo **HEAD** at once unless **§9.2** documents a safe pattern (branch-per-worker merge, locks). If **one repo** needs **parallel** implementation lanes, **Planner** **should** **split** work into **disjoint** scopes—separate **`repo_root`** (e.g. monorepo packages) or **`path_hints`** with **one dedicated `coder` instance** each—or **serialize** coders on that repo. **Tester** / **Reviewer** **may** still operate across the same tree per task scope.

⸻

4. Workflow (Core Loop)

Step 1: Input

User provides:

```text
"Build a rate limiter in Python"
```

Step 2: Planning Phase

**Before** **Planner** runs on **underspecified** goals, implementations **should** run the **clarification loop** (**§2.5.6**) so **Planner** is not the **first** and **only** interpreter of vague CEO text.

Planner generates:

- Requirements summary (stored per **§3.1** — global context and/or `Project.requirements_summary`, not inside `tasks`)
- Task list

Example:

```json
[
  {
    "id": "T1",
    "type": "code",
    "description": "create limiter class",
    "depends_on": [],
    "plan_revision_id": "rev-001"
  },
  {
    "id": "T2",
    "type": "test",
    "description": "write unit tests",
    "depends_on": ["T1"],
    "plan_revision_id": "rev-001"
  }
]
```

(After CEO approves `rev-001`, set **`approved_plan_revision_id`** on the project — §17.3.)

Step 3: CEO Approval

- Display plan (include **`plan_revision_id`** — §17.3)
- Wait for:
  - **APPROVE** — bind **`approved_plan_revision_id`** to the displayed revision; checkpoint immediately (§6.6); execution may start only tasks whose **`plan_revision_id`** matches (§3.2, §17.3).
  - **Modifications** — MVP **must** support **natural-language** feedback: Assistant (or Planner) produces a **new** task list and a **new** `plan_revision_id`; CEO must approve again. **Structured** edits to tasks (patch ops) are **optional** (§13).

Step 4: Execution Loop

Main loop (concept; authoritative detail in §7):

```python
while not all_tasks_done:
    pick next task  # §6.4.1 scheduling_dispatch_tick + §6.4 DAG-ready set
    worker = assign_or_provision_worker(task, state)  # §6.4.1; §2.2 / §7
    execute task  # via worker; detail in §7
    validate result
    if fail:
        analyze + retry
```

4.1 Task lifecycle and retry state machine (normative)

The pipeline is **not** a one-shot linear chain. Each **Task** is driven by an explicit **finite state machine**; the orchestrator is the **only** authority that changes `Task.status` and decides **retry vs terminal vs escalate**. **Who may set `done`** is **§2.5.7** (task closure)—**not** individual worker Tools.

**States** — use **§16** strings. Normative lifecycle:

- **`todo`** — runnable per §6.4 or **queued for retry** after a failed attempt (feedback merged into shared memory — §6.5.1). (*Informal: **pending**.*)
- **`in_progress`** — a worker holds the task; tools may write **local** context. (*Informal: **running**.*)
- **`needs_review`** (optional — §16) — worker pass **complete** but **Reviewer** **quality gate** (**§5.4**) **must** run before **`done`**; **document** if you use it (**§2.5.4**).
- **`done`** — terminal success for that task. (*Informal: **success**.*)
- **`failed`** — optional terminal per-task failure record before project-level **`blocked`** / `escalate()`; implementations **may** use `failed` + checkpoint instead of jumping straight to `Project.status: blocked`.
- **`blocked`** (optional on Task) — awaiting CEO or external input; distinct from “retryable failure.”

**Events and transitions (normative intent):**

| From | Event | To | Notes |
| ---- | ----- | -- | ----- |
| `todo` | worker starts | `in_progress` | Set `owner` / binding per §3.3 |
| `in_progress` | worker returns success | `done` | Checkpoint §6.6 — default when **no** **`needs_review`** gate |
| `in_progress` | worker returns success, Reviewer gate on success path | `needs_review` | Optional — **§2.5.4**; then Reviewer **§5.4** |
| `needs_review` | Reviewer approves / pass | `done` | Checkpoint §6.6 |
| `needs_review` | Reviewer requests changes | `todo` | Increment **`retry_count`** per policy; merge **§6.5.1** |
| `in_progress` | worker returns structured failure | (reviewer pass) | Reviewer Tool §5.4; **do not** silently re-run the same LLM step without recording feedback |
| After review | `retry_count < max_retries` | `todo` | Increment `retry_count`; attach **reviewer output** to **global** / **task-scoped memory** §6.5.1; orchestrator picks **which worker runs next** per routing rules below |
| After review | `retry_count >= max_retries` | `escalate()` / `blocked` | **Terminal** for the harness loop; human or CEO policy §7 |
| `blocked` | CEO / operator unblocks | `todo` or `in_progress` | Policy-defined |

**When to retry (normative):** retry **only** after a **Reviewer** (or equivalent structured diagnosis) step **unless** the failure is a **transient** provider error (§17.1) handled by bounded API retries **inside** the tool. **Same-task retry:** for a **`code`** task failure, re-dispatch **Coder** with updated memory. **`test`** task failure: **do not** treat as final; route to **implementation fix** — default policy: run **Coder** against the **upstream `code` task’s scope** (ids in `depends_on`) or **path hints** on the test task (§4.3), then re-run **Tester** for the failed **`test`** task (task returns to `todo` / `in_progress`). Implementations **must** document whether they **re-open** upstream `done` code tasks vs keep them `done` and use an explicit **fix pass** (orchestrator-invoked coder step); either is valid if **checkpoints** and **memory** make the fix auditable. **Concrete failure matrix:** **§4.4**.

**When the run ends (normative):** **Success** — all tasks for **`approved_plan_revision_id`** are `done` → set **`Project.status`** to `done`. **Failure / stop** — `escalate()`, CEO cancel, or unrecoverable error → `blocked` or `cancelled` per §16; **no** infinite retry loop.

**Loops vs linearity:** the **harness** is a **cycle** `implement → test → diagnose → fix → …` until pass or **max retries** / **escalate**. The DAG defines **dependencies**; the **state machine** defines **how failures re-enter** the loop (§8).

4.1.1 Runtime state transition ownership (normative)

**Problem addressed:** §4.1 defines **states** and **intent** but not **who** commits each change to the **authoritative** task / project store—leading to “is it the worker, the reviewer, or pytest?” ambiguity.

**Single writer:** the **Orchestrator** (Assistant process) **owns** persistence of **`Task.status`**, **`Project.status`**, **`Worker.status`**, **`Task.owner`**, and **`file_locks`**. **Planner**, **Coder**, **Tester**, and **Reviewer** **Tools** return **`ToolResult`** (**§6.3.1**) **only**—they **must not** directly set canonical **`Task.status`** in the store (**§2.5.7**).

| Outcome (summary) | **Who commits** | **When** |
| ----------------- | --------------- | -------- |
| `todo` → `in_progress` | Orchestrator | After **`assign_or_provision_worker`** selects a worker for dispatch (**§6.4.1**); **checkpoint** per **§6.6** |
| `in_progress` → `done` | Orchestrator | After **§2.5.7** closure: required Tools green (**Execution Tool** on **`verification`** for **`test`**, etc.) and **`needs_review`** path satisfied if used |
| `in_progress` → `needs_review` | Orchestrator | Worker Tool **`success: true`** and **§2.5.4** success-path Reviewer gate is enabled |
| `needs_review` → `done` | Orchestrator | After Reviewer Tool **`success`** with **pass** / structured approve (**§5.4**) |
| `needs_review` → `todo` | Orchestrator | After Reviewer requests changes (**§4.1**); merge feedback to **§6.5.1** |
| Failure from worker step | Orchestrator | After **`success: false`** **Result** → run Reviewer / routing per **§4.4**; orchestrator applies **`retry_count`**, **`todo`**, **`failed`**, **`escalate()`**—**not** the failing Tool |
| **`Project.status`** changes | Orchestrator | **§4.2** (e.g. CEO **APPROVE**, all tasks **`done`**, **`escalate()`**) |

**Tests do not auto-flip `Task.status`:** raw pytest exit code is **not** authoritative; the **Execution Tool** produces **`ToolResult`**, and the **Orchestrator** maps that to FSM transitions (**§6.2.1**).

4.2 Project / session orchestration state (normative)

**`Project.status`** (§16) complements per-task FSM: `planning` (pre-CEO-approve), `executing`, `done`, `blocked`, `cancelled`. Transitions: `planning` → `executing` on CEO **APPROVE**; `executing` → `done` when all tasks **done**; `executing` → `blocked` on **escalate** or hard stop; `blocked` → `executing` only after explicit human/CEO resume policy.

4.3 Planner executable output contract (normative)

**`plan.md` (or prose plan) is optional and non-authoritative for execution.** The **authoritative** plan artifact is the **structured task list** (JSON) materialized as **§3.2** tasks with **`plan_revision_id`** (§17.3).

**Minimum per task in the Planner output (beyond §3.2):**

- **`description`** — implementation- and test-tractable; **must** be specific enough for **Coder** and **Tester** to derive scope without guessing CEO intent alone.
- **`depends_on`** — DAG edges; validated for acyclicity §6.4.

**TaskSpec (required for §10.2 Mode 1 — §2.5.1 / §2.5.1a):** **`input`**, **`output`**, **`constraints`**, **`acceptance_criteria`**, **`test_plan`** on **every** task; **`verification`** on **every `type: test`** task—**must** appear in the **authoritative** JSON before CEO **APPROVE**, and the **whole** task list **must** pass **JSON Schema** validation (**§2.5.1a**).

**Strongly recommended (machine-consumable handoff):**

- **`path_hints`** (string[], optional) — glob-like or explicit paths under `/workspace/` for **conflict avoidance** §6.4 and **coder** focus.
- **`design_notes`** (string, optional) — short rationale; orchestrator **promotes** a digest to **global** so **Coder** / **Tester** / **Reviewer** share **why**, not only **what**.

Orchestrator **must** persist Planner outputs so **downstream tools** do not rely on **silos** (§6.5.1). **CEO-facing** rendering may still summarize the JSON into markdown.

4.3.1 Dynamic plan graph updates (normative)

**Problem addressed:** the DAG is **not** frozen after first **APPROVE**—**retry** mutates task memory, **replan** inserts tasks, **failure routing** may add branches (**§4.4**).

**Authoritative mutation surface:** only the **Orchestrator** applies changes to **`project.tasks[]`**, **`depends_on`**, and **`plan_revision_id`** on tasks after initial materialization. Typical operations (names illustrative):

	•	**`merge_replan_tasks(project, new_tasks, new_plan_revision_id)`** — after Planner + CEO **APPROVE** (**§17.3**): append or replace per README; **re-run** cycle detection (**§6.4**); **stamp** new **`plan_revision_id`** on every new task; **do not execute** until **`approved_plan_revision_id`** matches (**§17.3**).
	•	**Retry / feedback** — update **`retry_count`**, **§6.5.1** memory, optional **Task** text fields; **may** keep same **`plan_revision_id`** unless replan.
	•	**Failure-branch tasks** — if policy adds **new** task ids (e.g. explicit fix-pass node), same **merge** rules: **acyclic** `depends_on`, **checkpoint** (**§6.6**).

**`scheduling_dispatch_tick`** (**§6.4.1**) **always** reads the **current** graph from the store after any merge.

4.4 Failure handling strategy (normative)

This section makes **test failure** and related cases **explicit**; the state machine remains **§4.1**. **Treating every failure the same** (one generic “retry”) **without** a **`failure_type`** is **non-compliant** for **§10.2 Mode 1**—Assistant **must** branch on **taxonomy** and **log** the choice (**§2.5.9**).

**`FailureType` (normative tokens for routing + logs):** use these **exact** strings (or a documented superset in README) on **Reviewer** output, **`escalate()`** payloads, and **`DecisionLog`** (**§2.5.9**):

| **`failure_type`** | Typical signal | **Default routing** (override only via **documented** **`failure_policy`**) |
| ------------------ | -------------- | ----------------------------------------------------------------------------- |
| **`test_failure`** | Execution Tool **`success: false`** from pytest (§6.2, §6.2.1) | **Reviewer** → **§4.1** retry → **Coder** (fix implementation) then re-run **Tester** / pytest |
| **`syntax_error`** | Parse / compile / import error **before** or **outside** meaningful pytest (logs, Coder Tool) | **Reviewer** (short) → **Coder** retry with **explicit** error location—**do not** escalate to **Planner** unless **policy** says so after **N** attempts |
| **`requirement_mismatch`** | **Reviewer** or **Tester** concludes output **does not** meet **TaskSpec** / CEO intent (**§5.4** dim 1) | **Planner** replan path (**new** `plan_revision_id`, CEO **APPROVE**) **or** **`escalate()`** with CEO choice—**not** infinite **Coder**-only retries |
| **`infra_error`** | Timeout, disk, missing interpreter, provider outage (§17.1) | Transient → bounded **internal** retry / backoff; fatal → **`escalate()`** or `blocked`—**log** as **`infra_error`** |

**Legacy table (same facts, reader-friendly):**

| Kind | Maps to **`failure_type`** | First actions |
| ---- | -------------------------- | ------------- |
| **Test red** | **`test_failure`** | Persist **`last_pytest`** (§6.5.1); **never** mark project `done`; invoke **Reviewer** with logs + task id + TaskSpec |
| **Code / generation fail** | often **`syntax_error`** or **`test_failure`** after partial run | Reviewer → route per table above |
| **Infra** | **`infra_error`** | Classify transient vs fatal per **`failure_policy`** |
| **Flaky tests** | **`test_failure`** + policy flag (optional) | Bounded re-runs **only** with **logged** policy + **`DecisionLog`**—**no** silent loops |

**Recovery strategy (normative — per `failure_type`, not generic “fail → retry”)** — Assistant **must** execute **these** phases (subset of **§4.1** / **§7**) and **append** **`DecisionLog`** (**§2.5.9**) with **`failure_type`** + **`recovery_phase`**:

| **`failure_type`** | **Recovery phases** (order) | **Stop / escalate when** |
| ------------------ | --------------------------- | ------------------------- |
| **`test_failure`** | (1) Persist **`last_pytest`** (2) **Reviewer** structured diagnosis (3) Increment **`retry_count`** (4) Route **Coder** per **§4.1** (5) Re-queue **`test`** → Execution Tool on **`verification`** | **`retry_count`** ≥ per-task **`max_retries`** **or** **`budget.max_retries_total`** exhausted (**§17.2**) → **`escalate()`** |
| **`syntax_error`** | (1) **Reviewer** (short) classifies as syntax/import (2) **Coder** retry with pinned error snippet (3) Re-run same task scope | After **N** attempts (**`retry_policy`**) with **no** parse progress → **`escalate()`** or **Planner** if policy merges with **`requirement_mismatch`** |
| **`requirement_mismatch`** | (1) **Stop** blind **Coder** loop (2) **`DecisionLog`**: `recovery_route: replan_or_ceo` (3) **Planner** replan (**new** `plan_revision_id`) **or** **`escalate()`** with CEO **modify_plan** | **Never** unbounded **Coder-only** retries for this type |
| **`infra_error`** | (1) Classify **transient** vs **fatal** (**§17.1**) (2) Transient: bounded backoff **inside** tool or orchestrator (3) Fatal: **`escalate()`** / `blocked` | Auth/config errors → **fail fast**, **no** token burn loop |

**`test` task failure (step-by-step, normative):**

1. Store full pytest **JSON** (or equivalent) in **`last_pytest`** and checkpoint (§6.6).
2. Run **Reviewer** with **shared memory** (§5.4, §6.5.1); persist **`last_reviewer_feedback`**.
3. Increment **`retry_count`** on the harness loop per **implementation policy** (typically the **`test`** task and/or a linked **`code`** scope); **must** be **bounded** (§7).
4. Route **Coder** to fix implementation per **§4.1** (upstream `depends_on` **`code`** task or **`path_hints`**).
5. Re-queue **`test`** task (return to `todo` / `in_progress`); re-run **Execution Tool** after code changes.
6. If retries exhausted → **`escalate()`** with summary (task ids, logs pointer, counts).

**Forbidden:** treating red pytest as success; hiding failures from Reviewer; unbounded retry without **`retry_count`**.

4.5 Interface alignment phase (optional — Architect)

Real teams often **align interfaces before coding**. This spec admits that as an **optional** phase **after** requirements / plan draft and **before** or **woven into** **`code`** tasks.

When **enabled** (config or plan shape — §13):

- **`Worker.role: architect`** (registered extension) runs **`Task.type: design`** nodes that **do not** ship production logic—they produce **artifacts** under `/workspace/` (e.g. **`interface.md`**: public API, endpoints or module boundaries, **data model** sketch, invariants).
- **Planner** (or Assistant) **must** insert **`depends_on`** so **`code`** tasks **depend on** completed **`design`** tasks where alignment is required.
- Orchestrator **promotes** a short **`interface_digest`** into **global** (§6.5.1) so **Coder** / **Tester** / **Reviewer** share the same contract.

**MVP default:** phase **off**; turn on when registering **Architect** per **§13**.

⸻

5. Agent Responsibilities

5.1 Planner

Input:
	•	user goal

Output:
	•	**Authoritative:** structured task list (JSON) satisfying **§4.3** (each task: **`description`**, **`depends_on`**, **`plan_revision_id`**, **§2.5.1** TaskSpec fields, **`verification`** on **`type: test`**; optional **`priority`**, **`deadline`**, **`path_hints`**, **`design_notes`**).
	•	**Optional:** human-readable `plan.md` for CEO review — **must not** be the only plan surface; orchestrator materializes **§3.2** tasks from JSON.

Constraints:
	•	no code
	•	no execution

⸻

5.2 Coder

Input:
	•	task (including **`description`** and recommended **`acceptance_criteria`**, **`path_hints`** — §4.3)
	•	**shared memory slice** — at minimum **`requirements_summary`**, **`design_notes`** digest if present, **`last_reviewer_feedback`** / **`last_pytest`** when in a fix loop (§6.5.1)
	•	existing code context (files under `/workspace/`)

Output:
	•	code (prefer diff format)

**Implementation profiles (choose one; document in README):**

- **Profile A — LLM + file tools:** in-process model + **§6.1** / patch apply; **§6.5.2** applies to each model call.
- **Profile B — Terminal-agent Coder (e.g. Claude Code):** orchestrator runs a **subprocess / PTY** session of a **CLI coding agent** that **executes shell commands** and **writes files** under policy. The **outer** contract remains **§6.3** (`execute` → structured `Result`); **§9.1** / **§17.4** still gate commands and paths; **§6.5.2** applies to any **orchestrator-controlled** prompt turns inside the session. See **§13**.

**Both** profiles **must** respect **§9.4** when concurrent mutators are enabled.

Constraints:
	•	only write code
	•	no explanation

⸻

5.3 Tester

Input:
	•	task (including **`acceptance_criteria`** when provided — §4.3)
	•	**shared memory** — **`requirements_summary`** and relevant **design digest** so tests align with intent, not only with local diffs (§6.5.1)

Output:
	•	unit tests

⸻

5.4 Reviewer (system quality gatekeeper)

**Role:** **not** “comment on code style” only—the **Reviewer** is the **system quality gatekeeper** against **§2.5.1** **TaskSpec** and **artifacts** (**§2.5.2**).

Input:
	•	error logs / test results (when failing) **or** **workspace / artifact** pointers (when **success-path** gate—if **`needs_review`** §4.1)
	•	**shared memory** — **task id**, full **TaskSpec** fields (**`input`**, **`output`**, **`constraints`**, **`acceptance_criteria`**, **`test_plan`**), **`requirements_summary`**, **`design_digest`**, **`last_pytest`** when relevant (§6.5.1)

Output:
	•	**Structured `review_report`** (**recommended**) in Tool **`payload`** plus human-readable analysis; **must** address the **dimensions** below when evidence exists (cite **pass / fail / unknown** per dimension):
		1. **Requirement match** — implementation vs **TaskSpec** **`output`** / **`description`**.
		2. **Test coverage** — adequacy vs **`test_plan`** and **`acceptance_criteria`**.
		3. **Edge cases** — obvious gaps, error handling, boundary conditions.
		4. **Architecture / design fit** — consistency with **`design_notes`** / **`interface_digest`** when present.
		5. **Performance** — gross inefficiency or missing stated perf **constraints** (if any).

Constraints:
	•	DO NOT write production implementation code (diagnostic snippets **in** the report **OK** if policy allows)

⸻

5.5 Architect (optional division — §13)

**Not in the default MVP role set** unless explicitly registered (**§13**, **§16** extension values).

Input:
	•	user goal and/or **requirements_summary**; optional Planner task breakdown

Output:
	•	**`interface.md`** (required artifact when this role runs) under `/workspace/` — API surface, data model, constraints
	•	Optional machine-readable appendix (e.g. OpenAPI fragment) — implementation choice

Constraints:
	•	no implementation code in MVP profile (spec-only); **no** pytest ownership—**Tester** still validates implementation later
	•	**Tool + closed allowlist** like other workers (§17.4)

⸻

6. Tools (Must Implement)

6.1 File Tool
	•	read_file(path)
	•	write_file(path, content)

Orchestrator **must** apply **§9.4** before **`write_file`** when concurrent mutators are possible (or rely on proven **serial** exclusion).

⸻

6.2 Execution Tool

Run tests:

```bash
pytest
```

Return (failure example):

```json
{
  "success": false,
  "error": "...",
  "logs": "..."
}
```

Return (success example):

```json
{
  "success": true,
  "error": null,
  "logs": "..."
}
```

Run from repository root or explicitly set cwd to `/workspace/` so imports and test discovery match §9.

6.2.1 Execution substrate — how code and tests run (normative)

**Problem addressed:** “agents wrote files” is not enough—implementations **must** define the **real** runtime that executes tests and implied code.

	•	**Code** — “running” user-generated code means the **host Python** (or declared runtime) loading modules **from `/workspace/`** via normal imports after files are written; there is **no** separate mystery runtime unless documented. Document **interpreter version** (e.g. 3.11+) and optional **venv** path in README.
	•	**Tests** — **only** through the **Execution Tool** (§6.2): **subprocess** (or equivalent) invoking **`pytest`** with **cwd = `/workspace/`** (or documented equivalent), **argv** built from the task’s **`verification`** object (**§2.5.1a**—`paths` + `extra_args`), capturing **stdout/stderr** into structured **`logs`**, exit code → **`success`**. **No** ad-hoc “exec model text as shell” for pytest.
	•	**Environment** — `PYTHONPATH`, venv activation, and deps are **operator / repo** responsibility (e.g. `requirements.txt` in workspace generated or pinned); Assistant **may** surface “missing dependency” from logs to Reviewer.
	•	**Future** — containers, remote runners, multi-language test commands → **§13**; MVP stays **local subprocess + `/workspace/`** per §9.1.

⸻

6.3 Tool contract (SAS-aligned, required)

Every executable unit (file I/O, pytest, planner/coder/tester/reviewer LLM steps, and any nested agent) is a **Tool** in the SAS sense: uniform surface, composable, registry-addressable.

Each tool **must** define:

	•	**Stable `name`** (registry key) and short **description** (for LLM routing if used).
	•	**Input schema** and **output schema** — JSON-serializable types; validate inputs before execute.
	•	**`execute(input, context) -> Result`** — returns a structured result: `success`, optional `payload`, `error` / `logs` (same spirit as §6.2). Tools **must not** silently swallow exceptions; map to structured errors.
	•	**LLM-backed tools** — when `execute` calls a model, **message assembly** **must** follow **§6.5.2** (stable block order, system policy, truncation order).
	•	**Idempotency where practical** — file writes are explicit; pytest is read-mostly; LLM tools are inherently non-deterministic but should accept **deterministic task ids** in input for traceability.

**Optional but recommended (match SAS generators):** implement execution as a **Python generator** that **yields** progress / partial events, then a final result—enables streaming logs and **pause/resume** (§6.7). If MVP ships sync-only `execute`, keep the **same Result type** so generators can wrap later.

Nested **AgentV3**-style tools (sub-planner, sub-coder) are **optional** in v1; flat Tool list under orchestrator is OK.

6.3.1 Tool `Result` schema (normative)

**Problem addressed:** “everything is a Tool” is useless without a **portable** result shape so the orchestrator can branch, log, and drive **§4.4** / **§7** without ad-hoc parsing.

Every tool’s **`execute`** **must** return (or culminate in) a value matching this **minimum** structure (names may be nested under `payload` if documented):

| Field | Required | Type | Purpose |
| ----- | -------- | ---- | ------- |
| **`success`** | yes | boolean | **`true`** iff the tool’s contract succeeded. |
| **`error`** | if `success` is false | string \| null | Short machine- or human-readable reason. |
| **`logs`** | recommended | string \| null | Truncated stdout/stderr or trace (same spirit as §6.2). |
| **`payload`** | no | JSON object | Tool-specific structured output (e.g. parsed plan JSON, file paths written). |
| **`artifacts`** | no | string[] | Paths under `/workspace/` or opaque URIs **produced or mutated** by this step—enables audit and **§9.3** / CI. |

**Informative Python sketch:**

```python
# logical shape; map to your Result type
class ToolResult:
    success: bool
    error: str | None
    logs: str | None
    payload: dict | None
    artifacts: list[str]
```

**Input schema** for each tool **must** be **JSON-serializable** and **validated** before `execute` (already required above); **text** fields (e.g. `task.description` passed through) are **still** part of that schema as **`string`**.

⸻

6.4 Task scheduling (DAG, required)

Tasks (§3.2) form a directed graph: edge `A → B` exists if `B.depends_on` contains `A.id`.

**Scheduler policy (normative):** DAG + worker pool + retry **alone** do **not** define *which* ready task runs *when* or *how many* at once. Implementations **must** document a **`scheduler_policy`** (**§2.5.3**) that **binds** to the rules below—**default** binding: **deterministic** ordering among **§2.5.3a-eligible** tasks + **§2.2** / **`parallelism_policy`** concurrency caps. **Forbidden:** choosing the next task by **undefined** order or **model discretion**.

**Logic- and time-aware:** readiness is **logic-driven** (`depends_on`, plan approval). Among tasks that pass **§2.5.3a**, scheduling uses **`effective_priority_rank`** (SLA-adjusted—**§2.5.3a**), **`deadline`**, and **`sla_policy`**—**not** `depends_on` and **`retry_count`** alone, and **not** static **`Task.priority`** alone when **`deadline`** is set.

	•	**Cycle detection** — on plan load (after Planner or CEO edit), reject cyclic `depends_on` with a clear error; do not start execution.
	•	**Ready set** — a task is **runnable** when all `depends_on` ids are **done**, CEO has approved the plan, and the task’s **`plan_revision_id`** equals **`approved_plan_revision_id`** on the project (§17.3).
	•	**Dispatch eligibility** — DAG-runnable **≠** dispatchable for **budgeted** work: apply **§2.5.3a** layer **1** before assigning **LLM** (or other budgeted) steps; only **budget-eligible** tasks compete in the ordering below. Non-budget tools (e.g. pure file read) **may** be exempt—**document** in README.
	•	**Ordering (effective urgency + deadline)** — among tasks **eligible** per **§2.5.3a** for the current dispatch, Assistant **must** pick the **next** task using a **deterministic** sort: (1) **`effective_priority_rank`** (**§2.5.3a** / **§16** tier ordering: **`urgent`** > **`high`** > **`normal`** > **`low`**; **default** `normal` when no SLA boost applies), (2) **`deadline`** ascending (**earlier** first) when set—tasks **without** **`deadline`** sort **after** tasks **with** **`deadline`** at the same **effective** rank unless **`scheduler_policy`** documents otherwise, (3) stable tie-break **`Task.id`**. If **`deadline`** is **in the past** when the task becomes eligible, **emit** **`DecisionLog`** + **CEO-visible** warning and follow **`sla_policy`** (**§2.5.3**): **continue**, **bump** **`effective_priority_rank`**, or **`escalate()`**—**document** in README.
	•	**Parallelism** — if multiple tasks are runnable, implementation **may** run them **serially** (simpler) or **in parallel** (thread/process pool); both are valid if **workspace conflicts** are avoided (e.g. don’t run two coders writing the same paths concurrently without locking—MVP may serialize all `code` tasks).
	•	**Executable conflict control** — if **concurrent** mutating **`coder`**s (or equivalent) are **enabled**, the implementation **must** enforce **§9.4 file locks** **or** **prove** all such writers are **serialized**; **policy-only** “don’t collide” text is **insufficient**.
	•	**Concurrency ceiling for `code`** — enforce **§2.2** using the **effective** cap after any **host clamp** (§2.2): default **maximum two** concurrent executions of tasks with **`type: code`** (or two `coder` workers doing code work) **per orchestrator process** unless configuration changes it; excess ready code tasks remain **queued** until a slot opens. Other task types may use separate caps in config (e.g. lighter limits on `test` if desired); **optional** host-aware caps for non-code roles belong in §13 unless promoted earlier.
	•	**Worker pool (Assistant)** — when running in parallel, **Orchestrator** assigns each runnable task to a **Worker** (§3.3): reuse an **idle** worker of the right `role`, or **provision** a new logical worker until a **max-per-role** (or global) cap. When the queue is empty or a worker is unused, mark **idle** or **retire** per policy. Same rules as above: **no unsafe overlap** on the same files. For **`coder`** tasks, respect **repo–worker affinity** (§3.3): prefer binding **`repo_root`** + **`path_hints`** so each concurrent coder has a **distinct** repo or **safe** isolation.
	•	**Integration path** — when using SAS, map runnable sets to executor invocations with **dependencies** as in upstream DAG examples; worker pool may map to concurrent tool/agent instances.

6.4.1 Scheduling decision interface and core loop (normative)

**Problem addressed:** prose (“must be deterministic”, “use priority / deadline”) is **not** a **code-level** decision loop; reviewers cannot see **state → decision** or **how many** tasks one dispatch selects. This section fixes that.

**Decision interface (minimum shapes — implement as structs / Pydantic / typed dicts):**

```yaml
# DecisionInput — everything the scheduler needs for one dispatch tick
DecisionInput:
  tasks: [...]                    # §3.2 Task records
  project: {...}                  # §3.1 + approved_plan_revision_id, status
  budget_counters: {...}          # §17.2 / §6.5.1
  budget_limits: {...}            # §17.2 Budget block
  workers: [...]                 # §3.3 Worker records
  now: ...                        # wall-clock for SLA / deadline compare
  policies:                       # resolved §2.5.3 / §2.5.3a bindings
    scheduler_policy: {...}
    sla_policy: {...}
    scaling_policy: {...}
    parallelism_policy: {...}     # effective caps this tick
  file_locks: {...}               # §9.4 when used
  in_flight_tasks: [...]         # tasks with status in_progress — §9.4.1 conflict vs running

DecisionOutput:
  selected_tasks: [...]           # batch chosen this tick (subset of eligible)
  worker_assignment: [...]       # pairs (task_id, worker_id | null)
  decision_log_entries: [...]    # §2.5.9 append payload
  side_effect: null | escalate | blocked   # if no eligible work and budget exhausted, etc.
```

**Default sort precedence (answers “priority vs deadline?”):** primary key = **`effective_priority_rank`** as an **integer tier** after **§2.5.3a** (**`urgent`** > **`high`** > **`normal`** > **`low`** → map to **3, 2, 1, 0** respectively for comparison). Secondary key = **`deadline`** ascending (earlier first; **missing** **`deadline`** → sentinel **+∞** so those tasks sort **after** tasks with deadlines at the **same** tier). Tertiary = **`Task.id`** lexicographic stable tie-break. **Within this default, urgency tier sorts before deadline**—a **`low`** task with a sooner **`deadline`** still sorts **after** an **`urgent`** task with a later **`deadline`** unless **`sla_policy`** boosts the former’s **`effective_priority_rank`**.

**Batch scheduling (`select_parallel_batch`) — normative default:** **greedy** scan of the **sorted eligible** list; append task **`t`** to the batch iff (1) per-**`Task.type`** concurrency limits are respected (**§2.2** / **`parallelism_policy`**—at minimum **`type: code`** count in batch ≤ effective **`max_concurrent_code_tasks`**), and (2) **`workspace_safe(batch ∪ {t}, in_flight_tasks, file_locks)`** (**§9.4.1**) — **must** account for **already running** mutating tasks, **not** only pairwise checks inside the batch. **Stop** when no further task can be appended. **§7.1 MVO serial** mode is **equivalent** to **batch size 1** for mutating work unless README documents a higher cap.

**`assign_or_provision_worker(task, state)` — normative algorithm:**

1. **`required_role`** ← map **`Task.type`** → **`Worker.role`** (**§17.5**: `code`→`coder`, `test`→`tester`, `design`→`architect` when registered).
2. **Reuse:** from **`state.workers`** where **`role == required_role`**, **`status == idle`**, and **affinity** matches (**`repo_root`** / **`path_hints`** — §3.3), select **deterministically** (default: **lexicographically smallest** **`Worker.id`**; alternatives **documented** in README).
3. **Provision:** else if **active** workers of **`required_role`** **<** **`scaling_policy`** cap for that role (and global cap if any), **create** a new **`Worker`**, bind to **`task`**, return it.
4. **Else:** return **`null`** assignment this tick; task stays **`todo`**; **`DecisionLog`** **should** record **`decision: worker_cap_wait`** with **`task_id`**.

**Reference core loop (informative names — bind to your codebase):** the following **Python-shaped** pseudocode is the **intended** mechanical spine; **§2.5.3a** ordering and **§4.1** FSM still **authoritative** if this sketch omits an edge case.

```python
def scheduling_dispatch_tick(state: DecisionInput) -> DecisionOutput:
    ready = [
        t for t in state.tasks
        if t.status == "todo"
        and all(task_by_id(state.tasks, d).status == "done" for d in t.depends_on)
        and t.plan_revision_id == state.project["approved_plan_revision_id"]
        and state.project["status"] == "executing"
    ]
    eligible = [t for t in ready if not violates_budget_next_step(t, state)]
    if not eligible:
        return DecisionOutput(
            selected_tasks=[],
            worker_assignment=[],
            decision_log_entries=[{"decision": "escalate", "reason": "budget_exhausted"}],
            side_effect="escalate",
        )

    for t in eligible:
        t.effective_tier = compute_effective_priority_rank(
            t.priority, t.deadline, state.now, state.policies.sla_policy
        )  # §2.5.3a → one of urgent|high|normal|low

    tier_rank = {"urgent": 3, "high": 2, "normal": 1, "low": 0}
    INF = float("inf")
    ordered = sorted(
        eligible,
        key=lambda t: (-tier_rank[t.effective_tier], deadline_key(t.deadline, INF), t.id),
    )

    batch = select_parallel_batch(
        ordered,
        state,
        max_concurrent_code=state.effective_max_concurrent_code_tasks,  # §2.2 after host clamp
        workspace_safe=lambda b, t: workspace_safe(b, t, state.in_flight_tasks, state.file_locks),
    )

    assignments = [
        (task.id, assign_or_provision_worker(task, state)) for task in batch
    ]
    log_entries = [{"decision": "schedule_batch", "tasks": [a[0] for a in assignments]}]
    return DecisionOutput(
        selected_tasks=batch,
        worker_assignment=assignments,
        decision_log_entries=log_entries,
        side_effect=None,
    )
```

**Failure routing:** **`apply_failure_policy`** in ad-hoc loops is **not** a substitute for **§4.1** / **§4.4**; tasks **not** in **`todo`** or **blocked** by Reviewer / **`needs_review`** **do not** appear in **`ready`**. Hooks that **skip** a task based on **`failure_policy`** **must** **`DecisionLog`** the skip.

⸻

6.5 Three-layer context (required)

Mirror SAS **local / parent / global** so long runs and nested tools stay coherent. Store as a **JSON-like tree** (or `ContextNode`-equivalent) serializable with session checkpoints (§6.6).

| Layer | Scope | XR-AI-Co contents (minimum) |
| ----- | ----- | ---------------------------- |
| **global** | Whole session / project | `project` (§3.1), user goal text, CEO decision history, requirements summary from Planner, optional **`interface_digest`** (§4.5), **`plan_revision_id` / `approved_plan_revision_id`** (§17.3), harness signals (last pytest JSON, escalation flags) |
| **parent** | Orchestrator “frame” | Current phase (`planning` / `executing` / `blocked`), task queue snapshot, **active worker pool** (ids, roles, status, task binding), optional **`file_locks`** (**§9.4**), retry policy counters aggregate, **effective** `max_concurrent_code_tasks` after clamp, optional **host snapshot** (cpu_count, memory if captured—§2.2) |
| **local** | One tool invocation | Current task id + description, last LLM messages for that step, scratch notes, partial file edits before commit |

Rules:

	•	Tools read **local** by default; promote summaries to **parent**/**global** only through orchestrator or explicit tool contract.
	•	On **resume** after crash, reload **global** + **parent** from disk; **local** may be discarded or restored from last checkpoint per tool.

6.5.1 Shared memory contract (normative)

Workers **must not** be “each on their own island.” The orchestrator **maintains** a **shared, checkpointed** view (primarily **global**, optionally **parent**) that **all** role tools **read** through their **input schema** (§6.3).

**Minimum keys / payloads** (names are logical; implementations may namespace them):

| Key / pattern | Consumers | Purpose |
| ------------- | --------- | ------- |
| **`requirements_summary`** | Planner (write), Coder, Tester, Reviewer (read) | CEO + Planner intent |
| **`design_digest`** or aggregated **`design_notes` from tasks** | Coder, Tester, Reviewer | Planner rationale / constraints |
| **`interface_digest`** (optional) | Coder, Tester, Reviewer | Architect / **`interface.md`** summary when §4.5 enabled |
| **`last_pytest`** (structured §6.2) | Reviewer, Coder on retry | Ground truth for failures |
| **`last_reviewer_feedback`** (string or structured) | Coder, Tester on retry | Diagnosis and fix hints |
| **`task_feedback[task_id]`** (optional map) | Next invocation for that task | Per-task scratch that survives retries |
| **`knowledge_base`** (optional object) | Planner (read/write digest), Coder on retry, Reviewer | **§2.5.5** — e.g. **`failed_attempts`**, **`common_bugs`**, **`patterns`**, **`best_practices`** (each string[] or small structured rows); **redact** secrets |
| **`budget_counters`** (optional object) | Assistant (read/write) | **§17.2** — e.g. **`tokens_used_session`**, **`estimated_cost_project`**, **`retries_used_project`**; **checkpoint** with project |

**Promotion rules:** Planner outputs **requirements_summary** and per-task **`design_notes`** → orchestrator **writes** **`requirements_summary`** to **global** and merges **design** into **`design_digest`**. After pytest or Reviewer, orchestrator **updates** **`last_pytest`** / **`last_reviewer_feedback`** before re-dispatching **Coder** or **Tester** (§4.1). **Reviewer** **should** append **actionable** lines to **`knowledge_base`** when **`review_report`** finds recurring issues (**§2.5.5**).

**Anti-pattern:** passing **only** the current task id to a worker with **no** global slice — **non-compliant** for MVP except where a tool explicitly opts out in documented tests.

6.5.2 LLM prompt assembly (normative)

**Problem addressed:** **global / parent / local** define **where data lives**, not **how** it becomes an LLM **message list**. Without a **fixed recipe**, **Coder** (and other roles) will **vary unpredictably** across runs and implementations.

**Applies to:** every **Tool** whose `execute` invokes an LLM (**§6.3**) — Planner, Coder, Tester, Reviewer, optional Architect.

**Normative assembly** (map to your provider’s **system / user / assistant** or **developer** roles):

1. **System (or equivalent fixed role)** — **Stable** per **`Worker.role`**: **§17.4** (untrusted data, allowlist, `/workspace/` root, secrets), **§5.x** role constraints (e.g. Coder writes code only), and an explicit line that **structured sections below are orchestrator facts**, not permission to override policy.

2. **User-side content — same block order on every call for that role:**
   - **Block A — Global:** subset of **§6.5.1** keys (`requirements_summary`, `design_digest`, `interface_digest`, ids as needed). Use **stable headings** (e.g. `## Global`) **or** JSON with fixed key order so prompts are **diffable** and logs comparable.
   - **Block B — Parent:** phase, **task queue summary** (id + status), current **`retry_count`** if relevant, short worker binding—**no** unbounded dumps; **truncate** with ellipsis and checkpoint pointer when long.
   - **Block C — Local / task:** **`Task.description`**, **`acceptance_criteria`**, **`path_hints`**, trimmed **`last_pytest`**, **`last_reviewer_feedback`**, optional **`task_feedback[task_id]`**.
   - **Block D — Untrusted channel:** raw **user goal** / **CEO notes** **last**, so **§17.4** “policy first, untrusted last” is **mechanically** enforced.

3. **Tools / functions** — register **only** allowlisted tools in the provider’s native schema (**§17.4**); do **not** rely on free-text alone for tool definitions unless the stack has no alternative (document if so).

**Truncation when over budget (order of sacrifice):** (1) old **local** chat turns, (2) verbose **`last_pytest.logs`** (keep exit code, tail, summary), (3) **parent** queue detail, (4) **global** digests (summarize)—**never** drop or shorten the **system** policy block. **Document** the exact rules in README.

**Per-role matrix:** implementations **must** document which blocks each **`Worker.role`** receives (e.g. Reviewer **always** Block A+C with **`last_pytest`**; Planner may omit Block C for downstream tasks). **Single** table in README or code docstring is enough.

6.5.3 Context injection by role (normative)

**Injection** means: which **global / parent / local** slices and **which text fields** the orchestrator **must** place into tool input or **§6.5.2** blocks **before** each call. LLMs **do not** pull memory by themselves.

| Worker.role | Minimum injected sources (in addition to **§6.5.2** ordering) |
| ----------- | ---------------------------------------------------------------- |
| **Planner** | **global** (goal, prior `requirements_summary` if replan) + **parent** (phase, queue summary if any). |
| **Coder** | **global** (**§6.5.1** keys) + **current Task** record (**text** `description` + optional criteria / hints) + **workspace snapshot** (file **list** or **truncated** tree / `read_file` excerpts—document cap in README). |
| **Tester** | Same **global** / **task** slice as Coder for alignment; **may** omit heavy workspace if tests only need paths. |
| **Reviewer** | Full **TaskSpec** (**§2.5.1**) + **task** id + **`last_pytest`** (structured + tail of logs) + **`last_reviewer_feedback`** from prior attempt if any + **`retry_count`** + **`knowledge_base`** digest when present (**§2.5.5**). |

**Terminal-agent Coder (§5.2 Profile B):** the **wrapper Tool** **must** still receive the same **logical** injection (e.g. written to a temp **context file** or env JSON) so behavior matches Profile A.

⸻

6.6 Persistence & crash recovery (required)

**Checkpoint** at minimum after: Planner produces a plan; CEO approves; each task transitions to `done`; each failed attempt after Reviewer feedback; `escalate()`.

**Persist** (durable store, e.g. single `session.json` or sqlite—implementation choice):

	•	Project + all tasks (ids, `status`, `depends_on`, `retry_count`, `description`, `type`, **`plan_revision_id` per task**) — use canonical enums in **§16**
	•	Project-level **`plan_revision_id`** (current draft) and **`approved_plan_revision_id`** after CEO approve (§17.3)
	•	Optional **`requirements_summary`** (or global-context equivalent) per §3.1
	•	**Workers** list (§3.3): ids, roles, status, optional `current_task_id`, optional **`repo_root`** for `coder`
	•	Global + parent context blobs (or equivalent keys), including **§6.5.1** shared keys (`requirements_summary`, `last_pytest`, `last_reviewer_feedback`, **`knowledge_base`** when used, etc.), **`file_locks`** when used (**§9.4**), optional **host snapshot** and **effective code concurrency cap** when used (§2.2, §6.5)
	•	**`decision_log`** — append-only **`DecisionLog`** (**§2.5.9**); **ring buffer** with **documented** max entries **OK** if full history is archived elsewhere
	•	**`budget_counters`** — running totals for **§17.2** (**tokens**, **cost estimate**, **project-level retries**) when budgets enabled
	•	Last structured errors / pytest output references (or inlined if small)
	•	Orchestrator cursor: which tasks are done, which is “current”

**Crash recovery:** on restart, load latest checkpoint; **resume** from first non-`done` runnable task (respecting `depends_on`, **`plan_revision_id` vs `approved_plan_revision_id`** — §17.3); do not re-run CEO approval if **`approved_plan_revision_id`** already matches the tasks being executed (unless operator forces replan).

**Align with SAS:** follow the intent of upstream `persistence/` and generator **pause/resume**—exact file layout may differ.

⸻

6.7 Execution stream & pause/resume (required behavior, flexible implementation)

	•	**Observability** — orchestrator must log or stream **phase transitions**, **tool boundaries** (start/end, success/fail), and **§2.5.9** **`DecisionLog`** entries (**decision**, **reason**, **context**) for debugging and **“what is the system doing?”** audits.
	•	**Pause** — operator or API may pause between tasks or between tool steps; state must be **checkpointed** (§6.6) so restart is safe.
	•	**Resume** — reload checkpoint and continue DAG scheduling (§6.4).

Full **generator-native** execution like SAS is **recommended**; if the first shipping code uses synchronous tools, still **persist** after each task so behavior matches the table above.

⸻

7. Orchestrator Logic (IMPORTANT)

**Authoritative transitions:** task / project state machines **§4.1–§4.2** + **§4.1.1** ownership; task closure **§2.5.7**; retry routing **§4.1**; failure taxonomy **§4.4**; dynamic graph **§4.3.1**; shared memory updates **§6.5.1**; context injection **§6.5.3**; LLM prompt assembly **§6.5.2**; scheduling dispatch **§6.4.1**; continuous run loop **§7.1.1**; CEO failure UX **§7.2**; orchestrator MVP subset **§7.3**; Assistant **`DecisionLog`** **§2.5.9**.

7.1 Minimum viable orchestrator (MVO) (normative)

The full spec describes **DAG scheduling**, **worker pools**, **retry FSM**, **memory promotion**, and **checkpoints**—together resembling a **small job scheduler**. Trying to build **“Devin-class autonomy + company OS + infra-grade scheduler”** in **one leap** often yields **unfinished**, **non-running**, or **undebuggable** systems.

**MVO** is the **smallest** orchestrator that still **meets §10.1** and **MVP** requirements. **Ship MVO first**; add **§2.2** pool sophistication, **§9.2** branch-per-worker, **Architect**, and **distributed** runners **after** the green path works.

| Piece | MVO (first runnable milestone) | Progressive (later) |
| ----- | ------------------------------ | ------------------- |
| **Schedule** | **Serial** `get_next_task()` with **DAG** **`depends_on`** | Parallel ready-set, **§2.2** caps, host clamp |
| **Workers** | **One** logical worker id per **role** or **fully serial** execution | Dynamic **provision/retire**, **§3.3** `repo_root` affinity |
| **Memory** | **global** / **parent** / **local** **persisted**; LLM tools use **§6.5.2** | Richer parent dashboards, streaming |
| **Checkpoint** | Plan, CEO approve, each **`done`**, post-Reviewer failure, **`escalate()`** | Finer streaming checkpoints |
| **Revisioning** | **§9.2** snapshots **or** single-tree git; **§9.3** if git | Multi-branch merge orchestration |
| **Failure** | **§4.4** + bounded retry below | Flaky-test policies, etc. |

README **must** either claim **MVO complete** or list **spec gaps** and **target dates** (**§10** phased delivery).

7.1.1 Continuous orchestrator run loop (normative)

**Problem addressed:** **§6.4.1** defines **`scheduling_dispatch_tick`** (**DecisionInput → DecisionOutput**) but not the **long-running** process that **invokes** it, **persists** state, and **applies** **§4.1.1** after Tools return.

**Normative phases (single process; names illustrative):**

1. **Hydrate** — load **checkpoint** (**§6.6**); build **`DecisionInput`** including **`in_flight_tasks`** (**`Task.status == in_progress`**) and **`file_locks`** (**§9.4.1**).
2. **Gate** — if **`Project.status`** is not **`executing`** (or run is **paused**), **do not** schedule; handle CEO / operator UX.
3. **Schedule** — **`out = scheduling_dispatch_tick(decision_input)`** (**§6.4.1**); append **`out.decision_log_entries`**; **checkpoint** if required.
4. **Escalate path** — if **`out.side_effect`** is **`escalate`** / **`blocked`**, set **§4.2** / **§7.2** and **exit** loop iteration appropriately.
5. **Execute batch** — for each non-null **`worker_assignment`**: commit **`todo` → `in_progress`** (**§4.1.1**); run **`worker.execute(task)`** (**§6.3**); **Orchestrator** maps **`ToolResult` → FSM** (**§4.1**, **§4.4**, **§2.5.7**); update **`budget_counters`**, **`last_pytest`**, **locks** (**§17.2**, **§9.4**); **checkpoint** on material change (**§6.6**).
6. **Loop** — return to step 1 until **all** relevant tasks **`done`**, **`Project.status`** terminal, or **pause**.

**Forbidden:** worker or reviewer Tools **writing** canonical **`Task.status`**; **skipping** **checkpoint** after **§6.6**-listed events; **bypassing** **`scheduling_dispatch_tick`** for production dispatch without a **documented** equivalent (**§2.5.3**).

Pseudo-code (**simplified** — full spine **§7.1.1**; **`get_next_task`** **must** be implemented via **§6.4.1**; MVO often **batch size 1**):

```python
while not all_done(tasks):
    task = get_next_task()  # §6.4.1: first of greedy batch, or sole task in serial mode

    worker = assign_or_provision_worker(task, state)  # §6.4.1: reuse idle → else provision → else None
    if worker is None:
        continue  # at role/global cap — retry next tick; do not spin empty

    result = worker.execute(task)  # Tool contract §6.3; Tools do NOT set Task.status

    if result.success:
        apply_orchestrator_closure(task, result)  # §4.1.1 §2.5.7 → done / needs_review / …
    else:
        # §4.1.1: orchestrator runs Reviewer Tool, then commits retry_count / todo / escalate — not the worker
        apply_orchestrator_failure_routing(task, result)  # §4.4 / §5.4
```

In real code, **`apply_orchestrator_failure_routing`** wraps **Reviewer** **`Tool.execute`** plus FSM writes (**§4.1.1**).

`escalate()` (MVP): stop the run, emit a clear summary (task id, errors, retry count), and require **human** intervention before restarting—aligned with a **harness / authority** signal in the TokenFly sense, not a silent infinite loop. **What the CEO actually sees** is **normative** in **§7.2**—not only an internal function call.

7.2 CEO / operator UX on failure and `escalate()` (normative)

**Problem addressed:** `escalate()` is defined **procedurally**, but the **product experience** for the human **CEO** (or operator) **must** be **explicit**: otherwise failures feel like a **black box**.

**When:** On **`escalate()`**, on **`Project.status: blocked`** after hard failure, or when the implementation **stops** awaiting human decision after **max retries** (**§4.1**, **§4.4**).

**Executive report (minimum content)** — render in **CLI**, **log**, or **UI**; **also** persist enough in **global** / checkpoint (**§6.6**) to reconstruct after restart:

	•	**Status line** — e.g. task failure marker + **`Task.id`** (e.g. `Task failed: T2`).
	•	**Reason** — short human-readable string (e.g. `pytest failed`, `LLM timeout`, `Reviewer exhausted retries`); **may** include a **category** enum in structured form for automation.
	•	**Retry count** — current **`retry_count`** (and **`max_retries`** if configured).
	•	**Evidence pointer** — where to find **`last_pytest`**, **`last_reviewer_feedback`**, or checkpoint path (not necessarily full logs inline).

**Example (informative, not a strict string format):**

```text
Task failed: T2
Reason: pytest failed
Retry count: 3 / max 3
See: last_pytest in session checkpoint (state/session.json)
```

**Minimum CEO / operator choices** — the surface **must** offer **at least** these **classes** of next action (labels may be localized; **map** to state transitions):

| Action class | Meaning | Typical effect |
| ------------ | ------- | ---------------- |
| **Modify plan** | Replan with CEO input | New **`plan_revision_id`**; clear or supersede **`approved_plan_revision_id`** until next **APPROVE** (**§17.3**); **`Project.status`** → `planning` or equivalent |
| **Continue** | Human accepts risk or fixed environment | **Resume** execution: e.g. **reset** **`retry_count`** for named tasks with CEO ack, or **retry** same task once—**document** exact policy in README |
| **Abort** | Stop the mission | **`Project.status`** → `cancelled` (or remain `blocked` with no auto-resume); no silent restart |

Implementations **may** add **Retry once** or **Skip task** only if **documented** and **CEO-visible**; they **must not** be the **only** path (the three classes above stay available).

**Structured report (normative minimum for APIs / automation):** alongside human text, emit **JSON** matching at least:

```json
{
  "event": "escalate",
  "project_id": "P1",
  "task_id": "T2",
  "status": "failed",
  "failure_type": "test_failure",
  "reason": "tests_failed",
  "attempts": 3,
  "max_attempts": 3,
  "suggested_actions": ["modify_plan", "continue", "abort"]
}
```

**`failure_type`** **should** use **§4.4** tokens (`test_failure`, `syntax_error`, `requirement_mismatch`, `infra_error`) when known; omit or use `unknown` only if **documented**. **`reason`** **should** use **stable snake_case** tokens (e.g. `tests_failed`, `llm_timeout`) for programmatic handling; human copy **may** map them to phrases. **`suggested_actions`** **must** be a **non-empty** subset of the three CEO classes (**§7.2** table); ordering **may** reflect default recommendation.

7.3 Orchestrator scope — MVP subset vs “platform” (normative)

The orchestrator **currently** combines scheduling, pool policy, CEO gate, context, checkpoints, and failure UX—**easy to overbuild** into a **platform**. For **implementers (including AI coding agents):**

**In spec-compliant MVP (with §7.1 MVO, align §10.2 Mode 1):**

	•	**Sequential execution** of runnable tasks (still **DAG-correct**—only one mutating **`code`** path at a time is OK).
	•	**Retry loop** + **Reviewer** + **§4.4**.
	•	**CEO gate** on plan approval.
	•	**Context** merge + **§6.5.3** injection + **§6.5.2** assembly.
	•	**Checkpoints** (**§6.6**).
	•	**Single active mutator** on a given repo/workspace **or** **§9.4** locks—**recommended default** for first green build.

**Not required in MVP (defer to §10.2 Mode 2 / §13):**

	•	**True DAG parallelism** (many concurrent mutating coders without locks).
	•	**Dynamic pool scaling** as a **product feature** (beyond **§7.1**’s minimal worker rows).
	•	**Global / multi-project** scheduling as one binary.

Document the chosen subset in README so tools **do not** implement the **full** scheduler + infra controller **in one shot**.

⸻

8. Retry & Debug Loop

Must support:

- auto retry
- feedback-driven fix

Flow:

```text
code -> test -> fail -> analyze -> fix -> repeat
```

This loop is the **operational cycle** of the **task state machine** (**§4.1**): **analyze** is **Reviewer**; **fix** returns work to **Coder** (or equivalent) with **§6.5.1** memory populated; **repeat** is bounded by **`retry_count`** / **`max_retries`** until **`escalate()`** (**§7**). **Test failures** follow **§4.4** step-by-step.

⸻

9. Workspace

All generated code lives in:

```text
/workspace/
```

System must:

	•	read existing files
	•	modify files
	•	add new files

9.1 Security & sandbox (minimum policy)

	•	**Writable / executable surface** — `write_file`, code generation, and **pytest** must operate **only under `/workspace/`** (§9). Reject path traversal, writes to repo root secrets, `~/.ssh`, cloud metadata URLs in tool I/O, etc.
	•	**Secrets** — LLM and tool credentials use **environment variables** or OS secret stores only; **never** instruct agents to commit keys into `workspace/` or the spec repo.
	•	**Subprocess isolation** — default: run pytest with cwd anchored to `/workspace/`; optional hardening (containers, separate user, CI runners) is a **Future Extension** (§13), not MVP-blocked, but the **principle** above is normative.
	•	**Prompt-injection resistance (normative — §17.4)** — system prompts **must** state that embedded instructions in user goals, CEO notes, or logs **must not** override tool policy (paths, secrets, allowlist). **Only** registered **Tools** may run; no ad-hoc “run arbitrary shell from model text” unless routed through a **policy-checked** tool.

9.2 Workspace revisioning — simplified “git-like” layer (normative principles)

**Problem addressed:** blind **overwrite** of `/workspace/` by successive coders or retries loses **rollback** and **audit**; multi-worker **merge** conflicts need a policy.

**Normative principles (implementation-flexible):**

- **Single coherent tree** — `/workspace/` remains the **live** tree for pytest and tools; no requirement for a full hosted git host in MVP.
- **Recovery points** — before **each** task that mutates code (at minimum **`type: code`**), orchestrator **must** be able to **restore** a prior tree state **or** record a **parent revision id** for rollback. Acceptable mechanisms: (1) **`git`** initialized **inside** `/workspace/` with **commits** at task boundaries (recommended), (2) **filesystem snapshots** / tar of `/workspace/` in `state/` keyed by `task_id` + attempt, or (3) equivalent **content-addressed** blobs in checkpoint store — choose one and **document** in README.
- **Rollback** — on **retry** or **`escalate()`**, implementation **must** support **operator-visible** rollback to **last known good** commit/snapshot **per policy** (e.g. “before failed task T2 attempt 2”).
- **Concurrency** — **§6.4** already restricts unsafe overlap; **multiple coders** on **disjoint `path_hints`** **may** proceed in parallel **only** if revisioning policy avoids clobbering a shared **HEAD** (e.g. **branch per worker** then **sequential merge** by orchestrator, or **serialize** writers to one workspace). **Default MVP-safe:** **serialize** all mutating **`code`** tasks that **overlap paths**; **parallel** only when **`path_hints`** are **pairwise disjoint** and revisioning is documented.
- **Artifact lineage** — revision ids (**commit SHA**, snapshot key, or **`task_id`+attempt**) **must** be **correlatable** with **`last_pytest`** and **`ToolResult`** so **“test vN vs code vM”** is not ambiguous (**§2.5.8**). Prefer commit messages or tags that include **`task_id`** when practical.
- **Merge** — if branches/snapshots exist, **orchestrator** (not ad-hoc model text) **owns** **merge / discard** decisions after **Tester** signal or CEO policy; models **propose** patches, **tools** apply to the **checked-out** tree.

**Commit hygiene:** when using **git**, **§9.3** (**test-before-commit**) constrains **when** task-boundary commits are written so history stays **clean**.

**Relation to §13:** full **PR automation** and remote git are **future**; **§9.2** is the **local** minimum so **Tester** always runs against a **defined** tree state.

9.3 Test-before-commit (normative when using git)

**Goal:** keep **commit history** meaningful—**no** routine recording of **broken** trees as if they were deliverables.

When **`git`** is used inside `/workspace/` (or per-**`repo_root`** §3.3):

- **Task-boundary commits** (or **pushes** treated as durable checkpoints) **must** be created **only after** the **Execution Tool** reports **`success: true`** for the **pytest scope** that gates that task (or the project’s agreed test command—§6.2.1), **unless** a **documented** CEO/config override exists.
- **During** fix loops (**§4.4**, **§8**), **working tree** may change freely; **optional** WIP commits **may** be allowed **only** if README defines a **naming/policy** (e.g. `wip:` prefix) and **final** commits for a **`done`** task remain **test-first**.
- **Forbidden (default):** promoting a “finished” commit for a **`code`/`test`** task while pytest is **red** for that scope.

If revisioning uses **snapshots only** (no git), apply the **same spirit**: **name** or **tag** recovery points **after** green tests when the snapshot represents a **milestone**.

9.4 File-level write locks (normative when concurrent mutators exist)

**Problem addressed:** Rules such as “do not write the same file at once” (**§6.4**) are **not enforceable** by prose alone—implementations need a **mechanism**.

**When required:** If more than one **`coder`** (or any role) can **mutate** the same `/workspace/` tree **concurrently**, the implementation **must** use **either** (1) **`file_locks`** as below, **or** (2) **hard serialization** of **all** mutating writers so only one runs at a time (**document** which). **§7.1 MVO** with a **single** serial mutator **may** omit locks **only if** README states **no concurrent writers**.

**Data structure (minimal):** Assistant maintains **`file_locks`**: map **normalized path relative to `/workspace/`** → **`Worker.id`** (or **`task_id`** if locks bind to tasks). Example (informative):

```python
file_locks = {"src/x.py": "coder_1"}
```

**Acquire / release:** Before **`write_file`**, patch apply, or a **terminal-agent** write (**§5.2 Profile B**, §13), orchestrator **acquires** the lock for the target path (and **may** acquire **prefix** locks for **`path_hints`** directories—document policy). If the path is held by **another** worker, **do not** start the write—**queue** the task or **fail fast** per config. **Release** all paths held by a worker when its mutating task reaches **`done`**, terminal **`failed`**, or **`escalate`**; on **resume**, clear **stale** locks with a **logged** rule (e.g. TTL or owner task id mismatch).

**Granularity:** per-file locks satisfy MVP; **directory** locks optional.

9.4.1 Scheduler integration hooks (normative when concurrent mutators exist)

**Problem addressed:** “**must enforce file locks**” requires **callable** surfaces the **scheduler** and **write path** share—not only prose.

**Normative hooks (names illustrative; bind in code):**

	•	**`workspace_conflicts(candidate_task, running_tasks, file_locks) -> bool`** — **`true`** if **`candidate_task`**’s projected write set (from **`path_hints`**, declared **Tool** targets, or **conservative** repo root) **overlaps** locks held by **another** worker/task or **conflicts** with **`running_tasks`** that are **`in_progress`** on overlapping paths. Used inside **`select_parallel_batch`** (**§6.4.1**) and **before** dispatch.
	•	**`acquire_write_locks(worker_id, task_id, paths_normalized) -> ok | denied`** — called by orchestrator **immediately before** first mutating **Tool** for that dispatch; **denied** → **do not** start **`execute`**; leave task **`todo`** or **`in_progress`** rollback per policy.
	•	**`release_write_locks(worker_id)`** — on **`done`**, **`failed`**, **`escalate()`**, or worker **retire** (**§9.4**).

**Equivalence:** **hard-serialized** mutators **may** implement **`workspace_conflicts`** as “any other **`in_progress`** **`code`** task ⇒ conflict” without a lock map—**document** in README.

⸻

10. MVP Scope (DO NOT OVERBUILD)

**Phased delivery:** a first milestone may be **narrow** (e.g. one worker, serial execution) to reduce calendar time, but the codebase **must not permanently skip §6.3–§6.7**. If something ships temporarily incomplete, document it in README with a **removal date** or mark the build **spec-noncompliant** until fixed.

**10.1 Minimal closed-loop north star (normative)**

The **smallest** product story this spec cares about is **not** “full company sim on day one”:

```text
natural-language mission → plan (JSON) → CEO approve → code + tests in /workspace/ → pytest via Execution Tool (§6.2.1) → green or bounded retry / escalate
```

**Scope warning:** attempting **IDE super-agent**, **full company operating system**, and **scheduler-grade infra** (mini Kubernetes + Airflow) **simultaneously** is the main risk to **shipping**. **§7.1 MVO** and **§6.5.2** are deliberate **depth limiters**: get a **running, debuggable** loop, **then** widen.

**Assistant** in that slice **may** be a **single process** with **one logical worker per role type** (no visible “HR drama”)—but **must** still implement **DAG scheduling**, **checkpoints**, **shared memory** (**§6.5.1**), **LLM assembly** (**§6.5.2**), **failure policy** (**§4.4**), and **workspace revisioning** (**§9.2**) so the loop is **honest**, not a demo script. **Progressive enhancement:** parallel pools (**§6.4**, §13), **Architect** (**§4.5**, §13), and multi-project CEO portfolio are **explicitly later** unless you promote them from §13. A **requirements-clarification PM pass** (**§2.5.6**) is **recommended** (not the same as **§2.2** status summaries) and **does not** require §13 unless you want a full **`pm` worker** product line.

**10.2 Execution modes (normative labels)**

| Mode | Contents | Spec stance |
| ---- | -------- | ----------- |
| **Mode 0 — Bootstrap** | **Linear** ordering, **no** DAG abstraction, **no** durable checkpoint, **no** formal worker pool | **Throwaway spikes only**—**not** a compliant MVP; **do not** market as XR-AI-Co. |
| **Mode 1 — Spec MVP** | **DAG** + **context** (**§6.5**) + **checkpoints** (**§6.6**) + **Tool `Result`** (**§6.3.1**) + **§7.1** + **CEO gate** + **§7.2** | **Minimum** for “implements this spec” (**§10.1**). |
| **Mode 2 — Full system** | **Pool scaling**, richer parallelism, **multi-project** portfolio (**§13**) | **After** Mode 1 is **stable**. |

README **must** name the target **mode**. **Mode 1** aligns with **§7.3** MVP orchestrator subset.

Required — product loop
	•	planner (**§4.3** JSON plan; prose plan optional)
	•	coder
	•	tester
	•	reviewer (**§5.4** quality gate; structured **`review_report`** recommended)
	•	**§2.5.1 TaskSpec** + **§2.5.1a** **`verification`** on **every `type: test`** task; **JSON Schema** validation on plan JSON (**§14**); **§2.5.2** artifact vocabulary + **§6.3.1** paths; **§2.5.3** policy-driven Assistant (incl. **`scheduler_policy`**, **`budget_policy`**, **`sla_policy`**, **`scaling_policy`**) + **§2.5.3a** **composition** (budget before priority, SLA → **`effective_priority_rank`**)
	•	**§17.2 `Budget`** hard stops for Mode 1; **§6.4** / **§6.4.1** **`scheduling_dispatch_tick`** (**`DecisionInput` → `DecisionOutput`**, batch selection, **`assign_or_provision_worker`**)
	•	**§7.1.1** continuous orchestrator run loop (**checkpoint** ↔ **`scheduling_dispatch_tick`** ↔ **Tool.execute** ↔ **§4.1.1** FSM commits); **§4.1.1** state ownership; **§4.3.1** dynamic graph updates on replan
	•	orchestrator (CEO gate + retries + escalate) with **task / project state machines** (**§4.1–§4.2**) and **CEO-visible failure UX** (**§7.2**)
	•	**shared memory** for cross-role handoff (**§6.5.1**) and **LLM prompt assembly** (**§6.5.2**)
	•	**workspace revisioning** policy per **§9.2** (git in `/workspace/` or equivalent snapshots); if git is used, **test-before-commit** per **§9.3**
	•	**repo–worker affinity** for coders per **§3.3** (default one `coder` ↔ one repo unless split)
	•	**§9.4** file locks **+ §9.4.1** scheduler hooks (**`workspace_conflicts`**, **`acquire_write_locks`**) when **concurrent** mutators; **§7.1** serial MVO may omit locks if README says so
	•	**Assistant-managed dynamic worker pool** (§2.2): on-demand logical workers per role, caps, reuse/idle/retire—**single machine / one process is OK**; must persist worker list in checkpoints (§6.6); **default: at most two concurrent `code` tasks per process** (§2.2, §6.4)
	•	file + execution tools (§6.1–§6.2)

Required — SAS-aligned runtime (do not skip)
	•	Tool contract for every step (§6.3) including **`Result`** shape (**§6.3.1**) with **lineage-friendly** **`payload`** (**`task_id`**, **`plan_revision_id`**, attempt—**§2.5.8**) where applicable
	•	DAG-correct task scheduling (§6.4)
	•	Three-layer context (§6.5) with **§6.5.3** injection by role
	•	Persistence + crash recovery checkpoints (§6.6)
	•	Observable execution + pause/resume semantics (§6.7) including **checkpointed** **`decision_log`** (**§2.5.9**)
	•	**§17.1** timeouts / provider error taxonomy; **§17.2** **`budget`** block + **`budget_counters`** — **normative** for **§10.2 Mode 1**; **§17.2.1** cost **estimation** for proactive gates (**recommended**); **§17.3** plan revisions; **§17.4** injection minimums — **normative** for MVP

NOT required (for now)
	•	UI
	•	**Distributed / cloud autoscaling** (separate machines, queue-backed fleet, Kubernetes-style workers)
	•	Nested AgentV3 per worker (optional; flat tools OK)
	•	Standalone **PM worker role** as a **product requirement** — **no**; **optional / recommended** **requirements-clarification** pass is **§2.5.6** (distinct from **§2.2** status summaries)
	•	**Architect** / **`interface.md` phase** — **optional**; register via **§13** (**§4.5**, **§5.5**)
	•	**Learned reward / gamified peer pressure** as a **product requirement** — **no** for Mode 1; optional patterns and **§13** extensions — **§2.5.10**

⸻

11. CLI Interface

Example:

```bash
python main.py "build a rate limiter"
```

On **escalate** or **blocked**, the CLI **must** print (or attach) the **§7.2** executive report and accept **modify plan** / **continue** / **abort** (or equivalent flags / subcommands)—**not** exit with only a non-zero code and no context. It **must** also emit the **§7.2** **JSON** report on **stdout** or a **documented** path for scripting.

11.1 End-to-end example (informative — text in, structured loop)

**Input (natural language only):** `build a calculator in Python`

1. **Planner** → writes **`requirements_summary`** (text) + materializes **tasks** `T1` (type `code`, description text) and `T2` (type `test`, **`depends_on`**: [`T1`]).  
2. **CEO** → **APPROVE**; **`approved_plan_revision_id`** set.  
3. **Coder** on `T1` → **`write_file`** / terminal agent → **`ToolResult.artifacts`** lists new paths.  
4. **Tester** on `T2` → tests added → **Execution Tool** → **`success: false`**, **`logs`** capture pytest.  
5. **Reviewer** → diagnosis → **`last_reviewer_feedback`**.  
6. **Coder** (retry path) → fix → **Execution Tool** → **`success: true`**.  
7. **`T1`/`T2` → `done`**; **`Project.status` → `done`**.

If retries are **exhausted** at step 4–6 → **§7.2** human report + **JSON** (`reason: tests_failed`, etc.) → CEO chooses **modify_plan** / **continue** / **abort**.

⸻

12. Success Criteria

System should:

	•	generate working code
	•	generate tests
	•	pass all tests **via the Execution Tool** on a **defined** `/workspace/` tree (**§6.2.1**)
	•	require minimal human input (CEO gate + **§7.2** failure UX on **escalate** / **blocked** + optional resume—**§10.1**)

⸻

13. Future Extensions

	•	**Scheduler-grade control plane** — Airflow-/Kubernetes-style **orchestration UX**, cross-cluster workers, and heavy DAG analytics are **out of scope** until **§7.1 MVO** is **proven running**; this spec’s orchestrator stays a **harness**, not a generic data platform.
	•	**CEO mission portfolio** — multiple **Projects** in flight with priorities, shared policies, and cross-project context (still one CEO harness)
	•	**PM division (productized)** — multi-step discovery, templates, and CEO UX beyond **§2.5.6**’s **recommended** clarification pass; still **`Tool`-shaped** and config-driven (**§2.5.3**)
	•	**Cross-session knowledge** — richer **`knowledge_base`** stores, embeddings, or shared org memory beyond **§2.5.5**’s **minimum** slice
	•	**Architect division (interface alignment)** — register **`Worker.role: architect`** and **`Task.type: design`** with a **Tool** that writes **`/workspace/interface.md`** (API + data model), **`depends_on`** edges before **`code`** tasks, and **`interface_digest`** in global (**§4.5**, **§5.5**). Optional: diagram-to-spec tools, OpenAPI emit.
	•	**Richer parallelism** — beyond §6.4 defaults: **multiple coders** on **disjoint** `path_hints` with **branch-per-worker** merge policy (**§9.2**); **test/review** waves overlapping **code** on independent subgraphs; optional **per-role concurrency** knobs beyond code cap. **Still** subject to workspace safety and revisioning rules.
	•	**New departments (role types)** — e.g. security review, UX/design, SRE/runbooks, docs—each becomes a **Tool + worker role** registered like existing Planner/Coder/Tester/Reviewer (company grows without merging into one agent)
	•	**Cross-process resource coordination** — optional global cap or host-wide admission control when many terminals run at once (today: per-process cap only; operator manages aggregate load)
	•	**Distributed worker fleet** — queue-backed runners, multiple hosts, autoscale policies beyond §2.2 local pool
	•	Deeper **SAS integration**: native `AgentV3` nesting, YAML-only agent defs, upstream executor as sole scheduler
	•	TWE-style environment signals (tests, linters, budgets, “world” constraints) as first-class tool outputs
	•	**Learned rewards / RL policies** — scalar or learned **reward models** wired **only** through **documented** **`Tool`** surfaces and **§2.5.3**; **must** remain **auditable** and **subordinate** to **§17.2** / **§4.4** (**§2.5.10** guardrails)
	•	**Org UX: leaderboards, badges, “peer” narratives** — CEO-facing or worker-prompt **motivation** layers; **must** treat copy as **untrusted** for policy (**§17.4**); optional **factual** cross-lane stats in **§6.5.2** per **§2.5.10**
	•	**Terminal-agent Coder backend (e.g. Claude Code, Codex-class CLI)** — Implement **`coder`** as a **subprocess / PTY** driving a **terminal coding agent** (shell + file edits) **instead of** only chat-completion + **§6.1**. **Normative:** the **adapter** still exposes **§6.3** `execute` → `Result`; cwd and paths stay under **`/workspace/`** / **`repo_root`**; commands remain **allowlisted** or policy-wrapped (**§9.1**, **§17.4**). Feed **§6.5.2** context via env, initial prompt file, or wrapper—document binary, flags, timeouts in README. **§9.4** applies to the agent’s writes when concurrent mutators exist.
	•	git integration (auto commit / PR) — **§9.2** already requires a **local** revisioning story; this item is **remote** workflow / UI polish
	•	dashboard UI
	•	RAG for codebase context

⸻

14. Implementation Instruction (FOR CURSOR)

	•	Implement in **Python 3.11+**
	•	Use **§16** canonical strings for `Project` / `Task` / `Worker` status and role fields—no ad-hoc synonyms.
	•	**Align with SAS** (see §2.1): either **vendor** [TokenFlyAI/Agentic_System](https://github.com/TokenFlyAI/Agentic_System) or **mirror** its boundaries. **§6.3–§6.7 are normative**—implement them even if you do not import SAS yet.
	•	Repo layout (keep or nest under a single package):
		•	`tools/` — `read_file`, `write_file`, `run_pytest`, thin LLM-backed tools for planner/coder/tester/reviewer (each satisfies §6.3); optional **`architect`** tool when §13 enabled (**§5.5**)
		•	`agents/` — prompts, schemas, optional `AgentV3`-style wrappers if using SAS
		•	`schemas/` — **JSON Schema** for **`Task`** / plan validation (**§2.5.1a**), versioned (e.g. `task.v1.json`)
	•	`orchestrator/` — CEO gate, task store, **schema validation** on plans, **`orchestrator_run_loop`** (**§7.1.1**), **`scheduling_dispatch_tick`** (**§6.4.1**) + DAG + **§4.3.1** merge, **§4.1.1** FSM writer, **`workspace_conflicts` / `acquire_write_locks`** (**§9.4.1**), **worker pool** (provision / reuse / retire, caps—§2.2), **`file_locks`** (**§9.4**) if concurrent mutators, context service (§6.5), checkpoint writer (§6.6), **`budget_counters`** + optional **§17.2.1** estimates (**§17.2**), `assign_or_provision_worker` (**§6.4.1**), retry / `escalate`, optional **terminal-agent Coder adapter** (§13), calls into SAS or local executor
	•	`workspace/` — runtime mirror of §9 (gitignored generated code); **§9.2** revisioning (e.g. nested `.git`) lives **under** `/workspace/` or documented snapshot store; **§9.3** commit only after green pytest when using git
	•	`state/` or `.xr_session/` — checkpoints (gitignored) unless using SAS persistence only
	•	LLM calls: use a **single provider abstraction**; upstream SAS examples use OpenAI—**Anthropic (Claude) is fine** for XR-AI-Co if you implement the same “function / tool” calling surface your orchestration expects.
	•	Configs: prefer **YAML** for agent definitions when integrated with SAS; otherwise one small YAML or TOML for model name, paths, **`max_concurrent_code_tasks`** (default **2**), **`clamp_code_tasks_to_host`** (optional `true` to apply `min(config, host_ceiling)` per §2.2), optional **documented formula** for `host_ceiling` from `cpu_count`, optional per-role caps, **distinct `state_dir` / session id** when running multiple terminals, **`decision_log_max_entries`** (or archive policy) for **§2.5.9**, **`budget`** block per **§17.2**, **`scheduler_policy`** (incl. optional **documented** `scheduling_score` / tuple mapping per **§2.5.3a**), **`sla_policy`** with thresholds that drive **`effective_priority_rank`** (**§2.5.3a**, **§6.4**), **§2.5.3** policy blocks (**`retry_policy`**, **`scaling_policy`**, **`failure_policy`**, **`parallelism_policy`**) or equivalent keys, optional **§2.5.5** knowledge store path, and **§17.1** knobs: **`llm_call_timeout_sec`**, **`task_timeout_sec`**, optional **`session_max_duration_sec`**, **`max_retries_transient_api`**.
	•	**§7.1 MVO first** — serial DAG loop, then parallel pool / advanced revisioning.
	•	**LLM tools** — **§6.5.2** assembly for every model call.
	•	**End-to-end first**: CLI (§11) → plan → CEO approve → serial (or DAG) task run → pytest green; on failure, **§7.2** report + CEO choices.
	•	When integrating SAS: register tools in a **registry** matching upstream patterns; start from their demo configs and replace tools with XR `workspace/`-scoped file + pytest tools.

⸻

15. Final Goal

Build a system where:

```text
CEO sets mission -> harness keeps long-term focus -> Assistant staffs & scales org -> divisions execute -> software outcomes
```

⸻

16. Appendix: Enumerated field values (normative)

Use these **exact string values** in MVP unless §13 registers extensions.

| Field | Allowed values (MVP) |
| ----- | -------------------- |
| **`Project.status`** | `planning`, `executing`, `done`, `blocked`, `cancelled` |
| **`Task.status`** | `todo`, `in_progress`, `done`, `failed` (optional: `blocked` when awaiting CEO or external input; optional: `needs_review` when Reviewer gate sits between worker pass and `done` — **§2.5.4**, **§4.1**) |
| **`Task.type`** | `code`, `test` — add new types only with a matching **Tool + worker role** policy (§13). **§13 Architect pack:** `design` (interface / **`interface.md`** tasks — **§4.5**). |
| **`Task.priority`** | optional: `low`, `normal`, `high`, `urgent` — default **`normal`** if omitted; **persisted** Planner field—**§6.4** ordering uses **`effective_priority_rank`** (**§2.5.3a**) when **`deadline`** or **`sla_policy`** applies, not static priority alone |
| **`Worker.status`** | `idle`, `busy`, `retired` |
| **`Worker.role`** | `planner`, `coder`, `tester`, `reviewer` — extend per §13 when new divisions register. **§13 Architect pack:** `architect` (**§4.5**, **§5.5**). **Recommended PM pass:** `pm` or equivalent **only** if registered (**§2.5.6**); register in README when used. |

**`plan_revision_id` / `approved_plan_revision_id`:** opaque strings (e.g. UUID or `rev-NNN`); lifecycle in **§17.3**.

Implementations **must not** invent synonyms (`running` vs `in_progress`, etc.); map UI labels to these canonical strings internally. **Task.type** vs **Worker.role**: see **§17.5**.

⸻

17. Timeouts, budgets, plan revisions, and hardening

17.1 Timeouts and provider errors (normative)

	•	**LLM / remote tool calls** — every call **must** use a configurable **wall-clock timeout**; on timeout, return structured failure (may count toward task retry — §7). Document defaults in README.
	•	**Per-task execution** — each task (Coder, Tester, etc.) **should** have a **task timeout**; on expiry set `failed` or `blocked`, log, optionally **`escalate`** per policy.
	•	**Session** — optional **`session_max_duration_sec`**; on expiry stop cleanly and checkpoint.
	•	**Provider HTTP / API errors** — classify: **Transient** (429, 502, 503, timeouts) → bounded **retries with backoff** (config **`max_retries_transient_api`**); **Auth / config** (401, 403, missing key) → **fail fast** or **`escalate`**, no endless retry; **Client-style** 4xx from provider → surface as structured error to Reviewer / human, not silent loop.

17.2 Budget and cost control (normative for §10.2 Mode 1)

**Problem addressed:** **unbounded** workers + **unbounded** retries + **unbounded** LLM calls → **token explosion**, **runaway cost**, and **harness loops** that **feel** infinite even with per-task caps.

**Global vs local governance:** per-task **`retry_count`** / **`max_retries`** (**§4.1**) bound **local** retry loops on a single task. **`Budget`** limits and **`budget_counters`** are **session / project-global**: they cap **aggregate** LLM tokens, optional cost, and **project-wide** retry-driving transitions **across all tasks and workers**. **Worker provisioning** **must** respect **`scaling_policy`** (**§2.5.3**, **§2.2**) caps—**unbounded** logical worker spawn is **non-compliant** for **§10.2 Mode 1** when the declared policy defines a ceiling.

**`Budget` block (config + checkpointed counters — §6.5.1 / §6.6):** implementations **must** support **at least** these **keys** (YAML shape illustrative):

```yaml
budget:
  max_tokens_per_task: 200000      # hard stop for single task’s LLM usage (incl. retries)
  max_tokens_per_session: 2000000  # whole project session
  max_cost_per_project: null       # optional: provider currency units—document mapping
  max_retries_total: 50            # sum of retry-driving transitions **across all tasks** in project
```

**Normative behavior:**

	•	**Before** each **LLM** **Tool** call, Assistant **must** check **`budget_counters`** vs limits; if **exceeded**, **refuse** the call, **`DecisionLog`** with **`decision: budget_exceeded`**, and **`escalate()`** or **`blocked`**—**no** silent continue.
	•	**`max_retries_total`** applies **in addition** to per-task **`retry_count`** / **`max_retries`** (**§4.1**); whichever fires **first** wins.
	•	**`max_cost_per_project`** is **optional** only when the **provider** exposes **usable** cost metadata; if **set**, same hard-stop rules as tokens.
	•	Persist **`budget_counters`** in **checkpoint** every material state change (**§6.6**).

17.2.1 Cost estimation (recommended — proactive budget gate)

**Problem addressed:** post-hoc **`budget_counters`** catches overspend **after** an LLM call; **`violates_budget_next_step`** (**§6.4.1**) **should** incorporate **estimates** when providers cannot **pre-authorize** spend.

**Recommended (document in README / `budget_policy`):**

	•	**Per-role or per-call ceiling** — e.g. **`max_tokens_per_llm_call`** or **`estimated_tokens_cap`** before dispatching a **Coder** step.
	•	**Task hints** — optional Task fields **`estimated_prompt_tokens`**, **`estimated_completion_tokens`** (Planner- or policy-filled) used in **`violates_budget_next_step`** as **upper bounds**; **Planner** **may** omit—then use **conservative** defaults from config.
	•	**Rolling projection** — `budget_counters.tokens_used_session + estimate_next_call <= max_tokens_per_session` **before** **`scheduling_dispatch_tick`** admits a budgeted task.

**Normative floor:** even **without** estimates, **§17.2** **hard stops** after counters update **still** apply; estimates are **not** a substitute for **`budget_counters`**.

**Mode 0 spikes** **may** omit **`Budget`** **only** if README marks the build **spec-noncompliant** for cost safety.

17.3 Plan revision identity (normative)

	•	When Planner (or replan after CEO feedback) emits a task list, assign a new **`plan_revision_id`** to the project **draft** and **stamp every new Task** with that id.
	•	On CEO **APPROVE**, set **`approved_plan_revision_id` =** that revision; executor **must ignore** tasks whose `plan_revision_id` ≠ `approved_plan_revision_id`.
	•	**Replan** increments / replaces `plan_revision_id`; **`approved_plan_revision_id`** is cleared or superseded until the next approval.
	•	Checkpoints **must** include both ids (§6.6) so resume cannot execute a stale draft.

17.4 Prompt-injection and tool surface (normative)

	•	**System prompts** — require models to treat user content as **untrusted data** where it conflicts with **fixed policies** (workspace roots, secret handling, tool allowlist).
	•	**Tool allowlist** — each **Worker.role** maps to a **closed set** of Tools; orchestrator **must not** expose extra capabilities because the model asked.
	•	**Shell / network** — any bash or network tool **must** remain policy-gated (§9.1); never execute model-supplied shell as raw OS input without validation.

17.5 Task.type vs Worker.role (informative)

| Concept | Meaning |
| ------- | ------- |
| **`Worker.role`** | Which **pool** executes work: `planner`, `coder`, `tester`, `reviewer` (§16). |
| **`Task.type`** | Kind of **DAG node**: MVP `code`, `test` — what the task *is*. |
| **Planner work** | Runs mainly in **planning phase** before materialized tasks; **no** `Task.type: planner` required in MVP—Planner is a **role**, not a task type in the execution DAG. |
| **Architect** | **`Worker.role: architect`**; **`Task.type: design`** when §13 pack enabled—produces **`interface.md`**, not shipping code (**§4.5**, **§5.5**). |

17.6 Multi-process load (informative)

Cross-terminal **aggregate** CPU remains the **operator’s** tradeoff; optional **cross-process caps** stay in **§13**. Per-process rules in **§2.2** still apply.

