# -----------------------------------------------------------------------------
# openscad.mk: shared Make rules for OpenSCAD models.
#
# Set SCAD (and usually PARTS) in a model folder's Makefile, then include this
# file. README.md lists every variable and shows a complete example.
# -----------------------------------------------------------------------------
ifndef SCAD
$(error Set SCAD to the model's .scad file before including openscad.mk)
endif

SCAD_TOOLS    := $(patsubst %/,%,$(dir $(abspath $(lastword $(MAKEFILE_LIST)))))

OPENSCAD      ?= openscad
PYTHON        ?= python3
# The model picks what to render from this variable: -D 'part="lid"'.
PART_VAR      ?= part
# One STL per name, in print orientation. Empty means the model has no selector
# and renders to a single STL named after the .scad file.
PARTS         ?=
# Bed-ready arrangements of several parts, rendered the same way as PARTS.
PLATES        ?=
STL_DIR       ?= stl
# Any .scad next to the model may be an include, so all of them trigger a rebuild.
SCAD_DEPS     ?= $(wildcard $(dir $(SCAD))*.scad)
# Image names without the extension. Each one takes its OpenSCAD arguments from
# PREVIEW_<name>, and PREVIEW_FLAGS is added to all of them.
PREVIEWS      ?=
PREVIEW_FLAGS ?= --colorscheme=Tomorrow

# OpenSCAD 2021 resolves a relative output path against the .scad's folder for
# some formats, so every output is written by absolute path.
HERE          := $(CURDIR)
MODEL         := $(basename $(notdir $(SCAD)))

ifeq ($(strip $(PARTS)),)
PART_STLS     := $(STL_DIR)/$(MODEL).stl
else
PART_STLS     := $(PARTS:%=$(STL_DIR)/%.stl)
endif
PLATE_STLS    := $(PLATES:%=$(STL_DIR)/%.stl)
PREVIEW_PNGS  := $(PREVIEWS:%=%.png)

.PHONY: help all stl plates preview csg check view clean check-openscad
.DEFAULT_GOAL := help

help: ## List the targets
	@grep -hE '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{ printf "  make %-9s %s\n", $$1, $$2 }'

all: stl preview ## STLs and preview images

check-openscad:
	@command -v "$(OPENSCAD)" >/dev/null || { echo "openscad not found; install it first." >&2; exit 1; }

stl: $(PART_STLS) ## One STL per part in STL_DIR. Optional: PARTS="base lid"

plates: $(PLATE_STLS) ## The bed-ready plates in STL_DIR

ifeq ($(strip $(PARTS)),)
$(STL_DIR)/$(MODEL).stl: $(SCAD_DEPS) | check-openscad
	@mkdir -p "$(STL_DIR)"
	"$(OPENSCAD)" -o "$(HERE)/$@" "$(SCAD)"
endif

$(STL_DIR)/%.stl: $(SCAD_DEPS) | check-openscad
	@mkdir -p "$(STL_DIR)"
	"$(OPENSCAD)" -D '$(PART_VAR)="$*"' -o "$(HERE)/$@" "$(SCAD)"

preview: $(PREVIEW_PNGS) ## Re-render the preview images listed in PREVIEWS

ifneq ($(strip $(PREVIEW_PNGS)),)
$(PREVIEW_PNGS): %.png: $(SCAD_DEPS) | check-openscad
	"$(OPENSCAD)" $(PREVIEW_$*) $(PREVIEW_FLAGS) -o "$(HERE)/$@" "$(SCAD)"
endif

csg: $(MODEL).csg ## Export <model>.csg, which opens in FreeCAD with every solid separate

$(MODEL).csg: $(SCAD_DEPS) | check-openscad
	"$(OPENSCAD)" -o "$(HERE)/$@" "$(SCAD)"

check: $(PART_STLS) ## Verify every part is watertight, on the bed and support-free
	@command -v "$(PYTHON)" >/dev/null || { echo "$(PYTHON) not found." >&2; exit 1; }
	@"$(PYTHON)" "$(SCAD_TOOLS)/check_prints.py" $(PART_STLS)

view: check-openscad ## Open the model in the OpenSCAD GUI
	@"$(OPENSCAD)" "$(SCAD)" >/dev/null 2>&1 &

clean: ## Remove the generated STLs and CSG (preview images are kept)
	@rm -rf "$(STL_DIR)" "$(MODEL).csg"
	@echo "Removed $(STL_DIR) and $(MODEL).csg"
