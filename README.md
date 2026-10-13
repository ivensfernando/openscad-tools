# openscad-tools

Shared build rules for OpenSCAD models: one STL per printed part, preview images, a CSG export for FreeCAD and a printability
check. A Make include and one Python script, meant to be added to a project as a git submodule.

- `openscad.mk`: the Make rules. A model folder sets a few variables and includes it.
- `check_prints.py`: checks that each STL is watertight, sits on the bed and prints without support.
- `example/`: a small box with a lid, wired up the way a real model is.

Requirements: OpenSCAD (tested with 2021.01), GNU Make, and Python 3 with `numpy` for `make check`.

## Adding it to a project

```bash
git submodule add <url of this repository> hardware/tools/openscad_tools
```

## A model folder

The model selects what to render from a `part` variable, and every printed part is modelled in print orientation on z = 0:

```scad
part = "assembly"; // box | lid | assembly

if (part == "box") box();
else if (part == "lid") lid();
else assembly();
```

Its `Makefile` names the model and the parts, then includes the shared rules:

```make
SCAD     := box.scad
PARTS    := box lid
PREVIEWS := preview preview-cut

PREVIEW_preview     := -D 'part="assembly"' --camera=20,15,12,65,0,30,160 --imgsize=800,600
PREVIEW_preview-cut := -D 'cut=true' --camera=20,15,12,75,0,20,160 --imgsize=800,600

include ../tools/openscad_tools/openscad.mk
```

## Targets

| Target | What it does |
|---|---|
| `make help` | List the targets (the default). |
| `make stl` | Render one STL per name in `PARTS` to `stl/`. |
| `make plates` | Render the bed-ready arrangements in `PLATES` to `stl/`. |
| `make preview` | Render one PNG per name in `PREVIEWS`. |
| `make csg` | Export `<model>.csg`, which opens in FreeCAD with every solid separate. |
| `make check` | Render the parts, then run `check_prints.py` on them. |
| `make view` | Open the model in the OpenSCAD GUI. |
| `make all` | `stl` and `preview`. |
| `make clean` | Remove `stl/` and the CSG. Preview images are kept. |

Outputs are only re-rendered when a `.scad` file next to the model is newer than they are.

## Variables

| Variable | Default | Meaning |
|---|---|---|
| `SCAD` | (required) | The model's `.scad` file. |
| `PARTS` | empty | Part names. Empty means the model has no selector and renders to `stl/<model>.stl`. |
| `PLATES` | empty | Plate names, rendered like parts. |
| `PART_VAR` | `part` | The OpenSCAD variable the model selects on. |
| `STL_DIR` | `stl` | Where the STLs go. |
| `PREVIEWS` | empty | Image names without `.png`. Each takes its OpenSCAD arguments from `PREVIEW_<name>`. |
| `PREVIEW_FLAGS` | `--colorscheme=Tomorrow` | Arguments added to every preview. |
| `SCAD_DEPS` | every `.scad` next to the model | Files that trigger a rebuild. |
| `OPENSCAD`, `PYTHON` | `openscad`, `python3` | The programs to run. |

A subset can be given on the command line: `make stl PARTS="lid"`.

## The printability check

`check_prints.py` reads binary or ASCII STLs and fails if a part has an open edge, does not sit on z = 0, or has a
downward-facing surface shallower than 45 degrees that is open to the air. Overhang inside a closed cavity is reported but
allowed. It also prints each part's size and an estimated weight (at 1.24 g/cm3, the density of PLA).

```bash
python3 check_prints.py stl/*.stl
```

## Notes

- OpenSCAD 2021 resolves a relative output path against the `.scad`'s folder for some formats, so the rules write every output
  by absolute path.
- Two renders of the same part can list the same facets in a different order, so compare STLs by content, not byte for byte.
- Add `stl/` and `*.csg` to the project's `.gitignore`: they are build output.
