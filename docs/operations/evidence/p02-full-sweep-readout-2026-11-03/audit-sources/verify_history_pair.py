"""Data-free verification of archived actual Full Sweep history and reports."""
import argparse
import json
from pathlib import Path

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ['previous-report','previous-history','current-report','current-history','current-restore']:
        parser.add_argument('--'+key,required=True,type=Path)
    args=parser.parse_args()
    load=lambda p:json.loads(p.read_text(encoding='utf-8-sig'))
    previous,current=load(args.previous_report),load(args.current_report)
    old_history,new_history=load(args.previous_history),load(args.current_history)
    restore=load(args.current_restore)
    checks={
        'previous_history_loaded':previous['history_loaded'] is True,
        'current_history_loaded':current['history_loaded'] is True,
        'actual_cache_restore_success':restore['cache_restore_outcome']=='success' and restore['input_history_status']=='LOADED',
        'loaded_all_previous_entries':current['history_entries']>=len(old_history),
        'all_first_seen_dates_preserved':all(new_history.get(k)==v for k,v in old_history.items()),
        'all_chunks_success':all(r['rc']==0 for r in current['chunk_rows']),
        'no_current_failures':not current['failures'] and not current['new_failures'] and not current['old_failures'],
        'previous_failures_classified_new':set(previous['failures'])==set(previous['new_failures']) and not previous['old_failures'],
    }
    if not all(checks.values()):
        raise ValueError('history/report verification failed: '+','.join(k for k,v in checks.items() if not v))
    print(json.dumps({'status':'PASS','checks':checks,'previous_loaded_entries':previous['history_entries'],
        'previous_output_entries':len(old_history),'current_loaded_entries':current['history_entries'],
        'current_output_entries':len(new_history),'previous_failures_removed':sorted(set(previous['failures'])-set(current['failures']))},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
