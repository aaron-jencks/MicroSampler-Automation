# Microarchitectural Vulnerability Detection
This project investigates how best to utilize traces from pre-silicon simulation for vulnerability detection at the microarchitectural level of abstraction during the IC design life-cycle.  In particular, the analysis is focused on traces from executions of security critical applications in order to validate claims of properties enabling confidentiality protections.

The RISC-V BOOM processor released with the Chipyard framework from UC Berkeley is used as a testbed, along with cryptographic primitives from the BearSSL library as applications to study.

The tool has three stages: simulation, parsing and calculation of vulnerability metrics.

## Quick Start

### Dependencies

1. Requires Python3 >= 3.11 (suggest using <code>virtualenv</code> to install local version)
2. A valid `riscv64-unknown-elf` cross-compiler with the `fence` instruction enabled

### Development Server Setup

The development server that we use contains most of the code and infrastructure necessary to get this up and running. To do this you need to log into the server, then do the following:

1. `cd` into `/local/scratch/{YOUR USERNAME}`
2. Run `source /local/scratch/scripts/microsampler-env.sh`
3. Verify that `which riscv64-unknown-elf-gcc` outputs `/local/scratch/riscv/bin/riscv64-unknown-elf-gcc`
4. Make a python environment for yourself, I would suggest in `/local/scratch/{YOUR USERNAME}/venvs`. You can do this by running `python3.11 -m virtualenv /local/scratch/{YOUR USERNAME}/venvs/microsampler`. **Note:** If you do use my suggested directory location, you'll need to make the `venvs` directory first with `mkdir -p /local/scratch/{YOUR USERNAME}/venvs`. **NOTE:** The python version is VERY important, do not use just `python` you MUST use `python3.11`.
5. Activate your new python environment with `source {VENV LOCATION}/bin/activate` where `{VENV LOCATION}` would be `/local/scratch/{YOUR USERNAME}/venvs/microsampler` if you used the example above.
6. Install the project dependencies with `pip install -r requirements.txt`

### Local Setup

1. Create a Python environment with Python3 >= 3.11
2. Install repo dependencies: `pip install -r requirements.txt`
3. Run `make` in `apps/bearssl-0.6/microsampler_tests` to compile all the tests.

### The Pipeline

The MicroSampler project pipeline has three stages:
1. simulation: runs the simulator and generates the raw trace log
2. parse: parses the trace log into sampled microarchitectural state
3. stats: analyzes the parsed state samples for candidate class-specific behavior

There is a `scripts/launch_runs.sh` script, but it is not the reliable path right now, so this guide walks through the pipeline manually:

#### Simulation

To run the simulation, you need to have `BOOM_simulator` in the root of the repo. Create the log directory, then run the simulation script:

```bash
mkdir -p logs/DESIGN/SUITE/APP/ITERS/KEY
./scripts/do_simulation.sh KEY SUITE APP ITERS DESIGN > logs/DESIGN/SUITE/APP/ITERS/KEY/launch_simulation.log 2>&1
```

Where:
* `DESIGN` is the chip design, defaulting to `baseline`.
* `SUITE` is the suite of code to run, for example `microbench` or `bearssl_synthetic`.
* `APP` is the app version to run, for example `v1`, `v2`, `v3`, `v1_warmup`, or `v2_fence`. The BearSSL synthetic versions are in [apps/bearssl-0.6/microsampler_tests/src](apps/bearssl-0.6/microsampler_tests/src). The `microbench` suite currently uses `ct_ccopy`.
* `ITERS` is the number of iterations to run inside the unit under test.
* `KEY` is the stem of the key file in [scripts/keys](scripts/keys), for example `0xaa` for `0xaa.key`.

#### Parsing

To run the parser, first find the PC addresses for the region of interest and unit under test:

```bash
python scripts/pc_finder.py OBJECT_DUMP_FILE ROI_FUNC UUT_FUNC WARMUP
```

Where:
* `OBJECT_DUMP_FILE` is the object dump file generated from the target test case.
* `ROI_FUNC` is the function name for the region of interest. It can be the same as `UUT_FUNC`.
* `UUT_FUNC` is the function used as the unit under test.
* `WARMUP` should be `warmup` when the binary includes a warmup call before the measured call. Omit it otherwise.

For example:

```bash
python scripts/pc_finder.py apps/bearssl-0.6/microsampler_tests/build/v1_warmup.dump br_i31_modpow_v1 br_ccopy_v1 warmup
```

It will output a line of addresses that you need to pass to the parsing script. You run the parsing script like this:

