"""Operator-owned full update handler. Not a check-then-update authorization token.

If configured, the handler owns prepare/freeze/test/CAS-apply and the caller MUST
NOT fall through to the native updater, even on failure. No configuration means
unchanged native behavior. The host never loads code from a JSON field.
"""
import json
import os
from pathlib import Path
import subprocess

class UpdateHookError(RuntimeError): pass

def run_update_hook(install_root, home, *, branch='main', surface='cli'):
    path=Path(home)/'update-gate.json'
    if not path.exists() and not path.is_symlink(): return False
    if path.is_symlink() or not path.is_file() or path.stat().st_size>65536: raise UpdateHookError('invalid update hook configuration')
    try:
        cfg=json.loads(path.read_text())
        argv=cfg['argv']
        if set(cfg)!={'argv'} or not isinstance(argv,list) or not argv or any(not isinstance(x,str) or not x or '\x00' in x for x in argv) or not Path(argv[0]).is_absolute():
            raise ValueError()
        args=argv+['--install-root',str(Path(install_root).resolve()),'--home',str(Path(home).resolve()),'--branch',str(branch),'--surface',surface]
        result=subprocess.run(args,cwd=install_root,timeout=1800,stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=False)
        if result.returncode or len(result.stdout)>1048576:raise ValueError()
        reply=json.loads(result.stdout)
        if type(reply) is not dict or reply.get('ok') is not True or reply.get('handled') is not True:raise ValueError()
        return True
    except (OSError,ValueError,KeyError,TypeError,subprocess.SubprocessError) as exc:
        raise UpdateHookError('configured update handler refused; native updater was not invoked') from exc
