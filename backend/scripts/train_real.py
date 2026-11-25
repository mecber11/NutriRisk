"""Run scientific experiments against the acquired public country panel."""
import argparse
from app.services.real_research import run_real
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--trials',type=int,default=10);parser.add_argument('--run-id');parser.add_argument('--seed',type=int,default=42);args=parser.parse_args()
    if not 2 <= args.trials <= 150: parser.error('--trials must be between 2 and 150')
    result=run_real(args.run_id,args.trials,args.seed)
    from scripts.package_real import complete
    complete(result['id'])
    print(result['id'],result['status'])
