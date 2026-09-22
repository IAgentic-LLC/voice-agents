#!/usr/bin/env bash
# Chapter 5: place calls to two agents in turn, batch, stream, stream, batch,
# so neither always gets the earlier slot. Six calls each by default.
# Usage: ./alternate.sh cascaded-batch cascaded-stream runs/mine 6
a=$1; b=$2; run=$3; pairs=${4:-6}
for i in $(seq 1 "$pairs"); do
  if (( i % 2 )); then order="$a $b"; else order="$b $a"; fi
  for agent in $order; do
    uv run caller.py --agent "$agent" --calls 1 --run "$run-$agent"
  done
done
