from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parent
OLD=HERE.parent/'three_repo_batch6_20261102'
PROVIDER=OLD/'etf-host/my_data_etf'
STAGING=OLD/'etf-host/staging'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def protected():
    return {str(root):{'exists':root.exists()} for root in [
        Path.home()/'.qlib/qlib_data/my_data',Path.home()/'.qlib/qlib_data/my_data_1min']}


def main():
    before=protected()
    assert all(not row['exists'] for row in before.values())
    original=json.loads((OLD/'etf-provider-files.json').read_text(encoding='utf-8'))
    expected={row['path']:row['sha256'] for row in original}
    assert len(expected)==11406
    def verify():
        observed={p.relative_to(PROVIDER).as_posix():sha(p) for p in PROVIDER.rglob('*') if p.is_file()}
        assert observed==expected
    verify()
    calendar=pd.DatetimeIndex(pd.to_datetime((PROVIDER/'calendars/day.txt').read_text().splitlines()))
    samples=[]
    for code in ['SH510050','SH510300','SZ159915','SH510500']:
        stage=STAGING/(code.lower()+'.parquet')
        frame=pd.read_parquet(stage)
        frame=frame.set_index(pd.to_datetime(frame['date']))
        record={'code':code,'staging_sha256':sha(stage),'fields':{}}
        for field in ['open','high','low','close','volume','amount','vwap']:
            path=PROVIDER/'features'/code.lower()/(field+'.day.bin')
            data=np.fromfile(path,dtype='<f4')
            first=int(data[0])
            actual=pd.Series(np.nan,index=calendar,dtype=float)
            actual.iloc[first:first+len(data)-1]=data[1:]
            wanted=frame[field].reindex(calendar).astype(float)
            np.testing.assert_allclose(actual.to_numpy(),wanted.to_numpy(),rtol=1e-6,atol=1e-4,equal_nan=True)
            finite=np.isfinite(actual.to_numpy())&np.isfinite(wanted.to_numpy())
            error=float(np.max(np.abs(actual.to_numpy()[finite]-wanted.to_numpy()[finite])))
            if field in ['open','high','low','close','vwap']:
                assert error <= 1e-4
            record['fields'][field]={'finite_rows':int(finite.sum()),'max_absolute_error':error,'bin_sha256':sha(path)}
        samples.append(record)
    verify()
    after=protected()
    assert before==after
    report={'recorded_at_utc':datetime.now(timezone.utc).isoformat(),'status':'PASS_FROZEN_PROVIDER_REVALIDATION',
        'runner_sha256':sha(__file__),'provider_files_verified_unchanged':11406,'calendar_rows':len(calendar),
        'protected_provider_roots_before':before,'protected_provider_roots_after':after,
        'four_etf_seven_field_checks':samples,'provider_writes':False,'market_writes':False,
        'limits':['Frozen2020-01-02..2026-10-13 provider/staging only; not the latest front lake.',
            'Current protected root directories absent before/after. This is not a retroactive full-tree attestation of older runs.',
            'E4 fit/prediction is not rerun; its merged independently verified artifacts are referenced separately.']}
    (HERE/'p11-current-revalidation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    print('P11 frozen provider11406files,4ETFs x7fields and protected root absence verified')


if __name__=='__main__':
    main()
