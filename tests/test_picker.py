import unittest
from unittest.mock import patch, MagicMock
from omadocs.errors import Fault
from omadocs.picker import decode_selection, pick, MAX_OUTPUT


class PickerTest(unittest.TestCase):
    def test_multiple_literal_paths_round_trip_to_uris(self):
        from omadocs.files import parse_path
        paths = ['/tmp/Informe México $(literal) "quote".docx', '/tmp/100% ready.xlsx']
        result = decode_selection(('SEPARATOR'.join(paths) + '\n').encode(), 'SEPARATOR', 'files')
        self.assertEqual([str(parse_path(uri)) for uri in result['files']], paths)

    def test_empty_selection_is_cancelled(self):
        self.assertEqual(decode_selection(b'', 'SEP', 'files'), {'cancelled': True})

    def test_ambiguous_control_characters_and_remote_paths_are_rejected(self):
        for value in (b'/tmp/new\nline.docx\n', b'/tmp/tab\tname.docx\n', b'https://example.test/file.docx\n', b'relative.docx\n'):
            with self.assertRaises(Fault):
                decode_selection(value, 'SEP', 'files')

    def test_limits_and_credentials_single_selection(self):
        for value, kind in ((b'x' * (MAX_OUTPUT + 1), 'files'), ('SEP'.join(['/tmp/a.docx'] * 65).encode(), 'files'), (b'/tmp/a.jsonSEP/tmp/b.json', 'credentials')):
            with self.assertRaises(Fault):
                decode_selection(value, 'SEP', kind)

    def test_missing_picker_has_actionable_fallback(self):
        with patch('omadocs.picker.subprocess.Popen', side_effect=FileNotFoundError):
            result = pick('files')
        self.assertIn('Open with', result['error']['message'])

    def test_cancel_does_not_submit_paths(self):
        process = MagicMock()
        process.stdout.read.return_value = b'/tmp/not-submitted.docx\n'
        process.wait.return_value = 1
        process.poll.return_value = 1
        with patch('omadocs.picker.subprocess.Popen', return_value=process) as spawn:
            self.assertEqual(pick('files'), {'cancelled': True})
        command = spawn.call_args.args[0]
        self.assertEqual(command[0], 'zenity')
        self.assertIn('--multiple', command)
        self.assertNotIn('shell', spawn.call_args.kwargs)

    def test_invalid_mode_never_opens_dialog(self):
        with patch('omadocs.picker.subprocess.Popen') as spawn:
            with self.assertRaises(Fault):
                pick('anything')
        spawn.assert_not_called()
