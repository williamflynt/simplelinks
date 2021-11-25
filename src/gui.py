from collections import namedtuple
from typing import Any, Iterable, List, Optional, Tuple

import PySimpleGUI as sg
from fuzzywuzzy import fuzz

from load import load
from models import Graph, VertexType, VertexEntity

BUTTON_LINK = "-BUTTON-LINK-"
BUTTON_REMOVE = "-BUTTON-REMOVE-"
BUTTON_SAVE = "-BUTTON-SAVE-"

CHECKBOX_WRITE = "-CHECKBOX-WRITE-"

LISTBOX_LEFT = "-LISTBOX-LEFT-"
LISTBOX_RIGHT = "-LISTBOX-RIGHT-"
LISTBOX_RELS = "-LISTBOX-RELS-"

PREFIX_CHECKBOX = "-CHECKBOX-"
PREFIX_INPUT = "-INPUT-"
PREFIX_LISTBOX = "-LISTBOX-"
PREFIX_COUNTER = "-COUNTER-"

SUFFIX_FILTER = "-FILTER-"
SUFFIX_FUZZY = "-FUZZY-"

# ENTER key.
QT_ENTER_KEY1 = "special 16777220"
QT_ENTER_KEY2 = "special 16777221"
KEY_ENTER = "Return:36"
# DELETE key.
KEY_DELETE = "Delete:119"
# ESCAPE key.
KEY_ESCAPE = "Escape:9"

# Custom event to signal updating all listbox values.
EVENT_UPDATE_ALL = "-EVENT-UPDATE-ALL-"
# Hardcoded height of listboxes.
HEIGHT_LISTBOX_BASE = 50


class ListboxHolder:
    """Describes the components and keys of a sg.Listbox in our GUI."""

    def __init__(
        self,
        key,
        central,
        vertex,
        column,
        counter,
        searcher,
        filter_edge_selected,
        sort_fuzzy_central,
    ):
        self.key = key
        self.central = central
        self.vertex = vertex
        self.column = column
        self.counter = counter
        self.searcher = searcher
        self.filter_edge_selected = filter_edge_selected
        self.sort_fuzzy_central = sort_fuzzy_central

    # This listbox's key.
    key: str

    # Is this designated the "central" VertexType? (GUI specific, not a data thing)
    central: bool

    # The vertex this listbox represents.
    vertex: VertexType

    # The rows making up the sg.Column in this listbox.
    # Everything should be an `sg.*` element.
    column: List[List[Any]]

    # The key for the counter text that shows number of selected elements.
    counter: str

    # The key for the search filter input.
    searcher: str

    # The key for the checkbox toggling filter on edges (hide if related).
    filter_edge_selected: str

    # The key for the checkbox toggling sympathetic fuzzy filter on selected items
    # in the central_vtx_type vertex (if exists).
    sort_fuzzy_central: str

    def __iter__(self):
        yield self.key
        yield self.central
        yield self.vertex
        yield self.column
        yield self.counter
        yield self.searcher
        yield self.filter_edge_selected
        yield self.sort_fuzzy_central

    def __repr__(self) -> str:
        return f"Holder<{self.vertex}>"


class ListboxCollection:
    """
    Access the proper ListboxHolder by any key in O(1) time.

    Supports an optional central ListboxHolder.
    """

    def __init__(self, *boxes: ListboxHolder) -> None:
        self.boxes = []
        self.central: Optional[ListboxHolder] = None
        self._keymap = {}
        for b in boxes:
            self.add(b)

    def get(self, key: str) -> ListboxHolder:
        return self._keymap[key]

    def add(self, b: ListboxHolder) -> None:
        self.boxes.append(b)
        if b.central:
            self.central = b
        for item in b:
            if isinstance(item, str):
                self._keymap[item] = b

    def has(self, key: str) -> bool:
        return key in self._keymap

    @property
    def keys(self) -> Iterable[str]:
        return self._keymap

    def remove(self, b: ListboxHolder) -> None:
        self.boxes = [x for x in self.boxes if b.key != x.key]
        for item in b:
            if isinstance(item, str):
                self._keymap.pop(item, None)

    def replace(self, key: str, b: ListboxHolder) -> None:
        if not self.has(key):
            return self.add(b)
        existing = self.get(key)
        self.remove(existing)
        self.add(b)

    def __iter__(self):
        for b in self.boxes:
            yield b


