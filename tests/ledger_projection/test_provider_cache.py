"""Provider lifecycle uses only synthetic temporary ledgers."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import date
from decimal import Decimal
import builtins
import os
import sys
from types import ModuleType
from threading import Event

from beancount import loader
from beancount.core import data
from beancount.core.amount import Amount
from beancount.core.position import Cost, CostSpec
import pytest

from backend.infrastructure.persistence.beancount import beancount_provider as provider_module
from backend.infrastructure.persistence.beancount import ledger_write as writer
from backend.infrastructure.persistence.beancount.beancount_provider import BeancountServiceProvider as Provider
from backend.infrastructure.persistence.beancount.ledger_write import (
    CandidateSnapshot, LedgerSourceUnsupported, LedgerWriteConflict, ProjectionReceipt,
    ledger_lock, sample_source_state,
)


@pytest.fixture(autouse=True)
def reset_cache():
    Provider.clear()
    yield
    Provider.clear()


@pytest.fixture
def source(tmp_path):
    main = tmp_path / 'main.beancount'
    child = tmp_path / 'nested' / 'entries.beancount'
    child.parent.mkdir()
    main.write_text('plugin "beancount.plugins.auto_accounts"\ninclude "nested/entries.beancount"\n')
    child.write_text(
        '2025-01-01 * "first"\n'
        '  Assets:Cash  -1 CNY\n'
        '  Expenses:Food  1 CNY\n'
    )
    return main, child


@pytest.fixture
def calls(monkeypatch):
    observed = []
    official = loader._uncached_load_file
    def load(*args, **kwargs):
        observed.append(args[0])
        return official(*args, **kwargs)
    monkeypatch.setattr(loader, '_uncached_load_file', load)
    return observed


def replace_preserving_stat(path, old, new):
    stat = path.stat()
    path.write_text(path.read_text().replace(old, new))
    os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns))
    assert path.stat().st_size == stat.st_size


def test_hit_and_repeated_same_stat_modifications(source, calls):
    main, child = source
    first = Provider.get_service(main)
    assert Provider.get_service(main.parent / '.' / main.name) is first
    assert len(calls) == 1
    for old, new in [('first', 'other'), ('other', 'third')]:
        replace_preserving_stat(child, old, new)
        refreshed = Provider.get_service(main)
        assert refreshed is not first
        assert Provider.get_service(main) is refreshed
    assert len(calls) == 3
    assert first.entries[-1].narration == 'first'


def test_current_nested_include_members_are_resampled(source, calls):
    main, child = source
    first = Provider.get_service(main)
    grandchild = child.parent / 'more.beancount'
    grandchild.write_text('; new member\n')
    child.write_text(child.read_text() + 'include "more.beancount"\n')
    second = Provider.get_service(main)
    assert second is not first
    grandchild.write_text('; changed member\n')
    assert Provider.get_service(main) is not second
    assert len(calls) == 3


def test_invalidate_reload_clear_and_path_switch(source, calls, tmp_path):
    main, _ = source
    first = Provider.get_service(main)
    Provider.invalidate()
    second = Provider.get_service(main)
    assert second is not first
    Provider.reload()
    third = Provider.get_service(main)
    assert third is not second
    Provider.reload()
    assert Provider.get_service(main) is not third
    Provider.clear()
    fourth = Provider.get_service(main)
    other = tmp_path / 'other.beancount'
    other.write_text('; another ledger\n')
    assert Provider.get_service(other).ledger_path == other
    assert Provider.get_service(main) is not fourth
    assert len(calls) == 7


def test_direct_reload_success_invalidates_generation(source, calls):
    main, _ = source
    first = Provider.get_service(main)
    generation = first.load_generation
    first.reload()
    assert first.load_generation == generation + 1
    assert Provider.get_service(main) is not first
    assert len(calls) == 3


def test_direct_reload_failure_invalidates_generation_and_preserves_old_view(source, monkeypatch):
    main, _ = source
    first = Provider.get_service(main)
    entries = first.entries
    generation = first.load_generation
    official = loader._uncached_load_file
    def fail(*args, **kwargs):
        raise OSError('synthetic loader failure')
    monkeypatch.setattr(loader, '_uncached_load_file', fail)
    with pytest.raises(OSError):
        first.reload()
    assert first.load_generation == generation + 1
    assert first.entries is entries
    monkeypatch.setattr(loader, '_uncached_load_file', official)
    assert Provider.get_service(main) is not first


def test_provider_reload_failure_does_not_mutate_old_holder(source, monkeypatch):
    main, _ = source
    first = Provider.get_service(main)
    entries = first.entries
    generation = first.load_generation
    official = loader._uncached_load_file
    def fail(*args, **kwargs):
        raise OSError('synthetic loader failure')
    monkeypatch.setattr(loader, '_uncached_load_file', fail)
    with pytest.raises(OSError):
        Provider.reload()
    assert first.entries is entries
    assert first.load_generation == generation
    monkeypatch.setattr(loader, '_uncached_load_file', official)
    assert Provider.get_service(main) is not first


def test_unstable_formal_load_cancels_binding(source, monkeypatch):
    main, child = source
    first = Provider.get_service(main)
    official = loader._uncached_load_file
    def mutate(*args, **kwargs):
        result = official(*args, **kwargs)
        child.write_text(child.read_text() + '; mutation during load\n')
        return result
    monkeypatch.setattr(loader, '_uncached_load_file', mutate)
    with pytest.raises(LedgerWriteConflict):
        Provider.reload()
    monkeypatch.setattr(loader, '_uncached_load_file', official)
    assert Provider.get_service(main) is not first


def test_unknown_plugin_keeps_formal_execution_without_cache(source, calls, monkeypatch):
    main, _ = source
    external = main.parent / 'plugin-input.txt'
    external.write_text('first')
    executions = []
    module = ModuleType('untracked_external_plugin')
    def read_external(entries, options):
        value = external.read_text()
        executions.append(value)
        return [entry._replace(narration=value) if isinstance(entry, data.Transaction)
                else entry for entry in entries], []
    module.__plugins__ = ('read_external',)
    module.read_external = read_external
    monkeypatch.setitem(sys.modules, module.__name__, module)
    main.write_text(main.read_text().replace(
        'include "nested/entries.beancount"',
        'plugin "untracked_external_plugin"\ninclude "nested/entries.beancount"',
    ))
    first = Provider.get_service(main)
    assert not first.errors
    assert first.entries[-1].narration == 'first'
    external.write_text('other')
    second = Provider.get_service(main)
    assert second is not first
    assert second.entries[-1].narration == 'other'
    external.write_text('third')
    Provider.reload()
    assert Provider._state.service.entries[-1].narration == 'third'
    external.write_text('fourth')
    assert Provider.get_service(main).entries[-1].narration == 'fourth'
    assert executions == ['first', 'other', 'third', 'fourth']
    assert len(calls) == 4


def test_error_views_do_not_hit_cache(source, calls):
    main, child = source
    child.write_text('2025-01-01 * "unbalanced"\n  Assets:Cash  1 CNY\n')
    first = Provider.get_service(main)
    assert first.errors
    assert Provider.get_service(main) is not first
    assert len(calls) == 2


def candidate(path):
    entries, errors, options = writer.load_ledger_file(str(path))
    assert not errors
    state = sample_source_state(path)
    options = deepcopy(options)
    options['input_hash'] = 'mirror-value'
    snapshot = CandidateSnapshot(entries, {p: fp[2] for p, fp in state.fingerprints.items()}, options, path)
    receipt = ProjectionReceipt(snapshot, state.fingerprints, True, True)
    return snapshot, receipt


def test_publish_replaces_holder_and_clones_complete_view(source, calls):
    main, child = source
    old = Provider.get_service(main)
    child.write_text(child.read_text().replace('first', 'saved'))
    snapshot, receipt = candidate(main)
    count = len(calls)
    with ledger_lock(main):
        assert Provider.publish(snapshot, receipt)
    published = Provider.get_service(main)
    assert published is not old
    assert published.entries[-1].narration == 'saved'
    assert old.entries[-1].narration == 'first'
    assert published.entries is not snapshot.entries
    assert published.options is not snapshot.options
    assert published.options['input_hash'] == loader.compute_input_hash(published.options['include'])
    snapshot.entries[-1].meta['changed'] = True
    snapshot.options['title'] = 'changed'
    assert 'changed' not in published.entries[-1].meta
    assert published.options['title'] != 'changed'
    assert len(calls) == count
    replace_preserving_stat(child, 'saved', 'other')
    assert Provider.get_service(main) is not published
    replace_preserving_stat(child, 'other', 'third')
    assert Provider.get_service(main).entries[-1].narration == 'third'


@pytest.mark.parametrize('reason', ['missing', 'identity', 'fallback', 'not_ready', 'source', 'options'])
def test_publish_rejects_uncommitted_or_mismatched_candidate(source, calls, reason):
    main, child = source
    old = Provider.get_service(main)
    snapshot, receipt = candidate(main)
    if reason == 'missing':
        receipt = None
    elif reason == 'identity':
        receipt = ProjectionReceipt(deepcopy(snapshot), receipt.source_version, True, True)
    elif reason == 'fallback':
        receipt = ProjectionReceipt(snapshot, receipt.source_version, False, True)
    elif reason == 'not_ready':
        receipt = ProjectionReceipt(snapshot, receipt.source_version, True, False)
    elif reason == 'source':
        replace_preserving_stat(child, 'first', 'other')
    else:
        snapshot.options['unknown_physical_path'] = '/untracked-input'
    assert Provider.publish(snapshot, receipt) is False
    count = len(calls)
    assert Provider.get_service(main) is not old
    assert len(calls) == count + 1


def test_publish_failure_is_acceleration_fallback(source, monkeypatch):
    main, _ = source
    old = Provider.get_service(main)
    snapshot, receipt = candidate(main)
    official = loader.compute_input_hash
    def fail(*args):
        raise OSError('synthetic publish error')
    monkeypatch.setattr(loader, 'compute_input_hash', fail)
    assert Provider.publish(snapshot, receipt) is False
    monkeypatch.setattr(loader, 'compute_input_hash', official)
    assert Provider.get_service(main) is not old


def test_publish_follows_shared_ledger_lock(source):
    main, _ = source
    snapshot, receipt = candidate(main)
    started, done = Event(), Event()
    def publish():
        started.set()
        result = Provider.publish(snapshot, receipt)
        done.set()
        return result
    with ThreadPoolExecutor(max_workers=1) as executor:
        with ledger_lock(main):
            pending = executor.submit(publish)
            assert started.wait(timeout=2)
            assert not done.wait(timeout=0.05)
        assert pending.result(timeout=2)
    assert Provider.get_service(main).entries[-1].narration == 'first'


def test_unsupported_source_sampling_preserves_official_loading(source, calls, monkeypatch):
    main, _ = source
    def unsupported(*args):
        raise LedgerSourceUnsupported("synthetic unsupported source")
    monkeypatch.setattr(provider_module, 'sample_source_state', unsupported)
    first = Provider.get_service(main)
    assert not first.errors
    assert Provider.get_service(main) is not first
    assert len(calls) == 2


def test_pending_manifest_rejects_publication(source, monkeypatch):
    main, _ = source
    snapshot, receipt = candidate(main)
    monkeypatch.setattr(provider_module, 'has_pending_write', lambda path: True)
    assert Provider.publish(snapshot, receipt) is False


def test_publish_from_other_ledger_does_not_replace_current_holder(source, tmp_path):
    main, _ = source
    snapshot, receipt = candidate(main)
    other = tmp_path / 'other.beancount'
    other.write_text('; another ledger\n')
    holder = Provider.get_service(other)
    assert Provider.publish(snapshot, receipt) is False
    assert Provider._state.service is holder
    assert Provider._state.ledger_path == other


def test_hit_sampling_conflict_invalidates_old_binding(source, monkeypatch):
    main, _ = source
    old = Provider.get_service(main)
    official = provider_module.sample_source_state
    def conflict(*args):
        raise LedgerWriteConflict("synthetic sampling conflict")
    monkeypatch.setattr(provider_module, 'sample_source_state', conflict)
    with pytest.raises(LedgerWriteConflict):
        Provider.get_service(main)
    monkeypatch.setattr(provider_module, 'sample_source_state', official)
    assert Provider.get_service(main) is not old


def test_pickle_cache_never_supplies_or_mutates_provider_views(source, monkeypatch):
    main, child = source
    cache_path = type(main)(loader.get_cache_filename(loader.PICKLE_CACHE_FILENAME, str(main)))
    cached_load = loader.pickle_cache_function(
        lambda filename: str(cache_path), 0, loader._uncached_load_file,
    )
    old_entries, old_errors, old_options = cached_load(str(main), None, None, None)
    assert not old_errors
    assert old_entries[-1].narration == 'first'
    cache_bytes = cache_path.read_bytes()
    cache_stat = cache_path.stat()
    replace_preserving_stat(child, 'first', 'other')
    assert loader.needs_refresh(old_options) is False
    assert cached_load(str(main), None, None, None)[0][-1].narration == 'first'

    opened = []
    real_open = builtins.open
    def guard_open(file, *args, **kwargs):
        if isinstance(file, (str, os.PathLike)) and os.fspath(file) == str(cache_path):
            opened.append(file)
            raise AssertionError('Provider touched old pickle cache')
        return real_open(file, *args, **kwargs)
    monkeypatch.setattr(builtins, 'open', guard_open)
    current = Provider.get_service(main)
    assert current.entries[-1].narration == 'other'
    assert Provider.get_service(main) is current
    Provider.clear()
    assert Provider.get_service(main).entries[-1].narration == 'other'
    replace_preserving_stat(child, 'other', 'third')
    Provider.reload()
    assert Provider.get_service(main).entries[-1].narration == 'third'
    assert not opened
    assert cache_path.read_bytes() == cache_bytes
    assert cache_path.stat().st_mtime_ns == cache_stat.st_mtime_ns


def test_publish_isolates_nested_transaction_posting_metadata_and_lists(source):
    main, _ = source
    holder = Provider.get_service(main)
    snapshot, receipt = candidate(main)
    transaction = next(entry for entry in snapshot.entries if isinstance(entry, data.Transaction))
    transaction.meta['nested'] = {'values': [['snapshot']]}
    transaction.postings[0].meta['nested'] = {'values': [['posting']]}
    assert Provider.publish(snapshot, receipt)
    published = Provider.get_service(main)
    cloned = next(entry for entry in published.entries if isinstance(entry, data.Transaction))
    assert cloned.postings is not transaction.postings
    assert cloned.tags is transaction.tags
    assert cloned.links is transaction.links
    assert cloned.postings[0].units is transaction.postings[0].units
    cloned.meta['nested']['values'][0].append('published')
    cloned.postings[0].meta['nested']['values'][0].append('published')
    cloned.postings.append(cloned.postings[0])
    published.entries.clear()
    assert transaction.meta['nested']['values'] == [['snapshot']]
    assert transaction.postings[0].meta['nested']['values'] == [['posting']]
    assert len(transaction.postings) == 2
    old = next(entry for entry in holder.entries if isinstance(entry, data.Transaction))
    assert 'nested' not in old.meta
    assert 'nested' not in old.postings[0].meta
    assert len(old.postings) == 2
    transaction.meta['nested']['values'][0].append('candidate')
    transaction.postings[0].meta['nested']['values'][0].append('candidate')
    assert cloned.meta['nested']['values'] == [['snapshot', 'published']]
    assert cloned.postings[0].meta['nested']['values'] == [['posting', 'published']]


@pytest.mark.parametrize('unsupported', ['tags', 'links', 'amount_subclass', 'posting_account', 'cost_field', 'non_transaction'])
def test_clone_falls_back_for_unsupported_mutable_shapes(source, monkeypatch, unsupported):
    main, _ = source
    snapshot, _ = candidate(main)
    transaction = next(entry for entry in snapshot.entries if isinstance(entry, data.Transaction))
    if unsupported == 'tags':
        entry = transaction._replace(tags={'mutable'})
    elif unsupported == 'links':
        entry = transaction._replace(links={'mutable'})
    elif unsupported == 'amount_subclass':
        class MutableAmount(Amount):
            pass
        units = MutableAmount(Decimal('1'), 'CNY')
        units.extra = [['mutable']]
        entry = transaction._replace(postings=[transaction.postings[0]._replace(units=units)])
    elif unsupported == 'posting_account':
        entry = transaction._replace(postings=[transaction.postings[0]._replace(account=['mutable'])])
    elif unsupported == 'cost_field':
        entry = transaction._replace(postings=[transaction.postings[0]._replace(
            cost=Cost(Decimal('1'), 'CNY', date(2025, 1, 1), ['mutable']),
        )])
    else:
        entry = data.Open({'nested': [['mutable']]}, date(2025, 1, 1), 'Assets:Cash', ['CNY'], None)
    calls = []
    real_deepcopy = provider_module.deepcopy
    def copy(value):
        calls.append(value)
        return real_deepcopy(value)
    monkeypatch.setattr(provider_module, 'deepcopy', copy)
    cloned = provider_module._clone_entry(entry)
    assert calls == [entry]
    assert cloned == entry
    assert cloned is not entry
    if unsupported == 'tags':
        cloned.tags.add('changed')
        assert entry.tags == {'mutable'}
    elif unsupported == 'links':
        cloned.links.add('changed')
        assert entry.links == {'mutable'}
    elif unsupported == 'amount_subclass':
        cloned.postings[0].units.extra[0].append('changed')
        assert entry.postings[0].units.extra == [['mutable']]
    elif unsupported == 'posting_account':
        cloned.postings[0].account.append('changed')
        assert entry.postings[0].account == ['mutable']
    elif unsupported == 'cost_field':
        cloned.postings[0].cost.label.append('changed')
        assert entry.postings[0].cost.label == ['mutable']
    else:
        cloned.meta['nested'][0].append('changed')
        cloned.currencies.append('USD')
        assert entry.meta['nested'] == [['mutable']]
        assert entry.currencies == ['CNY']


@pytest.mark.parametrize('cost', [Cost(Decimal('1'), 'CNY', date(2025, 1, 1), None),
                                  CostSpec(Decimal('1'), None, 'CNY', None, None, False)])
def test_clone_reuses_only_verified_immutable_price_cost_and_amount(source, cost):
    main, _ = source
    snapshot, _ = candidate(main)
    transaction = next(entry for entry in snapshot.entries if isinstance(entry, data.Transaction))
    posting = transaction.postings[0]._replace(price=Amount(Decimal('2'), 'CNY'), cost=cost)
    entry = transaction._replace(postings=[posting])
    cloned = provider_module._clone_entry(entry)
    assert cloned.postings[0] is not posting
    assert cloned.postings[0].units is posting.units
    assert cloned.postings[0].price is posting.price
    assert cloned.postings[0].cost is cost
    assert cloned.postings[0].meta is not posting.meta
