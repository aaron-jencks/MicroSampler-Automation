# MicroSampler Automation

This subfolder for MicroSampler adds LLM agents into the loop of side-channel analysis using the MicroSampler pipeline. The current implementation uses a series of LLM agents to search for timing leakage in constant-time copy examples. The high-level loop works like this:

![flow loop](docs/loop.png)

The active orchestration and deployment paths use queued state machines from the `qstate` package. The governor loop, the local ccopy deployment flow, and the core MicroSampler deployment flow are all described by QSM JSON config files and executed by Python state classes. The MicroSampler core pipeline lives in [simulation/microsampler/core](simulation/microsampler/core); it can run the existing deployment process and automatically find the PC addresses of target functions and regions of interest from test-case object dumps.

## Next Steps

Work remains to be able to deploy custom test-cases to the core MicroSampler pipeline, as much of it relies on pre-made files and hard-coded values. The next steps are to utilize recent changes in [bearssl-0.6/ccopy/v2/harness](bearssl-0.6/ccopy/v2/harness) to enable running without the monotonic timing code so that the harness can be deployed directly to MicroSampler's simulator without having to change the code interface exposed to the agents. The [makefile](bearssl-0.6/ccopy/v2/harness/Makefile) needs to be modified to enable compiling with a cross-compiler instead of the system gcc, as well as generate object dump files. Finally code needs to be written to utilize that new make version instead of the default one. 

Work has been started on making a state machine that wraps the core MicroSampler deployment state machine, this keeps the core deployment testable, while also allowing us to write custom test-cases.

## Setup

### Development Server Setup

The development server that we use contains most of the code and infrastructure necessary to get this up and running. To do this you need to log into the server, then do the following:

1. `cd` into `/local/scratch/{YOUR USERNAME}`
2. Run `source /local/scratch/scripts/microsampler-env.sh`
3. Verify that `which riscv64-unknown-elf-gcc` outputs `/local/scratch/riscv/bin/riscv64-unknown-elf-gcc`
4. Clone this repo **make sure that you are on the right branch**
5. `cd` into the repo location
6. Build the pre-built test-cases, like described in the root README, by running `make` in `apps/bearssl-0.6/microsampler_tests` to compile all the tests.
7. Make a python environment for yourself, I would suggest in `/local/scratch/{YOUR USERNAME}/venvs`. You can do this by running `python3.11 -m virtualenv /local/scratch/{YOUR USERNAME}/venvs/microsampler`. **Note:** If you do use my suggested directory location, you'll need to make the `venvs` directory first with `mkdir -p /local/scratch/{YOUR USERNAME}/venvs`. **NOTE:** The python version is VERY important, do not use just `python` you MUST use `python3.11`.
8. Activate your new python environment with `source {VENV LOCATION}/bin/activate` where `{VENV LOCATION}` would be `/local/scratch/{YOUR USERNAME}/venvs/microsampler` if you used the example above.
9. Install the project dependencies with `pip install -r requirements.txt`
10. The setup for running the automation code on the development server is complete, you should be ready to verify your installation and start developing! You can skip to the **Verifying The System Setup** section next.

### Local Setup

If you want to set this up on your local machine, then you'll need to do additional setup.

1. You need a specific version of the `riscv64-unknown-elf-gcc`, specifically version 15.2.0 and it needs to have the `fence` instruction enabled.
2. Make sure that you have a python interpreter >=3.11.
3. Make sure that your environment variables are correctly set, I use the following script to make sure that everything is set correctly, these values will change depending on where you built your cross-compiler:
```bash
export RISCV="${RISCV:-/local/scratch/riscv}"
export RISCV_ARCH="${RISCV_ARCH:-rv64gc_zifencei}"
export RISCV_ABI="${RISCV_ABI:-lp64d}"
export MICRO_SAMPLER_TOOLCHAIN="${MICRO_SAMPLER_TOOLCHAIN:-riscv64-unknown-elf}"
export PKG_CONFIG_PATH="${RISCV}/lib/pkgconfig${PKG_CONFIG_PATH:+:${PKG_CONFIG_PATH}}"
export PATH="${RISCV}/bin:${PATH}:${RISCV}/riscv64-unknown-elf/bin"
```

After this, the core setup remains the same:

1. Clone this repo **make sure that you are on the right branch**
2. `cd` into the repo location
3. Build the pre-built test-cases, like described in the root README, by running `make` in `apps/bearssl-0.6/microsampler_tests` to compile all the tests.
4. Make a python environment for yourself, it should be Python 3.11+. Contrary to what the root README says.
5. Activate your new python environment.
6. Install the project dependencies with `pip install -r requirements.txt`
7. The setup should be complete, verify your system using the next section.

### Verifying The System Setup

