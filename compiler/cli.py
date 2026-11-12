"""
CLI entry point for PGC compiler.

Subcommands:
  compile           — compile one or more STRUCTURE artifacts (S1–S9 pipeline)
  output-root       — print where a build configuration writes

Pipeline: S1 EXTRACT → S2 CANONICALIZE → S3 SEMANTIC_ADDRESSING →
          S4 GOVERN → S5 CONSTRUCT → S6 PROJECT → S7 MATERIALIZE → S8 VERIFY → S9 ATTEST

Each stage is a pure function: State → State.

ARCHITECTURAL INVARIANT:
- Compiler MUST NOT import: execution, runtime
- Compiler is PURE: extract, canonicalize, address, govern, construct, project, materialize, verify, attest
- Compiler outputs: JSON artifacts ONLY
"""

import os
import sys
from typing import Any

import click

from compiler.graph.state import State
from compiler.stages import (
    s1_extract,
    s2_canonicalize,
    s3_semantic_addressing,
    s4_govern,
    s5_construct,
    s6_project,
    s7_materialize,
    s8_verify,
    s9_attest,
)
from compiler.atoms.errors import CompilerError
from compiler.structure_loader import FORBIDDEN_STRUCTURE


def assert_structure_integrity(structure_code: str) -> None:
    """
    Verify build anchor is not using legacy fragmented structure.
    """
    if structure_code in FORBIDDEN_STRUCTURE:
        raise RuntimeError(
            f"LEGACY BUILD ATTEMPTED: '{structure_code}' is forbidden.\n"
            f"The compiler now requires consolidated master artifacts."
        )


@click.group()
def cli() -> None:
    """PGC protocol compiler — topology-native governance compilation."""
    pass


@cli.command()
@click.option(
    "--structure",
    type=str,
    multiple=True,
    help="STRUCTURE artifact code(s) (e.g. STRUCTURE_BUILD_PLATFORM_CONFIG_V0)",
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="Verbose output (full error context, stage metadata)",
)
def compile(
    structure: tuple,
    verbose: bool,
) -> None:
    """
    Compile STRUCTURE artifacts through the S1–S8 pipeline.

    Chains 8 pure stages: EXTRACT → CANONICALIZE → SEMANTIC_ADDRESSING →
    GOVERN → CONSTRUCT → PROJECT → MATERIALIZE → VERIFY.
    """
    structures = list(structure)
    # No default and no "all": a platform is whatever a build configuration declares, and none is
    # minimal by nature (6a §8). A default would name one configuration as the platform, and an
    # "all" list would name domain builds a platform invocation cannot reach.
    if not structures:
        raise click.UsageError("name the build configuration: --structure STRUCTURE_BUILD_<...>_CONFIG_V<n>")

    click.echo(f"Starting PGC build for {len(structures)} structure(s)")
    click.echo()

    success_count = 0
    fail_count = 0

    for struct_code in structures:
        try:
            agg_type = _get_aggregation_type(struct_code)
            if agg_type:
                raise ValueError(
                    f"'{struct_code}' declares aggregation_type '{agg_type}' — "
                    "the Phase B aggregation compile path is retired. Per-domain "
                    "vocabulary is materialized in Phase A (S7); cross-structure "
                    "query metadata (protocol_snapshot/artifact_index/) is emitted "
                    "by the compile pipeline (S7 MATERIALIZE). Aggregation STRUCTUREs are not "
                    "compilable."
                )
            _run_compile(struct_code, verbose=verbose)
            success_count += 1
        except CompilerError as e:
            click.echo(f"Build failed for {struct_code}: {e.format(verbose=verbose)}", err=True)
            fail_count += 1
        except Exception as e:
            click.echo(f"Build failed for {struct_code}: {e}", err=True)
            fail_count += 1

    click.echo("=" * 40)
    click.echo(f"Build Summary: {success_count} succeeded, {fail_count} failed")

    if fail_count > 0:
        sys.exit(1)


@cli.command("output-root")
@click.option("--structure", required=True, help="The build configuration whose output root to print")
def output_root_command(structure: str) -> None:
    """Print where a build configuration writes, as its declaration resolves.

    For scripts that follow a build with a step reading its output: they ask the compiler rather
    than restate the path, so the declaration stays the only place it is written.
    """
    from compiler.structure_loader import load_structure_artifact, get_bootstrap_search_roots
    from compiler.governance_engine.platform_root import output_root

    config = load_structure_artifact(structure, get_bootstrap_search_roots())
    config["structure_artifact_code"] = structure
    click.echo(output_root(config))


