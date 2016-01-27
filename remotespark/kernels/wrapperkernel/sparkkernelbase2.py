# Copyright (c) 2015  aggftw@gmail.com
# Distributed under the terms of the Modified BSD License.
import requests
from ipykernel.ipkernel import IPythonKernel
from remotespark.utils.ipythondisplay import IpythonDisplay

import remotespark.utils.configuration as conf
from remotespark.utils.log import Log


class SparkKernelBase2(IPythonKernel):
    def __init__(self, implementation, implementation_version, language, language_version, language_info,
                 kernel_conf_name, session_language, client_name, **kwargs):
        # Required by Jupyter - Override
        self.implementation = implementation
        self.implementation_version = implementation_version
        self.language = language
        self.language_version = language_version
        self.language_info = language_info

        # Override
        self.kernel_conf_name = kernel_conf_name
        self.session_language = session_language
        self.client_name = client_name

        super(SparkKernelBase2, self).__init__(**kwargs)

        self._logger = Log(self.client_name)
        self._never_started = True
        self._fatal_error = None
        self._ipython_display = IpythonDisplay()

        # Disable warnings for test env in HDI
        requests.packages.urllib3.disable_warnings()

        if not kwargs.get("testing", False):
            self._load_magics_extension()
            if conf.use_auto_viz():
                self._register_auto_viz()

    def do_execute(self, code, silent, store_history=True, user_expressions=None, allow_stdin=False):
        if self._fatal_error is not None:
            return self._repeat_fatal_error()
        try:
            return self._do_execute(code, silent, store_history, user_expressions, allow_stdin)
        except Exception as e:
            self._show_internal_error(e)
            return self._complete_cell()

    def do_shutdown(self, restart):
        # Cleanup
        self._delete_session()

        return self._do_shutdown_ipykernel(restart)

    def _do_execute(self, code, silent, store_history, user_expressions, allow_stdin):
        code_to_run = code
        if not code.strip().startswith("%"):
            code_to_run = "%%spark\n{}".format(code)

        res = self._execute_cell(code_to_run, silent, store_history, user_expressions, allow_stdin)

        return res

    def _load_magics_extension(self):
        register_magics_code = "%load_ext remotespark.kernels"
        self._execute_cell(register_magics_code, True, False, shutdown_if_error=True,
                           log_if_error="Failed to load the Spark kernels magics library.")
        self._logger.debug("Loaded magics.")

    def _register_auto_viz(self):
        register_auto_viz_code = """from remotespark.datawidgets.utils import display_dataframe
ip = get_ipython()
ip.display_formatter.ipython_display_formatter.for_type_by_name('pandas.core.frame', 'DataFrame', display_dataframe)"""
        self._execute_cell(register_auto_viz_code, True, False, shutdown_if_error=True,
                           log_if_error="Failed to register auto viz for notebook.")
        self._logger.debug("Registered auto viz.")

    def _delete_session(self):
        code = "%_delete_session"
        self._execute_cell_for_user(code, True, False)

    def _execute_cell(self, code, silent, store_history=True, user_expressions=None, allow_stdin=False,
                      shutdown_if_error=False, log_if_error=None):
        reply_content = self._execute_cell_for_user(code, silent, store_history, user_expressions, allow_stdin)

        if shutdown_if_error and reply_content[u"status"] == u"error":
            error_from_reply = reply_content[u"evalue"]
            if log_if_error is not None:
                message = "{}\nException details:\n\t\"{}\"".format(log_if_error, error_from_reply)
                return self._abort_with_fatal_error(message)

        return reply_content

    def _execute_cell_for_user(self, code, silent, store_history=True, user_expressions=None, allow_stdin=False):
        return super(SparkKernelBase2, self).do_execute(code, silent, store_history, user_expressions, allow_stdin)

    def _do_shutdown_ipykernel(self, restart):
        return super(SparkKernelBase2, self).do_shutdown(restart)

    def _complete_cell(self):
        """A method that runs a cell with no effect. Call this and return the value it
        returns when there's some sort of error preventing the user's cell from executing; this
        will register the cell from the Jupyter UI as being completed."""
        return self._execute_cell("None", False, True, None, False)

    def _show_user_error(self, message):
        self._logger.error(message)
        self._ipython_display.send_error(message)

    def _show_internal_error(self, e):
        self._logger.error("ENCOUNTERED AN INTERNAL ERROR: {}".format(e))
        self._ipython_display.send_error("An internal error was encountered. "
                                         "Please file an issue at https://github.com/jupyter-incubator/sparkmagic")

    def _queue_fatal_error(self, message):
        """Queues up a fatal error to be thrown when the next cell is executed; does not
        raise an error immediately. We use this for errors that happen on kernel startup,
        since IPython crashes if we throw an exception in the __init__ method."""
        self._fatal_error = message

    def _abort_with_fatal_error(self, message):
        """Queues up a fatal error and throws it immediately."""
        self._queue_fatal_error(message)
        return self._repeat_fatal_error()

    def _repeat_fatal_error(self):
        """Throws an error that has already been queued."""
        error = conf.fatal_error_suggestion().format(self._fatal_error)
        self._logger.error(error)
        self._ipython_display.send_error(error)
        return self._complete_cell()