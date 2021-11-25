# SimpleLinks 🖇

An embarrassingly naive GUI that powers embarrassingly naive graph construction.

![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white) 

#### Contents

1. [Quickstart](#quickstart)
2. [Your Own Vertex Types](#your-own-vertex-types)
3. [Artifacts](#artifacts)
4. [ToDo](#todo)
5. [Thanks](#thanks)
6. [License](#license)

### Quickstart

You need to install (or have installed) two system packages:

* [graphviz](https://www.graphviz.org/download/) (`apt-get install -y graphviz`)
* [poetry](https://python-poetry.org/docs/) (run their script - but read it first!)

Run this command and close/cancel the file selection window:

```sh
# From the `simplelinks` root directory...
python ./src/main.py
```

Make some relationships! SimpleLinks will automatically save your progress.
See your graph by opening the PDF in `out/m-<random-key>-graph-mapping.gv.pdf`.

### Your Own Vertex Types

Create a CSV with the following header row:

```
entity,vertex_id
```

It will look like this:

| entity | vertex_id |
| --- | --- |
| gretchen | person |
| cucumber | food-1 |
| bokchoy | food-1 |
| pizza | food-2 |
| cheeseburger | food-2 |
| broccoli | food-1 |
| jane | person |
| ryan | person |

If you want to initialize your `VertexTypes` with even more info, or even 
initialize with existing edges, you can use this format:

```
entity,vertex_name,vertex_id,vertex_central,edge_type,directed,entity2,vertex_name2,vertex_id2
```

Finally, start the GUI and load your CSV.

### Artifacts

The output contains three files:

* A `.csv` with all entities, vertex types, and edges. Entities may be duplicated if they have multiple edges.
* The [DOT notation](https://www.graphviz.org/doc/info/lang.html) for the graph.
* Rendered `.pdf` of `Edge` objects and their `VertexEntity` nodes, as well as `VertexType`.

The output files are in `./out/` where the `.` is the working directory (probably the directory from which you ran the GUI).

### ToDo

This was a quick hack at a GUI. If this is going to be more useful, we have work to do!

* [ ] Automated testing - do some. Any, really.
* [ ] Document existing functionality and How-To.
* [ ] Clean up event handling and event definitions.
* [ ] Clean up artifact output (specifically directory choice).
* [ ] Allow description and metadata on `VertexEntity`.
* [ ] Search over description and metadata, too.
* [ ] If a central `VertexEntity` is defined, also fuzzy match over description and metadata.
* [ ] Preview windows / hover data about `VertexEntity`. Dedicated window for each `VertexType`.

### Thanks

I built this on back of the tremendous efforts by other people, especially:

* [PySimpleGUI]()
* [fuzzywuzzy]()

### License

Please refer to <https://unlicense.org> and the [LICENSE.md](./LICENSE.md) file in this repo.