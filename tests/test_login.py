"""Registration ownership and external OS choices without changing the host OS."""
from pathlib import Path
import tempfile
from types import SimpleNamespace
from unittest.mock import Mock, PropertyMock, patch
import unittest
from PySide6.QtWidgets import QMessageBox
from tests.qt_case import QtCase, APP
from tests.fake_platform import fake_platform
from mini_whiteboard.login import LoginState
from mini_whiteboard.platform.windows.login import WindowsLogin, RUN_KEY, APPROVAL_KEY, VALUE_NAME
from mini_whiteboard.platform.macos.login import MacLogin
from mini_whiteboard.app import WhiteboardApplication, main


class Registry:
    def __init__(self):self.values={};self.writes=[]
    def get(self,key,name):return self.values.get((key,name))
    def put(self,key,name,value):self.values[key,name]=value;self.writes.append(('put',key,name,value))
    def remove(self,key,name):self.values.pop((key,name),None);self.writes.append(('remove',key,name))


class WindowsLoginTests(unittest.TestCase):
    def setUp(self):
        self.folder=tempfile.TemporaryDirectory();self.addCleanup(self.folder.cleanup)
        self.exe=Path(self.folder.name)/'App café 日本語'/'Mini Whiteboard.exe'
        self.exe.parent.mkdir();self.exe.write_bytes(b'owned test executable')
        self.registry=Registry()
        self.login=WindowsLogin(self.exe,frozen=True,temporary_roots=[],registry=self.registry)

    def test_default_off_and_state_reads_do_not_register(self):
        for _ in range(10):self.assertFalse(self.login.state().enabled)
        self.assertEqual(self.registry.writes,[])

    def test_command_keeps_the_loader_path_instead_of_a_host_backing_path(self):
        backing=Path(self.folder.name)/'host-private-cache'/'Mini Whiteboard.exe'
        with patch.object(Path,'resolve',return_value=backing):
            login=WindowsLogin(self.exe,frozen=True,registry=self.registry)
        self.assertEqual(login.command,f'"{self.exe.absolute()}" --login')
        self.assertNotIn('host-private-cache',login.command)

    def test_unicode_command_enable_disable_preserves_unrelated_values(self):
        self.registry.values[RUN_KEY,'AnotherApp']='untouched'
        self.assertTrue(self.login.set_enabled(True).enabled)
        self.assertEqual(self.registry.values[RUN_KEY,VALUE_NAME],f'"{self.exe.absolute()}" --login')
        self.login.set_enabled(True)
        self.assertEqual(len(self.registry.writes),1)
        self.assertFalse(self.login.set_enabled(False).registered)
        self.assertEqual(self.registry.values,{(RUN_KEY,'AnotherApp'):'untouched'})

    def test_external_disable_is_observed_without_reenabling_approval(self):
        self.login.set_enabled(True);self.registry.writes.clear()
        self.registry.values[APPROVAL_KEY,VALUE_NAME]=b'\x03'+b'\0'*11
        self.assertFalse(self.login.state().enabled)
        self.assertTrue(self.login.state().approval_required)
        self.assertTrue(self.login.set_enabled(True).approval_required)
        self.assertEqual(self.registry.writes,[])
        self.login.set_enabled(False)
        self.assertNotIn((RUN_KEY,VALUE_NAME),self.registry.values)
        self.assertNotIn((APPROVAL_KEY,VALUE_NAME),self.registry.values)

    def test_external_removal_stays_off_across_new_service_and_menu_reads(self):
        self.login.set_enabled(True);self.registry.values.pop((RUN_KEY,VALUE_NAME));self.registry.writes.clear()
        fresh=WindowsLogin(self.exe,frozen=True,temporary_roots=[],registry=self.registry)
        self.assertFalse(fresh.state().registered)
        self.assertFalse(fresh.set_enabled(False).registered)
        self.assertEqual(self.registry.writes,[])

    def test_unknown_approval_format_is_not_reported_as_enabled(self):
        self.login.set_enabled(True)
        self.registry.values[APPROVAL_KEY,VALUE_NAME]=b'future format'
        self.assertTrue(self.login.state().approval_required)
        self.assertFalse(self.login.state().enabled)

    def test_foreign_entry_is_never_replaced_or_removed(self):
        self.registry.values[RUN_KEY,VALUE_NAME]='"C:\\Windows\\notepad.exe" --login'
        before=dict(self.registry.values)
        for enabled in (True,False):
            with self.assertRaises(OSError):self.login.set_enabled(enabled)
        self.assertEqual(self.registry.values,before)
        self.assertEqual(self.registry.writes,[])

    def test_ownership_is_rechecked_before_enable_write(self):
        self.login.set_enabled(True);self.registry.writes.clear()
        original=self.registry.get;reads=[]
        def changed(key,name):
            if key==RUN_KEY:
                reads.append(1)
                if len(reads)>1:return 'foreign command'
            return original(key,name)
        self.registry.get=changed
        with self.assertRaises(OSError):self.login.set_enabled(True)
        self.assertEqual(self.registry.writes,[])

    def test_explicit_choice_moves_a_registration_from_another_copy(self):
        self.registry.values[RUN_KEY,VALUE_NAME]='"C:\\Other folder\\Mini Whiteboard.exe" --login'
        self.assertIn('different',self.login.state().detail)
        self.login.set_enabled(True)
        self.assertEqual(self.registry.values[RUN_KEY,VALUE_NAME],self.login.command)

    def test_source_temporary_and_build_paths_cannot_register(self):
        for frozen,roots in ((False,[]),(True,[self.exe.parent])):
            service=WindowsLogin(self.exe,frozen=frozen,temporary_roots=roots,registry=self.registry)
            self.assertFalse(service.state().available)
            with self.assertRaises(OSError):service.set_enabled(True)
        project=Path(self.folder.name)/'project';(project/'.git').mkdir(parents=True)
        exe=project/'dist'/'Mini Whiteboard.exe';exe.parent.mkdir();exe.write_bytes(b'fixture')
        self.assertFalse(WindowsLogin(exe,frozen=True,temporary_roots=[],registry=self.registry).state().available)
        self.assertEqual(self.registry.writes,[])

    def test_registration_read_and_write_failures_are_reported(self):
        with patch.object(self.registry,'put',side_effect=PermissionError('test denied')):
            with self.assertRaisesRegex(OSError,'test denied'):self.login.set_enabled(True)
        with patch.object(self.registry,'get',side_effect=PermissionError('test denied')):
            self.assertFalse(self.login.state().available)
            with self.assertRaisesRegex(OSError,'test denied'):self.login.set_enabled(False)


    def test_windows_command_limit_counts_utf16_units(self):
        command='"C:\\'+('\U0001f58a'*130)+'\\Mini Whiteboard.exe" --login'
        self.assertLess(len(command),260)
        with patch.object(WindowsLogin,'command',new_callable=PropertyMock,return_value=command):
            self.assertFalse(self.login.state().available)
            with self.assertRaises(OSError):self.login.set_enabled(True)
        self.assertEqual(self.registry.writes,[])


