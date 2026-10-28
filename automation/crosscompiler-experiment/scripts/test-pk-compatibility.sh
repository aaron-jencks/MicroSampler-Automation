#!/usr/bin/env bash
# PK x GCC matrix. Bash orchestration, jq metadata, and a streaming Python
# detector for the PC/exception trace already emitted by the BOOM binary.
# All old artifacts are read-only. New output is confined to pk-compatibility/.
# Run on the server with --preflight-only, then --run. Never invoke with sudo.
set -Eeuo pipefail
shopt -s inherit_errexit

PROJECT=/local/scratch/vologzhanin.2/MicroSampler-Automation
EXP=$PROJECT/automation/crosscompiler-experiment
ROOT=$EXP/pk-compatibility
META=$ROOT/metadata SOURCES=$ROOT/sources BUILDS=$ROOT/builds
PREFIXES=$ROOT/toolchains LOGS=$ROOT/logs
STATE=$META/state.json INVENTORY=$META/inventory.json
BOOM=$PROJECT/BOOM_simulator STUB=$EXP/stub.c
MICRO=$PROJECT/apps/microbench/ct_ccopy/0xaa/ct_ccopy
AUTHORITATIVE_PK=/local/scratch/jencks.5/workspace/src/riscv-pk
BOOM_SHA=0ecc28d64150d08f9314f9dd1f69dea858e738e6aa8402b2e61186e691ea6d1c
STUB_SHA=f92a4650afd1781064999a6d5f0412923b07c65f3a22c94f65f449899c65f81e
MICRO_SHA=f1934cd5e7df1c31144c1f113fe890e0607e07b517e3cdfa29acbc951c2d40cb
VERSIONS=(16.2.0 15.3.0 14.4.0 13.5.0 12.5.0)
PKS=(
    abadfdc507d5a75b6272dc360e70a80a510c758a
    1a52fa44aba49307137ea2ad5263613da33a877b
    1f5bcbe4d0ee32ff3bfc3b001a2121628a29ae65
    4f3debe4d04f56d31089c1c716a27e2d5245e9a1
    e8e6b3aaee44d43b48164fbd377864c3a682dbd3
    a3e4ac61d2b1ff37a22b9193b85d3b94273e80cb
)
RELEASES=(
    '1.14.0' '1.13.0' '1.12.3' '1.12.2,1.12.1,1.12.0'
    '1.11.0,1.10.0,1.9.1,1.9.0,1.8.1,1.8.0,1.7.1,1.7.0,1.6.2,1.6.1,1.6.0,1.5.0'
    '1.4.0'
)
# Official gitlinks verified from GitHub release trees on 2026-09-20.
# Path for every row: toolchains/riscv-tools/riscv-pk (mode 160000).
release_rows() {
    cat <<'ROWS'
1.14.0 0acc1e1de2d3284bcd4d876956932a013ffe1949 abadfdc507d5a75b6272dc360e70a80a510c758a
1.13.0 69eba860a352343e4ac6b6df0f3638a79a86ec78 1a52fa44aba49307137ea2ad5263613da33a877b
1.12.3 6f0c448ec2e529faf507352a2427a3527e1ca186 1f5bcbe4d0ee32ff3bfc3b001a2121628a29ae65
1.12.2 dccedae00f4dd626425f8f89c93f55ee11e4193e 4f3debe4d04f56d31089c1c716a27e2d5245e9a1
1.12.1 5929221722dff4f9cf2132f0fda42dcb1cab3229 4f3debe4d04f56d31089c1c716a27e2d5245e9a1
1.12.0 404c8d361de98a98967f5d7a9bf51cbe8434d4c9 4f3debe4d04f56d31089c1c716a27e2d5245e9a1
1.11.0 ac58f38d77c99e9d1cafa64dfd6d4b00bdcd43e1 e8e6b3aaee44d43b48164fbd377864c3a682dbd3
1.10.0 b7644b2455cc4bae190e811a5d8085f3aad85b87 e8e6b3aaee44d43b48164fbd377864c3a682dbd3
1.9.1 968b207ccade6f61d6f9bb2e19a54781d4a96f26 e8e6b3aaee44d43b48164fbd377864c3a682dbd3
1.9.0 7475bfb1a05802ac4dfc3990a889f93164b8d798 e8e6b3aaee44d43b48164fbd377864c3a682dbd3
1.8.1 004297b6a8c01be1b2110c4cf4f9393ae1ff8805 e8e6b3aaee44d43b48164fbd377864c3a682dbd3
1.8.0 2d03d10837fc1a7569d10ae2c91c8132c7fee77d e8e6b3aaee44d43b48164fbd377864c3a682dbd3
1.7.1 992664220d95edf610475031fd8a82d0cd743f7f e8e6b3aaee44d43b48164fbd377864c3a682dbd3
1.7.0 4a1189693d8134973010ac91abf7f085bbf0b49d e8e6b3aaee44d43b48164fbd377864c3a682dbd3
1.6.2 481398b910fa95ec88dd578c67ba358a4d83129d e8e6b3aaee44d43b48164fbd377864c3a682dbd3
1.6.1 83b7b94fef70fa808a5fb75eff2dc78907af6014 e8e6b3aaee44d43b48164fbd377864c3a682dbd3
1.6.0 dcf8da4b2d3a4deead95462fce36a6db5693ed45 e8e6b3aaee44d43b48164fbd377864c3a682dbd3
1.5.0 b5d013190d637e634113cb5179f8c8885df1945a e8e6b3aaee44d43b48164fbd377864c3a682dbd3
1.4.0 58076cfb260a3be502d6d1c25b577da39277a7fc a3e4ac61d2b1ff37a22b9193b85d3b94273e80cb
ROWS
}
TARGET=riscv64-unknown-elf ARCH=rv64gc_zifencei ABI=lp64d
JOBS=8 SEED=1 LIMIT=1800 MICRO_LIMIT=60
BIN_REV=49d4d3fafa4ec4ff5a3460d91d5b1ed5286487db
NEW_REV=5e5e51f1dc56a99eb4648c28e00d73b6ea44a8b0
PK_URL=https://github.com/riscv-software-src/riscv-pk.git
BIN_URL=https://sourceware.org/git/binutils-gdb.git
NEW_URL=https://sourceware.org/git/newlib-cygwin.git
HOST_PATH=/usr/local/bin:/usr/bin:/bin
RECIPE=pk-matrix-v3-timeout1800-traploop
TRAP_DETECTOR=$EXP/scripts/detect-boom-trap-loop.py
TRAP_EVIDENCE=
ACTIVE= ACTIVE_MONITOR= SESSION= SESSION_LOG= ENV_ID= RUN_JSON= CLASS= SELECTED_SOURCE=
TC_JSON= STUB_JSON= PK_JSON= PAIR_LOG= KEY= CURRENT_PK= CURRENT_GCC= CURRENT_RELEASES=
BUILD_CS=0 TOTAL_START=0
SELF=${BASH_SOURCE[0]}

