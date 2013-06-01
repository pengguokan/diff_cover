"""
High-level integration tests of diff-cover tool.
"""

import unittest
from mock import patch
import os
import os.path
from subprocess import Popen
from StringIO import StringIO
import tempfile
import shutil
from textwrap import dedent
from diff_cover.tool import main
from diff_cover.diff_reporter import GitDiffError


class DiffCoverIntegrationTest(unittest.TestCase):
    """
    High-level integration test.
    The `git diff` is a mock, but everything else is our code.
    """

    GIT_DIFF_OUTPUT = dedent("""
    diff --git a/subdir/file1.py b/subdir/file1.py
    index 629e8ad..91b8c0a 100644
    --- a/subdir/file1.py
    +++ b/subdir/file1.py
    @@ -3,6 +3,7 @@ Text
    More text
    Even more text

    @@ -33,10 +34,13 @@ Text
     More text
    +Another change

    diff --git a/subdir/file2.py b/subdir/file2.py
    index 629e8ad..91b8c0a 100644
    --- a/subdir/file2.py
    +++ b/subdir/file2.py
    @@ -3,6 +3,7 @@ Text
     More text
    -Even more text

    diff --git a/README.rst b/README.rst
    index 629e8ad..91b8c0a 100644
    @@ -3,6 +3,7 @@ Text
     More text
    -Even more text
    """).strip()

    COVERAGE_XML = dedent("""
    <coverage>
        <packages>
            <classes>
                <class filename="subdir/file1.py">
                    <methods />
                    <lines>
                        <line hits="0" number="2" />
                        <line hits="1" number="7" />
                        <line hits="0" number="8" />
                    </lines>
                </class>
                <class filename="subdir/file2.py">
                    <methods />
                    <lines>
                        <line hits="0" number="2" />
                        <line hits="1" number="7" />
                        <line hits="0" number="8" />
                    </lines>
                </class>
            </classes>
        </packages>
    </coverage>
    """)

    EXPECTED_CONSOLE_REPORT = dedent("""
    Diff Coverage
    -------------
    subdir/file2.py (50%): Missing line(s) 8
    subdir/file1.py (50%): Missing line(s) 8
    -------------
    Total:   4 line(s)
    Missing: 2 line(s)
    Coverage: 50%
    """).strip() + "\n"

    EXPECTED_HTML_REPORT = dedent("""
    <!DOCTYPE html PUBLIC "-//W3C//DTD HTML 4.01//EN" "http://www.w3.org/TR/html4/strict.dtd">
    <html>
    <head>
    <meta http-equiv='Content-Type' content='text/html; charset=utf-8'>
    <title>Diff Coverage</title>
    </head>
    <body>
    <h1>Diff Coverage</h1>
    <table border="1">
    <tr>
    <th>Source File</th>
    <th>Diff Coverage (%)</th>
    <th>Missing Line(s)</th>
    </tr>
    <tr>
    <td>subdir/file2.py</td>
    <td>50%</td>
    <td>8</td>
    </tr>
    <tr>
    <td>subdir/file1.py</td>
    <td>50%</td>
    <td>8</td>
    </tr>
    </table>
    <ul>
    <li><b>Total</b>: 4 line(s)</li>
    <li><b>Missing</b>: 2 line(s)</li>
    <li><b>Coverage</b>: 50%</li>
    </ul>
    </body>
    </html>
    """).strip()

    # Path to the temporary coverage XML file, so we can clean it up later
    _coverage_xml_path = None

    def setUp(self):
        """
        Create fake coverage XML file
        """
        # Write the XML coverage report to a temp directory
        self._coverage_xml_path = self._write_to_temp(self.COVERAGE_XML)

        # Create mocks 
        self._mock_communicate = patch.object(Popen, 'communicate').start()
        self._mock_sys = patch('diff_cover.tool.sys').start()

    def tearDown(self):
        """
        Clean up the XML coverage report we created.
        Undo all patches.
        """
        os.remove(self._coverage_xml_path)
        patch.stopall()

    def test_diff_cover_console(self):

        # Patch the output of `git diff`
        self._set_git_diff_output(self.GIT_DIFF_OUTPUT, "")

        # Capture stdout to a string buffer
        string_buffer = StringIO()
        self._capture_stdout(string_buffer)

        # Patch sys.argv
        self._set_sys_args(['diff-cover', self._coverage_xml_path,
                            '--git-branch', 'master'])

        # Run diff-cover
        main()

        # Check the output to stdout
        report = string_buffer.getvalue()
        self.assertEqual(report, self.EXPECTED_CONSOLE_REPORT)

    def test_diff_cover_html(self):

        # Patch the output of `git diff`
        self._set_git_diff_output(self.GIT_DIFF_OUTPUT, "")

        # Create a temporary directory to hold the output HTML report
        # Add a cleanup to ensure the directory gets deleted
        temp_dir = tempfile.mkdtemp()
        self.addCleanup(lambda: shutil.rmtree(temp_dir))

        # Patch sys.argv
        report_path = os.path.join(temp_dir, 'diff_coverage.html')
        self._set_sys_args(['diff-cover', self._coverage_xml_path,
                            '--git-branch', 'master',
                            '--html-report', report_path])

        # Run diff-cover
        main()

        # Load the content of the HTML report
        with open(report_path) as html_report:
            html = html_report.read()
            self.assertEqual(html, self.EXPECTED_HTML_REPORT)

    def test_git_diff_error(self):

        # Patch sys.argv
        self._set_sys_args(['diff-cover', self._coverage_xml_path,
                            '--git-branch', 'master'])

        # Configure git diff to output to stderr
        self._set_git_diff_output("", "fatal error")

        # Expect an error
        with self.assertRaises(GitDiffError):
            main()

    def _set_sys_args(self, argv):
        """
        Patch sys.argv with the argument array `argv`.
        """
        self._mock_sys.argv = argv

    def _capture_stdout(self, string_buffer):
        """
        Redirect output sent to `sys.stdout` to the StringIO buffer
        `string_buffer`.
        """
        self._mock_sys.stdout = string_buffer

    def _set_git_diff_output(self, stdout_str, stderr_str):
        """
        Patch the call to `git diff` to always output
        `stdout_str` to stdout and `stderr_str` to stderr.
        """
        self._mock_communicate.return_value = (stdout_str, stderr_str)

    def _write_to_temp(self, text):
        """
        Write `text` to a temporary file, then return the path.
        """
        _, path = tempfile.mkstemp()

        with open(path, "w") as file_handle:
            file_handle.write(text)
            file_handle.close()

        return path
