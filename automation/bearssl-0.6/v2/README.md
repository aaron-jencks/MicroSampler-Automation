# ChatGPT Non-RTL Leakage Detection

This directory houses the framework for using ChatGPT to automatically verify constant-time code.
It operates by prompting the LLM to fill in an interface defined in [skeleton.h](harness/skeleton.h).
The LLM can choose when to run the simulation, it can also read and write files in a sandbox, giving it the ability to perform its own data analysis.

## Running

Make sure that your python environment contains the dependencies listed in [requirements.txt](requirements.txt).

The main file is [governor.py](governor.py). Most of the configuration data is stored in config files stored in the [config](config) folder.
The program uses a cascading config file pattern, meaning that the left-most config file has priority over the preceding ones.

The usage is:
```
python governor.py [--dry-run] [--default-config PATH] [CONFIGS...]
```

`--dry-run` runs up through the first prompt, but does not send any data to the LLM.
`--default-config` specifies the default config to use (default: [config/default.json](config/default.json))
`CONFIGS` is an optional space-separated list of zero config files to use in cascading order.

### Example Usage

```
python governor.py --dry-run config/some-test.json config/local.json
```
