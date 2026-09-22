# Chapter 5: the PowerShell version of alternate.sh.
# Usage: .\alternate.ps1 cascaded-batch cascaded-stream runs/mine 6
param($a, $b, $run, $pairs = 6)
foreach ($i in 1..$pairs) {
  $order = if ($i % 2) { @($a, $b) } else { @($b, $a) }
  foreach ($agent in $order) {
    uv run caller.py --agent $agent --calls 1 --run "$run-$agent"
  }
}