class MacLoginTests(unittest.TestCase):
    def setUp(self):
        self.folder=tempfile.TemporaryDirectory();self.addCleanup(self.folder.cleanup)
        self.apps=Path(self.folder.name)/'Applications';self.bundle=self.apps/'Mini Whiteboard.app'
        self.exe=self.bundle/'Contents/MacOS/Mini Whiteboard';self.exe.parent.mkdir(parents=True);self.exe.write_bytes(b'fixture')
        self.status=0;self.calls=[]
        self.service=SimpleNamespace(status=lambda:self.status,registerAndReturnError_=self.register,
                                     unregisterAndReturnError_=self.unregister)
        self.login=MacLogin(service=self.service,executable=self.exe,bundle=self.bundle,frozen=True,
                            temporary_roots=[],applications_roots=(self.apps,))

    def register(self,_error):self.calls.append('register');self.status=1;return True,None
    def unregister(self,_error):self.calls.append('unregister');self.status=0;return True,None

    def test_default_external_disable_and_explicit_enable_disable(self):
        self.assertFalse(self.login.state().enabled);self.assertEqual(self.calls,[])
        self.assertTrue(self.login.set_enabled(True).enabled)
        self.status=0
        for _ in range(10):self.assertFalse(self.login.state().enabled)
        self.assertEqual(self.calls,['register'])
        self.login.set_enabled(True);self.assertFalse(self.login.set_enabled(False).registered)
        self.assertEqual(self.calls,['register','register','unregister'])

    def test_pending_approval_is_honest_and_can_be_removed(self):
        self.status=2
        self.assertFalse(self.login.state().enabled)
        self.assertTrue(self.login.state().approval_required)
        self.assertTrue(self.login.state().registered)
        self.assertFalse(self.login.set_enabled(False).registered)
        self.assertEqual(self.calls,['unregister'])

    def test_registration_error_is_not_reported_as_enabled(self):
        error=SimpleNamespace(localizedDescription=lambda:'Signing or approval test failure')
        self.service.registerAndReturnError_=lambda _error:(False,error)
        with self.assertRaisesRegex(OSError,'Signing or approval'):self.login.set_enabled(True)
        self.assertFalse(self.login.state().enabled)

    def test_rejected_registration_with_pending_approval_reports_pending(self):
        def pending(_error):self.status=2;return False,None
        self.service.registerAndReturnError_=pending
        self.assertTrue(self.login.set_enabled(True).approval_required)

    def test_source_missing_bundle_and_unknown_status_are_unavailable(self):
        self.login.frozen=False;self.assertFalse(self.login.state().available)
        self.login.frozen=True;self.login.applications_roots=(self.apps/'elsewhere',)
        self.assertFalse(self.login.state().available)
        self.login.applications_roots=(self.apps,);self.status=3
        self.assertFalse(self.login.state().available)
        self.assertEqual(self.calls,[])

    def test_native_read_error_is_reported_without_a_menu_exception(self):
        self.service.status=Mock(side_effect=Exception('native read failed'))
        self.assertFalse(self.login.state().available)


