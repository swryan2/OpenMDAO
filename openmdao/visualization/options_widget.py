"""
A widget-based representation of OptionsDictionary for use in Jupyter notebooks.
"""

try:
    import ipywidgets as widgets
    from ipywidgets import interact, Layout
    from IPython.display import display
except Exception:
    widgets = None

from openmdao.utils.options_dictionary import OptionsDictionary
from openmdao.utils.general_utils import simple_warning


class OptionsWidget(object):
    """
    Widget to set options.

    Parameters
    ----------
    opts : OptionsDictionary
        Options to edit.
    """

    def __init__(self, opts):
        """
        Initialize.
        """
        if widgets is None:
            simple_warning(f"ipywidgets is required to use {self.__class__.__name__}."
                           "To install it run `pip install openmdao[notebooks]`.")
            return

        _dict = opts._dict
        _widgets = []
        _style = {'description_width': 'initial', 'align-items': 'center'}
        # _path = opts._parent_name+'.options'

        messages = widgets.Output()

        @messages.capture(clear_output=True)
        def option_changed(change):
            owner = change['owner']
            newval = change['new']

            name = owner.description
            option = _dict[name]

            # if it's an arbitrary list, parse lines of text
            if option['types'] is list and option['values'] is None:
                newval = newval.strip().split('\n')

            try:
                opts[name] = newval
            except ValueError as err:
                print(str(err))

        for name, option in sorted(_dict.items()):
            val = option['val']
            types = option['types']
            values = option['values']
            desc = option['desc']

            if values:
                if types is list:
                    _widgets.append(widgets.SelectMultiple(
                        description=name,
                        tooltip=desc,
                        options=sorted(values),
                        value=val,
                        disabled=False,
                        style=_style
                    ))
                    continue
                else:
                    _widgets.append(widgets.Dropdown(
                        description=name,
                        tooltip=desc,
                        options=values,
                        value=val,
                        disabled=False,
                        style=_style
                    ))
                    continue

            upper = option['upper']
            lower = option['lower']

            if upper and lower:
                if isinstance(val, int):
                    _widgets.append(widgets.IntSlider(
                        description=name,
                        tooltip=desc,
                        min=lower,
                        max=upper,
                        value=val,
                        step=1,
                        disabled=False,
                        continuous_update=False,
                        orientation='horizontal',
                        readout=True,
                        readout_format='d',
                        style=_style
                    ))
                else:
                    _widgets.append(widgets.FloatSlider(
                        description=name,
                        tooltip=desc,
                        min=lower,
                        max=upper,
                        value=val,
                        disabled=False,
                        continuous_update=False,
                        orientation='horizontal',
                        readout=True,
                        readout_format='f',
                        style=_style
                    ))
                continue

            if isinstance(val, float):
                _widgets.append(widgets.FloatText(
                    description=name,
                    tooltip=desc,
                    min=lower,
                    max=upper,
                    value=val,
                    disabled=False,
                    continuous_update=False,
                    orientation='horizontal',
                    readout=True,
                    readout_format='f',
                    style=_style
                ))
                continue

            if isinstance(val, int):
                _widgets.append(widgets.IntText(
                    description=name,
                    tooltip=desc,
                    min=lower,
                    max=upper,
                    value=val,
                    step=1,
                    disabled=False,
                    continuous_update=False,
                    orientation='horizontal',
                    readout=True,
                    readout_format='d',
                    style=_style
                ))
                continue

            types = option['types']

            if types == list:
                _widgets.append(widgets.Textarea(
                    description=name,
                    tooltip=desc,
                    value='\n'.join(val),
                    continuous_update=False,
                    rows=5,
                    disabled=False,
                    style=_style
                ))
                continue

            # unhandled option type, just show value as uneditable text
            _widgets.append(widgets.Textarea(
                description=name,
                tooltip=desc,
                value=str(val),
                disabled=True,
                style=_style
            ))

        for wdgt in _widgets:
            wdgt.observe(option_changed, 'value')

        # sort widgets by how many rows they use
        _wdgt_rows = [(wdgt.rows if getattr(wdgt, 'rows', None) else 1, wdgt) for wdgt in _widgets]
        _wdgt_rows.sort(key=lambda x: x[0])
        _widgets = [wdgt for _, wdgt in _wdgt_rows]

        box_layout = Layout(display='flex', flex_flow='row wrap')
        grid = widgets.GridBox(children=_widgets, layout=box_layout)

        # label = widgets.Label(value=_path, layout=Layout(width='100%', style='font-style:oblique'))
        # header = widgets.HBox([label], layout=Layout(width='100%'))
        # # from pprint import pprint
        # # pprint(dir(header.layout))
        # header.layout.align_items = 'center'
        # header.layout.align_content = 'center'
        # header.layout.justify_content = 'space-around'
        # display(widgets.VBox([label, grid]))

        display(grid)

        display(messages)
