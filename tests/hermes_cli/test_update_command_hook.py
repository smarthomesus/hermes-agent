import json
import subprocess
from unittest.mock import Mock
import pytest
from hermes_cli.update_command_hook import run_update_hook,UpdateHookError

@pytest.mark.parametrize('result',[{'ok':True,'handled':True},{'ok':True},{'ok':False,'handled':True},None])
def test_handler_contract_never_falls_through(tmp_path,monkeypatch,result):
    (tmp_path/'update-gate.json').write_text(json.dumps({'argv':['/absolute/operator-handler','literal;not-a-shell']}))
    fake=Mock(return_value=subprocess.CompletedProcess([],0,json.dumps(result).encode(),b''))
    monkeypatch.setattr(subprocess,'run',fake)
    if result=={'ok':True,'handled':True}:assert run_update_hook(tmp_path,tmp_path)
    else:
        with pytest.raises(UpdateHookError):run_update_hook(tmp_path,tmp_path)
    argv=fake.call_args.args[0]
    assert argv[:2]==['/absolute/operator-handler','literal;not-a-shell']
    assert fake.call_args.kwargs['timeout']==1800  # The handler owns the complete update, not a 30s preflight.
    assert '--install-root' in argv

@pytest.mark.parametrize('cfg',[{'argv':['relative']},{'argv':'/absolute'}, {'argv':[]},{'argv':['/absolute'],'extra':True}])
def test_invalid_config_never_executes(tmp_path,monkeypatch,cfg):
    (tmp_path/'update-gate.json').write_text(json.dumps(cfg))
    fake=Mock();monkeypatch.setattr(subprocess,'run',fake)
    with pytest.raises(UpdateHookError):run_update_hook(tmp_path,tmp_path)
    fake.assert_not_called()

def test_absent_preserves_native(tmp_path):assert not run_update_hook(tmp_path,tmp_path)

def test_timeout_refuses(tmp_path,monkeypatch):
    (tmp_path/'update-gate.json').write_text(json.dumps({'argv':['/absolute/handler']}))
    monkeypatch.setattr(subprocess,'run',Mock(side_effect=subprocess.TimeoutExpired('handler',30)))
    with pytest.raises(UpdateHookError):run_update_hook(tmp_path,tmp_path)

def test_both_surfaces_wired():
    from pathlib import Path
    root=Path(__file__).resolve().parents[2]
    assert 'if not run_update_hook(' in (root/'hermes_cli/main.py').read_text()
    assert 'await runUpdateCommandHook(' in (root/'apps/desktop/electron/main.ts').read_text()


@pytest.mark.parametrize('target_exists', [False, True])
def test_symlink_never_means_native_fallback(tmp_path, monkeypatch, target_exists):
    target = tmp_path/'target.json'
    if target_exists:
        target.write_text('{"argv":["/operator/update"]}')
    (tmp_path/'update-gate.json').symlink_to(target)
    fake = Mock()
    monkeypatch.setattr(subprocess, 'run', fake)
    with pytest.raises(UpdateHookError):
        run_update_hook(tmp_path, tmp_path)
    fake.assert_not_called()