class LoginMenuTests(QtCase):
    def controller(self):
        platform=fake_platform();self.current=LoginState();self.choices=[]
        def set_enabled(value):self.choices.append(value);self.current=LoginState(registered=value,enabled=value);return self.current
        platform.login=SimpleNamespace(state=lambda:self.current,set_enabled=set_enabled,open_settings=Mock())
        controller=WhiteboardApplication(APP,platform=platform)
        self.addCleanup(controller.cleanup)
        self.addCleanup(platform.runtime.close)
        return controller

    def test_menu_is_off_by_default_and_writes_only_after_trigger(self):
        controller=self.controller()
        action=lambda:next(a for a in controller.menu.actions() if a.text()=='Open at login')
        self.assertTrue(action().isCheckable());self.assertFalse(action().isChecked());self.assertEqual(self.choices,[])
        action().trigger();self.assertEqual(self.choices,[True]);self.assertTrue(action().isChecked())
        self.current=LoginState(registered=True,approval_required=True,detail='Requires OS approval')
        controller.rebuild_menu();self.assertFalse(action().isChecked());self.assertEqual(self.choices,[True])
        self.assertEqual(action().toolTip(),'Requires OS approval')
        settings=next(a for a in controller.menu.actions() if a.text()=='Open startup settings…')
        settings.trigger();controller.platform.login.open_settings.assert_called_once()
        remove=next(a for a in controller.menu.actions() if a.text()=='Turn off Open at login')
        remove.trigger();self.assertEqual(self.choices,[True,False])
        self.assertFalse(self.current.registered);self.assertFalse(action().isChecked())
        self.assertNotIn('Turn off Open at login',[a.text() for a in controller.menu.actions()])
        self.assertEqual(controller.boards,[])

    def test_failed_choice_shows_error_and_remains_off(self):
        controller=self.controller();controller.platform.login.set_enabled=Mock(side_effect=OSError('denied'))
        with patch.object(QMessageBox,'warning') as warning:controller.change_login(True)
        warning.assert_called_once();self.assertFalse(self.current.enabled)

    def test_duplicate_manual_and_login_launches_do_not_activate_an_existing_copy(self):
        platform=fake_platform();guard=SimpleNamespace(acquired=False,close=Mock())
        platform.runtime.single_instance=Mock(return_value=guard)
        platform.runtime.activate_existing=Mock()
        for args in (['Mini Whiteboard'],['Mini Whiteboard','--login']):
            with patch('mini_whiteboard.app.get_platform',return_value=platform),patch('sys.argv',args):
                self.assertEqual(main(),0)
        self.assertEqual(guard.close.call_count,2);platform.runtime.activate_existing.assert_not_called()