usage() {
    cat <<'HELP'
Usage: bash test-pk-compatibility.sh MODE
  --help             No writes; display usage.
  --self-test        No writes; test classification and approved mapping.
  --preflight-only   Inventory/validate artifacts, dependencies, resources;
                     run MicroBench once. No PK/GCC source acquisition/builds.
  --run              Same preflight, then the approved six PK x five GCC matrix.
Requires Bash >=4.4, jq, GNU tools, setsid/flock and existing build dependencies.
Uses seed 1, +verbose, -j8, rv64gc_zifencei/lp64d, 1800-second BOOM timeout.
Live trap-loop detection requires four matching valid cause-1 exceptions, three
equal cycle/retirement periods, and three identical committed-PC sequences.
Trap evidence fails and terminates a pair early. Otherwise, exit 0 + BOOM pass
marker + elapsed <1800s is success.
Stops the entire search immediately on success. No sudo, source patches,
changes to existing toolchains, or deletion of previous evidence.
Writes only to:
  /local/scratch/vologzhanin.2/MicroSampler-Automation/automation/crosscompiler-experiment/pk-compatibility/
State: metadata/state.json. Concise results: logs/results.tsv.
Exit: 0 success/preflight passed; 1 matrix exhausted; 2 infrastructure/review stop.
HELP
}
now() { date -u +%FT%TZ; }
ticks() { local up rest; read -r up rest < /proc/uptime; printf '%s\n' "$((10#${up/./}))"; }
hash() { sha256sum -- "$1" | cut -d ' ' -f1; }
say() { printf '%s\n' "$*"; if [[ -n $SESSION_LOG ]]; then printf '%s\n' "$*" >> "$SESSION_LOG"; fi; }
cleanup() {
    if [[ -n $ACTIVE ]]; then
        kill -KILL -- "-$ACTIVE" 2>/dev/null || :
        wait "$ACTIVE" 2>/dev/null || :
        ACTIVE=
    fi
    if [[ -n $ACTIVE_MONITOR ]]; then
        kill -TERM "$ACTIVE_MONITOR" 2>/dev/null || :
        wait "$ACTIVE_MONITOR" 2>/dev/null || :
        ACTIVE_MONITOR=
    fi
}
die() { trap - ERR; say "[STOP] $*" >&2; cleanup; exit 2; }
trap cleanup EXIT
trap 'die "Interrupted; artifacts retained, unfinished pair is resumable."' INT TERM HUP
trap 'die "Command failed at line $LINENO. See session/build logs; prior artifacts preserved."' ERR
contained() {
    local p; p=$(realpath -m -- "$1")
    [[ $p == "$ROOT" || $p == "$ROOT/"* ]] || die "Refusing write outside matrix: $1"
}
directory() { contained "$1"; mkdir -p -- "$1"; }
save_json() {
    local path=$1 data
    contained "$path"; contained "$path.pending"
    data=$(cat)
    jq -e 'type=="object" or type=="array"' >/dev/null <<< "$data" || die "Invalid JSON for $path"
    printf '%s\n' "$data" > "$path.pending"
    mv -- "$path.pending" "$path"
}
state_update() { local filter=$1; shift; jq "$@" "$filter" "$STATE" | save_json "$STATE"; }
# Never source/eval checkpoint data. Artifact paths must stay within EXP.
old_path() { [[ $(realpath -m -- "$1") == "$EXP/"* ]]; }
elf_ok() {
    local hdr
    hdr=$(readelf -h "$1" 2>/dev/null) || return 1
    [[ $hdr == *ELF64* && $hdr == *little\ endian* && $hdr == *"$2"* ]]
}
space() {
    local min=${1:-5368709120} free inodes
    free=$(df -PB1 "$ROOT" | awk 'NR==2 {print $4}')
    inodes=$(df -Pi "$ROOT" | awk 'NR==2 {print $4}')
    (( free >= min && inodes >= 1000 )) || die "INSUFFICIENT_DISK_SPACE: $free bytes, $inodes inodes. Nothing deleted."
}
# Match sorted(Path.rglob('*')) from the original runner: tuple-of-components
# order, not a flat lexical sort (foo/bar sorts before foo.c in pathlib).
legacy_stream() {
    local root=$1 dir=$2 p rel target digest
    while IFS= read -r -d '' p; do
        rel=${p#"$root/"}
        if [[ -L $p ]]; then
            target=$(readlink -- "$p") || return 1
            printf 'L%s%s' "$rel" "$target"
        elif [[ -d $p ]]; then
            legacy_stream "$root" "$p" || return 1
        elif [[ -f $p ]]; then
            digest=$(hash "$p") || return 1
            printf 'F%s%s' "$rel" "$digest"
        fi
    done < <(find "$dir" -mindepth 1 -maxdepth 1 -print0 | LC_ALL=C sort -z)
}
legacy_hash() { legacy_stream "$1" "$1" | sha256sum | cut -d ' ' -f1; }
bash_tree_hash() {
    (cd "$1"
     find . -type f -print0 | sort -z | xargs -0 -r sha256sum
     find . -printf '%y %m %p -> %l\n' | sort) | sha256sum | cut -d ' ' -f1
}
artifact_check() {
    local json=$1 rows p sha
    jq -e 'type=="object" and length>0 and all(.[]; type=="string" and test("^[0-9a-f]{64}$"))' >/dev/null <<< "$json" || return 1
    rows=$(jq -r 'to_entries[]|[.key,.value]|@tsv' <<< "$json") || return 1
    while IFS=$'\t' read -r p sha; do
        old_path "$p" && [[ -f $p && $(hash "$p") == "$sha" ]] || return 1
    done <<< "$rows"
}
classify() {
    local rc=$1 cs=$2 seconds=$3 timed=$4 passed=$5 failed=$6 traploop=$7
    if (( traploop )); then CLASS=TRAP_LOOP_DETECTED
    elif (( timed || cs >= seconds*100 )); then CLASS=BOOM_TIMEOUT
    elif (( rc == 125 || rc == 126 || rc == 127 )); then CLASS=SIMULATOR_START_FAILED
    elif (( rc >= 128 )); then CLASS=BOOM_CRASH
    elif (( passed && (rc || failed) )); then CLASS=AMBIGUOUS_EXECUTION
    elif (( rc || failed )); then CLASS=EXECUTION_FAILED
    elif (( passed )); then CLASS=SUCCESS
    else CLASS=AMBIGUOUS_EXECUTION; fi
}
self_test() {
    local rc cs timed passed failed traploop expected n=0
    while read -r rc cs timed passed failed traploop expected; do
        classify "$rc" "$cs" "$LIMIT" "$timed" "$passed" "$failed" "$traploop"
        [[ $CLASS == "$expected" ]] || die "Expected $expected, got $CLASS"
        n=$((n+1))
    done <<'CASES'
0 1 0 1 0 0 SUCCESS
0 180000 0 1 0 0 BOOM_TIMEOUT
137 179999 1 1 0 0 BOOM_TIMEOUT
139 1 0 0 0 0 BOOM_CRASH
127 1 0 0 0 0 SIMULATOR_START_FAILED
0 1 0 0 0 0 AMBIGUOUS_EXECUTION
1 1 0 0 1 0 EXECUTION_FAILED
0 1 0 1 1 0 AMBIGUOUS_EXECUTION
1 1 0 1 0 0 AMBIGUOUS_EXECUTION
137 1 0 0 0 0 BOOM_CRASH
137 1 0 0 0 1 TRAP_LOOP_DETECTED
CASES
    [[ $(release_rows | wc -l) == 19 && $(release_rows | awk '{print $3}' | sort -u | wc -l) == 6 ]] || die 'Mapping count mismatch'
    printf 'PASS: %s classification checks; 19 releases / 6 PK revisions; no writes.\n' "$n"
}
# All external builds/simulations get their own process group. GNU timeout and
# a monotonic parent watchdog both enforce the deadline. Output never tees to tty.
run() {
    local cwd=$1 out=$2 err=$3 limit=$4; shift 4
    local start finish next rc=0 timed=0 argv begun cmdline
    local monitor_rc=0 monitor_failed=0 traploop=0 evidence=${TRAP_EVIDENCE:-}
    local -a cmd=("$@")
    contained "$out"; contained "$err"
    [[ -d $cwd ]] || die "Missing command directory: $cwd"
    if (( limit )); then cmd=(timeout --verbose --signal=KILL "${limit}s" "${cmd[@]}"); fi
    argv=$(jq -cn --args '$ARGS.positional' -- "${cmd[@]}")
    begun=$(now); start=$(ticks); next=$((start+1000))
    if [[ $out == "$err" ]]; then
        printf '\n[%s] ' "$begun" >> "$out"; printf '%q ' "${cmd[@]}" >> "$out"; printf '\n' >> "$out"
        (cd "$cwd"; exec setsid -- "${cmd[@]}" </dev/null >> "$out" 2>&1) &
    else
        (cd "$cwd"; exec setsid -- "${cmd[@]}" </dev/null > "$out" 2> "$err") &
    fi
    ACTIVE=$!
    if [[ -n $evidence ]]; then
        contained "$evidence"; contained "$evidence.pending"; contained "$evidence.detector.stderr"
        rm -f -- "$evidence" "$evidence.pending" "$evidence.detector.stderr"
        python3 "$TRAP_DETECTOR" --log "$err" --producer-pid "$ACTIVE" --evidence "$evidence" \
            2> "$evidence.detector.stderr" &
        ACTIVE_MONITOR=$!
    fi
    while kill -0 "$ACTIVE" 2>/dev/null; do
        if [[ -n $evidence && -f $evidence ]]; then
            traploop=1
            kill -KILL -- "-$ACTIVE" 2>/dev/null || :
            break
        fi
        if [[ -n $ACTIVE_MONITOR ]] && ! kill -0 "$ACTIVE_MONITOR" 2>/dev/null; then
            wait "$ACTIVE_MONITOR" 2>/dev/null || monitor_rc=$?
            ACTIVE_MONITOR=
            if (( monitor_rc == 10 )) && [[ -f $evidence ]]; then
                traploop=1
                kill -KILL -- "-$ACTIVE" 2>/dev/null || :
                break
            elif (( monitor_rc == 0 )); then
                # The detector observed the producer exit and drained the log;
                # the shell may still briefly report the unreaped job as alive.
                continue
            else
                monitor_failed=1
                kill -KILL -- "-$ACTIVE" 2>/dev/null || :
                break
            fi
        fi
        finish=$(ticks)
        if (( limit && finish-start >= limit*100 )); then
            timed=1; kill -KILL -- "-$ACTIVE" 2>/dev/null || :; break
        fi
        if (( finish >= next )); then space; next=$((finish+1000)); fi
        sleep 0.1
    done
    wait "$ACTIVE" 2>/dev/null || rc=$?
    ACTIVE=
    # Let the live follower consume the simulator's final buffered trace, then
    # stop it. A complete evidence file is authoritative even if its exit status
    # races with this cleanup.
    if [[ -n $ACTIVE_MONITOR ]]; then
        local drain
        for drain in {1..20}; do
            [[ -f $evidence ]] && break
            kill -0 "$ACTIVE_MONITOR" 2>/dev/null || break
            sleep 0.1
        done
        if kill -0 "$ACTIVE_MONITOR" 2>/dev/null; then
            kill -TERM "$ACTIVE_MONITOR" 2>/dev/null || :
        fi
        monitor_rc=0
        wait "$ACTIVE_MONITOR" 2>/dev/null || monitor_rc=$?
        ACTIVE_MONITOR=
        if (( monitor_rc != 0 && monitor_rc != 10 && monitor_rc != 143 )); then monitor_failed=1; fi
    fi
    if [[ -n $evidence && -f $evidence ]]; then traploop=1; fi
    finish=$(ticks)
    if (( rc == 124 )); then timed=1; fi
    if (( limit && rc == 137 )) && tail -c 16384 "$err" | grep -a 'timeout: sending signal KILL' >/dev/null; then timed=1; fi
    # Use descriptive jq variable names here.  Older jq releases on servers
    # can misparse short names that overlap jq keywords (notably `end`).
    RUN_JSON=$(jq -n --argjson argv "$argv" --arg cwd "$cwd" --arg started_at "$begun" --arg ended_at "$(now)" \
        --arg out "$out" --arg err "$err" --argjson return_code "$rc" --argjson elapsed_cs "$((finish-start))" \
        --argjson was_timed "$timed" --argjson time_limit "$limit" --argjson trap_loop "$traploop" --arg evidence "$evidence" \
        '{executed:$argv,cwd:$cwd,started:$started_at,ended:$ended_at,stdout:$out,stderr:$err,returncode:$return_code,
          duration_seconds:($elapsed_cs/100),timed_out:($was_timed==1),trap_loop_detected:($trap_loop==1),
          trap_loop_evidence:(if $trap_loop==1 then $evidence else null end),
          forced_termination:(($was_timed==1) or ($trap_loop==1)),limit_seconds:$time_limit}')
    (( monitor_failed == 0 )) || die "Trap-loop detector failed; see $evidence.detector.stderr"
    space
}
checked() {
    run "$@"
    [[ $(jq -r .returncode <<< "$RUN_JSON") == 0 ]] || die "Infrastructure/source command failed. See $(jq -r .stderr <<< "$RUN_JSON")"
}
build_run() {
    run "$1" "$2" "$2" 0 "${@:3}"
    BUILD_CS=$((BUILD_CS + $(jq '(.duration_seconds*100)|round' <<< "$RUN_JSON")))
    if [[ $(jq -r .returncode <<< "$RUN_JSON") != 0 ]]; then
        (( $(jq -r .returncode <<< "$RUN_JSON") < 128 )) || die "Build terminated by signal; see $2"
        if tail -c 262144 "$2" | grep -aiE 'No space left|Disk quota exceeded|Cannot allocate memory|out of memory|Killed signal|Permission denied' >/dev/null; then
            die "Build resource/permission error; see $2"
        fi
        return 1
    fi
}
boom_test() {
    local dir=$1 seconds=$2; shift 2
    local passed=0 failed=0 traploop=0 rc cs timed evidence=$dir/trap-loop-evidence.json
    directory "$dir"
    TRAP_EVIDENCE=$evidence
    run "$dir" "$dir/boom.stdout" "$dir/boom.stderr" "$seconds" "$BOOM" -s "$SEED" +verbose "$@"
    TRAP_EVIDENCE=
    if grep -aE '^\*\*\* PASSED \*\*\* Completed after [0-9]+ cycles[[:space:]]*$' "$dir/boom.stdout" "$dir/boom.stderr" >/dev/null; then passed=1; fi
    if grep -aE '\*\*\* FAILED \*\*\*|Assertion failed|%Error|terminate called|Segmentation fault' "$dir/boom.stdout" "$dir/boom.stderr" >/dev/null; then failed=1; fi
    read -r rc cs timed traploop < <(jq -r '[.returncode,(.duration_seconds*100|round),(if .timed_out then 1 else 0 end),(if .trap_loop_detected then 1 else 0 end)]|@tsv' <<< "$RUN_JSON")
    classify "$rc" "$cs" "$seconds" "$timed" "$passed" "$failed" "$traploop"
    RUN_JSON=$(jq --arg result "$CLASS" --argjson passed "$passed" --argjson failed "$failed" \
        --arg oh "$(hash "$dir/boom.stdout")" --arg eh "$(hash "$dir/boom.stderr")" \
        '.+{classification:$result,pass_marker:($passed==1),failure_marker:($failed==1),
        stdout_sha256:$oh,stderr_sha256:$eh,
        pc_loop_analysis:(if .trap_loop_detected then "DETECTED" else "NOT_DETECTED" end)}' <<< "$RUN_JSON")
}

# Reuse validation: full original tree digest + completed-stage artifact hashes,
# exact compiler version/target, ABI/default ISA, binutils and runtime presence.
compiler_ok() {
    local cc=$1 version=$2 prefix=${1%/bin/*} defaults actual
    [[ -x $cc ]] && old_path "$cc" || return 1
    [[ $("$cc" -dumpfullversion) == "$version" && $("$cc" -dumpmachine) == "$TARGET" ]] || return 1
    [[ $("$cc" -print-multi-lib) == '.;' ]] || return 1
    defaults=$("$cc" -Q --help=target) || return 1
    grep -E -- '-mabi=[[:space:]]+lp64d([[:space:]]|$)' >/dev/null <<< "$defaults" || return 1
    grep -E -- '-march=[[:space:]]+rv64imafdc_zicsr_zifencei' >/dev/null <<< "$defaults" || return 1
    for actual in as ld ar ranlib readelf objcopy objdump; do [[ -x $prefix/bin/$TARGET-$actual ]] || return 1; done
    [[ -f $prefix/$TARGET/lib/libc.a && -f $prefix/$TARGET/lib/crt0.o ]] || return 1
}
legacy_identity_ok() {
    jq -e --arg target "$TARGET" --arg arch "$ARCH" --arg abi "$ABI" --arg b "$BIN_REV" --arg n "$NEW_REV" \
        '.identity | .target==$target and .arch==$arch and .abi==$abi and
         .companions.binutils[1]==$b and .companions.newlib[1]==$n' "$1" >/dev/null
}
# Check documented configure options independently of opaque Bash identity.
config_ok() {
    local build=$1 prefix=$2 stage args
    for stage in binutils initial-gcc final-gcc newlib; do
        [[ -f $build/$stage/configure-complete.json ]] || return 1
        args=$(jq -c '.arguments // .args' "$build/$stage/configure-complete.json") || return 1
        jq -e --arg t "--target=$TARGET" --arg p "--prefix=$prefix" \
            'index($t)!=null and index($p)!=null and index("--disable-multilib")!=null' >/dev/null <<< "$args" || return 1
        if [[ $stage != newlib ]]; then
            jq -e --arg a "--with-arch=$ARCH" --arg b "--with-abi=$ABI" \
                'index($a)!=null and index($b)!=null and index("--with-isa-spec=20191213")!=null' >/dev/null <<< "$args" || return 1
        fi
        local src
        src=$(jq -r .source "$build/$stage/configure-complete.json") || return 1
        case $stage in
            binutils) [[ $src == */binutils-$BIN_REV ]] || return 1;;
            newlib) [[ $src == */newlib-$NEW_REV ]] || return 1;;
        esac
    done
}
import_toolchain() {
    local file=$1 version=$2 kind=$3 a cc prefix build expected actual stage art
    [[ -f $file ]] || return 1
    a=$(jq -ce --arg v "$version" '.attempts[$v] | select(.stages.toolchain.complete==true)' "$file") || return 1
    cc=$(jq -r '.compiler // (.prefix+"/bin/riscv64-unknown-elf-gcc")' <<< "$a")
    prefix=$(jq -r .prefix <<< "$a"); build=$(jq -r .build <<< "$a")
    old_path "$prefix" && old_path "$build" || return 1
    config_ok "$build" "$prefix" || return 1
    if [[ $kind == legacy ]]; then legacy_identity_ok "$file" || return 1; fi
    for stage in binutils newlib toolchain; do
        jq -e --arg s "$stage" '.stages[$s].complete==true' >/dev/null <<< "$a" || return 1
        art=$(jq -c --arg s "$stage" '.stages[$s].artifacts' <<< "$a")
        artifact_check "$art" || return 1
    done
    expected=$(jq -r '.toolchain_tree_sha256 // empty' <<< "$a")
    [[ $expected =~ ^[0-9a-f]{64}$ && -d $prefix ]] || return 1
    if [[ $kind == legacy ]]; then actual=$(legacy_hash "$prefix"); else actual=$(bash_tree_hash "$prefix"); fi
    [[ $actual == "$expected" ]] || return 1
    compiler_ok "$cc" "$version" || return 1
    TC_JSON=$(jq -n --arg version "$version" --arg cc "$cc" --arg prefix "$prefix" --arg tree "$actual" \
        --arg kind "$kind" --arg state "$file" --argjson previous "$a" \
        '{status:"REUSABLE_EXISTING_TOOLCHAIN",version:$version,compiler:$cc,prefix:$prefix,
          tree_sha256:$tree,tree_kind:$kind,origin:$state,previous:$previous}')
}
# Own fallback manifests use the same legacy-compatible digest for portability.
import_own_toolchain() {
    local version=$1 manifest=$META/gcc-$1.json cc prefix
    [[ -f $manifest ]] || return 1
    jq -e '.complete==true' "$manifest" >/dev/null || return 1
    cc=$(jq -r .compiler "$manifest"); prefix=$(jq -r .prefix "$manifest")
    compiler_ok "$cc" "$version" || return 1
    [[ $(legacy_hash "$prefix") == "$(jq -r .tree_sha256 "$manifest")" ]] || die "Own fallback toolchain changed: $prefix"
    TC_JSON=$(cat "$manifest")
}
inventory() {
    local version all='{}' status
    for version in "${VERSIONS[@]}"; do
        say "[CHECK] Existing GCC $version: provenance and installed-file hashes"
        TC_JSON=
        if import_toolchain "$EXP/logs/state.json" "$version" legacy; then :
        elif import_toolchain "$EXP/logs/bash/state.json" "$version" bash; then :
        elif import_own_toolchain "$version"; then :
        else
            TC_JSON=$(jq -n --arg v "$version" '{version:$v,status:"NEEDS_BUILD",reason:"No complete usable toolchain with matching provenance"}')
        fi
        all=$(jq --arg v "$version" --argjson t "$TC_JSON" '.+{($v):$t}' <<< "$all")
        say "[GCC] $version: $(jq -r .status <<< "$TC_JSON")"
    done
    printf '%s\n' "$all" | save_json "$INVENTORY"
}
resources() {
    local cpus memory cg quota period maximum used cap
    space 21474836480
    cpus=$(nproc); memory=$(awk '/^MemAvailable:/ {printf "%.0f",$2*1024}' /proc/meminfo)
    cg=$(awk -F: '$1==0 {print $3}' /proc/self/cgroup)
    if [[ -n $cg ]]; then
        cg=/sys/fs/cgroup$cg
        while [[ $cg == /sys/fs/cgroup* ]]; do
            if [[ -r $cg/cpu.max ]]; then
                read -r quota period < "$cg/cpu.max"
                if [[ $quota != max ]]; then cap=$((quota/period)); ((cap>0)) || cap=1; ((cap>=cpus)) || cpus=$cap; fi
            fi
            if [[ -r $cg/memory.max ]]; then
                read -r maximum < "$cg/memory.max"
                if [[ $maximum != max ]]; then
                    read -r used < "$cg/memory.current"; cap=$((maximum-used)); ((cap>=memory)) || memory=$cap
                fi
            fi
            cg=${cg%/*}
        done
    fi
    (( cpus >= JOBS && memory >= JOBS*1073741824 )) || die 'Insufficient resources for approved eight build jobs'
    say "[RESOURCES] CPUs $cpus; available memory $memory bytes. Up to ~225 GiB of traces may accumulate; quotas are not measured."
}
preflight() {
    local lib libs fingerprint rows mapping sha version need_network=0
    [[ $(hash "$BOOM") == "$BOOM_SHA" && $(hash "$STUB") == "$STUB_SHA" && $(hash "$MICRO") == "$MICRO_SHA" ]] || die 'Fixed BOOM, stub or MicroBench identity changed'
    [[ -r $TRAP_DETECTOR ]] || die "Missing trap-loop detector: $TRAP_DETECTOR"
    elf_ok "$BOOM" X86-64 && elf_ok "$MICRO" RISC-V || die 'Invalid baseline ELF'
    resources
    # Header/link checks, using the same native probe as the first experiment.
    cat > "$TMPDIR/probe.cc" <<'CPP'
#include <gmp.h>
#include <mpfr.h>
#include <mpc.h>
#include <zlib.h>
int main(){mpz_t z;mpz_init(z);mpz_clear(z);mpfr_t f;mpfr_init2(f,53);mpfr_clear(f);mpc_t c;mpc_init2(c,53);mpc_clear(c);return zlibVersion()?0:1;}
CPP
    checked "$TMPDIR" "$SESSION/preflight.log" "$SESSION/preflight.log" 0 g++ probe.cc -o probe -lmpc -lmpfr -lgmp -lz
    checked "$TMPDIR" "$SESSION/preflight.log" "$SESSION/preflight.log" 0 ./probe
    local library_output
    library_output=$({ ldd "$BOOM"; ldd "$TMPDIR/probe"; })
    [[ $library_output != *'not found'* ]] || die 'Unresolved native library'
    libs=$(awk '{for(i=1;i<=NF;i++)if($i~/^\//)print $i}' <<< "$library_output" | sort -u)
    fingerprint=$({
        printf '%s\n' "$RECIPE" "$TARGET" "$ARCH" "$ABI" "$LIMIT" "$SEED" "$BIN_REV" "$NEW_REV"
        sha256sum "$SELF" "$TRAP_DETECTOR" "$BOOM" "$STUB" "$MICRO"
        uname -a; getconf GNU_LIBC_VERSION
        git -C "$PROJECT" rev-parse HEAD
        git -C "$PROJECT" diff --no-ext-diff --binary HEAD -- .
        for lib in gcc g++ make as ld; do sha256sum "$(command -v "$lib")"; done
        while IFS= read -r lib; do sha256sum "$lib"; done <<< "$libs"
        release_rows
    } | sha256sum | cut -d ' ' -f1)
    ENV_ID=$fingerprint
    if [[ -f $STATE ]] && [[ $(jq -r .environment "$STATE") != "$ENV_ID" ]]; then
        local prior_environment archive
        prior_environment=$(jq -r .environment "$STATE")
        [[ $prior_environment =~ ^[0-9a-f]{64}$ ]] || die 'Existing state has an invalid environment identity'
        archive=$META/state.$prior_environment.json
        contained "$archive"
        if [[ -f $archive ]]; then
            cmp -s -- "$STATE" "$archive" || die "Conflicting preserved state: $archive"
        else
            cp -p -- "$STATE" "$archive"
        fi
        jq -n --arg e "$ENV_ID" --arg t "$(now)" --arg previous "$archive" \
            '{schema:1,environment:$e,created:$t,previous_state:$previous,pairs:{}}' | save_json "$STATE"
        say "[STATE] Procedure changed; prior state preserved at $archive"
    elif [[ ! -f $STATE ]]; then
        jq -n --arg e "$ENV_ID" --arg t "$(now)" '{schema:1,environment:$e,created:$t,pairs:{}}' | save_json "$STATE"
    fi
    rows=$(release_rows)
    mapping=$(jq -Rn '[inputs | split(" ") | {release:.[0],chipyard_commit:.[1],pk_commit:.[2],path:"toolchains/riscv-tools/riscv-pk"}]' <<< "$rows")
    printf '%s\n' "$mapping" | save_json "$META/chipyard-pk-map.json"
    inventory
    # Query network only when the matrix has missing source snapshots. No downloads
    # or builds in --preflight-only; local objects can satisfy source acquisition.
    for sha in "${PKS[@]}"; do
        if [[ ! -f $SOURCES/pk/$sha.json ]] && ! pk_object_available "$sha"; then need_network=1; fi
    done
    if (( need_network )); then checked "$SESSION" "$SESSION/preflight.log" "$SESSION/preflight.log" 60 git ls-remote --exit-code "$PK_URL" HEAD; fi
    if jq -e 'any(.[];.status=="NEEDS_BUILD")' "$INVENTORY" >/dev/null; then
        for version in "${VERSIONS[@]}"; do
            [[ $(jq -r --arg v "$version" '.[$v].status' "$INVENTORY") == NEEDS_BUILD ]] || continue
            if [[ ! -f $EXP/sources/gcc-$version.json && ! -f $EXP/sources/bash/gcc-$version.json && ! -f $SOURCES/gcc-$version.json ]]; then
                checked "$SESSION" "$SESSION/preflight.log" "$SESSION/preflight.log" 60 curl --fail --location --head --connect-timeout 15 --max-time 45 "https://gcc.gnu.org/pub/gcc/releases/gcc-$version/gcc-$version.tar.xz"
            fi
        done
    fi
    say '[PREFLIGHT] MicroBench baseline (once; PK is not involved)'
    boom_test "$SESSION" "$MICRO_LIMIT" "$MICRO"
    printf '%s\n' "$RUN_JSON" | save_json "$SESSION/preflight.json"
    [[ $CLASS == SUCCESS ]] || die "BOOM baseline failed independently of PK compatibility: $CLASS"
    say '[PREFLIGHT] PASSED. Live valid-exception/committed-PC trap-loop detector is enabled.'
}

pk_object_available() {
    local sha=$1 repo
    for repo in "$AUTHORITATIVE_PK" "$SOURCES/pk.git"; do
        if [[ -d $repo ]] && git -c safe.directory="$repo" -C "$repo" cat-file -e "$sha^{commit}" 2>/dev/null; then return 0; fi
    done
    return 1
}
# Every source snapshot has a completed tree digest. Interrupted extractions are
# preserved and not adopted. Only exact objects are exported; old trees untouched.
source_verified() {
    [[ -f $1.json && -d $1 ]] || return 1
    [[ $(legacy_hash "$1") == "$(jq -r .tree_sha256 "$1.json")" ]] || die "Source snapshot changed: $1"
}
# Copy verified existing sources once before a fallback build, preventing any
# build-system regeneration from writing into the earlier experiment's tree.
copy_source() {
    local old=$1 dest=$2 revision=$3
    if source_verified "$dest"; then SELECTED_SOURCE=$dest; return; fi
    [[ ! -e $dest ]] || die "Incomplete source copy: $dest"
    directory "${dest%/*}"
    checked "$SOURCES" "$SESSION/preflight.log" "$SESSION/preflight.log" 0 cp -a --no-preserve=ownership -- "$old" "$dest"
    [[ $(legacy_hash "$old") == "$(legacy_hash "$dest")" ]] || die 'Source copy verification failed'
    jq -n --arg r "$revision" --arg tree "$(legacy_hash "$dest")" --arg from "$old" \
        '{revision:$r,tree_sha256:$tree,copied_from:$from}' | save_json "$dest.json"
    SELECTED_SOURCE=$dest
}
extract() {
    local archive=$1 dest=$2 revision=$3 listing link
    [[ ! -e $dest ]] || die "Incomplete/unrecorded source snapshot: $dest; retained for review"
    listing=$(tar -tf "$archive")
    if grep -E '(^/|(^|/)\.\.(/|$))' >/dev/null <<< "$listing"; then die "Unsafe archive names: $archive"; fi
    if tar -tvf "$archive" | awk 'substr($0,1,1)!~/[-dlh]/ {bad=1} END{exit !bad}'; then die "Unsafe archive types: $archive"; fi
    directory "$dest"
    checked "$SOURCES" "$SESSION/preflight.log" "$SESSION/preflight.log" 0 tar -xf "$archive" -C "$dest" --no-same-owner --no-same-permissions
    while IFS= read -r -d '' link; do
        [[ $(realpath -m "$link") == "$dest/"* ]] || die "Escaping source link: $link"
    done < <(find "$dest" -type l -print0)
    jq -n --arg sha "$revision" --arg tree "$(legacy_hash "$dest")" --arg archive "$(hash "$archive")" \
        '{revision:$sha,tree_sha256:$tree,archive_sha256:$archive}' | save_json "$dest.json"
}
git_source() {
    local name=$1 url=$2 sha=$3 dest=$4 repo=$SOURCES/$1.git candidate found=
    if source_verified "$dest"; then
        [[ $(jq -r .revision "$dest.json") == "$sha" ]] || die 'Source revision mismatch'
        SELECTED_SOURCE=$dest; return
    fi
    for candidate in "$AUTHORITATIVE_PK" "$EXP/sources/$name-$sha.git" "$EXP/sources/bash/$name-$sha.git" "$repo"; do
        if [[ -d $candidate ]] && git -c safe.directory="$candidate" -C "$candidate" cat-file -e "$sha^{commit}" 2>/dev/null; then found=$candidate; break; fi
    done
    if [[ -z $found ]]; then
        if [[ ! -d $repo ]]; then checked "$SOURCES" "$SESSION/preflight.log" "$SESSION/preflight.log" 0 git init --bare "$repo"; fi
        checked "$SOURCES" "$SESSION/preflight.log" "$SESSION/preflight.log" 600 git -C "$repo" fetch --depth=1 "$url" "$sha"
        [[ $(git -C "$repo" rev-parse FETCH_HEAD) == "$sha" ]] || die 'Fetched object mismatch'
        checked "$SOURCES" "$SESSION/preflight.log" "$SESSION/preflight.log" 0 git -C "$repo" fsck --no-reflogs
        found=$repo
    fi
    directory "${dest%/*}"
    checked "$SOURCES" "$SESSION/preflight.log" "$SESSION/preflight.log" 0 git -c safe.directory="$found" -C "$found" archive --format=tar --output="$dest.tar" "$sha"
    extract "$dest.tar" "$dest" "$sha"
    SELECTED_SOURCE=$dest
}
reuse_source() {
    local name=$1 revision=$2 base dest expected actual
    for base in "$EXP/sources" "$EXP/sources/bash"; do
        dest=$base/$name
        [[ -d $dest && -f $dest.json ]] || continue
        if [[ $base == "$EXP/sources" ]]; then
            expected=$(jq -r '.tree_sha256 // empty' "$dest.json")
            actual=$(legacy_hash "$dest")
        else
            expected=$(jq -r '.tree // empty' "$dest.json")
            actual=$(bash_tree_hash "$dest")
        fi
        [[ -n $expected && $expected == "$actual" ]] || continue
        # Named SHA is checked against recorded revision when present.
        [[ $(jq -r '.revision // empty' "$dest.json") == "$revision" ]] || continue
        copy_source "$dest" "$SOURCES/$name" "$revision"; return 0
    done
    return 1
}
gcc_source() {
    local version=$1 base dest expected actual archive=$SOURCES/gcc-$1.tar.xz copied=0
    # Official GCC marker from the original runner records URL rather than revision.
    for base in "$EXP/sources" "$EXP/sources/bash"; do
        dest=$base/gcc-$version
        [[ -f $dest.json && -d $dest/gcc-$version ]] || continue
        if [[ $base == "$EXP/sources" ]]; then expected=$(jq -r .tree_sha256 "$dest.json"); actual=$(legacy_hash "$dest")
        else expected=$(jq -r .tree "$dest.json"); actual=$(bash_tree_hash "$dest"); fi
        if [[ $expected == "$actual" ]]; then
            copy_source "$dest" "$SOURCES/gcc-$version" "$version"
            SELECTED_SOURCE=$SOURCES/gcc-$version/gcc-$version; return
        fi
    done
    dest=$SOURCES/gcc-$version
    if source_verified "$dest"; then SELECTED_SOURCE=$dest/gcc-$version; return; fi
    base=https://gcc.gnu.org/pub/gcc/releases/gcc-$version
    # Reuse existing verified download before attempting a network transfer.
    local parent sum
    for parent in "$EXP/sources" "$EXP/sources/bash"; do
        [[ -f $parent/gcc-$version.tar.xz && -f $parent/gcc-$version.sha512.sum ]] || continue
        sum=$(awk -v f="gcc-$version.tar.xz" '$2==f || $2=="*"f {print $1}' "$parent/gcc-$version.sha512.sum")
        if [[ $sum =~ ^[[:xdigit:]]{128}$ ]] && printf '%s  %s\n' "$sum" "$parent/gcc-$version.tar.xz" | sha512sum -c --status; then
            extract "$parent/gcc-$version.tar.xz" "$dest" "$version"; SELECTED_SOURCE=$dest/gcc-$version; return
        fi
    done
    checked "$SOURCES" "$SESSION/preflight.log" "$SESSION/preflight.log" 0 curl --fail --location --proto '=https' --proto-redir '=https' --connect-timeout 20 --retry 2 --speed-limit 1024 --speed-time 120 -o "$SOURCES/gcc-$version.sha512.sum" "$base/sha512.sum"
    expected=$(awk -v f="gcc-$version.tar.xz" '$2==f || $2=="*"f {print $1}' "$SOURCES/gcc-$version.sha512.sum")
    [[ $expected =~ ^[[:xdigit:]]{128}$ ]] || die 'Invalid GCC source checksum'
    checked "$SOURCES" "$SESSION/preflight.log" "$SESSION/preflight.log" 0 curl --fail --location --proto '=https' --proto-redir '=https' --connect-timeout 20 --retry 2 --speed-limit 1024 --speed-time 120 -o "$archive.partial" "$base/gcc-$version.tar.xz"
    printf '%s  %s\n' "$expected" "$archive.partial" | sha512sum -c --status || die 'GCC download checksum failed'
    mv "$archive.partial" "$archive"
    extract "$archive" "$dest" "$version"
    SELECTED_SOURCE=$dest/gcc-$version
}

# New fallback GCC builds alone use these functions. Never execute the old
# experiment scripts or make/install within an existing prefix/source directory.
configure_build() {
    local source=$1 build=$2 mode=$3 log=$4; shift 4
    local identity marker=$build/configure-complete.json
    directory "$build"
    identity=$(jq -cn --arg source "$source" --arg cc "${CC:-}" --args '{source:$source,cc:$cc,args:$ARGS.positional}' -- "$@")
    if [[ -f $marker ]]; then
        [[ $(jq -c . "$marker") == "$identity" && -f $build/Makefile ]] || die 'Configure checkpoint mismatch'
    else
        build_run "$build" "$log" "$source/configure" "$@" || return 1
        printf '%s\n' "$identity" | save_json "$marker"
    fi
    case $mode in
        compiler)
            build_run "$build" "$log" make -j"$JOBS" all-gcc || return 1
            build_run "$build" "$log" make -j"$JOBS" install-gcc || return 1;;
        install)
            build_run "$build" "$log" make -j"$JOBS" || return 1
            build_run "$build" "$log" make -j"$JOBS" install || return 1;;
        pk) build_run "$build" "$log" make -j"$JOBS" pk || return 1;;
    esac
}
fallback_stage() {
    local stage=$1 source=$2 build=$3 mode=$4 artifact=$5; shift 5
    local marker=$build/complete.json
    if [[ -f $marker ]]; then artifact_check "$(jq -c .artifacts "$marker")" || die "Changed fallback artifact: $stage"; return; fi
    configure_build "$source" "$build" "$mode" "$PAIR_LOG/build.log" "$@" || return 1
    [[ -f $artifact ]] || die "Missing fallback artifact: $artifact"
    jq -n --arg p "$artifact" --arg sha "$(hash "$artifact")" '{artifacts:{($p):$sha}}' | save_json "$marker"
}
fallback_gcc() {
    local version=$1 prefix=$PREFIXES/gcc-$1 build=$BUILDS/gcc/$1 gccsrc binsrc newsrc
    directory "$prefix"; directory "$build"
    if [[ -f $META/gcc-$version.json ]] && jq -e '.failed==true' "$META/gcc-$version.json" >/dev/null; then return 1; fi
    say "[BUILD] Missing GCC $version (existing toolchains are untouched)"
    gcc_source "$version"; gccsrc=$SELECTED_SOURCE
    if ! reuse_source binutils-$BIN_REV "$BIN_REV"; then git_source binutils "$BIN_URL" "$BIN_REV" "$SOURCES/binutils-$BIN_REV"; fi
    binsrc=$SELECTED_SOURCE
    if ! reuse_source newlib-$NEW_REV "$NEW_REV"; then git_source newlib "$NEW_URL" "$NEW_REV" "$SOURCES/newlib-$NEW_REV"; fi
    newsrc=$SELECTED_SOURCE
    export PATH=$prefix/bin:$HOST_PATH RISCV=$prefix
    local -a arch=(--with-arch="$ARCH" --with-abi="$ABI" --with-isa-spec=20191213)
    local -a gccargs=(--target="$TARGET" --prefix="$prefix" --disable-multilib --disable-shared --disable-threads
        --enable-languages=c,c++ --with-newlib --with-sysroot="$prefix/$TARGET" --disable-libssp --disable-libquadmath
        --disable-libgomp --disable-nls --disable-tm-clone-registry --disable-bootstrap "${arch[@]}")
    fallback_stage binutils "$binsrc" "$build/binutils" install "$prefix/bin/$TARGET-ld" \
        --target="$TARGET" --prefix="$prefix" --disable-multilib --enable-plugins --disable-werror --disable-nls \
        --disable-gdb --disable-sim --disable-libdecnumber --disable-readline "${arch[@]}" || return 1
    fallback_stage initial-gcc "$gccsrc" "$build/initial-gcc" compiler "$build/initial-gcc/gcc/xgcc" \
        "${gccargs[@]}" --disable-tls 'CFLAGS_FOR_TARGET=-Os -mcmodel=medlow' 'CXXFLAGS_FOR_TARGET=-Os -mcmodel=medlow' || return 1
    fallback_stage newlib "$newsrc" "$build/newlib" install "$prefix/$TARGET/lib/libc.a" \
        --target="$TARGET" --prefix="$prefix" --disable-multilib --enable-newlib-io-long-double --enable-newlib-io-long-long \
        --enable-newlib-io-c99-formats --enable-newlib-register-fini \
        "CFLAGS_FOR_TARGET=-O2 -D_POSIX_MODE -ffunction-sections -fdata-sections -mcmodel=medlow -march=$ARCH -mabi=$ABI" || return 1
    fallback_stage final-gcc "$gccsrc" "$build/final-gcc" install "$prefix/bin/$TARGET-gcc" \
        "${gccargs[@]}" --enable-tls --with-native-system-header-dir=/include \
        'CFLAGS_FOR_TARGET=-Os -mcmodel=medlow' 'CXXFLAGS_FOR_TARGET=-Os -mcmodel=medlow' || return 1
    compiler_ok "$prefix/bin/$TARGET-gcc" "$version" || die 'Fallback compiler validation failed'
    TC_JSON=$(jq -n --arg v "$version" --arg p "$prefix" --arg cc "$prefix/bin/$TARGET-gcc" --arg tree "$(legacy_hash "$prefix")" \
        '{complete:true,status:"REUSABLE_EXISTING_TOOLCHAIN",version:$v,prefix:$p,compiler:$cc,tree_sha256:$tree,tree_kind:"legacy",origin:"matrix-fallback"}')
    printf '%s\n' "$TC_JSON" | save_json "$META/gcc-$version.json"
    jq --arg v "$version" --argjson t "$TC_JSON" '.[$v]=$t' "$INVENTORY" | save_json "$INVENTORY"
}
ensure_stub() {
    local cc prefix previous path expected map marker recipe dir oldbuild config
    cc=$(jq -r .compiler <<< "$TC_JSON"); prefix=$(jq -r .prefix <<< "$TC_JSON")
    previous=$(jq -c '.previous // {}' <<< "$TC_JSON")
    path=$(jq -r '.stub // empty' <<< "$previous")
    # Old script recipe has no PK inputs. Check source identity, ELF/map hashes,
    # completion and toolchain provenance before importing it.
    if [[ -n $path ]] && jq -e '.stages.stub.complete==true' >/dev/null <<< "$previous"; then
        local origin
        origin=$(jq -r .origin <<< "$TC_JSON")
        if [[ $(jq -r 'if (.identity|type)=="object" then .identity.stub else "" end' "$origin") == "$STUB_SHA" ]] && \
            artifact_check "$(jq -c '.stages.stub.artifacts' <<< "$previous")" && elf_ok "$path" RISC-V; then
            STUB_JSON=$(jq -n --arg path "$path" --arg sha "$(hash "$path")" '{path:$path,sha256:$sha,reused:true}')
            return
        fi
    fi
    recipe=$(printf '%s' "$(jq -r .tree_sha256 <<< "$TC_JSON")|$STUB_SHA|$ARCH|$ABI|-Os|--static" | sha256sum | cut -d ' ' -f1)
    dir=$BUILDS/stub/$recipe; marker=$dir/manifest.json
    if [[ -f $marker ]]; then
        if jq -e '.failed==true' "$marker" >/dev/null; then return 1; fi
        artifact_check "$(jq -c .artifacts "$marker")" || die 'Cached stub changed'
        STUB_JSON=$(jq -c '.stub + {reused:true}' "$marker"); return
    fi
    directory "$dir"
    if ! build_run "$dir" "$PAIR_LOG/build.log" "$cc" -march="$ARCH" -mabi="$ABI" -Os --static "-Wl,-Map=$dir/stub.map" "$STUB" -o "$dir/stub.elf"; then
        jq -n --arg log "$PAIR_LOG/build.log" '{failed:true,diagnostics:$log}' | save_json "$marker"
        return 1
    fi
    elf_ok "$dir/stub.elf" RISC-V || die 'Invalid new stub ELF'
    STUB_JSON=$(jq -n --arg path "$dir/stub.elf" --arg sha "$(hash "$dir/stub.elf")" '{path:$path,sha256:$sha,reused:false}')
    jq -n --argjson s "$STUB_JSON" --arg map "$dir/stub.map" --arg mh "$(hash "$dir/stub.map")" \
        '{stub:$s,artifacts:{($s.path):$s.sha256,($map):$mh}}' | save_json "$marker"
}
ensure_pk() {
    local sha=$1 cc prefix source=$SOURCES/pk/$1 build=$BUILDS/pk/$1/gcc-$CURRENT_GCC marker
    cc=$(jq -r .compiler <<< "$TC_JSON"); prefix=$(jq -r .prefix <<< "$TC_JSON")
    marker=$build/manifest.json
    if [[ -f $marker ]]; then
        [[ $(jq -r .toolchain "$marker") == "$(jq -r .tree_sha256 <<< "$TC_JSON")" ]] || die 'PK toolchain identity changed'
        artifact_check "$(jq -c .artifacts "$marker")" || die 'Cached PK binary changed'
        PK_JSON=$(jq -c '.pk + {reused:true}' "$marker"); return
    fi
    git_source pk "$PK_URL" "$sha" "$source"
    directory "$build"
    # Old configure scripts can silently ignore unknown --with-* arguments.
    # Require support, rather than adapting or patching a historical revision.
    checked "$build" "$PAIR_LOG/diagnostics.txt" "$PAIR_LOG/diagnostics.txt" 30 "$source/configure" --help
    if ! grep -F -- '--with-arch' "$PAIR_LOG/diagnostics.txt" >/dev/null || ! grep -F -- '--with-abi' "$PAIR_LOG/diagnostics.txt" >/dev/null; then
        printf 'Historical configure lacks required --with-arch/--with-abi; no options changed.\n' >> "$PAIR_LOG/build.log"
        return 1
    fi
    export CC="$cc -march=$ARCH -mabi=$ABI" CXX=$prefix/bin/$TARGET-g++
    export AR=$prefix/bin/$TARGET-ar RANLIB=$prefix/bin/$TARGET-ranlib READELF=$prefix/bin/$TARGET-readelf OBJCOPY=$prefix/bin/$TARGET-objcopy
    local rc=0
    configure_build "$source" "$build" pk "$PAIR_LOG/build.log" --host="$TARGET" --prefix="$build/pk-install" --with-arch="$ARCH" --with-abi="$ABI" || rc=$?
    unset CC CXX AR RANLIB READELF OBJCOPY
    (( rc == 0 )) || return 1
    elf_ok "$build/pk" RISC-V || die 'Invalid PK ELF after successful build'
    PK_JSON=$(jq -n --arg p "$build/pk" --arg sha "$(hash "$build/pk")" '{path:$p,sha256:$sha,reused:false}')
    jq -n --argjson pk "$PK_JSON" --arg commit "$sha" --arg tc "$(jq -r .tree_sha256 <<< "$TC_JSON")" \
        --arg target "$TARGET" --arg arch "$ARCH" --arg abi "$ABI" \
        '{pk:$pk,commit:$commit,toolchain:$tc,target:$target,arch:$arch,abi:$abi,artifacts:{($pk.path):$pk.sha256}}' | save_json "$marker"
    checked "$build" "$PAIR_LOG/diagnostics.txt" "$PAIR_LOG/diagnostics.txt" 0 "$prefix/bin/$TARGET-readelf" -h -l -A "$build/pk"
}
# Existing GCC-experiment PKs are deliberately not imported: the recorded PK
# commit 9c61d298... is not in any approved release. The same applies to their
# negative executions: zero exact pairs overlap this approved matrix.
# Within this matrix, complete results are keyed by the entire procedure and
# artifact identities, not just a version string.
pair_key() {
    printf '%s\n' "$ENV_ID" "$CURRENT_PK" "$CURRENT_GCC" "$(jq -r .tree_sha256 <<< "$TC_JSON")" \
        "$(jq -r .sha256 <<< "$STUB_JSON")" "$RECIPE" | sha256sum | cut -d ' ' -f1
}
rebuild_summary() {
    local path=$LOGS/results.tsv
    contained "$path.pending"
    {
        printf 'timestamp\tchipyard_releases\tpk_commit\tgcc_version\tgcc_path\tboom_sha256\tresult\tbuild_seconds\tsimulation_seconds\ttotal_seconds\ttimeout\tpc_loop\tdiagnostics\n'
        jq -r '.pairs[] | [.ended,.releases,.pk_commit,.gcc_version,.compiler,.boom_sha256,.classification,
             .build_seconds,(.execution.duration_seconds // 0),.total_seconds,(.execution.timed_out // false),
             (.execution.pc_loop_analysis // "NOT_APPLICABLE"),.diagnostics] | @tsv' "$STATE"
    } > "$path.pending"
    mv "$path.pending" "$path"
}
record_pair() {
    local result=$1 execution=${2:-null} result_json
    result_json=$(jq -n --arg class "$result" --arg pk "$CURRENT_PK" --arg gcc "$CURRENT_GCC" --arg rel "$CURRENT_RELEASES" \
        --arg cc "$(jq -r '.compiler // "unavailable"' <<< "$TC_JSON")" --arg boom "$BOOM_SHA" --arg boom_path "$BOOM" \
        --arg ended_at "$(now)" --arg log "$PAIR_LOG" --argjson b "$BUILD_CS" --argjson total "$(( $(ticks)-TOTAL_START ))" \
        --argjson execution "$execution" --argjson tc "$TC_JSON" --argjson stub "${STUB_JSON:-null}" --argjson artifact "${PK_JSON:-null}" \
        '{complete:true,classification:$class,pk_commit:$pk,gcc_version:$gcc,releases:$rel,compiler:$cc,
          boom_sha256:$boom,boom_path:$boom_path,ended:$ended_at,diagnostics:$log,build_seconds:($b/100),total_seconds:($total/100),
          execution:$execution,toolchain:$tc,stub:$stub,pk:$artifact,
          pc_loop_analysis:($execution.pc_loop_analysis // "NOT_APPLICABLE")}')
    printf '%s\n' "$result_json" | save_json "$PAIR_LOG/result.json"
    state_update '.pairs[$key]=$r' --arg key "$KEY" --argjson r "$result_json"
    rebuild_summary
    say "[RESULT] PK ${CURRENT_PK:0:12} x GCC $CURRENT_GCC: $result; build $(jq -r .build_seconds <<< "$result_json")s; simulation $(jq -r '.execution.duration_seconds // 0' <<< "$result_json")s; total $(jq -r .total_seconds <<< "$result_json")s"
    say "  Diagnostics: $PAIR_LOG"
    CLASS=$result
}
verify_pair() {
    local r=$1 path sha
    # Failed builds have no PK; successful PK/stub artifacts must still match.
    while IFS=$'\t' read -r path sha; do
        [[ -f $path && $(hash "$path") == "$sha" ]] || die "Cached pair artifact changed: $path"
    done < <(jq -r '[.pk,.stub] | .[] | select(.!=null) | [.path,.sha256] | @tsv' <<< "$r")
    if [[ $(jq -r .classification <<< "$r") == SUCCESS ]]; then
        while IFS=$'\t' read -r path sha; do
            [[ -f $path && $(hash "$path") == "$sha" ]] || die 'Cached success evidence changed'
        done < <(jq -r '.execution | [.stdout,.stdout_sha256],[.stderr,.stderr_sha256] | @tsv' <<< "$r")
        jq --argjson limit "$LIMIT" -e '.execution | .returncode==0 and .pass_marker==true and .failure_marker==false and
            .timed_out==false and .trap_loop_detected==false and .pc_loop_analysis=="NOT_DETECTED" and .duration_seconds<$limit' \
            >/dev/null <<< "$r" || die 'Invalid cached success'
    fi
}
success() {
    local r=$1
    say '============================================================'
    say 'YAY — SUCCESS!'
    say 'Compatible PK × GCC combination found'
    say '============================================================'
    jq --arg limit "$LIMIT" -r '"Chipyard release(s): \(.releases)\nPK commit: \(.pk_commit)\nGCC: \(.gcc_version)\nCompiler: \(.compiler)\nPK binary: \(.pk.path)\nStub: \(.stub.path)\nBOOM: \(.boom_path)\nBOOM SHA-256: \(.boom_sha256)\nExit: \(.execution.returncode)\nSimulation: \(.execution.duration_seconds)s (<\($limit)s)\nInvocation: \(.execution.executed|@sh)\nDiagnostics: \(.diagnostics)"' <<< "$r"
    "$(jq -r .compiler <<< "$r")" --version
    say "Target: $TARGET; ISA: $ARCH; ABI: $ABI; seed: $SEED"
    say 'Normal successful completion; no timeout; no qualifying trap-loop signature detected.'
}
run_pair() {
    local index=$1 version=$2 number=$3 old prefix
    CURRENT_PK=${PKS[index]}; CURRENT_RELEASES=${RELEASES[index]}; CURRENT_GCC=$version
    TC_JSON=$(jq -c --arg v "$version" '.[$v]' "$INVENTORY")
    STUB_JSON= PK_JSON= CLASS= BUILD_CS=0 TOTAL_START=$(ticks)
    PAIR_LOG=$LOGS/pairs/$CURRENT_PK/gcc-$version/$(basename "$SESSION")
    directory "$PAIR_LOG"
    say "Testing $number/30: Chipyard $CURRENT_RELEASES; PK $CURRENT_PK; GCC $version"
    say "  BOOM: $BOOM (SHA-256 $BOOM_SHA)"
    # Build failures have no stub hash yet. Their dedicated keys remain tied to
    # this run's environment and, where available, the validated toolchain.
    if [[ $(jq -r .status <<< "$TC_JSON") == NEEDS_BUILD ]]; then
        KEY=$ENV_ID-$CURRENT_PK-$version-toolchain-failed
    else
        KEY=$ENV_ID-$CURRENT_PK-$version-$(jq -r .tree_sha256 <<< "$TC_JSON")-stub-failed
    fi
    old=$(jq -c --arg k "$KEY" '.pairs[$k] // null' "$STATE")
    if [[ $old != null ]]; then
        CLASS=$(jq -r .classification <<< "$old")
        say "[SKIP] Exact prerequisite failure already recorded: $CLASS; $(jq -r .diagnostics <<< "$old")"
        return
    fi
    if [[ $(jq -r .status <<< "$TC_JSON") == NEEDS_BUILD ]]; then
        if ! fallback_gcc "$version"; then
            jq -n --arg v "$version" --arg log "$PAIR_LOG" '{failed:true,version:$v,diagnostics:$log}' | save_json "$META/gcc-$version.json"
            KEY=$ENV_ID-$CURRENT_PK-$version-toolchain-failed
            record_pair TOOLCHAIN_BUILD_FAILED; return
        fi
    fi
    prefix=$(jq -r .prefix <<< "$TC_JSON")
    export PATH=$prefix/bin:$HOST_PATH RISCV=$prefix
    if ! ensure_stub; then
        KEY=$ENV_ID-$CURRENT_PK-$version-$(jq -r .tree_sha256 <<< "$TC_JSON")-stub-failed
        record_pair STUB_BUILD_FAILED; return
    fi
    KEY=$(pair_key)
    old=$(jq -c --arg k "$KEY" '.pairs[$k] // null' "$STATE")
    if [[ $old != null ]] && jq -e '.complete==true' >/dev/null <<< "$old"; then
        verify_pair "$old"
        CLASS=$(jq -r .classification <<< "$old")
        say "[SKIP] Exact pair already completed: $CLASS; $(jq -r .diagnostics <<< "$old")"
        if [[ $CLASS == SUCCESS ]]; then success "$old"; fi
        return
    fi
    say '[BUILD] PK (reuse a verified completed artifact when available)'
    if ! ensure_pk "$CURRENT_PK"; then record_pair PK_BUILD_FAILED; return; fi
    say "[RUN] BOOM simulation; ${LIMIT}-second limit; live trap-loop detection; full trace captured"
    boom_test "$PAIR_LOG" "$LIMIT" "$(jq -r .path <<< "$PK_JSON")" "$(jq -r .path <<< "$STUB_JSON")"
    [[ $CLASS != SIMULATOR_START_FAILED ]] || die "BOOM failed to launch; see $PAIR_LOG"
    record_pair "$CLASS" "$RUN_JSON"
    if [[ $CLASS == SUCCESS ]]; then success "$(jq -c --arg k "$KEY" '.pairs[$k]' "$STATE")"; fi
}
main() {
    [[ $# == 1 ]] || { usage; exit 2; }
    case $1 in --help|-h) usage; return;; --self-test) self_test; return;; --run|--preflight-only) ;; *) usage; exit 2;; esac
    (( BASH_VERSINFO[0]>4 || (BASH_VERSINFO[0]==4 && BASH_VERSINFO[1]>=4) )) || die 'Bash 4.4+ required'
    export PATH=$HOST_PATH LC_ALL=C TZ=UTC GIT_OPTIONAL_LOCKS=0 GIT_CONFIG_NOSYSTEM=1 GIT_CONFIG_GLOBAL=/dev/null GIT_TERMINAL_PROMPT=0
    unset CC CXX CFLAGS CXXFLAGS CPPFLAGS LDFLAGS LIBRARY_PATH CPATH C_INCLUDE_PATH CPLUS_INCLUDE_PATH GCC_EXEC_PREFIX COMPILER_PATH CONFIG_SITE MAKEFLAGS MFLAGS LD_PRELOAD LD_LIBRARY_PATH RISCV AR RANLIB READELF OBJCOPY
    local tool p index version number=0
    for tool in jq python3 gcc g++ make as ld ar ranlib readelf git curl tar xz gzip bzip2 awk sed grep bison flex makeinfo perl timeout uname getconf ldd flock setsid sha256sum sha512sum realpath readlink find sort xargs cut df nproc date sleep tail mv mkdir cp cmp rm cat wc; do
        command -v "$tool" >/dev/null || die "Missing dependency: $tool. Required for build/provenance/supervision; no packages installed."
    done
    [[ $(timeout --version) == *'GNU coreutils'* && $(tar --version) == *'GNU tar'* && $(make --version) == *'GNU Make'* ]] || die 'GNU timeout/tar/make required'
    [[ -d $EXP && $(realpath "$EXP") == "$EXP" && $(realpath -m "$ROOT") == "$ROOT" ]] || die "Run on the server with the original nonsymlink experiment: $EXP"
    # Inspect all existing output symlinks before creating any file.
    if [[ -d $ROOT ]]; then while IFS= read -r -d '' p; do contained "$p"; done < <(find "$ROOT" -type l -print0); fi
    directory "$META"
    contained "$META/experiment.lock"; exec 9>> "$META/experiment.lock"
    flock -n 9 || die 'Another PK matrix run holds the lock'
    # Lock the old runner's existing lock read-only; do not create/edit old files.
    if [[ -f $EXP/logs/experiment.lock ]]; then
        exec 8< "$EXP/logs/experiment.lock"; flock -n 8 || die 'The GCC experiment is still running'
    fi
    for p in "$LOGS" "$SOURCES" "$BUILDS" "$PREFIXES" "$ROOT/tmp"; do directory "$p"; done
    SESSION=$LOGS/sessions/$(date -u +%Y%m%dT%H%M%S)-$$
    directory "$SESSION"; SESSION_LOG=$SESSION/preflight.log
    export TMPDIR=$ROOT/tmp/$(basename "$SESSION") TMP=$ROOT/tmp/$(basename "$SESSION") TEMP=$ROOT/tmp/$(basename "$SESSION")
    directory "$TMPDIR"
    export XDG_CACHE_HOME=$TMPDIR/cache
    directory "$XDG_CACHE_HOME"
    SELF=$(realpath "$SELF")
    preflight
    [[ $1 != --preflight-only ]] || return 0
    for index in "${!PKS[@]}"; do
        for version in "${VERSIONS[@]}"; do
            number=$((number+1))
            # Do not put this function in an if/|| context: Bash would disable
            # errexit inside it. Individual expected build failures are handled.
            run_pair "$index" "$version" "$number"
            [[ $CLASS != SUCCESS ]] || return 0
            unset CC CXX AR RANLIB READELF OBJCOPY RISCV
            export PATH=$HOST_PATH
        done
    done
    say "Approved matrix exhausted without success. Results: $LOGS/results.tsv"
    exit 1
}
if [[ ${BASH_SOURCE[0]} == "$0" ]]; then main "$@"; fi
