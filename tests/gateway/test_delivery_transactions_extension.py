from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from gateway import delivery_transactions as d
from hermes_cli.plugins import get_plugin_manager, PluginManager, PluginManifest

@pytest.mark.parametrize('outcome',['confirmed','failed_before_send','ambiguous_timeout'])
def test_pinned_exact_once(monkeypatch,outcome):
    p=SimpleNamespace(prepare=lambda ctx,body:{'body':body,'metadata':{},'transaction':object()},settle=Mock(return_value=True))
    monkeypatch.setattr(get_plugin_manager(),'_delivery_transaction_providers',{'telegram':p})
    lease=d.prepare_delivery('telegram',{},'body')
    get_plugin_manager()._delivery_transaction_providers.clear()
    assert lease.settle(outcome,['mid'])
    assert not lease.settle('confirmed',['late'])
    p.settle.assert_called_once()

@pytest.mark.parametrize('shape',[{},True,{'body':42,'metadata':{},'transaction':None}])
def test_invalid_prepare_refused(monkeypatch,shape):
    monkeypatch.setattr(get_plugin_manager(),'_delivery_transaction_providers',{'telegram':SimpleNamespace(prepare=lambda *a:shape)})
    with pytest.raises(ValueError):d.prepare_delivery('telegram',{},'body')

def test_missing_strip_inert(monkeypatch):
    monkeypatch.setattr(get_plugin_manager(),'_delivery_transaction_providers',{})
    assert d.prepare_optional_delivery('telegram',{},'body') is None
    assert d.strip_delivery_controls('body ⟦HERMES_CRON_DECISIONS {"buttons":[]}⟧')=='body'

def test_native_failed_load_revokes(tmp_path):
    root=tmp_path/'delivery-example';root.mkdir()
    (root/'__init__.py').write_text("class P:\n def prepare(self,*a):pass\n def settle(self,*a):pass\ndef register(ctx):\n ctx.register_delivery_transaction_provider('telegram',P())\n raise RuntimeError('failed load')\n")
    m=PluginManager();m._load_plugin(PluginManifest(name='delivery-example',key='delivery-example',path=str(root),source='user'))
    assert m._plugins['delivery-example'].error
    assert not m._delivery_transaction_providers

def test_scheduler_wiring():
    from pathlib import Path
    text=(Path(__file__).resolve().parents[2]/'cron/scheduler_delivery.py').read_text()
    assert text.count("lease.settle('ambiguous_timeout')")>=3
    assert "lease.settle('failed_before_send')" in text
    assert 'prepare_optional_delivery(t.platform_name' in text


@pytest.mark.parametrize('mode', ['confirmed', 'missing-id', 'failed-result', 'runtime-error', 'metadata', 'empty'])
def test_real_standalone_caller_settles_without_replay(monkeypatch, mode):
    import ast, asyncio, concurrent.futures, contextvars, logging, sys, __future__
    from pathlib import Path
    from unittest.mock import AsyncMock
    provider = SimpleNamespace(prepare=lambda ctx, body: {
        'body': '' if mode == 'empty' else body,
        'metadata': {'controls': True} if mode == 'metadata' else {},
        'transaction': object()}, settle=Mock(return_value=True))
    monkeypatch.setattr(get_plugin_manager(), '_delivery_transaction_providers', {'telegram': provider})
    result = {'success': mode != 'failed-result', 'message_id': None if mode == 'missing-id' else 'mid'}
    send = AsyncMock(return_value=result)
    if mode == 'runtime-error':
        send.side_effect = RuntimeError('transport failed after dispatch')
    monkeypatch.setitem(sys.modules, 'tools.send_message_tool', SimpleNamespace(_send_to_platform=send))
    source = Path(__file__).resolve().parents[2]/'cron/scheduler_delivery.py'
    node = next(n for n in ast.parse(source.read_text()).body
                if isinstance(n, ast.FunctionDef) and n.name == '_standalone_send')
    namespace = dict(asyncio=asyncio, concurrent=concurrent, contextvars=contextvars,
                     logger=logging.getLogger(__name__),
                     _sched=SimpleNamespace(_interpreter_shutting_down=lambda *args: False),
                     _get_standalone_send_timeout=lambda: 1,
                     _result_field=lambda result, key: result.get(key))
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(source), 'exec',
                 flags=__future__.annotations.compiler_flag), namespace)
    target = SimpleNamespace(platform_name='telegram', platform='telegram', pconfig=None,
                             chat_id='peer', thread_id=None, job={'id': 'fixture'}, where='peer')
    namespace['_standalone_send'](target, 'body', [])
    assert send.await_count == (0 if mode in {'metadata', 'empty'} else 1)
    expected = 'confirmed' if mode == 'confirmed' else (
        'failed_before_send' if mode in {'metadata', 'empty'} else 'ambiguous_timeout')
    assert provider.settle.call_count == 1
    assert provider.settle.call_args.args[1] == expected
