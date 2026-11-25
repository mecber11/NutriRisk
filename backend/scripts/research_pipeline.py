"""Run the comparable scientific study without changing operational models."""
import argparse
from app.services.research import new_run_id, run_study

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--trials', type=int, default=50)
    parser.add_argument('--seed', type=int, default=42)
    args = parser.parse_args()
    if not 2 <= args.trials <= 150:
        parser.error('--trials debe estar entre 2 y 150')
    run_id = new_run_id()
    print(f'run_id={run_id}', flush=True)
    run_study(run_id, args.trials, args.seed)
    print(f'COMPLETED {run_id}', flush=True)
