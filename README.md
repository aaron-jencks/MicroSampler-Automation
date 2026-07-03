# Microarchitectural Vulnerability Detection
This project investigates how best to utilize traces from pre-silicon simulation for vulnerability detection at the microarchitectural level of abstraction during the IC design life-cycle.  In particular, the analysis is focused on traces from executions of security critical applications in order to validate claims of properties enabling confidentiality protections.

The RISC-V BOOM processor released with the Chipyard framework from UC Berkeley is used as a testbed, along with cryptographic primitives from the BearSSL library as applications to study.

The tool has three stages: simulation, parsing and calculation of vulnerability metrics.

## Quick Start

### Dependencies

1. Requires Python3 >= 3.11 (suggest using <code>virtualenv</code> to install local version)
2. A valid `risv64-unknown-elf` cross-compiler with `fence` instruction enabled

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

The MicroSampler project pipeline consists of a few stages:
1. simulation: runs the simulation and generates the raw log output
2. parse: parses the simulation log output
3. stats: generates the statistical analysis of the parsed output

There is a `scripts/launch_jobs.sh` script, but it does not work correctly, so this guide will walk you through running the examples manually:

#### Simulation

To run the simulation you need to have the BOOM_simulator in the root of the repo, then run the following:

```bash
mkdir -p "logs/$design/$suite/$app/$iters/$key"
./scripts/do_simulation.sh "$key" "$suite" "$app" "$iters" "$design" > "logs/$design/$suite/$app/$iters/$key/launch_simulation.log" 2>&1
```

Where:
* `$design` is the chip design, defaults to `baseline`
* `$suite` is the suite of code to run (ie. microbench, bearssl_synthetic)
* `$app` is the app version to run (ie. v1, v2, v3, v1_warmup, v2_fence, etc...). The different versions can be found in [apps/bearssl-0.6/microsampler_tests/src](apps/bearssl-0.6/microsampler_tests/src) and there is one version of `microbench` which is `ct_ccopy`.
* `$iters` is the number of iterations to run inside of the UUT
* `$key` is the name of the key file to use, these are found in [scripts/keys](scripts/keys), it should be the stem of the filename (ie. 0xaa.key -> 0xaa)

#### Parsing

To run the parsing you need the PC addresses first, to find these, run the python script:

```bash
python scripts/pc_finder.py OBJECT_DUMP_FILE ROI_FUNC UUT_FUNC WARMUP
```

Where:
* OBJECT_DUMP_FILE is the object dump file found by running `objdump` on the target test-case source code.
* ROI_FUNC can be the same as UUT_FUNC and indicates the function name that should call the UUT.
* UUT_FUNC indicates the function name that is used as the UUT.
* WARMUP indicates whether there is warmup call to the UUT

An example call would be something like this:

```bash
python scripts/pc_finder.py apps/bearssl-0.6/microsampler_tests/build/v1_warmup.dump br_i31_modpow_v1 br_ccopy_v1 "warmup"
```

It will output a line of addresses that you need to pass to the parsing script. You run the parsing script like this:

```bash
./scripts/do_parse.sh "$key" PC_FINDER_OUTPUT "$suite" "$app" "$iters" "$design" > "logs/$design/$suite/$app/$iters/$key/launch_parse.log" 2>&1
```

Where:
* `$key`, `$suite`, `$app`, `$iters`, and `$design` are the same as defined in the Simulation section
* PC_FINDER_OUTPUT is the unquoted output of the pc_finder script.

An example run of this would be:
```bash
./scripts/do_parse.sh 0xaa 0x008000010e 0x0080000124 0x0080000196 0x0080000130 0x008000019a microbench ct_ccopy 100 baseline > "logs/baseline/microbench/ct_ccopy/100/0xaa/launch_parse.log" 2>&1
```

Notice that the log prefix is the same as the simulation step.

#### Stats

The last step is the stats analysis step. It essentially works just like the other two steps, so its format is:

```bash
./scripts/do_stats.sh "$key" "$suite" "$app" "$phi" "$alpha" "$window" "$iters" "$design" > "logs/$design/$suite/$app/$iters/$key/launch_stats.log" 2>&1
```

Where:
* Everything except `$phi`, `$alpha` and `$window` are the same as the previous two steps
* `$phi` is a floating point number, default is 0.9
* `$alpha` is a floating point number, default is 0.1
* `$window` is a number, default is 1

### Full Example

Below is a full example for the following parameters:
```bash
design=baseline
suite=microbench
app=ct_ccopy
key=0xaa
iters=100
phi=0.9
alpha=0.1
window=1
```

```bash
mkdir -p "logs/baseline/microbench/ct_ccopy/100/0xaa"
./scripts/do_simulation.sh "0xaa" "microbench" "ct_ccopy" "100" "baseline" > "logs/$design/$suite/$app/$iters/$key/launch_simulation.log" 2>&1
python scripts/pc_finder.py "apps/microbench/ct_ccopy/0xaa/ct_ccopy.dump" "test_ccopy_loop" "ccopy" "warmup"
```

pc_finder will output: `0x0080000120 0x0080000124 0x0080000196 0x0080000130 0x008000019a`. After that:

```bash
./scripts/do_parse.sh 0xaa 0x008000010e 0x0080000124 0x0080000196 0x0080000130 0x008000019a microbench ct_ccopy 100 baseline > "logs/baseline/microbench/ct_ccopy/100/0xaa/launch_parse.log" 2>&1
./scripts/do_stats.sh "0xaa" "microbench" "ct_ccopy" "0.9" "0.1" "1" "100" "baseline" > "logs/baseline/microbench/ct_ccopy/100/0xaa/launch_stats.log" 2>&1
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