If you have done everything correctly so far, then you can run `python -m unittest -s tests` from within the `automation` folder. It will check that you have the repo cloned correctly, that you have the correct cross-compiler version, the correct capabilities installed in the cross-compiler, and that the MicroSampler setup can run with your existing setup.

#### Common Issues

* **`unittest` completes successfully, but found no tests:** Either you have not checked out the correct branch of the repo, or you ran the tests from a directory different from the `automation` directory.
* **The cross-compiler version does not match:** If using the development server, make sure that you run `source /local/scratch/scripts/microsampler-env.sh` every time that you login. Otherwise, you may be using a system installed cross-compiler, but the unit tests require a very specific version of gcc, otherwise the PC addresses used to test the pc_finder module will fail. If you know that your compiler would work otherwise (other versions should work, they may just result in different binary layouts, but the pc_finder can compensate for this), then you can ignore this issue.
* **The `fence` instruction is required for the cross-compiler:** If using the development server, make sure that you run `source /local/scratch/scripts/microsampler-env.sh` every time that you login. Otherwise, this means that your riscv cross-compiler does not have the `fence` instruction enabled, this is required if you want to replicate the pre-built results, which specifically use the `fence` instruction. If you don't intend to use the existing test-cases, then you can ignore this.
* **The Core MicroSampler Deployment State Machine did not return None:** This means that either one of the 2 directly preceding issues were ignored, or the cross-compiler is not setup correctly, resulting in either a build error, a simulation error, or something else. Verify that you have followed the setup directions exactly so that your environment is identical. If using the development server, make sure that you run `source /local/scratch/scripts/microsampler-env.sh` every time that you login.

## Quickstart

Then run the default ccopy example with:

```bash
python governor.py
```

The built-in defaults live in `config.py`. JSON config files are cascading overrides, so an experiment config only needs to define the fields that differ from the defaults. You can override the default `ccopy_v2` config using the `--configs` flag, like this:

```bash
python governor.py --configs config/ccopy_v3.json
```

**Note:** V3 is considered to be actually constant-time, so the program may never terminate, you can use the default V2 example above to show that the program terminates correctly.

## Important Components

### Cascading Config Files

Configuration is defined with Pydantic models in `config.py` and loaded through `parse_configs`. The root model is `BaseConfig`, which contains the harness, interpreter, LLM, agent, logging, and final report settings. Each JSON config file is validated against that schema, and later config files override earlier/default values.

This gives collaborators two useful extension points:

1. Use JSON to override existing config fields for a specific experiment.
2. Add new Pydantic config classes when a new module needs structured settings.

For example, a custom experiment module can define its own config shape and attach it to `BaseConfig`:

```python
from pathlib import Path
from pydantic import BaseModel


class MyExperimentConfig(BaseModel):
    dataset_prefix: Path
    max_trials: int = 100
    enable_extra_checks: bool = False


class BaseConfig(BaseModel):
    # existing fields...
    my_experiment: MyExperimentConfig = MyExperimentConfig(
        dataset_prefix=Path("experiments/data")
    )
```

Once the field is part of `BaseConfig`, an override file can set it:

```json
{
  "my_experiment": {
    "dataset_prefix": "experiments/ccopy_v4/data",
    "max_trials": 500
  }
}
```

Code that receives the config object can then use `ctx.my_experiment.max_trials` instead of manually parsing dictionaries. This is the preferred pattern for reusable modules because it keeps config validation close to the interface that consumes it.

### Queued State Machines and qstate

