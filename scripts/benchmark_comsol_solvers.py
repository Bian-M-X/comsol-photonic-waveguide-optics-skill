"""Serial, bounded comparison of direct solvers on an existing reviewed MPH.

Dry-run by default. The source MPH is only loaded; generated Java, runtime
directories, copied results, failed logs and receipts stay in a new output
directory. This development script is not a public MCP execution capability.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import time
from pathlib import Path


def file_sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def java_literal(text: str) -> str:
    if any(ord(c) < 32 for c in text):
        raise ValueError("control characters are not valid in paths, tags or expressions")
    return json.dumps(text, ensure_ascii=True)


def generate_source(model: Path, output: Path, solver: str, solution: str, stationary: str,
                    direct: str, coupled: str, dataset: str, expressions: list[str]) -> str:
    expr = ", ".join(java_literal(item) for item in expressions)
    return f'''import com.comsol.model.Model;
import com.comsol.model.util.ModelUtil;
public class SolverBenchmark {{
  public static void main(String[] args) throws Exception {{
    Model m = ModelUtil.load("Benchmark", {java_literal(str(model))});
    System.out.println("BENCH_VERSION=" + ModelUtil.getComsolVersion());
    for (String tag : m.sol().tags()) m.sol(tag).clearSolutionData();
    m.sol({java_literal(solution)}).feature({java_literal(stationary)}).feature({java_literal(direct)})
      .set("linsolver", {java_literal(solver)});
    m.sol({java_literal(solution)}).feature({java_literal(stationary)}).feature({java_literal(coupled)})
      .set("linsolver", {java_literal(direct)});
    if ({java_literal(solver)}.equals("cudss")) {{
      m.sol({java_literal(solution)}).feature({java_literal(stationary)}).feature({java_literal(direct)})
        .set("cudssprecision", "double");
    }}
    System.out.println("BENCH_REQUESTED_SOLVER={solver}");
    long start = System.nanoTime();
    m.sol({java_literal(solution)}).runAll();
    System.out.println("BENCH_SOLVE_SECONDS=" + (System.nanoTime()-start)*1e-9);
    m.result().numerical().create("benchmark_metrics", "EvalGlobal");
    m.result().numerical("benchmark_metrics").set("data", {java_literal(dataset)});
    m.result().numerical("benchmark_metrics").set("expr", new String[]{{{expr}}});
    double[][] data = m.result().numerical("benchmark_metrics").getReal();
    for (int i=0; i<data.length; i++) {{
      if (data[i].length != 1) throw new IllegalStateException("Benchmark requires one solution value per metric");
      if (!Double.isFinite(data[i][0])) throw new IllegalStateException("Nonfinite metric");
      System.out.println("BENCH_METRIC_" + i + "=" + data[i][0]);
    }}
    m.save({java_literal(str(output))});
    System.out.println("BENCH_COMPLETE");
  }}
}}
'''


def run_process(command: list[str], cwd: Path, log: Path, timeout: int) -> tuple[int, float]:
    start = time.perf_counter()
    with log.open("wb") as stream:
        proc = subprocess.Popen(command, cwd=cwd, stdout=stream, stderr=subprocess.STDOUT,
                                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        try:
            code = proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            if os.name == "nt":
                subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False,
                               creationflags=subprocess.CREATE_NO_WINDOW)
            else:
                proc.kill()
            proc.wait(timeout=30)
            return 124, time.perf_counter() - start
    return code, time.perf_counter() - start


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--solver-root", type=Path, required=True)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True, help="new directory; never reused")
    parser.add_argument("--solution", default="sol1")
    parser.add_argument("--stationary", default="s1")
    parser.add_argument("--direct", default="d1")
    parser.add_argument("--coupled", default="fc1")
    parser.add_argument("--dataset", default="dset1")
    parser.add_argument("--metric", action="append", required=True, help="reviewed real-valued COMSOL expression")
    parser.add_argument("--solvers", nargs="+", choices=("pardiso", "mumps", "cudss"),
                        default=["pardiso", "mumps", "cudss"])
    parser.add_argument("--repeats", type=int, choices=range(1, 6), default=2)
    parser.add_argument("--processors", type=int, choices=range(1, 33), default=8)
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    if os.name != "nt":
        parser.error("this runner currently qualifies the Windows native COMSOL entrypoints only")
    if not 30 <= args.timeout <= 1800 or not 1 <= len(args.metric) <= 16:
        parser.error("timeout must be 30..1800 seconds and metric count 1..16")
    if len(set(args.solvers)) != len(args.solvers) or len(set(args.metric)) != len(args.metric):
        parser.error("solvers and metrics must not contain duplicates")
    if any(not expression.strip() or any(ord(c) < 32 for c in expression) for expression in args.metric):
        parser.error("metrics must be nonempty real expressions without control characters")
    for tag in (args.solution, args.stationary, args.direct, args.coupled, args.dataset):
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,63}", tag):
            parser.error("solver/dataset tags must be simple identifiers")
    model, destination = args.model.resolve(strict=True), args.output.resolve()
    if model.suffix.lower() != ".mph" or not model.is_file() or destination.exists():
        parser.error("model must be an MPH file and output directory must not already exist")
    compiler = args.solver_root / "bin/win64/comsolcompile.exe"
    batch = args.solver_root / "bin/win64/comsolbatch.exe"
    if not compiler.is_file() or not batch.is_file():
        parser.error("official COMSOL native entrypoints were not found")
    plan = {"model_sha256": file_sha256(model), "processors": args.processors,
            "solvers": args.solvers, "repeats": args.repeats, "timeout_per_native_process_s": args.timeout,
            "metrics": args.metric, "solution": args.solution, "stationary": args.stationary,
            "direct": args.direct, "coupled": args.coupled, "dataset": args.dataset,
            "execute": args.execute,
            "claim_boundary": "solver comparison on this fixture; no convergence or device acceptance"}
    print(json.dumps(plan, indent=2), flush=True)
    if not args.execute:
        return 0
    destination.mkdir(parents=True, exist_ok=False)
    (destination / "plan.json").write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
    results = []
    unavailable: set[str] = set()
    for repeat in range(args.repeats):
        # Alternate ordering to make warm-up/order effects visible.
        order = args.solvers if repeat % 2 == 0 else list(reversed(args.solvers))
        for solver in order:
            if solver in unavailable:
                continue
            folder = destination / f"r{repeat + 1}-{solver}"
            folder.mkdir()
            for sub in ("prefs", "config", "tmp"):
                (folder / sub).mkdir()
            output = folder / "result.mph"
            source = folder / "SolverBenchmark.java"
            source.write_text(generate_source(model, output, solver, args.solution, args.stationary,
                                             args.direct, args.coupled, args.dataset, args.metric), encoding="utf-8")
            row = {"repeat": repeat + 1, "solver": solver,
                   "source_sha256": file_sha256(source)}
            code, wall = run_process([str(compiler), str(source)], folder, folder / "compile.txt", args.timeout)
            row.update(compile_exit=code, compile_wall_s=wall)
            if code == 0 and source.with_suffix(".class").is_file():
                command = [str(batch), "-np", str(args.processors), "-prefsdir", str(folder / "prefs"),
                           "-configuration", str(folder / "config"), "-tmpdir", str(folder / "tmp"),
                           "-inputfile", str(source.with_suffix(".class")), "-batchlog", str(folder / "batch.log")]
                code, wall = run_process(command, folder, folder / "console.txt", args.timeout)
                console = (folder / "console.txt").read_text(encoding="utf-8", errors="replace")
                row.update(batch_exit=code, batch_wall_s=wall)
                match = re.search(r"BENCH_SOLVE_SECONDS=([0-9.eE+-]+)", console)
                if match:
                    row["study_solve_s"] = float(match.group(1))
                row["metrics"] = {args.metric[int(i)]: float(value) for i, value in
                                  re.findall(r"BENCH_METRIC_(\d+)=([0-9.eE+-]+)", console)}
                row["completed"] = (code == 0 and "BENCH_COMPLETE" in console and output.is_file()
                                    and output.stat().st_size > 0 and len(row["metrics"]) == len(args.metric))
                if row["completed"]:
                    row["mph_sha256"] = file_sha256(output)
                else:
                    unavailable.add(solver)
            else:
                row["completed"] = False
                unavailable.add(solver)
            results.append(row)
            (destination / "results.json").write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
            print(json.dumps(row), flush=True)
    return 0 if results and all(r["completed"] for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
