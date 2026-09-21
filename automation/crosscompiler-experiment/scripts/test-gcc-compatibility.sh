#!/usr/bin/env bash
# One authored file; Python's standard library provides process-group supervision,
# monotonic timing, JSON checkpoints, archive validation, and streaming log capture.
# Run with bash: no chmod, system installation, or shell configuration is needed.
# --help and --self-test are read-only. Other modes create runtime artifacts ONLY
# below the fixed server experiment directory. Original PK and project sources
# are never built in place. No sudo, source patches, cleanup, or Git checkout.
set -euo pipefail
command -v python3 >/dev/null || { printf '%s\n' 'Python 3 is required; nothing was changed.' >&2; exit 2; }
export PYTHONDONTWRITEBYTECODE=1
python3 -u - "$0" "$@" <<'PYTHON'
import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import selectors
import shlex
import shutil
import signal
import stat
import subprocess as sp
import sys
import tarfile
import time

PROJECT = Path('/local/scratch/vologzhanin.2/MicroSampler-Automation')
ROOT = PROJECT / 'automation/crosscompiler-experiment'
PK_SOURCE = Path('/local/scratch/jencks.5/workspace/src/riscv-pk')
PK_REV = '9c61d29846d8521d9487a57739330f9682d5b542'
EXISTING_PK = Path('/local/scratch/riscv/riscv64-unknown-elf/bin/pk')
BOOM = PROJECT / 'BOOM_simulator'
MICRO = PROJECT / 'apps/microbench/ct_ccopy/0xaa/ct_ccopy'
STUB = ROOT / 'stub.c'
BOOM_SHA = '0ecc28d64150d08f9314f9dd1f69dea858e738e6aa8402b2e61186e691ea6d1c'
STUB_SHA = 'f92a4650afd1781064999a6d5f0412923b07c65f3a22c94f65f449899c65f81e'
# Majors first released in 2022 through 2026; newest maintenance release as
# verified at https://gcc.gnu.org/releases.html on 2026-09-20. Never auto-expand.
VERSIONS = ('16.2.0', '15.3.0', '14.4.0', '13.5.0', '12.5.0')
TARGET, ARCH, ABI = 'riscv64-unknown-elf', 'rv64gc_zifencei', 'lp64d'
SEED, JOBS, LIMIT, MICRO_LIMIT = 1, 8, 300, 60
# Fixed companion revisions inspected in the existing riscv-gnu-toolchain tree:
# binutils 2.46 release and Newlib 4.5.0 (2024-12-31 snapshot).
COMPANIONS = {
    'binutils': ('https://sourceware.org/git/binutils-gdb.git',
                 '49d4d3fafa4ec4ff5a3460d91d5b1ed5286487db'),
    'newlib': ('https://sourceware.org/git/newlib-cygwin.git',
               '5e5e51f1dc56a99eb4648c28e00d73b6ea44a8b0'),
}
GIB = 1024 ** 3
# Planning reserves, NOT architectural requirements. No automatic deletion.
FIRST_RESERVE, STOP_RESERVE = 20 * GIB, 5 * GIB
PASS_PATTERN = re.compile(rb'^\*\*\* PASSED \*\*\* Completed after [0-9]+ cycles\s*$', re.M)
BAD_PATTERN = re.compile(rb'\*\*\* FAILED \*\*\*|Assertion failed|%Error|terminate called|Segmentation fault')
ENV = dict(os.environ)
ENV.update(PATH='/usr/local/bin:/usr/bin:/bin', LC_ALL='C', TZ='UTC',
           PYTHONDONTWRITEBYTECODE='1', GIT_OPTIONAL_LOCKS='0',
           GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL='/dev/null',
           GIT_TERMINAL_PROMPT='0')
for key in ('CC', 'CXX', 'CFLAGS', 'CXXFLAGS', 'CPPFLAGS', 'LDFLAGS', 'LIBRARY_PATH',
            'CPATH', 'C_INCLUDE_PATH', 'CPLUS_INCLUDE_PATH', 'GCC_EXEC_PREFIX',
            'COMPILER_PATH', 'CONFIG_SITE', 'MAKEFLAGS', 'MFLAGS', 'LD_PRELOAD',
            'LD_LIBRARY_PATH', 'RISCV'):
    ENV.pop(key, None)
ACTIVE = None
SESSION_LOG = None
SESSION = None
STATE = None
CURRENT = None


class Stop(Exception):
    pass


