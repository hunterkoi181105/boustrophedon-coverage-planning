"""Run the 300-map, single-seed AC300 experiment. Restart to reuse finished maps."""
import csv
import os
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
MAPS = ROOT / "benchmarks/ac300_full"
OUT = ROOT / "results/ac300_all"
ALGOS = ["tsp-greedy", "tsp-2opt", "gtsp", "gtsp-exact", "aco"]


def run_map(path):
    target = OUT / "maps" / f"{path.stem}.csv"
    if target.exists():
        return
    with TemporaryDirectory(dir=target.parent) as tmp:
        work = Path(tmp)
        shutil.copy2(path, work)
        env = dict(os.environ, PYTHONPATH=os.pathsep.join(filter(None, (str(ROOT / "src"), os.environ.get("PYTHONPATH")))), OPENBLAS_NUM_THREADS="1",
                   OMP_NUM_THREADS="1")
        cmd = [sys.executable, "-m", "coverage_planning.benchmark", "--maps", str(work),
               "--algorithms", *ALGOS, "--seeds", "0", "--no-save-runs", "--out", str(work/"runs.csv")]
        result = subprocess.run(cmd, env=env, capture_output=True, text=True)
        if result.returncode:
            raise RuntimeError(f"{path.name}: {result.stderr}")
        with (work/"runs.csv").open(newline="", encoding="utf8") as f:
            reader = csv.DictReader(f)
            fields = reader.fieldnames
            rows = list(reader)
        if [r["algorithm"] for r in rows] != ALGOS:
            raise ValueError(f"Incomplete map: {path.name}")
        with (work/"final.csv").open("w", newline="", encoding="utf8") as f:
            writer = csv.DictWriter(f, fields)
            writer.writeheader()
            for row in rows:
                row["source_file"] = path.relative_to(ROOT).as_posix()
                writer.writerow(row)
        (work/"final.csv").replace(target)
    print(path.stem, flush=True)


if __name__ == "__main__":
    paths = sorted(MAPS.glob("*.json"), key=lambda p: (int(p.stem.split("_")[0][2:]), p.stem))
    if len(paths) != 300:
        sys.exit(f"Expected 300 maps, found {len(paths)}")
    (OUT/"maps").mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(max_workers=6) as pool:
        list(pool.map(run_map, paths))
    with (OUT/"runs.csv.tmp").open("wb") as out:
        for i, path in enumerate(paths):
            with (OUT/"maps"/f"{path.stem}.csv").open("rb") as f:
                if i:
                    f.readline()
                shutil.copyfileobj(f, out)
    (OUT/"runs.csv.tmp").replace(OUT/"runs.csv")