def start(m: Graph, central_vtx_type: Optional[VertexType] = None) -> None:
    """
    Run a GUI to map 2->N VertexTypes to a `central_vtx_type` VertexType and each other.

    Return optional load data if we want to run a new window with new data (ie:
    the user selected Load).
    """
    fn = sg.popup_get_file(
        "Choose CSV (or cancel for default)",
        "Load Mapping",
        default_extension="csv",
        file_types=(("CSV", "*.csv"),),
    )
    if fn:
        m, central_vtx_type = load(fn)

    window, boxes = _window_init(m, central_vtx_type)
    searcher_events = [lb.searcher for lb in boxes]
    frs_events = [lb.filter_edge_selected for lb in boxes]
    ffc_events = [lb.sort_fuzzy_central for lb in boxes]
    # If we loaded from file, let's honor the edges we have by filtering.
    _, values = window.read(timeout=1)
    _set_filtered_values(window, EVENT_UPDATE_ALL, boxes, m, values)
    window.refresh()
    while True:
        # Update the "entities" in our edges listbox "VertexType".
        rel_lb = boxes.get(LISTBOX_RELS)
        if rel_lb:
            rel_lb.vertex = namedtuple("mockvertex", "entities")(m.edges)

        # Wait for an event and process.
        event, values = window.read()
        print("***", event)
        print(values)
        if event == sg.WIN_CLOSED or event == "Cancel":
            break

        # Check how many listbox keys we see that have populated values.
        # If it's at least two, we can link entities.
        linkable = sum([int(bool(values.get(x.key))) for x in boxes.boxes]) >= 2

        if event == KEY_ESCAPE:
            values = _deselect_all_listbox(window, boxes.boxes, values)
            _set_filtered_values(window, EVENT_UPDATE_ALL, boxes, m, values)
        if event in boxes.keys:
            disabled = True
            if linkable:
                disabled = False
            window[BUTTON_LINK].update(disabled=disabled)
            window[BUTTON_REMOVE].update(disabled=True)
            _set_filtered_values(window, event, boxes, m, values)
        if event in searcher_events:
            _set_filtered_values(window, event, boxes, m, values)
        if event in frs_events:
            _set_filtered_values(window, event, boxes, m, values)
        if event in ffc_events:
            _set_filtered_values(window, event, boxes, m, values)
        if event == LISTBOX_RELS:
            vals = values.get(LISTBOX_RELS)
            if vals:
                values = _deselect_all_listbox(window, boxes, values, LISTBOX_RELS)
                window[BUTTON_LINK].update(disabled=True)
            window[BUTTON_REMOVE].update(disabled=not vals)
            _set_filtered_values(window, EVENT_UPDATE_ALL, boxes, m, values)
        if event in (BUTTON_LINK, "\r", KEY_ENTER, QT_ENTER_KEY1, QT_ENTER_KEY2):
            if linkable:
                grouped = _grouped_entities(boxes, values, LISTBOX_RELS)
                if boxes.central and values.get(boxes.central.key):
                    m.add_edges_central(*grouped, central_vertex=central_vtx_type)
                else:
                    m.add_edges(*grouped)
                values = _deselect_all_listbox(window, boxes, values)
                window[LISTBOX_RELS].update(values=m.edges)
                window[BUTTON_LINK].update(disabled=True)
                if values[CHECKBOX_WRITE]:
                    m.write()
                _set_filtered_values(window, EVENT_UPDATE_ALL, boxes, m, values)
        if event in [BUTTON_REMOVE, KEY_DELETE]:
            vals = values.get(LISTBOX_RELS)
            if vals:
                m.remove_edge(*[x.edge_id for x in vals])
            window[LISTBOX_RELS].update(values=m.edges)
            if values[CHECKBOX_WRITE]:
                m.write()
            _set_filtered_values(window, EVENT_UPDATE_ALL, boxes, m, values)
        if event == BUTTON_SAVE:
            m.write()

        window[BUTTON_SAVE].update(disabled=bool(len(m.edges) == 0))

        window.refresh()

    window.close()


