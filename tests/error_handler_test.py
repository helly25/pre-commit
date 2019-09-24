# -*- coding: utf-8 -*-
from __future__ import absolute_import
from __future__ import unicode_literals

import io
import os.path
import re
import sys

import mock
import pytest

from pre_commit import error_handler
from testing.util import cmd_output_mocked_pre_commit_home


@pytest.fixture
def mocked_log_and_exit():
    with mock.patch.object(error_handler, '_log_and_exit') as log_and_exit:
        yield log_and_exit


def test_error_handler_no_exception(mocked_log_and_exit):
    with error_handler.error_handler():
        pass
    assert mocked_log_and_exit.call_count == 0


def test_error_handler_fatal_error(mocked_log_and_exit):
    exc = error_handler.FatalError('just a test')
    with error_handler.error_handler():
        raise exc

    mocked_log_and_exit.assert_called_once_with(
        'An error has occurred',
        exc,
        # Tested below
        mock.ANY,
    )

    assert re.match(
        r'Traceback \(most recent call last\):\n'
        r'  File ".+pre_commit.error_handler.py", line \d+, in error_handler\n'
        r'    yield\n'
        r'  File ".+tests.error_handler_test.py", line \d+, '
        r'in test_error_handler_fatal_error\n'
        r'    raise exc\n'
        r'(pre_commit\.error_handler\.)?FatalError: just a test\n',
        mocked_log_and_exit.call_args[0][2],
    )


def test_error_handler_uncaught_error(mocked_log_and_exit):
    exc = ValueError('another test')
    with error_handler.error_handler():
        raise exc

    mocked_log_and_exit.assert_called_once_with(
        'An unexpected error has occurred',
        exc,
        # Tested below
        mock.ANY,
    )
    assert re.match(
        r'Traceback \(most recent call last\):\n'
        r'  File ".+pre_commit.error_handler.py", line \d+, in error_handler\n'
        r'    yield\n'
        r'  File ".+tests.error_handler_test.py", line \d+, '
        r'in test_error_handler_uncaught_error\n'
        r'    raise exc\n'
        r'ValueError: another test\n',
        mocked_log_and_exit.call_args[0][2],
    )


def test_error_handler_keyboardinterrupt(mocked_log_and_exit):
    exc = KeyboardInterrupt()
    with error_handler.error_handler():
        raise exc

    mocked_log_and_exit.assert_called_once_with(
        'Interrupted (^C)',
        exc,
        # Tested below
        mock.ANY,
    )
    assert re.match(
        r'Traceback \(most recent call last\):\n'
        r'  File ".+pre_commit.error_handler.py", line \d+, in error_handler\n'
        r'    yield\n'
        r'  File ".+tests.error_handler_test.py", line \d+, '
        r'in test_error_handler_keyboardinterrupt\n'
        r'    raise exc\n'
        r'KeyboardInterrupt\n',
        mocked_log_and_exit.call_args[0][2],
    )


def test_log_and_exit(cap_out, mock_store_dir):
    with pytest.raises(SystemExit):
        error_handler._log_and_exit(
            'msg', error_handler.FatalError('hai'), "I'm a stacktrace",
        )

    printed = cap_out.get()
    log_file = os.path.join(mock_store_dir, 'pre-commit.log')
    printed_lines = printed.splitlines()
    print(printed_lines)
    assert len(printed_lines) == 7
    assert printed_lines[0] == '### version information'
    assert re.match(r'^pre-commit.version=\d+\.\d+\.\d+$', printed_lines[1])
    assert printed_lines[2].startswith('sys.version=')
    assert printed_lines[3].startswith('sys.executable=')
    assert printed_lines[4] == '### error information'
    assert printed_lines[5] == 'msg: FatalError: hai'
    assert printed_lines[6] == 'Check the log at {}'.format(log_file)

    assert os.path.exists(log_file)
    with io.open(log_file) as f:
        logged_lines = f.read().splitlines()
        assert len(logged_lines) == 7
        assert printed_lines[0] == '### version information'
        assert re.match(
            r'^pre-commit.version=\d+\.\d+\.\d+$',
            printed_lines[1],
        )
        assert logged_lines[2].startswith('sys.version=')
        assert logged_lines[3].startswith('sys.executable=')
        assert logged_lines[5] == 'msg: FatalError: hai'
        assert logged_lines[6] == "I'm a stacktrace"


def test_error_handler_non_ascii_exception(mock_store_dir):
    with pytest.raises(SystemExit):
        with error_handler.error_handler():
            raise ValueError('☃')


def test_error_handler_no_tty(tempdir_factory):
    pre_commit_home = tempdir_factory.get()
    output = cmd_output_mocked_pre_commit_home(
        sys.executable, '-c',
        'from __future__ import unicode_literals\n'
        'from pre_commit.error_handler import error_handler\n'
        'with error_handler():\n'
        '    raise ValueError("\\u2603")\n',
        retcode=1,
        tempdir_factory=tempdir_factory,
        pre_commit_home=pre_commit_home,
    )
    log_file = os.path.join(pre_commit_home, 'pre-commit.log')
    output_lines = output[1].replace('\r', '').splitlines()
    assert (
        output_lines[-2] == 'An unexpected error has occurred: ValueError: ☃'
    )
    assert output_lines[-1] == 'Check the log at {}'.format(log_file)