```bash
./scripts/do_parse.sh KEY PC_FINDER_OUTPUT SUITE APP ITERS DESIGN > logs/DESIGN/SUITE/APP/ITERS/KEY/launch_parse.log 2>&1
```

Where:
* `KEY`, `SUITE`, `APP`, `ITERS`, and `DESIGN` are the same as defined in the Simulation section.
* `PC_FINDER_OUTPUT` is the unquoted output of the `pc_finder.py` script.

An example run of this would be:
```bash
./scripts/do_parse.sh 0xaa 0x0080000120 0x0080000124 0x0080000196 0x0080000130 0x008000019a microbench ct_ccopy 100 baseline > logs/baseline/microbench/ct_ccopy/100/0xaa/launch_parse.log 2>&1
```

Notice that the log prefix is the same as the simulation step.

#### Stats

The last step is the stats analysis step:

```bash
./scripts/do_stats.sh KEY SUITE APP PHI ALPHA WINDOW ITERS DESIGN > logs/DESIGN/SUITE/APP/ITERS/KEY/launch_stats.log 2>&1
```

Where:
* `KEY`, `SUITE`, `APP`, `ITERS`, and `DESIGN` are the same as the previous two steps.
* `PHI` is the high-frequency threshold used by `scripts/stats.py` when selecting candidate microarchitectural states. A state must appear in at least this fraction of iterations for one data class to be treated as representative. The default in `scripts/launch_runs.sh` is `0.90`.
* `ALPHA` is the low-frequency exclusion threshold used for the other data classes. A candidate is rejected if another class also sees that state at or above this frequency. The default in `scripts/launch_runs.sh` is `0.10`.
* `WINDOW` is the number of key bits grouped into one data class. `WINDOW=1` compares single-bit classes, giving two possible classes. Larger windows create `2**WINDOW` possible classes and reduce the number of analyzed loop groups to roughly `ITERS / WINDOW`. The default in `scripts/launch_runs.sh` is `1`.

`PHI` and `ALPHA` are implementation thresholds for candidate selection in this script, not statistical p-values.

### Full Example

Below is a full example using `DESIGN=baseline`, `SUITE=microbench`, `APP=ct_ccopy`, `KEY=0xaa`, `ITERS=100`, `PHI=0.9`, `ALPHA=0.1`, and `WINDOW=1`.

```bash
mkdir -p logs/baseline/microbench/ct_ccopy/100/0xaa
./scripts/do_simulation.sh 0xaa microbench ct_ccopy 100 baseline > logs/baseline/microbench/ct_ccopy/100/0xaa/launch_simulation.log 2>&1
python scripts/pc_finder.py apps/microbench/ct_ccopy/0xaa/ct_ccopy.dump test_ccopy_loop ccopy warmup
```

pc_finder will output: `0x0080000120 0x0080000124 0x0080000196 0x0080000130 0x008000019a`. After that:

```bash
./scripts/do_parse.sh 0xaa 0x0080000120 0x0080000124 0x0080000196 0x0080000130 0x008000019a microbench ct_ccopy 100 baseline > logs/baseline/microbench/ct_ccopy/100/0xaa/launch_parse.log 2>&1
./scripts/do_stats.sh 0xaa microbench ct_ccopy 0.9 0.1 1 100 baseline > logs/baseline/microbench/ct_ccopy/100/0xaa/launch_stats.log 2>&1
```

<!-- The file <code>scripts/launch_runs.sh</code> is a job scheduling script for a local cluster. This can be used to launch multiple runs across nodes using SSH of the same application, selecting different inputs (keys) and hardware designs. This script is simply a helper-wrapper which then executes <code>do_simulation.sh</code>, <code>do_parse.sh</code> and <code>do_stats.sh</code> followed by <code>parse_trace.py</code> and <code>stats.py</code>, respectively.
The script should be called three times to launch the simulation, parsing and stats collection phases. Below are some examples of its use:  
> <code>./scripts/launch_runs.sh -action simulate -suite bearssl_synthetic -appsi v2 -design baseline -mode ssh</code>    

This will launch seperate simulations of the v2 application using each available key as input, defined in the <code>keys</code> array of <code>launch_runs.sh</code>

> <code>./scripts/launch_runs.sh -action simulate -suite bearssl_synthetic  **-appsi "v1 v2 v3"**  **-keysi 0xaa** -design baseline -mode ssh</code> 
   
This will launch a simulation only for the 0xaa input, for three applications (v1, v2 & v3)

> <code>./scripts/launch_runs.sh -action simulate -suite bearssl_synthetic -appsi v2 -design baseline **-mode dryrun**</code> 

Print the command that will be issued to the remote node over SSH, instead of running it
-->