# --- HELPERS ---


def _deselect_all_listbox(
    window: sg.Window, boxes: Iterable[ListboxHolder], values: dict, *excludes: str
) -> dict:
    """Deselect all values from all listboxes. Return updated values."""
    for b in boxes:
        key = b
        if not isinstance(b, str):
            key = b.key
        if key in excludes:
            continue
        window[key].set_value([])
        # Update the values dict for follow-on processing with other funcs.
        values[key] = []
        if not isinstance(b, str):
            window[b.counter].update(value="0")

    return values


def _fuzzy_match(x: VertexEntity, *any_of: VertexEntity) -> int:
    """
    Check if `x` is a fuzzy entity name match against any of the `any_of` entities.
    """
    m = 0
    for item in any_of:
        m = max(m, fuzz.partial_ratio(x.entity, item.entity))
        if m >= 100:
            return m
    return m


def _fuzzy_match_str(x: VertexEntity, *any_of: str) -> int:
    """
    Check if `x` is a fuzzy entity name match against any of the `any_of` strings.
    """
    m = 0
    for item in any_of:
        m = max(m, fuzz.WRatio(x.entity, item))
        if m >= 100:
            return m
    return m


def _grouped_entities(
    boxes: Iterable[ListboxHolder], values: dict, *excludes: str
) -> List[List[VertexEntity]]:
    """Return a list of VertexEntity in lists by VertexType."""
    g = [values.get(b.key, []) for b in boxes if b.key not in excludes]
    return [item for item in g if item]


def _set_filtered_values(
    window: sg.Window,
    event: str,
    boxes: ListboxCollection,
    m: Graph,
    values: dict,
) -> None:
    """
    Update the values for the Listbox associated with `event`.

    If `event` is a selection change on the central_vtx_type VertexType, also update those
    listboxes that have central_vtx_type filtering enabled.
    """
    if event == EVENT_UPDATE_ALL:
        for b in boxes:
            # Don't pass the key, because the `central_vtx_type` vertex (if it exists)
            # will make us do almost double the work.
            _set_filtered_values(window, b.searcher, boxes, m, values)
        return
    if not boxes.has(event):
        return
    box = boxes.get(event)

    if not box.vertex:
        return
    filtered_vals = box.vertex.entities

    if search_string := values[box.searcher]:
        filtered_vals = filter(
            lambda x: x.entity.startswith(search_string)
            or search_string in x.entity
            or _fuzzy_match_str(x, search_string) > 75,
            filtered_vals,
        )
    if values[box.filter_edge_selected]:
        edges = []
        for _, v in m.edges.edges_by_vertex.items():
            edges.extend(v)
        if edges:
            filtered_vals = filter(lambda x: x not in edges, filtered_vals)
    if values[box.sort_fuzzy_central] and not box.central:
        if central_selected := values[boxes.central.key]:
            ranked = [(_fuzzy_match(x, *central_selected), x) for x in filtered_vals]
            sorted_by_rank = sorted(ranked, reverse=True, key=lambda x: x[0])
            # Only return the top 5 results.
            filtered_vals = [x[1] for x in sorted_by_rank[:5]]

    # Get the filtered values, plus any previously selected entities. In other
    # words, don't ever filter things that are selected.
    final_entities = list(set(filtered_vals).union(set(values.get(box.key, set()))))
    # Order entities in the same way as the VertexType has them originally.
    original_order = [x for x in box.vertex.entities if x in final_entities]
    selected_entities = [original_order.index(f) for f in values[box.key]]
    # Setting values will clear any selected items without set_to_index.
    window[box.key].update(values=original_order, set_to_index=selected_entities)
    window[box.counter].update(value=str(len(selected_entities)))

    if box.central and event == box.key:
        # If we updated the central_vtx_type vertex, we need to filter all the others that
        # have the filtering option selected.
        to_update = [
            b
            for b in boxes
            if not b.central  # Guard against logic errors.
            and b != box  # Guard against logic errors.
            and values[b.sort_fuzzy_central]
        ]
        for b in to_update:
            _set_filtered_values(window, b.sort_fuzzy_central, boxes, m, values)