def _run_compile(structure: str, verbose: bool) -> None:
    """
    Run PGC compilation pipeline (S1-S8) for a single structure.

    Each stage is a pure function: State -> State.
    Pipeline halts on first stage with errors.
    """
    if not structure.startswith("STRUCTURE_BUILD_"):
        click.echo(f"Invalid STRUCTURE artifact: {structure}", err=True)
        raise ValueError(f"Invalid structure code: {structure}")

    assert_structure_integrity(structure)

    from compiler.structure_loader import load_structure_artifact, get_bootstrap_search_roots

    try:
        structure_config = load_structure_artifact(structure, get_bootstrap_search_roots())
    except Exception as e:
        raise RuntimeError(f"Failed to load STRUCTURE artifact {structure}: {e}") from e

    structure_config["structure_artifact_code"] = structure

    # Derive display label from structure code: STRUCTURE_BUILD_BLOCKCHAIN_CONFIG_V0 → "blockchain"
    build_scope = structure.removeprefix("STRUCTURE_BUILD_").split("_CONFIG_")[0].lower()

    click.echo(f"PGC Compiling  {build_scope} ..")
    click.echo(f"   STRUCTURE: {structure}")
    click.echo()

    state = State.initial(structure_config)

    stages = [
        ("S1_EXTRACT", s1_extract),
        ("S2_CANONICALIZE", s2_canonicalize),
        ("S3_SEMANTIC_ADDRESSING", s3_semantic_addressing),
        ("S4_GOVERN", s4_govern),
        ("S5_CONSTRUCT", s5_construct),
        ("S6_PROJECT", s6_project),
        ("S7_MATERIALIZE", s7_materialize),
        ("S8_VERIFY", s8_verify),
        ("S9_ATTEST", s9_attest),
    ]

    for stage_name, stage_fn in stages:
        click.echo(f"   {stage_name}...")
        state = stage_fn(state)

        if verbose:
            for key, value in state.stage_metadata.items():
                click.echo(f"      {key}: {value}")

        if state.has_errors:
            click.echo(f"   {stage_name} failed with {len(state.errors)} error(s):", err=True)
            for error in state.errors:
                click.echo(f"      {error.format(verbose=verbose)}", err=True)
            # A refusal is a determination and is evidenced as fully as an admission (EV-3, EN-12).
            # AI-8 permits exactly this: after refusal the governed state is as though the proposal
            # had not been made, "except for the evidence that it was refused".
            from compiler.diagnostics import determination
            rec = determination.write(state, structure, "REFUSED", failed_at=stage_name)
            if rec:
                click.echo(f"   determination recorded: {rec}", err=True)
            else:
                click.echo("   WARNING: determination record could not be written", err=True)
            raise RuntimeError(f"PGC build failed at {stage_name} for {structure}")

        if state.warnings:
            click.echo(f"      {len(state.warnings)} warning(s)")
            if verbose:
                for w in state.warnings:
                    click.echo(f"         {w.message}")

    click.echo()
    click.echo(f"   Trace events: {len(state.trace_events)}")
    click.echo(f"   Materialized: {len(state.materialized_paths)} artifacts")
    verified = state.stage_metadata.get("verified", False)
    attested = state.stage_metadata.get("attested", False)
    click.echo(f"   Verified: {verified}")
    click.echo(f"   Attested: {attested}")
    click.echo()
    click.echo(f"PGC build complete for {structure}!")

    # The admission is evidenced by the same record shape as a refusal, so the two are comparable.
    from compiler.diagnostics import determination
    rec = determination.write(state, structure, "ADMITTED")
    if rec:
        click.echo(f"   determination recorded: {rec}")

    _machine_block_health(state, structure, verbose)

    click.echo(f"\n{60*'='}\n")


def _machine_block_health(state: Any, structure: str, verbose: bool) -> None:
    """Post-successful-build diagnostic: do artifacts declare machine-block keys the compiler
    consumes? Heuristic, warning-only, scoped to kinds not already closed by schema conformance.
    Never affects build success. See compiler.diagnostics.machine_block_health.
    """
    try:
        from pathlib import Path
        from compiler.diagnostics import machine_block_health as mbh
        from compiler.structure_loader import load_structure_artifact, get_bootstrap_search_roots
        dispatch = load_structure_artifact("STRUCTURE_SCHEMA_DISPATCH_V0", get_bootstrap_search_roots())
        closed = set((dispatch.get("core", {}) or {}).get("schema_dispatch", {}) or {})
        compiler_src = Path(mbh.__file__).resolve().parent.parent  # compiler/ package root
        report = mbh.check(state.graph.nodes.values(), closed, compiler_src)
        for line in mbh.format_report(report, verbose):
            click.echo(line)
    except Exception as e:  # diagnostics must never break a successful build
        if verbose:
            click.echo(f"   (machine-block health diagnostic skipped: {e})")


def _get_aggregation_type(structure_code: str) -> str | None:
    """
    Return the aggregation_type declared in a STRUCTURE artifact, or None.

    Aggregation structures (Phase Type B) have an `aggregation_type` field
    and must NOT be routed through _run_compile().
    """
    from compiler.structure_loader import load_structure_artifact, get_bootstrap_search_roots
    try:
        config = load_structure_artifact(structure_code, get_bootstrap_search_roots())
        return config.get("aggregation_type") or None
    except Exception:
        return None


if __name__ == "__main__":
    cli()
