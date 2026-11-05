"""External, bounded early-release observations; never rewrites an old failure.

Called with the existing packaged harness's owned process/input functions. A
hidden full-monitor preview is evidence of preparation, not proof of every
internal acceptance state. Unknown acceptance stays unknown in the report.
"""
import ctypes as C
from ctypes import wintypes as W
import json
import time

FUNCTIONAL_SECONDS = 2.0


def classify(*, cancelled, zero, prepared_before_move, count, exact, focused, clean):
    if not clean or count > 1:
        return 'FAIL'
    if cancelled or zero:
        return 'PASS' if count == 0 else 'FAIL'
    if count == 1:
        return 'PASS' if exact and focused else 'FAIL'
    return 'FAIL' if prepared_before_move else 'UNRESOLVED: acceptance not externally observed'


def exercise(c, case):
    from PySide6.QtTest import QTest
    from PySide6.QtGui import QImage
    from mini_whiteboard.geometry import Rect
    from mini_whiteboard.settings import SHADOW
    from mini_whiteboard.hotkey_config import ACTIONS
    from mini_whiteboard import windows as n

    output, process, user = c['args'].output, c['process'], c['u']
    key, boards, previews = c['key'], c['boards'], c['previews']
    foreground, target = c['foreground'], c['target_hwnd']
    report = {'case': case, 'functional_deadline_seconds': FUNCTIONAL_SECONDS,
              'deadline_basis': 'Diagnostic liveness bound, four times the previously observed approximately 0.5 s delay; not a performance SLA.',
              'acceptance_limit': 'Only owned preview creation is externally observable; absence cannot prove that the hotkey was never accepted.',
              'events': [], 'prelude': [], 'result': 'INCOMPLETE'}
    path = output/'early-release.json'
    origin = time.perf_counter_ns()
    monitor_rects = [m.rect for m in n.monitors()]
    pending_pixels=[]
    observation_cost=[]

    def now():
        return (time.perf_counter_ns()-origin)/1e6

    def save():
        path.write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')

    def observe(label):
        observation_started=time.perf_counter_ns()
        windows = []
        for hwnd in c['windows'](include_hidden=True):
            try:
                rect = c['bounds'](hwnd)
                windows.append({'hwnd': hwnd, 'title': c['name'](hwnd), 'visible': bool(c['visible'](hwnd)),
                                'rect': vars(rect), 'preview_geometry': rect in monitor_rects})
            except RuntimeError:
                pass
        row = {'event': label, 'ms': now(), 'windows': windows,
               'board_count': len(boards()), 'visible_preview': bool(previews()),
               'preparation_observed': any(w['preview_geometry'] for w in windows),
               'foreground': int(foreground() or 0), 'cursor': list(n.cursor_position()),
               'held': [vk for vk in c['pressed'] if user.GetAsyncKeyState(vk) & 0x8000],
               'process_exit': process.poll()}
        report['events'].append(row)
        observation_cost.append((time.perf_counter_ns()-observation_started)/1e6)
        return row

    def wait_until(predicate, seconds=FUNCTIONAL_SECONDS):
        deadline = time.monotonic()+seconds
        while time.monotonic() < deadline and process.poll() is None:
            if predicate():
                return True
            QTest.qWait(5)
        return bool(predicate())

    def resources(label):
        handle = n.bind(n.kernel32,'OpenProcess',W.HANDLE,W.DWORD,W.BOOL,W.DWORD)(0x1000, False, process.pid)
        if not handle:
            return {'stage': label, 'error': 'OpenProcess failed'}
        try:
            count = W.DWORD()
            n.bind(n.kernel32, 'GetProcessHandleCount', W.BOOL, W.HANDLE, C.POINTER(W.DWORD))(handle, C.byref(count))
            gui = n.bind(user, 'GetGuiResources', W.DWORD, W.HANDLE, W.DWORD)
            return {'stage': label, 'handles': count.value, 'gdi': gui(handle, 0), 'user': gui(handle, 1),
                    'owned_top_level_windows': len(c['windows'](True))}
        finally:
            n.bind(n.kernel32,'CloseHandle',W.BOOL,W.HANDLE)(handle)

    def finish_prelude(chord, first, begin, end, ordinal, capture_observation=False):
        c['configure_trace']('prelude-'+str(ordinal))
        c['start'](chord, begin)
        start = now()
        QTest.qWait(120)
        at120 = observe('prelude-120ms')
        if not at120['visible_preview'] and not wait_until(lambda: bool(previews())):
            raise RuntimeError('Prelude preview missing beyond functional bound')
        c['set_cursor'](*end)
        for _ in range(6):
            key(chord[-1]); QTest.qWait(12)
        if capture_observation:
            n.capture_rect(Rect(150,190,430,290)).save(str(output/'prelude-preview.png'))
        for vk in (first,)+tuple(v for v in reversed(chord) if v != first):
            key(vk, True); QTest.qWait(150)
            if len(boards()) != 1 and not wait_until(lambda: len(boards()) == 1):
                raise RuntimeError('Prelude result missing beyond functional bound')
        if capture_observation:
            n.capture_rect(Rect(180,220,360,220)).save(str(output/'prelude-result.png'))
        report['prelude'].append({'ordinal':ordinal,'preview_at_original_120ms':at120['visible_preview'],
                                 'elapsed_ms':now()-start})
        c['settled']('prelude'); c['close_boards'](); save()

    def prelude():
        import itertools
        binding = c['configuration'].create
        variants = tuple(itertools.product(*(c['modifier_keys'][m] for m in ('meta','ctrl','alt','shift') if m in binding.modifiers)))
        count = case.get('prelude', 0)
        if not count:
            return
        points = (((180,220),(540,440)),((540,440),(180,220)),((180,440),(540,220)),((540,220),(180,440)))
        completed = 0
        for modifiers in variants:
            chord = (*modifiers,binding.windows_key)
            for index, first in enumerate(chord):
                if count != 'full' and completed >= int(count):
                    return
                begin,end = points[index]
                finish_prelude(chord,first,begin,end,completed,capture_observation=completed==0)
                completed += 1
            if count == 'full':
                c['start'](chord,(180,220)); QTest.qWait(100)
                c['set_cursor'](540,440); key(27); QTest.qWait(50); key(27,True)
                for _ in range(8):
                    key(binding.windows_key); QTest.qWait(15)
                c['settled']('prelude cancellation')
                if boards() or previews():
                    raise RuntimeError('Prelude cancellation left a window')
        if count == 'full':
            chord = (*variants[0],binding.windows_key)
            for _ in range(3):
                c['start'](chord,(180,220)); QTest.qWait(20); c['set_cursor'](540,440)
                for vk in reversed(chord): key(vk,True)
                QTest.qWait(200)
                if len(boards()) != 1 and not wait_until(lambda: len(boards()) == 1):
                    raise RuntimeError('Prelude rapid gesture lost')
                c['settled']('prelude rapid'); c['close_boards']()
            c['start'](chord,(180,220)); QTest.qWait(40); c['drain']()
            c['settled']('prelude zero area')
            if boards() or previews(): raise RuntimeError('Prelude zero-area cancellation failed')

    def gesture(spec, label):
        previous_boards=set(boards())
        binding = c['configuration'].create if spec['action']=='W' else c['configuration'].capture
        modifiers = tuple(c['modifier_keys'][m][spec.get('side',0)] for m in ('meta','ctrl','alt','shift') if m in binding.modifiers)
        chord = (*modifiers,binding.windows_key)
        first = chord[spec.get('release_index',-1)]
        begin, end = (180,220), (540,440)
        zero, cancel = bool(spec.get('zero')), bool(spec.get('escape'))
        if zero: end = begin
        if cancel:
            probe_id = 0x7D41
            if not user.RegisterHotKey(None,probe_id,binding.windows_modifiers|n.MOD_NOREPEAT,27):
                return {'result':'NOT RUN: Escape chord conflict','scope':label}
            user.UnregisterHotKey(None,probe_id)
        c['configure_trace'](label)
        c['focus']()
        expected_pixels = n.capture_rect(Rect(180,220,360,220)) if spec['action']=='Q' and not zero and not cancel else None
        c['start'](chord,begin)
        started = now()
        snapshots = [observe(label+'-after-injection')]
        moved = False
        repeat_at = {1,2} if spec.get('repeats') else set()
        repeated = set()
        hold = spec['hold_ms']
        while now()-started < hold:
            elapsed = now()-started
            if not moved and elapsed >= min(15,hold/2):
                before_move = observe(label+'-before-move')
                snapshots.append(before_move)
                c['set_cursor'](*end); moved = True
            for fraction in repeat_at-repeated:
                if elapsed >= hold*fraction/3:
                    key(binding.windows_key); repeated.add(fraction)
            QTest.qWait(1)
            snapshots.append(observe(label+'-holding'))
        if not moved:
            snapshots.append(observe(label+'-before-move'))
            c['set_cursor'](*end)
        at_release = observe(label+'-at-release')
        release_time = now()
        if cancel:
            key(27)
        else:
            key(first,True)
        completion = None
        until = time.monotonic()+FUNCTIONAL_SECONDS
        while time.monotonic() < until and process.poll() is None:
            QTest.qWait(5)
            snapshot = observe(label+'-after-release')
            new_boards=set(boards())-previous_boards
            if new_boards and completion is None:
                completion = snapshot
            if new_boards and not snapshot['visible_preview']:
                break
            if (zero or cancel) and any(s['preparation_observed'] for s in snapshots) and not snapshot['preparation_observed']:
                break
        if cancel: key(27,True)
        for vk in tuple(c['pressed']): key(vk,True)
        QTest.qWait(5)  # Dispatch this driver's native input observations.
        final = observe(label+'-after-key-drain')
        found = list(set(boards())-previous_boards)
        exact = focused = False
        paper = None
        if len(found)==1:
            r = c['bounds'](found[0]); shadow=round(SHADOW*user.GetDpiForWindow(found[0])/96)
            paper=Rect(r.x+shadow,r.y+shadow,r.width-2*shadow,r.height-2*shadow)
            exact = paper == Rect(180,220,360,220)
            focused = foreground()==found[0]
        prepared = next((s for s in snapshots if s['preparation_observed']),None)
        before_move = next(s for s in snapshots if s['event'].endswith('before-move'))
        prepared_before_move = any(s['preparation_observed'] and s['ms']<=before_move['ms'] for s in snapshots)
        clean = not final['visible_preview'] and not final['held'] and process.poll() is None
        if not found: clean = clean and foreground()==target
        status=classify(cancelled=cancel,zero=zero,prepared_before_move=prepared_before_move,
                        count=len(found),exact=exact,focused=focused,clean=clean)
        visible_at = next((s['ms'] for s in report['events'] if s['event'].startswith(label+'-') and s['visible_preview']),None)
        result={'scope':label,'result':status,'injection_finished_ms':started,'release_ms':release_time,
                'actual_hold_ms':release_time-started,'first_released_vk':27 if cancel else first,
                'preview_visible_at_release':at_release['visible_preview'],
                'preparation_observed_before_move':prepared_before_move,
                'preparation_first_ms':prepared['ms'] if prepared else None,
                'preview_first_ms':visible_at,'preview_latency_ms':visible_at-started if visible_at else None,
                'board_count':len(found),'exact_geometry':exact,'paper':vars(paper) if paper else None,
                'focus_on_result':focused,'clean':clean,'completion_ms':completion['ms'] if completion else None,
                'acceptance':'externally observed preparation before movement' if prepared_before_move else 'not established by external observation'}
        if expected_pixels is not None and exact and focused:
            pending_pixels.append((result,found[0],expected_pixels,label))
        return result

    def verify_pixels(result,hwnd,expected_pixels,label):
            user.SetForegroundWindow(hwnd)
            if foreground()!=hwnd:
                result['capture_export_error']='Owned board did not acquire focus'
                result['result']='UNRESOLVED: clipboard inspection focus unavailable'
                return
            # Verify the actual captured object through normal context-menu and
            # clipboard commands. The owned target is static in the sampled region.
            c['app'].clipboard().clear()
            c['set_cursor'](360,330); c['mouse'](8,0,0,0,0); c['mouse'](16,0,0,0,0)
            QTest.qWait(100)
            for vk in (0x24,0x28,0x0D): key(vk); key(vk,True); QTest.qWait(30)
            key(0xA2); key(ord('C')); key(ord('C'),True); key(0xA2,True)
            wait_until(lambda:not c['app'].clipboard().image().isNull(),1)
            image=c['app'].clipboard().image()
            expected_pixels.save(str(output/(label+'-expected.png')))
            if not image.isNull(): image.save(str(output/(label+'-clipboard.png')))
            result['capture_pixels_equal']=image.convertToFormat(QImage.Format.Format_RGBA8888)==expected_pixels.convertToFormat(QImage.Format.Format_RGBA8888)
            if not result['capture_pixels_equal']: result['result']='FAIL: captured clipboard pixels differ or export was unavailable'

    try:
        required={ACTIONS[0] if case['action']=='W' else ACTIONS[1]}
        if case.get('prelude'): required.add(ACTIONS[0])
        if not required <= c['available_actions']:
            report['result']='NOT RUN: configured OS shortcut conflict'
            return 1
        save(); report['resources']=[resources('fresh')]
        prelude(); report['resources'].append(resources('after-prelude')); save()
        report['primary']=gesture(case,'primary'); save()
        # The next gesture is a separate control, without restarting or a warm-up.
        report['next']=gesture({'action':case['action'],'hold_ms':120,'release_index':-1},'next')
        QTest.qWait(1000)  # Observe late callbacks after the two consecutive gestures, never before the next input.
        expected_count=report['primary'].get('board_count',0)+report['next'].get('board_count',0)
        report['late_callback_check']={'expected_boards':expected_count,'actual_boards':len(boards()),'preview_remaining':bool(previews())}
        late_clean=len(boards())==expected_count and not previews()
        for item in pending_pixels: verify_pixels(*item)
        if boards(): c['close_boards']()
        report['closed_board_cleanup']=not boards() and not previews() and process.poll() is None
        report['resources'].append(resources('after-next'))
        statuses=[report['primary']['result'],report['next']['result']]
        report['result']='PASS' if all(s=='PASS' for s in statuses) else 'FAIL' if any(s.startswith('FAIL') for s in statuses) else 'UNRESOLVED'
        if not late_clean or not report['closed_board_cleanup']: report['result']='FAIL'
        return 0 if report['result']=='PASS' else 1
    except Exception as error:
        report['error']=str(error)
        raise
    finally:
        report['observer_cost']={'samples':len(observation_cost),'total_ms':sum(observation_cost),
            'maximum_sample_ms':max(observation_cost,default=0),
            'limit':'Only this probe sampling is measured; keyboard/window hooks and source profiling also affect scheduling.'}
        save()
