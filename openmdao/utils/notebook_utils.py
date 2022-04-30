"""Checking for interactive notebook mode."""
import sys
import importlib
import inspect

try:
    from IPython.display import display, HTML, IFrame, Code
    from IPython import get_ipython
    ipy = get_ipython() is not None
except ImportError:
    ipy = display = HTML = IFrame = None

from openmdao.utils.general_utils import simple_warning

try:
    from tabulate import tabulate
except ImportError:
    tabulate = None

colab = 'google.colab' in sys.modules


def _get_object_from_reference(reference):
    """
    Return object of given reference path.

    Parameters
    ----------
    reference : str
        Dot path of desired class.

    Returns
    -------
    str
        Object of the given class.
    """
    split = reference.split('.')
    right = []
    obj = None
    while split:
        try:
            obj = importlib.import_module('.'.join(split))
            break
        except ModuleNotFoundError:
            right.append(split.pop())
    if obj:
        for entry in reversed(right):
            obj = getattr(obj, entry)
    return obj


def get_code(reference, hide_doc_string=False):
    """
    Return the source code of the given reference path to a function.

    Parameters
    ----------
    reference : str
        Dot path of desired function.
    hide_doc_string : bool
        Option to hide the docstring.

    Returns
    -------
    IPython.display.Code
        Source code of the given class or function.
    """
    obj = inspect.getsource(_get_object_from_reference(reference))

    if hide_doc_string:
        obj = obj.split('"""')
        del obj[1]
        obj = ''.join(obj)

    if ipy:
        return Code(obj, language='python')
    else:
        simple_warning("IPython is not installed. Run `pip install openmdao[notebooks]` or "
                       "`pip install openmdao[docs]` to upgrade.")


def display_source(reference, hide_doc_string=False):
    """
    Display the source code of the given reference path to a function.

    Parameters
    ----------
    reference : str
        Dot path of desired function.
    hide_doc_string : bool
        Option to hide the docstring.
    """
    if ipy:
        display(get_code(reference, hide_doc_string))


def show_options_table(reference, recording_options=False):
    """
    Return the options table of the given reference path.

    Parameters
    ----------
    reference : str or object
        Dot path of desired class or function or an instance.

    recording_options : bool
        If True, display recording options instead of options.

    Returns
    -------
    IPython.display
        Options table of the given class or function.
    """
    if isinstance(reference, str):
        obj = _get_object_from_reference(reference)()
    else:
        obj = reference

    if ipy:
        if not hasattr(obj, "options"):
            html = obj.to_table(fmt='html')
        elif not recording_options:
            html = obj.options.to_table(fmt='html')
        else:
            html = obj.recording_options.to_table(fmt='html')

        # Jupyter notebook imposes right justification, so we have to enforce what we want:
        # - Center table headers
        # - Left justify table columns
        # - Limit column width so there is adequate width left for the deprecation message
        style = '<{tag} style="text-align:{align}; max-width:{width}; overflow-wrap:break-word;">'

        cols = html.count('<th>')                 # there could be 5 or 6 columns
        width = '300px' if cols > 5 else '600px'  # limit width depending on number of columns

        html = html.replace('<th>', style.format(tag='th', align='center', width=width))
        html = html.replace('<td>', style.format(tag='td', align='left', width=width))

        return display(HTML(html))
    else:
        simple_warning("IPython is not installed. Run `pip install openmdao[notebooks]` or "
                       "`pip install openmdao[docs]` to upgrade.")


from traitlets import default
from traitlets.config import Config

from nbclient import NotebookClient
from nbconvert.preprocessors.execute import ExecutePreprocessor
from nbconvert.exporters.python import PythonExporter
from pprint import pprint

# key for widget state in notebook
widget_key = 'application/vnd.jupyter.widget-view+json'

# values that should not be quoted
unquoted = ['True', 'False', 'None']