class StageFailed(Exception):
    pass


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def digest(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def say(message):
    line = str(message)
    print(line, flush=True)
    if SESSION_LOG:
        with open(SESSION_LOG, 'a', encoding='utf-8') as f:
            f.write(line + '\n')


def banner(message):
    say('=' * 64)
    say(message)
    say('=' * 64)


def contained(path):
    p = Path(path).resolve()
    if p != ROOT and ROOT not in p.parents:
        raise Stop('Refusing write outside experiment: ' + str(path))
    return p


def directory(path):
    p = contained(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def save(path, value):
    p = contained(path)
    temp = contained(str(p) + '.pending')
    with open(temp, 'w', encoding='utf-8') as f:
        json.dump(value, f, indent=2, sort_keys=True)
        f.write('\n')
        f.flush()
        os.fsync(f.fileno())
    os.replace(temp, p)


def read_json(path):
    try:
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    except (ValueError, OSError) as e:
        raise Stop('Invalid checkpoint {}: {}'.format(path, e))


def capture(argv, cwd=None):
    result = sp.run([str(x) for x in argv], cwd=cwd, env=ENV,
                    stdout=sp.PIPE, stderr=sp.PIPE, text=True, timeout=30)
    if result.returncode:
        raise Stop('{}: {}'.format(shlex.join([str(x) for x in argv]), result.stderr.strip()))
    return result.stdout.strip()


def git_pk(*args):
    return capture(['git', '-c', 'safe.directory=' + str(PK_SOURCE), '-C', PK_SOURCE, *args])


def kill_active():
    if ACTIVE is not None:
        try:
            os.killpg(ACTIVE.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        ACTIVE.wait()


def interrupted(signum, frame):
    kill_active()
    raise Stop('INTERRUPTED by signal {}; partial artifacts retained.'.format(signum))


def space(minimum=STOP_RESERVE):
    free = shutil.disk_usage(ROOT).free
    fs = os.statvfs(ROOT)
    if free < minimum or fs.f_favail < 1000:
        raise Stop('INSUFFICIENT_DISK_SPACE: {:.1f} GiB / {} free inodes. '
                   'No data deleted; free space or obtain approval for cleanup.'.format(free / GIB, fs.f_favail))
    return free


def run(argv, cwd, log, limit=None, env=None, trace=False):
    """Own the complete process group; tee builds, preserve raw BOOM streams.

    Linux timeout enforces BOOM's limit; a monotonic watchdog independently
    kills its whole group at the same deadline, including stubborn descendants.
    A forced timeout never qualifies as success, even if a pass line exists.
    """
    global ACTIVE
    cwd, log = directory(cwd), contained(log)
    out_path = contained(str(log) + '.stdout') if trace else log
    err_path = contained(str(log) + '.stderr') if trace else out_path
    command = [str(x) for x in argv]
    executed = ['timeout', '--verbose', '--signal=KILL', str(limit) + 's', *command] if limit else command
    say('[STAGE] {}\n  cwd: {}\n  log: {}'.format(shlex.join(executed), cwd, log))
    start, begun = time.monotonic(), now()
    result = dict(command=command, executed=executed, cwd=str(cwd), started=begun,
                  limit_seconds=limit, stdout=str(out_path), stderr=str(err_path))
    save(str(log) + '.command.json', result)
    timed_out = False
    stream = None
    try:
        with open(out_path, 'wb') as out:
            if trace:
                stream = open(err_path, 'wb')
            ACTIVE = sp.Popen(executed, cwd=cwd, env=env or ENV, stdin=sp.DEVNULL,
                              stdout=out if trace else sp.PIPE,
                              stderr=stream if trace else sp.STDOUT, start_new_session=True)
            selector = selectors.DefaultSelector()
            if not trace:
                selector.register(ACTIVE.stdout, selectors.EVENT_READ)
            next_report = start + 10
            while True:
                elapsed = time.monotonic() - start
                if limit and elapsed >= limit and ACTIVE.poll() is None:
                    timed_out = True
                    kill_active()
                if trace:
                    time.sleep(0.1)
                else:
                    for key, _ in selector.select(0.2):
                        data = os.read(key.fd, 65536)
                        if data:
                            out.write(data)
                            out.flush()
                            sys.stdout.buffer.write(data)
                            sys.stdout.buffer.flush()
                        else:
                            selector.unregister(key.fileobj)
                if time.monotonic() >= next_report:
                    free = space()
                    if trace:
                        size = out_path.stat().st_size + err_path.stat().st_size
                        say('[WAIT] BOOM {:.1f}s / {}s; trace {:.2f} GiB; free {:.1f} GiB'.format(
                            elapsed, limit, size / GIB, free / GIB))
                    next_report = time.monotonic() + 10
                if ACTIVE.poll() is not None and (trace or not selector.get_map()):
                    break
            rc = ACTIVE.wait()
            # Always remove any remaining descendants of the owned group.
            kill_active()
            ACTIVE = None
            selector.close()
        if stream:
            stream.close()
            stream = None
        elapsed = time.monotonic() - start
        # timeout's own diagnostic distinguishes its KILL from an unrelated crash.
        if trace and not timed_out:
            with open(err_path, 'rb') as f:
                f.seek(max(0, err_path.stat().st_size - 16384))
                tail = f.read()
            timed_out = (rc == 124 or (rc == 137 and b'timeout: sending signal KILL' in tail))
        result.update(ended=now(), duration_seconds=elapsed, returncode=rc,
                      timed_out=timed_out, forced_termination=timed_out)
        save(str(log) + '.result.json', result)
        space()
        if not trace and rc:
            with open(log, 'rb') as f:
                f.seek(max(0, log.stat().st_size - 256 * 1024))
                tail = f.read()
            if rc < 0 or re.search(rb'No space left|Disk quota exceeded|Cannot allocate memory|out of memory|Killed signal|Permission denied', tail, re.I):
                raise Stop('INFRASTRUCTURE_FAILED: command failed from signal/resource/permission error; see ' + str(log))
        return result
    finally:
        kill_active()
        ACTIVE = None
        if stream:
            stream.close()


def output_flags(paths):
    passed = failed = False
    # Chunk scanning bounds memory even for multi-gigabyte traces or long lines.
    for path in paths:
        overlap = b''
        with open(path, 'rb') as f:
            for block in iter(lambda: f.read(1024 * 1024), b''):
                data = overlap + block
                passed = passed or bool(PASS_PATTERN.search(data))
                failed = failed or bool(BAD_PATTERN.search(data))
                overlap = data[-4096:]
    return passed, failed


def classify(rc, elapsed, limit, timed_out, passed, failed):
    if timed_out or elapsed >= limit:
        return 'BOOM_TIMEOUT'
    if rc < 0 or rc in (134, 137, 139):
        return 'BOOM_CRASH'
    if rc in (125, 126, 127):
        return 'SIMULATOR_START_FAILED'
    if passed and (rc != 0 or failed):
        return 'AMBIGUOUS_EXECUTION'
    if rc != 0 or failed:
        return 'EXECUTION_FAILED'
    return 'SUCCESS' if passed else 'AMBIGUOUS_EXECUTION'


def boom_test(binary_args, directory_path, limit):
    result = run([BOOM, '-s', str(SEED), '+verbose', *binary_args],
                 directory_path, Path(directory_path) / 'boom', limit=limit, trace=True)
    passed, failed = output_flags([result['stdout'], result['stderr']])
    result.update(pass_marker=passed, failure_marker=failed,
                  classification=classify(result['returncode'], result['duration_seconds'],
                                          limit, result['timed_out'], passed, failed),
                  trap_detector='NOT USED: successful completion is the approved working criterion')
    save(Path(directory_path) / 'evaluation.json', result)
    say('[RESULT] {}: exit={}, elapsed={:.3f}s, pass_marker={}, failure_marker={}'.format(
        result['classification'], result['returncode'], result['duration_seconds'], passed, failed))
    return result


def checked(argv, cwd, log, env=None, limit=None):
    result = run(argv, cwd, log, env=env, limit=limit)
    if result['returncode']:
        raise StageFailed('exit {}: {}'.format(result['returncode'], log))


def ensure_elf(path, machine):
    with open(path, 'rb') as f:
        head = f.read(64)
    if len(head) < 64 or head[:6] != b'\x7fELF\x02\x01' or int.from_bytes(head[18:20], 'little') != machine:
        raise Stop('Expected little-endian ELF64 machine {}: {}'.format(machine, path))


def check_pk():
    if git_pk('rev-parse', '--show-toplevel') != str(PK_SOURCE):
        raise Stop('PK path is not the expected repository root')
    if git_pk('rev-parse', 'HEAD') != PK_REV or git_pk('status', '--porcelain', '--untracked-files=normal'):
        raise Stop('PK revision/working tree differs from the inspected source; human review required')
    for name in ('configure', 'configure.ac', 'Makefile.in', 'pk/pk.h', 'machine/mtrap.c'):
        if not os.access(PK_SOURCE / name, os.R_OK):
            raise Stop('Missing/unreadable PK source: ' + name)


def fingerprint():
    check_pk()
    if digest(BOOM) != BOOM_SHA or digest(STUB) != STUB_SHA:
        raise Stop('BOOM or immutable stub hash differs from the investigated artifact')
    libraries = {}
    probe = ROOT / 'tmp' / SESSION.name / 'native-probe/probe'
    for executable in (BOOM, probe):
        for line in capture(['ldd', executable]).splitlines():
            if 'not found' in line:
                raise Stop('Unresolved runtime library: ' + line)
            for token in line.split():
                if token.startswith('/') and Path(token).is_file():
                    libraries[token] = digest(token)
    return dict(schema=1, script=digest(Path(sys.argv[1]).resolve()), pk_revision=PK_REV,
                pk_configure=digest(PK_SOURCE / 'configure'), pk_makefile=digest(PK_SOURCE / 'Makefile.in'),
                boom=digest(BOOM), microbench=digest(MICRO), stub=digest(STUB),
                existing_pk=digest(EXISTING_PK), versions=VERSIONS, target=TARGET, arch=ARCH, abi=ABI,
                seed=SEED, limit=LIMIT, jobs=JOBS, companions=COMPANIONS,
                native_gcc=capture(['gcc', '--version']), native_gxx=capture(['g++', '--version']),
                native_gcc_hash=digest(Path(shutil.which('gcc', path=ENV['PATH'])).resolve()),
                native_gxx_hash=digest(Path(shutil.which('g++', path=ENV['PATH'])).resolve()),
                host=capture(['uname', '-a']), host_libc=capture(['getconf', 'GNU_LIBC_VERSION']),
                runtime_libraries=libraries)


def preflight():
    global STATE
    banner('Cross-Compiler Experiment Preflight')
    say('No known-good PK baseline is required. No trap-loop detector is used.')
    failures = []

    def check(label, action):
        try:
            action()
            say('[PASS] ' + label)
            return True
        except (Stop, StageFailed, OSError, sp.SubprocessError) as e:
            failures.append(label + ': ' + str(e))
            say('[FAIL] ' + failures[-1])
            return False

    def tools():
        # Newlib/binutils/GCC build plus the script's own logging/provenance tools.
        required = ('bash', 'gcc', 'g++', 'make', 'as', 'ld', 'ar', 'ranlib', 'readelf',
                    'git', 'curl', 'tar', 'xz', 'gzip', 'bzip2', 'awk', 'sed', 'grep',
                    'bison', 'flex', 'makeinfo', 'perl', 'timeout', 'uname', 'getconf', 'ldd')
        missing = [x for x in required if not shutil.which(x, path=ENV['PATH'])]
        if missing:
            raise Stop('Missing tools: {}. System installation is disabled by the user-directory-only '
                       'policy; obtain separately authorized dependency provisioning, then rerun.'.format(', '.join(missing)))
        if 'GNU Make' not in capture(['make', '--version']) or 'GNU coreutils' not in capture(['timeout', '--version']):
            raise Stop('GNU Make and GNU coreutils timeout are required')
        for command in ('gcc', 'g++', 'make', 'git', 'curl', 'timeout'):
            say(capture([command, '--version']).splitlines()[0])
        say('Host OS:\n' + Path('/etc/os-release').read_text().strip())

    tools_ok = check('Required host tools and Linux timeout', tools)

    def inputs():
        for p in (BOOM, MICRO, STUB, EXISTING_PK):
            if not p.is_file() or not os.access(p, os.R_OK):
                raise Stop('Missing/unreadable input: ' + str(p))
        if not os.access(BOOM, os.X_OK):
            raise Stop('BOOM is not executable; permissions will not be changed')
        ensure_elf(BOOM, 62)
        ensure_elf(MICRO, 243)
        ensure_elf(EXISTING_PK, 243)
        if digest(BOOM) != BOOM_SHA or digest(STUB) != STUB_SHA:
            raise Stop('BOOM/stub identity mismatch; no automatic substitution')
        say('Existing PK is recorded only; it is NOT a known-good baseline.')

    inputs_ok = check('BOOM, prebuilt MicroBench, immutable stub and existing server PK', inputs)
    pk_ok = check('Authoritative PK revision and clean source (read-only)', check_pk) if tools_ok else False
    say('[PASS] Explicit project-recipe target: {}; ISA {}; ABI {}; Newlib; no multilib'.format(TARGET, ARCH, ABI))
    say('[NOTE] ISA/ABI reproduce the archived project recipe; they do not prove PK compatibility.')

    def resources():
        available = space(FIRST_RESERVE)
        cpus = len(os.sched_getaffinity(0))
        memory = int(re.search(r'^MemAvailable:\s+(\d+)', Path('/proc/meminfo').read_text(), re.M).group(1)) * 1024
        # Account for the process's cgroup v2 hierarchy, not just machine totals.
        for line in Path('/proc/self/cgroup').read_text().splitlines():
            if line.startswith('0::'):
                cg = Path('/sys/fs/cgroup') / line[3:].lstrip('/')
                for parent in (cg, *cg.parents):
                    if parent == Path('/sys') or parent == Path('/'):
                        break
                    mf, cf = parent / 'memory.max', parent / 'cpu.max'
                    if mf.exists() and mf.read_text().strip() != 'max':
                        used = int((parent / 'memory.current').read_text())
                        memory = min(memory, max(0, int(mf.read_text()) - used))
                    if cf.exists():
                        quota, period = cf.read_text().split()
                        if quota != 'max':
                            cpus = min(cpus, max(1, int(quota) // int(period)))
        say('Free disk {:.1f} GiB; effective CPUs {}; available memory {:.1f} GiB; jobs {}'.format(
            available / GIB, cpus, memory / GIB, JOBS))
        if cpus < JOBS:
            raise Stop('Effective CPU allocation is below approved -j8; review job count before running')
        if memory < JOBS * GIB:
            raise Stop('Less than 1 GiB available per build job; conservative planning gate, '
                       'not a GCC requirement. Review resources before starting')
        if available < 100 * GIB:
            say('[WARN] Full retention may exceed capacity: 30–75 GiB build/source/install estimate '
                'plus potentially large traces. No automatic deletion.')
        say('[WARN] Filesystem free space does not prove remaining per-user quota.')

    check('Storage, CPU and memory planning reserves', resources)

    def native_probe():
        # Runtime-only probes: no separate authored helper source file.
        probe = directory(ROOT / 'tmp' / SESSION.name / 'native-probe')
        code = '#include <gmp.h>\n#include <mpfr.h>\n#include <mpc.h>\n#include <zlib.h>\nint main(){mpz_t z;mpz_init(z);mpz_clear(z);mpfr_t f;mpfr_init2(f,53);mpfr_clear(f);mpc_t c;mpc_init2(c,53);mpc_clear(c);return zlibVersion()?0:1;}\n'
        source = contained(probe / 'probe.cc')
        source.write_text(code)
        checked(['g++', source, '-o', probe / 'probe', '-lmpc', '-lmpfr', '-lgmp', '-lz'],
                probe, SESSION / 'native-build.log')
        checked([probe / 'probe'], probe, SESSION / 'native-execute.log')
        # Record the simulator's resolved libraries; fingerprint() hashes them
        # and the build libraries linked into this native probe for safe resume.
        checked(['ldd', BOOM], probe, SESSION / 'boom-libraries.log')

    if tools_ok:
        check('Native compiler, GMP/MPFR/MPC/zlib headers and links; output execution permission', native_probe)

    def network():
        for version in VERSIONS:
            base = 'https://gcc.gnu.org/pub/gcc/releases/gcc-' + version
            for name in ('gcc-' + version + '.tar.xz', 'sha512.sum'):
                checked(['curl', '--fail', '--location', '--proto', '=https', '--proto-redir', '=https',
                         '--head', '--connect-timeout', '15', '--max-time', '45', base + '/' + name],
                        SESSION, SESSION / ('network-gcc-' + version + '-' + name.replace('.', '-') + '.log'))
        for name, (url, rev) in COMPANIONS.items():
            # Only refs, not source downloads. Exact pinned object retrieval is
            # verified before attempts; unavailable objects stop as infrastructure.
            checked(['git', 'ls-remote', '--exit-code', url, 'HEAD'],
                    SESSION, SESSION / ('network-' + name + '.log'), limit=60)

    if tools_ok:
        check('GCC archive/checksum URLs and companion upstream connectivity', network)

    if inputs_ok and tools_ok:
        def microbench():
            result = boom_test([MICRO], directory(SESSION / 'microbench'), MICRO_LIMIT)
            if result['classification'] != 'SUCCESS':
                raise Stop('Existing BOOM MicroBench did not succeed; {}. '
                           'This is not candidate GCC incompatibility. Logs: {}'.format(
                               result['classification'], SESSION / 'microbench'))
            say('NOTE: This validates BOOM_Simulator/runtime operation only.')
            say('Proxy-kernel compatibility has NOT yet been established.')
        check('BOOM_Simulator MicroBench sanity test', microbench)

    if tools_ok and inputs_ok and pk_ok:
        def resume_check():
            global STATE
            identity = fingerprint()
            identity = json.loads(json.dumps(identity))
            state_path = ROOT / 'logs/state.json'
            if state_path.exists():
                STATE = read_json(state_path)
                if STATE.get('identity') != identity:
                    raise Stop('Configuration/source/host identity changed. Retained state will not be overwritten.')
                say('Validated existing experiment identity; {} recorded attempts'.format(len(STATE['attempts'])))
            else:
                # Reject unexplained populated artifact trees instead of adopting them.
                for name in ('sources', 'builds', 'toolchains'):
                    p = ROOT / name
                    if p.exists() and any(p.iterdir()):
                        raise Stop('Artifacts without state metadata: ' + str(p))
                STATE = dict(identity=identity, attempts={}, created=now())
                say('Fresh experiment; no completed stages inferred from directories.')
        check('Fixed-input identity and resumability metadata', resume_check)

    save(SESSION / 'preflight.json', dict(ended=now(), failures=failures, passed=not failures))
    if failures:
        banner('PREFLIGHT FAILED\nGCC compatibility testing was NOT started.')
        for failure in failures:
            say('- ' + failure)
        say('Only experiment-local preflight logs/probes were created; no packages or original sources changed.')
        raise Stop('Correct the failed checks, then rerun. Preflight log: ' + str(SESSION_LOG))
    banner('PREFLIGHT PASSED\nBOOM_Simulator passed its independent MicroBench sanity check.\n'
           'Host environment appears ready for GCC compatibility testing.\n'
           'Proxy-kernel compatibility remains unknown.')


def persist():
    save(ROOT / 'logs/state.json', STATE)


def extract(archive, destination):
    destination = contained(destination)
    if destination.exists():
        raise Stop('Uncheckpointed extraction already exists; preserving it for review: ' + str(destination))
    directory(destination)
    with tarfile.open(archive) as tf:
        # Reject devices, absolute/traversing names and links outside the tree.
        for member in tf.getmembers():
            p = destination / member.name
            if member.name.startswith('/') or '..' in Path(member.name).parts:
                raise Stop('Unsafe archive path: ' + member.name)
            if not (member.isfile() or member.isdir() or member.issym() or member.islnk()):
                raise Stop('Unsupported archive member: ' + member.name)
            if member.issym() or member.islnk():
                target = (p.parent if member.issym() else destination) / member.linkname
                if destination not in target.resolve().parents and target.resolve() != destination:
                    raise Stop('Archive link escapes extraction directory: ' + member.name)
        # tar does not restore ownership and is only used after path validation.
    checked(['tar', '--extract', '--file', archive, '--directory', destination,
             '--no-same-owner', '--no-same-permissions'], SESSION, SESSION / (destination.name + '-extract.log'))


def source_tree_hash(path):
    h = hashlib.sha256()
    for p in sorted(Path(path).rglob('*')):
        rel = str(p.relative_to(path)).encode()
        if p.is_symlink():
            h.update(b'L' + rel + os.readlink(p).encode())
        elif p.is_file():
            h.update(b'F' + rel + digest(p).encode())
    return h.hexdigest()


def companion(name, url, rev):
    destination = ROOT / 'sources' / (name + '-' + rev)
    marker = ROOT / 'sources' / (name + '-' + rev + '.json')
    if marker.exists():
        data = read_json(marker)
        if data['revision'] != rev or source_tree_hash(destination) != data['tree_sha256']:
            raise Stop('Companion source changed: ' + str(destination))
        say('[RESUME] Verified ' + name + ' ' + rev)
        return destination
    # Fetch into a private bare repository; no checkout/submodule changes anywhere.
    repo = ROOT / 'sources' / (name + '-' + rev + '.git')
    if not repo.exists():
        checked(['git', 'init', '--bare', repo], SESSION, SESSION / (name + '-init.log'))
    say('Source: {} / {}; pinned revision {}; required fixed toolchain component'.format(name, url, rev))
    checked(['git', '--git-dir=' + str(repo), 'fetch', '--depth=1', url, rev],
            SESSION, SESSION / (name + '-fetch.log'), limit=600)
    got = capture(['git', '--git-dir=' + str(repo), 'rev-parse', 'FETCH_HEAD'])
    if got != rev:
        raise Stop('Pinned component identity mismatch: ' + name)
    checked(['git', '--git-dir=' + str(repo), 'fsck', '--no-reflogs'],
            SESSION, SESSION / (name + '-fsck.log'))
    archive = ROOT / 'sources' / (name + '-' + rev + '.tar')
    checked(['git', '--git-dir=' + str(repo), 'archive', '--format=tar', '--output=' + str(archive), rev],
            SESSION, SESSION / (name + '-archive.log'))
    extract(archive, destination)
    save(marker, dict(url=url, revision=rev, archive_sha256=digest(archive), tree_sha256=source_tree_hash(destination)))
    return destination


def download(url, path, log):
    path = contained(path)
    partial = contained(str(path) + '.partial')
    # Retry only network/download transport, never a configure or execution result.
    checked(['curl', '--fail', '--location', '--proto', '=https', '--proto-redir', '=https',
             '--connect-timeout', '20', '--retry', '2', '--retry-delay', '3',
             '--speed-limit', '1024', '--speed-time', '120', '--output', partial, url], SESSION, log)
    os.replace(partial, path)


def gcc_source(version, attempt):
    base = 'https://gcc.gnu.org/pub/gcc/releases/gcc-' + version
    filename = 'gcc-' + version + '.tar.xz'
    archive = ROOT / 'sources' / filename
    sums = ROOT / 'sources' / ('gcc-' + version + '.sha512.sum')
    destination = ROOT / 'sources' / ('gcc-' + version)
    marker = ROOT / 'sources' / ('gcc-' + version + '.json')
    if marker.exists():
        data = read_json(marker)
        if data['url'] != base + '/' + filename or digest(archive) != data['archive_sha256'] or source_tree_hash(destination) != data['tree_sha256']:
            raise Stop('GCC source/archive changed; refusing unsafe resume: ' + version)
        say('[RESUME] Verified GCC source ' + version)
        return destination / ('gcc-' + version)
    say('[DOWNLOAD] GCC {} from {}'.format(version, base))
    download(base + '/sha512.sum', sums, Path(attempt['log']) / 'checksum-download.log')
    expected = None
    for line in sums.read_text().splitlines():
        fields = line.split()
        if len(fields) == 2 and fields[1].lstrip('*') in (filename, './' + filename):
            expected = fields[0]
    if not expected or not re.fullmatch('[0-9a-fA-F]{128}', expected):
        raise Stop('Missing/invalid upstream SHA-512 entry for ' + filename)
    download(base + '/' + filename, archive, Path(attempt['log']) / 'source-download.log')
    h = hashlib.sha512()
    with open(archive, 'rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    if h.hexdigest().lower() != expected.lower():
        raise Stop('SOURCE_VERIFICATION_FAILED: ' + str(archive))
    # Checksum transported over upstream HTTPS; not a separately verified signature.
    extract(archive, destination)
    save(marker, dict(url=base + '/' + filename, checksum_url=base + '/sha512.sum',
                      sha512=expected, archive_sha256=digest(archive), tree_sha256=source_tree_hash(destination)))
    return destination / ('gcc-' + version)


def stage(attempt, name, action, artifacts):
    stages = attempt.setdefault('stages', {})
    if name in stages and stages[name].get('complete'):
        for p, sha in stages[name]['artifacts'].items():
            if not Path(p).is_file() or digest(p) != sha:
                raise Stop('Completed-stage artifact missing/changed: ' + p)
        say('[RESUME] {} already completed and artifacts verified'.format(name))
        return
    say('[STAGE] GCC {}: {}'.format(attempt['version'], name))
    stages[name] = dict(complete=False, started=now())
    persist()
    action()
    for p in artifacts:
        if not Path(p).is_file():
            raise Stop('Stage claimed success but artifact is absent: ' + str(p))
    stages[name].update(complete=True, ended=now(), artifacts={str(p): digest(p) for p in artifacts})
    persist()


def configure_make(source, build, configure_args, targets, logdir, env):
    directory(build)
    # Interrupted stages retain the same build tree; GNU make resumes incrementally.
    # Never make clean, remove a build tree, or patch sources on retry.
    configuration = dict(source=str(source), arguments=configure_args)
    marker = build / 'configure-complete.json'
    if marker.exists():
        if read_json(marker) != configuration or not (build / 'Makefile').is_file():
            raise Stop('Inconsistent configure checkpoint: ' + str(build))
    else:
        checked([source / 'configure', *configure_args], build, logdir / (build.name + '-configure.log'), env)
        save(marker, configuration)
    for index, target in enumerate(targets):
        checked(['make', '-j' + str(JOBS), *target], build,
                logdir / (build.name + '-make-' + str(index) + '.log'), env)


def attempt_version(version, common):
    global CURRENT
    check_pk()
    if digest(BOOM) != BOOM_SHA or digest(STUB) != STUB_SHA:
        raise Stop('Fixed BOOM/stub input changed between attempts')
    old = STATE['attempts'].get(version)
    if old and old.get('finished'):
        # Verify stages even for completed failed attempts; do not infer from files.
        for item in old.get('stages', {}).values():
            if item.get('complete'):
                for p, sha in item['artifacts'].items():
                    if not Path(p).is_file() or digest(p) != sha:
                        raise Stop('Retained attempt artifact changed: ' + p)
        if old.get('toolchain_tree_sha256') and source_tree_hash(Path(old['prefix'])) != old['toolchain_tree_sha256']:
            raise Stop('Retained toolchain changed: ' + old['prefix'])
        if old.get('classification') == 'SUCCESS':
            r = old['execution']
            passed, failed = output_flags([r['stdout'], r['stderr']])
            if classify(r['returncode'], r['duration_seconds'], LIMIT, r['timed_out'], passed, failed) != 'SUCCESS':
                raise Stop('Retained successful execution evidence is inconsistent')
        say('[RESUME] GCC {} already finished: {} — {}'.format(version, old['classification'], old['reason']))
        return old
    space(FIRST_RESERVE)
    tag = 'gcc-' + version + '-' + ARCH + '-' + ABI
    build = directory(ROOT / 'builds' / tag)
    prefix = directory(ROOT / 'toolchains' / tag)
    if old:
        a = old
        # Unique stage logs on every invocation; interrupted logs never overwritten.
        log = directory(Path(a['log']) / ('resume-' + SESSION.name))
        a.setdefault('resume_logs', []).append(str(log))
    else:
        log = directory(ROOT / 'logs' / tag / SESSION.name)
        a = dict(version=version, started=now(), log=str(log), prefix=str(prefix),
                 build=str(build), stages={}, finished=False)
        STATE['attempts'][version] = a
    CURRENT = a
    persist()
    banner('Testing GCC {} — attempt {} of {}'.format(version, VERSIONS.index(version) + 1, len(VERSIONS)))
    say('Sources: {}\nBuild: {}\nCompiler prefix: {}\nLogs: {}'.format(ROOT / 'sources', build, prefix, log))
    started = time.monotonic()
    try:
        # Source transport/integrity errors stop the experiment, never count as GCC incompatibility.
        try:
            src = gcc_source(version, dict(a, log=str(log)))
        except StageFailed as e:
            raise Stop('SOURCE_DOWNLOAD_FAILED: ' + str(e))
        a['source'] = str(src)
        a['source_identity'] = read_json(ROOT / 'sources' / ('gcc-' + version + '.json'))
        persist()
        env = dict(ENV, PATH=str(prefix / 'bin') + ':' + ENV['PATH'], RISCV=str(prefix))
        cc, cxx = prefix / 'bin' / (TARGET + '-gcc'), prefix / 'bin' / (TARGET + '-g++')
        arch_args = ['--with-arch=' + ARCH, '--with-abi=' + ABI, '--with-isa-spec=20191213']
        gcc_args = ['--target=' + TARGET, '--prefix=' + str(prefix), '--disable-multilib',
                    '--disable-shared', '--disable-threads', '--enable-languages=c,c++',
                    '--with-newlib', '--with-sysroot=' + str(prefix / TARGET),
                    '--disable-libssp', '--disable-libquadmath', '--disable-libgomp',
                    '--disable-nls', '--disable-tm-clone-registry', '--disable-bootstrap', *arch_args]
        phase = 'TOOLCHAIN_BUILD_FAILED'
        stage(a, 'binutils', lambda: configure_make(common['binutils'], build / 'binutils',
              ['--target=' + TARGET, '--prefix=' + str(prefix), '--disable-multilib',
               '--enable-plugins', '--disable-werror', '--disable-nls', '--disable-gdb',
               '--disable-sim', '--disable-libdecnumber', '--disable-readline', *arch_args],
              [[], ['install']], log, env), [prefix / 'bin' / (TARGET + '-as'), prefix / 'bin' / (TARGET + '-ld')])
        stage(a, 'initial-gcc', lambda: configure_make(src, build / 'initial-gcc',
              [*gcc_args, '--disable-tls', 'CFLAGS_FOR_TARGET=-Os -mcmodel=medlow',
               'CXXFLAGS_FOR_TARGET=-Os -mcmodel=medlow'],
              [['all-gcc'], ['install-gcc']], log, env), [build / 'initial-gcc/gcc/xgcc'])
        stage(a, 'newlib', lambda: configure_make(common['newlib'], build / 'newlib',
              ['--target=' + TARGET, '--prefix=' + str(prefix), '--disable-multilib',
               '--enable-newlib-io-long-double', '--enable-newlib-io-long-long',
               '--enable-newlib-io-c99-formats', '--enable-newlib-register-fini',
               'CFLAGS_FOR_TARGET=-O2 -D_POSIX_MODE -ffunction-sections -fdata-sections -mcmodel=medlow -march=' + ARCH + ' -mabi=' + ABI],
              [[], ['install']], log, env), [prefix / TARGET / 'lib/libc.a', prefix / TARGET / 'lib/crt0.o'])

        def final_gcc():
            configure_make(src, build / 'final-gcc', [*gcc_args, '--enable-tls',
                '--with-native-system-header-dir=/include',
                'CFLAGS_FOR_TARGET=-Os -mcmodel=medlow', 'CXXFLAGS_FOR_TARGET=-Os -mcmodel=medlow'],
                [[], ['install']], log, env)
            # Record all installed tools/runtime files, not just the GCC driver.
            a['toolchain_tree_sha256'] = source_tree_hash(prefix)

        stage(a, 'toolchain', final_gcc, [cc, cxx])
        if source_tree_hash(prefix) != a.get('toolchain_tree_sha256'):
            raise Stop('Installed toolchain contents changed; refusing unsafe resume')
        actual = capture([cc, '-dumpfullversion'])
        if actual != version or capture([cc, '-dumpmachine']) != TARGET:
            raise Stop('Built compiler version/target mismatch: ' + actual)
        checked([cc, '-v'], build, log / 'compiler-version.log', env)
        checked([cc, '-print-multi-lib'], build, log / 'compiler-multilib.log', env)
        phase = 'PK_BUILD_FAILED'
        pk_build = build / 'pk'
        def build_pk():
            pk_env = dict(env, CC=str(cc) + ' -march=' + ARCH + ' -mabi=' + ABI,
                          CXX=str(cxx), AR=str(prefix / 'bin' / (TARGET + '-ar')),
                          RANLIB=str(prefix / 'bin' / (TARGET + '-ranlib')),
                          READELF=str(prefix / 'bin' / (TARGET + '-readelf')),
                          OBJCOPY=str(prefix / 'bin' / (TARGET + '-objcopy')))
            configure_make(common['pk'], pk_build,
                           ['--host=' + TARGET, '--prefix=' + str(build / 'pk-install'),
                            '--with-arch=' + ARCH, '--with-abi=' + ABI], [['pk']], log, pk_env)
        stage(a, 'pk', build_pk, [pk_build / 'pk'])
        phase = 'STUB_BUILD_FAILED'
        stub_binary = build / 'stub.elf'
        stage(a, 'stub', lambda: checked([cc, '-march=' + ARCH, '-mabi=' + ABI, '-Os', '--static',
              '-Wl,-Map=' + str(build / 'stub.map'), STUB, '-o', stub_binary], build, log / 'stub-build.log', env),
              [stub_binary, build / 'stub.map'])
        for label, binary in (('pk', pk_build / 'pk'), ('stub', stub_binary)):
            ensure_elf(binary, 243)
            checked([prefix / 'bin' / (TARGET + '-readelf'), '-h', '-l', '-A', binary],
                    build, log / (label + '-elf.log'), env)
            checked([prefix / 'bin' / (TARGET + '-objdump'), '-d', binary],
                    build, log / (label + '-disassembly.log'), env)
        a.update(pk=str(pk_build / 'pk'), stub=str(stub_binary), compiler=str(cc))
        persist()
        result = boom_test([pk_build / 'pk', stub_binary], directory(log / 'simulation'), LIMIT)
        a.update(classification=result['classification'], reason='exit {}; elapsed {:.3f}s; pass marker {}'.format(
                 result['returncode'], result['duration_seconds'], result['pass_marker']), execution=result)
        if result['classification'] in ('BOOM_CRASH', 'SIMULATOR_START_FAILED', 'AMBIGUOUS_EXECUTION'):
            a['needs_review'] = True
    except StageFailed as e:
        a.update(classification=phase, reason=str(e))
    a.update(finished=True, ended=now(), active_duration_seconds=time.monotonic() - started)
    persist()
    save(log / 'attempt-result.json', a)
    next_index = VERSIONS.index(version) + 1
    next_version = VERSIONS[next_index] if next_index < len(VERSIONS) else 'none — range exhausted'
    say('GCC {} | {} | {}\nDuration this invocation: {:.1f}s\nComplete attempt logs: {}\nNext: {}'.format(
        version, a['classification'], a['reason'], a['active_duration_seconds'], a['log'],
        'STOP' if a['classification'] == 'SUCCESS' or a.get('needs_review') else next_version))
    CURRENT = None
    return a


def success(a):
    r = a['execution']
    banner('YAY — SUCCESS!\nCompatible GCC version found: ' + a['version'])
    say('Compiler: ' + a['compiler'])
    say(capture([a['compiler'], '--version']))
    say('Target: {}; ISA: {}; ABI: {}; runtime: Newlib; multilib: disabled'.format(TARGET, ARCH, ABI))
    say('PK: {}\nStub: {}\nInvocation: {}'.format(a['pk'], a['stub'], shlex.join(r['executed'])))
    say('BOOM exit status: {}; elapsed {:.3f}s < 300s; BOOM pass marker present.'.format(
        r['returncode'], r['duration_seconds']))
    say('No trap-loop detector was used. Successful completion satisfies the approved working assumption.')
    say('Logs: {}\nRetained toolchain: {}\nNo older GCC release will be tested.'.format(a['log'], a['prefix']))


def self_test():
    cases = [(0, 1, False, True, False, 'SUCCESS'),
             (0, 300, False, True, False, 'BOOM_TIMEOUT'),
             (137, 299, True, True, False, 'BOOM_TIMEOUT'),
             (139, 1, False, False, False, 'BOOM_CRASH'),
             (127, 1, False, False, False, 'SIMULATOR_START_FAILED'),
             (0, 1, False, False, False, 'AMBIGUOUS_EXECUTION'),
             (1, 1, False, False, True, 'EXECUTION_FAILED'),
             (0, 1, False, True, True, 'AMBIGUOUS_EXECUTION')]
    for rc, elapsed, timeout, passed, failed, expected in cases:
        assert classify(rc, elapsed, 300, timeout, passed, failed) == expected
    assert PASS_PATTERN.search(b'*** PASSED *** Completed after 123 cycles\n')
    assert not PASS_PATTERN.search(b'wrapper says PASSED\n')
    assert BAD_PATTERN.search(b'*** FAILED *** via dtm (code = 1)')
    # Exercise real checkpoint control flow using an existing file as the
    # artifact, while replacing persistence and logging with in-memory stubs.
    from unittest.mock import patch
    artifact = Path(sys.argv[1]).resolve()
    attempt = dict(version='test')
    actions = []
    with patch.dict(globals(), persist=lambda: None, say=lambda message: None):
        stage(attempt, 'example', lambda: actions.append('built'), [artifact])
        stage(attempt, 'example', lambda: actions.append('unexpected rebuild'), [artifact])
        assert actions == ['built'] and attempt['stages']['example']['complete']
        with patch.dict(globals(), digest=lambda path: 'changed'):
            try:
                stage(attempt, 'example', lambda: None, [artifact])
                raise AssertionError('Changed artifact was accepted')
            except Stop:
                pass
        def fail_stage():
            raise StageFailed('simulated interruption')
        try:
            stage(attempt, 'interrupted', fail_stage, [artifact])
        except StageFailed:
            pass
        assert not attempt['stages']['interrupted']['complete']
        stage(attempt, 'interrupted', lambda: actions.append('resumed'), [artifact])
        assert attempt['stages']['interrupted']['complete'] and actions[-1] == 'resumed'
    try:
        contained('/local/scratch/jencks.5/forbidden-output')
        raise AssertionError('External output path was accepted')
    except Stop:
        pass
    print('PASS: 11 completion checks, 4 checkpoint checks, and write-boundary rejection. No files created.')


def main():
    global SESSION, SESSION_LOG
    parser = argparse.ArgumentParser(prog='test-gcc-compatibility.sh', description='Server-only isolated GCC/PK compatibility experiment. '
        'No system installation or writes outside the fixed experiment directory. '
        'Running --run or --preflight-only creates normal experiment logs, probes, checkpoints, '
        'and (with --run) retained sources/builds/toolchains under that directory.')
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--run', action='store_true', help='preflight, then autonomous version iteration')
    mode.add_argument('--preflight-only', action='store_true', help='checks and MicroBench only; no source downloads/builds')
    mode.add_argument('--self-test', action='store_true', help='read-only in-memory classifier checks')
    args = parser.parse_args(sys.argv[2:])
    if args.self_test:
        self_test()
        return 0
    if not PROJECT.is_dir() or PROJECT.resolve() != PROJECT or ROOT.resolve() != ROOT or not ROOT.is_dir():
        raise Stop('Run on the server with the existing nonsymlink project/experiment paths: ' + str(ROOT))
    # Reject pre-existing links escaping the write boundary before creating logs.
    for p in ROOT.rglob('*'):
        if p.is_symlink():
            contained(p)
    if not os.access(ROOT, os.W_OK):
        raise Stop('Experiment directory is not writable; permissions will not be changed')
    directory(ROOT / 'logs')
    import fcntl
    lock = open(contained(ROOT / 'logs/experiment.lock'), 'a')
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        raise Stop('Another experiment process holds the lock')
    session_id = dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%S') + '-' + str(os.getpid())
    SESSION = directory(ROOT / 'logs' / ('preflight-' + session_id))
    SESSION_LOG = SESSION / 'preflight.log'
    temp = directory(ROOT / 'tmp' / session_id)
    ENV.update(TMPDIR=str(temp), TMP=str(temp), TEMP=str(temp),
               HOME=str(directory(temp / 'home')), XDG_CACHE_HOME=str(directory(temp / 'cache')))
    for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
        signal.signal(sig, interrupted)
    preflight()
    if args.preflight_only:
        say('Preflight-only complete. GCC compatibility testing was NOT started.')
        return 0
    for name in ('sources', 'builds', 'toolchains'):
        directory(ROOT / name)
    persist()
    for prior in STATE['attempts'].values():
        if prior.get('needs_review'):
            raise Stop('Retained {} needs human review: {}'.format(prior['version'], prior['classification']))
    # PK snapshot uses Git archive of the verified clean source, never configure in place.
    pk_copy = ROOT / 'sources' / ('pk-' + PK_REV)
    pk_marker = ROOT / 'sources' / ('pk-' + PK_REV + '.json')
    if not pk_marker.exists():
        archive = ROOT / 'sources' / ('pk-' + PK_REV + '.tar')
        checked(['git', '-c', 'safe.directory=' + str(PK_SOURCE), '-C', PK_SOURCE,
                 'archive', '--format=tar', '--output=' + str(archive), PK_REV], SESSION, SESSION / 'pk-snapshot.log')
        extract(archive, pk_copy)
        save(pk_marker, dict(revision=PK_REV, tree_sha256=source_tree_hash(pk_copy)))
    elif source_tree_hash(pk_copy) != read_json(pk_marker)['tree_sha256']:
        raise Stop('PK snapshot changed; refusing resume')
    common = {'pk': pk_copy}
    for name, (url, rev) in COMPANIONS.items():
        try:
            common[name] = companion(name, url, rev)
        except StageFailed as e:
            raise Stop('COMPANION_SOURCE_FAILED: ' + str(e))
    for version in VERSIONS:
        a = attempt_version(version, common)
        if a['classification'] == 'SUCCESS':
            success(a)
            return 0
        if a.get('needs_review'):
            raise Stop('Execution needs review; older versions were not started. See ' + a['log'])
    banner('Approved GCC range exhausted — no successful configuration found')
    say('GCC version | Result | Reason | Log')
    for version in VERSIONS:
        a = STATE['attempts'][version]
        say('{} | {} | {} | {}'.format(version, a['classification'], a['reason'], a['log']))
    return 1


try:
    sys.exit(main())
except (Stop, StageFailed, OSError, sp.SubprocessError, ValueError) as exc:
    kill_active()
    message = str(exc)
    try:
        if CURRENT is not None:
            CURRENT.update(interrupted_at=now(), interruption=message)
            persist()
        if SESSION:
            save(SESSION / 'stopped.json', dict(time=now(), reason=message))
        say('[STOP] ' + message)
        if SESSION_LOG:
            say('Session log: ' + str(SESSION_LOG))
    except OSError:
        print('[STOP] ' + message, file=sys.stderr)
        print('Could not save final metadata; existing logs/artifacts retained.', file=sys.stderr)
    sys.exit(2)
PYTHON