This project uses [`qstate`](https://pypi.org/project/qstate/) for queued state machines. The package source and docs are in the [`qsm` GitHub repository](https://github.com/aaron-jencks/qsm), with the JSON config format documented in [`docs/config.md`](https://github.com/aaron-jencks/qsm/blob/main/docs/config.md). The dependency is declared in `requirements.txt` as `qstate>=1.3.0`.

A queued state machine is a workflow runner where each state performs one unit of work and schedules follow-up work by appending state names to a queue. States receive a `StateContext` containing:

- `ctx.queue`: the queue of state names to execute next.
- `ctx.context`: the shared run context for the machine.
- `ctx.stop(result)`: a way to stop the loop and return an error or result to the caller.

This pattern is useful here because agent orchestration and deployment both need conditional control flow. For example, a failed ccopy build schedules another implementation attempt, while a successful simulation schedules analysis.

The governor and deployment machines are loaded from JSON config files:

```python
from qstate import QSM


deployment_controller = QSM.from_config_file(
    ctx.deployment_qsm_path,
    ctx=ctx,
)

governor = QSM.from_config_file(
    ctx.governor_qsm_path,
    ctx=ctx,
    deployment_controller=deployment_controller,
    # other runtime services are injected here too
)
```

Each configured state is a normal Python class:

```python
from qstate import State, StateContext


class AnalysisState(State):
    def execute(self, ctx: StateContext):
        ctx.context.current_stats = generate_statistical_analysis(
            ctx.context.current_results
        )
        ctx.queue.append("summarization")
```

The main QSM configs to read first are:

- [config/governor/ccopy_qsm.json](config/governor/ccopy_qsm.json): the agent/governor loop.
- [config/governor/ccopy_deployment_qsm.json](config/governor/ccopy_deployment_qsm.json): the local ccopy harness deployment flow.
- [config/governor/microsampler_deployment_core_qsm.json](config/governor/microsampler_deployment_core_qsm.json): the core MicroSampler deployment flow.

### Governor

`governor.py` is the orchestration entrypoint. It builds the report log, template controller, deployment QSM, agent tool registry, and agents, then loads the governor QSM from `ctx.governor_qsm_path`.

Each state owns one unit of work. Agent states render a prompt, call an LLM-backed `Agent`, store the structured response, log an event, and append the next state name to the queue. Non-agent states run deployment/simulation, generate statistics, or conclude the run. Shared run data lives in `GovernorContext`, so states communicate by updating the context rather than passing large argument lists through every call.

The current governor flow is configured in [config/governor/ccopy_qsm.json](config/governor/ccopy_qsm.json):

```text
hypothesis -> implementation -> simulation -> analysis -> summarization -> hypothesis
```

The loop reaches `conclusion` when analysis crosses the configured score threshold. If deployment reports an implementation error, the simulation state records feedback and schedules another `implementation` state instead of continuing to analysis.

### Deployments

Deployment modules are responsible for turning generated code and run configuration into timing results. The current deployment interface is a `qstate.QSM`. `governor.py` loads the active deployment machine from `ctx.deployment_qsm_path` and passes it into the governor's simulation state.

For the local ccopy examples, [config/governor/ccopy_deployment_qsm.json](config/governor/ccopy_deployment_qsm.json) runs this sequence:

```text
verify -> write -> compile -> prepare -> run_full -> run_loop -> tabulate
```

The ccopy deployment states validate generated includes, write the generated `attack.c`, build the harness, stage the executable and assembly, run the configured number of harness processes, parse the JSON timing output, and store the final dataframe on the deployment QSM context.

The ccopy harness also emits compiler assembly for the deployed attack. The `attack.o` Makefile rule compiles `build/attack.s` with the same `CFLAGS` and `CPPFLAGS` used for `attack.o`, plus assembly-only flags. During the `prepare` deployment state, that file is copied to `ctx.harness.deployment_prefix / ctx.harness.assembly_file`, beside the deployed harness executable. This gives later agent states a stable read-only view of the generated attack assembly for the same build that was run.

The statistics pipeline expects timing data with columns like:

```text
run_name, random_seed, global_iteration, inner_iteration, bit, class, key, duration
```

The core MicroSampler deployment machine is configured in [config/governor/microsampler_deployment_core_qsm.json](config/governor/microsampler_deployment_core_qsm.json). It prepares log directories, finds PC addresses from object dumps, runs the MicroSampler simulation script, parses results, runs statistics, and loops over configured apps and keys.

To support a new target or benchmark style, add:

1. A context dataclass for the deployment data that must persist across states.
2. State classes for build, staging, simulation, parsing, and error handling.
3. A QSM JSON config that maps state names to those classes.
4. A config override that points `deployment_qsm_path` at the new QSM file.

The lower-level helpers in `simulation/states.py` are reusable when the target follows a subprocess-heavy pattern. `DeploymentState` gives deployment states access to `BaseConfig`, and `SubprocessDeploymentState` provides checked subprocess execution that can stop the QSM with structured deployment errors.

### Prompt Templates

Prompt templates are rendered by `TemplateController` in `prompting/templates.py`. A template can include tags using either:

```text
[[tag]]
[[tag:arg1:arg2]]
```

Tags are registered with `create_template_tool`. A tag handler receives the config object, the controller, the tag name, parsed arguments, and optional runtime keyword arguments:

```python
def insert_run_name(ctx, client, tag_name, args, kwargs):
    return ctx.final_report.run_name


template_controller.create_template_tool("run_name", insert_run_name)
```

The template:

```text
Current run: [[run_name]]
```

will render with the value returned by the handler.

The default project tags are registered in `templates.py`:

- `[[source:path]]`: inserts a source file inside a fenced code block.
- `[[config:key:path]]`: inserts a value from the config object.
- `[[allowed_references]]`: lists local headers the generated attack may include.
- `[[runtime_data:key]]`: inserts runtime data passed into `process_template`.
- `[[model:hypothesis]]`, `[[model:implementation]]`, `[[model:summary]]`: describes a structured Pydantic output model.
- `[[hypothesis]]`: formats the current hypothesis and run configuration.
- `[[sim_feedback]]`: formats build/runtime feedback, or `None`.
- `[[results]]`: formats compact statistical results for summarization.
- `[[summary]]`: formats the previous summarization for the next hypothesis step.

System prompts are rendered when agents are created. Input prompts are rendered each time a state calls an agent, so they can use runtime values from `GovernorContext`, such as the current hypothesis, implementation, statistics, or previous summary.

### Agents

`prompting/client.py` defines the `Agent` wrapper around LangChain's `create_agent` and `ChatOpenAI`. Agents are invoked by governor QSM states; the agent wrapper handles model calls, while the state machine decides when each agent runs and what happens with its output. Each agent has:

- A model name from config.
- A rendered system prompt.
- A set of prompt template paths.
- Optional runtime tools selected by config.
- A Pydantic response model used as the structured output format.
- Its own LangGraph checkpoint thread.
- Optional context compaction controlled by `ctx.llm.context_compaction`.

The current response models live in `agents/responses.py`:

- `Hypothesis`: describes the next implementation-guiding strategy and run configuration.
- `Implementation`: contains the generated `attack.c` source and a summary of changes.
- `Summarization`: interprets a completed or failed simulation and gives guidance for the next hypothesis.

To define a new agent, add a new Pydantic response model first:

```python
class Review(BaseModel):
    finding: str
    recommendation: str
```

Then create prompt templates for it, add a config entry with its model, template paths, and optional runtime tools, and instantiate it with `create_agent_from_config` in `governor.py`:

```python
review_agent = create_agent_from_config(
    ctx,
    template_controller,
    "review",
    Review,
    dry,
)
```

In normal use, the new agent also needs a state that renders its input prompt, calls `agent.prompt_model`, stores the structured response in `GovernorContext`, logs a report event, and appends the next state to the queue. Add that state to the governor QSM JSON config so it becomes part of the active workflow. This keeps the agent interface reusable while letting the state machine decide when and why the agent runs.

Model choice and prompt paths are config-driven, so collaborators can iterate on prompt engineering without rewriting the agent wrapper.

Runtime tools are separate from prompt-template tags. Prompt-template tags run before a prompt is sent and are registered on `TemplateController`. Runtime tools are LangChain tools passed to `create_agent`, so the model may call them during its turn. Tool names are configured per agent with `AgentConfig.tools`, resolved through `prompting.tools.AgentToolRegistry`, and unknown tool names fail during agent construction. The generic registry lives in `prompting/tools.py`; concrete default tool implementations and registration live in the root-level `tools.py`, mirroring the split between `prompting/templates.py` and root-level `templates.py`.

The default summarization agent is configured with `read_attack_assembly`. That tool reads only the deployed `attack.s` path from config and raises `MissingAttackAssemblyError` if the file is absent. It does not run `make`, spawn subprocesses, or accept model-supplied file paths.

### Reports

Reports are generated from an event transcript. The transcript is the ordered list of `ReportEvent` objects recorded during the governor run. Instead of having each section collect its own data while the loop runs, states log structured events, and report sections later decide how to render those events.

This makes the report system reusable in two ways:

1. New states or modules can add new event types without changing every report section.
2. New report sections can interpret the same transcript differently.

The base event type is defined in `reporting/events.py`:

```python
class ReportEvent:
    def __init__(self, iteration, state, kind, payload):
        self.iteration = iteration
        self.state = state
        self.kind = kind
        self.timestamp = datetime.now(tz=timezone.utc)
        self.payload = payload
```

Default event subclasses in `reporting/default/events.py` represent hypothesis outputs, implementations, build errors, simulation errors, analysis results, summaries, and final conclusions. To add a new event, subclass `ReportEvent` and choose:

- `iteration`: which governor iteration produced the event.
- `state`: which state produced it.
- `kind`: a short event category, such as `output`, `error`, or `deployment`.
- `payload`: the structured object, exception, dataframe, or metadata the report should render.

Report sections subclass `ReportSection` from `reporting/sections.py` and implement `body(ctx, events)`. The base class wraps the body in a collapsible HTML `<details>` section and renders Markdown with table and fenced-code support:

```python
class MySection(ReportSection):
    def __init__(self):
        super().__init__(index=2, name="My Section")

    def body(self, ctx, events):
        interesting = [e for e in events if e.kind == "output"]
        return f"Found {len(interesting)} output events."
```

Register sections with `ReportLog.add_section`. Sections are sorted by `index` before rendering.

The default report contains a timeline section and a final verification section. The timeline renders the transcript iteration by iteration, while final verification finds the latest conclusion or analysis event and renders the final scores, hypothesis, implementation, and statistics.

For tables, use `MarkdownTableBuilder` from `reporting/tables.py`. It can render Markdown tables or styled HTML tables, which helps keep report tables readable inside the generated HTML.