def _window_init(
    m: Graph, central_vtx_type: Optional[VertexType]
) -> Tuple[sg.Window, ListboxCollection]:
    boxes = ListboxCollection()
    for vertex in m.vertexs:
        lb_key = f"{PREFIX_LISTBOX}{vertex.vertex_id}-"
        is_central = central_vtx_type and vertex.vertex_id == central_vtx_type.vertex_id
        lb = ListboxHolder(
            lb_key,
            is_central,
            vertex,
            [],
            f"{PREFIX_COUNTER}{lb_key}",
            f"{PREFIX_INPUT}{lb_key}",
            f"{PREFIX_CHECKBOX}{lb_key}{SUFFIX_FILTER}",
            f"{PREFIX_CHECKBOX}{lb_key}{SUFFIX_FUZZY}",
        )

        lb.column = [
            [sg.Text(vertex.name), sg.Text("0", key=lb.counter)],
            [sg.Input(size=(30, 1), enable_events=True, key=lb.searcher)],
            [
                sg.Listbox(
                    values=vertex.entities,
                    select_mode=sg.LISTBOX_SELECT_MODE_MULTIPLE,
                    size=(30, HEIGHT_LISTBOX_BASE),
                    enable_events=True,
                    key=lb_key,
                )
            ],
            [
                sg.Checkbox(
                    "Hide items with edges",
                    default=True,
                    key=lb.filter_edge_selected,
                    enable_events=True,
                )
            ],
            [
                sg.Checkbox(
                    "Fuzzy filter on central_vtx_type item(s)",
                    disabled=is_central,
                    default=True and not is_central,
                    key=lb.sort_fuzzy_central,
                    enable_events=True,
                )
            ],
        ]

        boxes.add(lb)

    edge_lb = ListboxHolder(
        LISTBOX_RELS,
        False,
        namedtuple("mockvertex", "entities")(m.edges),
        [],
        f"{PREFIX_COUNTER}{LISTBOX_RELS}",
        f"{PREFIX_INPUT}{LISTBOX_RELS}",
        f"{PREFIX_CHECKBOX}{LISTBOX_RELS}{SUFFIX_FILTER}",
        f"{PREFIX_CHECKBOX}{LISTBOX_RELS}{SUFFIX_FUZZY}",
    )
    edge_col = [
        [sg.Text("edges"), sg.Text("0", key=edge_lb.counter)],
        [sg.Input(size=(60, 1), enable_events=True, key=edge_lb.searcher)],
        [
            sg.Listbox(
                values=m.edges,
                select_mode=sg.LISTBOX_SELECT_MODE_MULTIPLE,
                size=(60, HEIGHT_LISTBOX_BASE),
                enable_events=True,
                key=LISTBOX_RELS,
            )
        ],
        [
            sg.Checkbox(
                "Hide items with edges",
                default=False,
                disabled=True,
                key=edge_lb.filter_edge_selected,
                enable_events=False,
                visible=False,
            )
        ],
        [
            sg.Checkbox(
                "Fuzzy filter on central_vtx_type item(s)",
                disabled=False,
                default=True,
                key=edge_lb.sort_fuzzy_central,
                enable_events=True,
            )
        ],
    ]
    edge_lb.column = edge_col

    layout = [
        [
            *[sg.Column(b.column) for b in boxes],
            sg.VerticalSeparator(),
            sg.Column(edge_col),
        ],
        [
            sg.Button("Link", key=BUTTON_LINK, disabled=True),
            sg.Button("Remove", key=BUTTON_REMOVE, disabled=True),
            sg.Button("Save", key=BUTTON_SAVE, disabled=True),
            sg.Checkbox("Save on updates", default=True, key=CHECKBOX_WRITE),
        ],
    ]

    boxes.add(edge_lb)

    return sg.Window("entity Mapper", layout, return_keyboard_events=True), boxes
