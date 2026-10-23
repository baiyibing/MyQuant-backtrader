import os, time, subprocess
BASE = r'D:\exports\bt_corp_actions_20261006'
WORK = os.path.join(BASE, 'work')
PY = r'D:\anaconda3\python.exe'
MODEL = 'kimi-code/kimi-for-coding-highspeed'
qs = os.path.join(WORK, 'QUOTA_STOP.txt')
stamp = time.strftime('%Y%m%d_%H%M')
archived = None
if os.path.exists(qs):
    archived = os.path.join(WORK, f'QUOTA_STOP.bak_{stamp}')
    os.rename(qs, archived)
    print('ARCHIVED', archived)
else:
    print('NO_QUOTA_STOP')
log = os.path.join(WORK, 'run_all_20261016_resume9_highspeed.log')
err = os.path.join(WORK, 'run_all_20261016_resume9_highspeed.err')
pidf = os.path.join(WORK, 'runner_20261016_resume9_highspeed.pid')
flags = 0x00000008 | 0x00000200 | 0x01000000
env = os.environ.copy()
env['KIMI_MODEL'] = MODEL
launch_ts = time.strftime('%Y-%m-%d %H:%M:%S')
with open(log, 'a', encoding='utf-8') as lf:
    lf.write(f'==== launch {launch_ts} model={MODEL} ====\n')
lf = open(log, 'a', encoding='utf-8')
ef = open(err, 'a', encoding='utf-8')
p = subprocess.Popen([PY, os.path.join(WORK, 'driver.py'), 'all', '3'], cwd=WORK, env=env, stdout=lf, stderr=ef, creationflags=flags, close_fds=False)
time.sleep(2)
alive = p.poll() is None
try:
    import ctypes
    h = ctypes.windll.kernel32.OpenProcess(0x1000, False, p.pid)
    if h:
        alive = True
        ctypes.windll.kernel32.CloseHandle(h)
except Exception:
    pass
with open(pidf, 'w', encoding='utf-8') as f:
    f.write(f'{p.pid}\n{launch_ts}\nbreakaway\nmodel={MODEL}\n')
print('PID', p.pid)
print('ALIVE', alive)
print('LAUNCH_TS', launch_ts)
print('MODEL', MODEL)
print('LOG', log)
print('ARCHIVED_NAME', os.path.basename(archived) if archived else '')
time.sleep(25)
print('QUOTA_REAPPEARED', os.path.exists(qs))
print('POLL', p.poll())
try:
    import ctypes
    h = ctypes.windll.kernel32.OpenProcess(0x1000, False, p.pid)
    print('STILL_ALIVE', bool(h))
    if h: ctypes.windll.kernel32.CloseHandle(h)
except Exception as e:
    print('still_alive_err', e)
print('LOG_TAIL')
print(open(log, encoding='utf-8', errors='replace').read()[-2500:])