class OMPreprocessor(ExecutePreprocessor):
    # widget types for which we will generate code
    widget_types = [
        'DropdownModel',
        'FloattTextModel',
        'IntTextModel',
        'SelectMultipleModel',
        'TextareaModel',
    ]

    # container to collect commands when processing widgets
    widget_code = []

    def process_widget(self, widget, obj_name):
        """
        Generate Python code to reflect widget state.

        Python commands are added to the `widget_code` class attribute.

        Parameters
        ----------
        widget : dict
            Metadata for widget.
        obj_name: str
            The name of the object to which the widget properties are to be applied.
        """
        wtype = widget['_model_name']
        if wtype in self.widget_types and not widget['disabled']:
            desc = widget['description']

            if wtype in ['FloatTestModel', 'IntTextModel']:
                cmd = f"{obj_name}.{desc} = {widget['value']}"
            elif wtype == 'DropdownModel':
                val = widget['_options_labels'][widget['index']]
                if val not in unquoted and not val.isnumeric():
                    val = f"'{val}'"
                cmd = f"{obj_name}.{desc} = {val}"
            elif wtype == 'SelectMultipleModel':
                values = [widget['_options_labels'][i] for i in widget['index']]
                cmd = f"{obj_name}.{desc} = {values}"
            elif wtype == 'TextareaModel':
                lines = widget['value'].split('\n') if widget['value'] else []
                cmd = f"{obj_name}.{desc} = {lines}"

            self.widget_code.append(cmd)

        if 'children' in widget:
            for child in widget['children']:
                child_id = child.replace("IPY_MODEL_", "")
                self.process_widget(self.widget_state[child_id], obj_name)

    def preprocess(self, nb, resources=None, km=None):
        """
        Preprocess notebook executing each code cell.

        The input argument *nb* is modified in-place.

        Parameters
        ----------
        nb : NotebookNode
            Notebook being executed.
        resources : dictionary (optional)
            Additional resources used in the conversion process.
        km: KernelManager (optional)
            Optional kernel manager.

        Returns
        -------
        nb : NotebookNode
            The executed notebook.
        resources : dictionary
            Additional resources used in the conversion process.
        """
        super().preprocess(nb, resources, km)

        for cell in self.nb.cells:
            if cell['cell_type'] == 'code':

                meta = cell['metadata']
                if 'tags' in meta:
                    tags = meta['tags']
                    if 'remove-input' in tags or 'active-pynb' in tags:
                        cell['source'] = ''
                        continue

                if 'outputs' in cell:
                    for outp in cell['outputs']:
                        if 'data' in outp and widget_key in outp['data']:
                            # the object which generated the widget will be the last line
                            # of the cell source (otherwise the widget would not display)
                            obj_name = cell['source'].rstrip().split('\n')[-1]
                            model_id = outp['data'][widget_key]['model_id']
                            self.process_widget(self.widget_state[model_id], obj_name)

                if self.widget_code:
                    cell['source'] += '\n'+'\n'.join(self.widget_code)
                    self.widget_code = []

        return self.nb, self.resources


class OMExporter(PythonExporter):
    """
    Exports an OpenMDAO code file.
    Note that the file produced will have a shebang of '#!/usr/bin/env python'
    regardless of the actual python version used in the notebook.
    """
    def __init__(self, config=None, **kw):
        """
        Public constructor

        Parameters
        ----------
        config : ``traitlets.config.Config``
            User configuration instance.
        `**kw`
            Additional keyword arguments passed to parent __init__
        """
        self.preprocessors.append(OMPreprocessor())

        super().__init__(config=None, **kw)


    @property
    def default_config(self):
        c = Config({
            "ExecutePreprocessor": {"enabled": False},
            "ClearOutputPreprocessor": {"enabled": False},
            "TemplateExporter": {"exclude_output_prompt": True, "exclude_input_prompt": True}
        })
        c.merge(super().default_config)
        return c


def cite(reference):
    """
    Return the citation of the given reference path.

    Parameters
    ----------
    reference : str
        Dot path of desired class or function.
    """
    obj = _get_object_from_reference(reference)()

    print(obj.cite)

    return


def notebook_mode():
    """
    Check if the environment is interactive and if tabulate is installed.

    Returns
    -------
    bool
        True if the environment is an interactive notebook.
    """
    if ipy and tabulate is None:
        simple_warning("Tabulate is not installed. Run `pip install openmdao[notebooks]` to "
                       "install required dependencies. Using ASCII for outputs.")
    return ipy


notebook = notebook_mode()
