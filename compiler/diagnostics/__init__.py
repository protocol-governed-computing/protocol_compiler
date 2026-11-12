"""Post-compile diagnostics — observations about a successful build, never gates.

Diagnostics run AFTER the S1–S9 pipeline. They do not participate in success/failure and
never change compiled output. Their job is to let the compiler observe itself — e.g. detect
when the declaration language has advanced beyond the compiler's consumption surface.
"""
