"""Export OpenMDAO script from jupyter notebook."""

import os
import os.path

from traitlets import default
from traitlets.config import Config

from nbconvert.preprocessors.execute import ExecutePreprocessor
from nbconvert.exporters.python import PythonExporter

# key for widget state in notebook
widget_key = 'application/vnd.jupyter.widget-view+json'

# values that should not be quoted
unquoted = ['True', 'False', 'None']


class OMPreprocessor(ExecutePreprocessor):
    """
    Preprocessor used to generate OpenMDAO script from a Jupyter notebook.

    Removes invisible cells and assigns attributes to objects that have a
    associated widget view based on widget metadata.

    Parameters
    ----------
    **kwargs : dict of keyword arguments
        Argumenst for super classes.

    Attributes
    ----------
    _widget_types : list
        List of widget types for which we will generate code.
    _widget_code : list
        List of commands generated by processing widgets.
    """

    def __init__(self, **kwargs):
        """
        Initialize all attributes.
        """
        super().__init__(**kwargs)

        # widget types for which we will generate code
        self._widget_types = [
            'DropdownModel',
            'FloattTextModel',
            'IntTextModel',
            'SelectMultipleModel',
            'TextareaModel',
        ]

        # list of commands generated by processing widgets
        self._widget_code = []

    def process_widget(self, widget, obj_name):
        """
        Generate Python code to reflect widget state.

        Python commands are added to the `widget_code` class attribute.

        Parameters
        ----------
        widget : dict
            Metadata for widget.
        obj_name : str
            The name of the object to which the widget properties are to be applied.
        """
        wtype = widget['_model_name']
        if wtype in self._widget_types and not widget['disabled']:
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

            self._widget_code.append(cmd)

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
        resources : dict
            Additional resources used in the conversion process.
        km : KernelManager
            Optional kernel manager.

        Returns
        -------
        nb : NotebookNode
            The executed notebook.
        resources : dictionary
            Additional resources used in the conversion process.
        """
        super().preprocess(nb, resources, km)

        for cell in nb.cells:
            if cell['cell_type'] == 'code':

                meta = cell['metadata']
                if 'tags' in meta:
                    tags = meta['tags']
                    if 'remove-input' in tags or 'active-ipynb' in tags:
                        cell['source'] = ''
                        continue

                if 'outputs' in cell:
                    for outp in cell['outputs']:
                        if 'data' in outp and widget_key in outp['data']:
                            # the object which generated the widget will be the last line
                            # of the cell source (otherwise the widget would not display)
                            obj_name = cell['source'].rstrip().split('\n')[-1]
                            if '(' not in obj_name:
                                # simple objects only (no constructors or functions)
                                model_id = outp['data'][widget_key]['model_id']
                                self.process_widget(self.widget_state[model_id], obj_name)

                if self._widget_code:
                    cell['source'] += '\n' + '\n'.join(self._widget_code)
                    self._widget_code = []

        return nb, resources


class OMExporter(PythonExporter):
    """
    Exports an OpenMDAO (python) script via nbconvert.

    Parameters
    ----------
    config : ``traitlets.config.Config``
        User configuration instance.
    **kwargs : dict of keyword arguments
        Argumenst for super classes.

    Notes
    -----
    The nbconvert package uses the 'nbconvert.exporters' entry point to find custom
    exporters so this class should be added to setup.py, e.g.:

        entry_points = {
            'nbconvert.exporters': ['openmdao=openmdao.utils.notebook_export:OMExporter'],
        }

    Alternatively, it can be used by explicitly passing a command line argument, e.g.

        jupyter nbconvert --to openmdao.utils.notebook_export.OMExporter notebook.ipynb

    see: https://nbconvert.readthedocs.io/en/latest/external_exporters.html
    """

    def __init__(self, config=None, **kwargs):
        """
        Public constructor.
        """
        self.preprocessors.append(OMPreprocessor())

        super().__init__(config=None, **kwargs)

    @property
    def default_config(self):
        """
        Customize configuration for OpenMDAO exporter.
        """
        c = Config({
            "ExecutePreprocessor": {"enabled": False},
            "ClearOutputPreprocessor": {"enabled": False},
            "TemplateExporter": {"exclude_output_prompt": True, "exclude_input_prompt": True}
        })
        c.merge(super().default_config)
        return c


def _jupyter_bundlerextension_paths():
    """
    Declare metadata for OpenMDAO bundler extension.

    Notes
    -----
    The Jupyter notebook server supports the writing of bundler extensions that transform, package,
    and download/deploy notebook files. This function declares an OpenMDAO bundler.

    see: https://jupyter-notebook.readthedocs.io/en/stable/extending/bundler_extensions.html
    """
    return [{
        'name': 'openmdao_bundler',                       # unique bundler name
        'label': 'OpenMDAO Script',                       # human-readable menu item label
        'module_name': 'openmdao.utils.notebook_export',  # module containing bundle()
        'group': 'download'                               # group under 'deploy' or 'download' menu
    }]


def bundle(handler, model):
    """
    Bundle the notebook referenced by the given model.

    After bundling, issues a Tornado web response using the `handler` to redirect
    the user's browser, download a file, show a HTML page, etc. This function
    must finish the handler response before returning either explicitly or by
    raising an exception.

    Parameters
    ----------
    handler : tornado.web.RequestHandler
        Handler that serviced the bundle request.
    model : dict
        Notebook model from the configured ContentManager.

    Notes
    -----
    An 'OpenMDAO Script' menu item appears under "File -> Download as" per the metadata above.
    When a user clicks the menu item, a new browser tab opens and the notebook server invokes
    this bundle function.

    The bundler must be enabled using the command:

        jupyter bundlerextension enable --py openmdao.utils.notebook_export --sys-prefix

    Note that this writes the bundler metadata to ~/.jupyter/nbconfig/notebook.json,
    which means it persists and is not tied to a particular python environment.

    see: https://jupyter-notebook.readthedocs.io/en/stable/extending/bundler_extensions.html
    """
    from nbconvert.nbconvertapp import NbConvertApp

    class OMExporterApp(NbConvertApp):
        @default("export_format")
        def default_export_format(self):
            return "openmdao"

    ipynb_file = model['path']
    py_file = ipynb_file.replace('.ipynb', '.py')

    try:
        os.remove(py_file)
        print("Existing file deleted.")
    except Exception as err:
        print(err)

    omx = OMExporterApp()
    omx.initialize()
    omx.notebooks = [model['path']]
    omx.convert_notebooks()
    handler.finish(f"OpenMDAO script saved to {os.getcwd()}/{py_file}.")
