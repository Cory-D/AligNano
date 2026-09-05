# AligNano: Terminal FASTA, A3M, and Stockholm (STO) Alignment Editor

A lightweight, dependency-free Python terminal interface for browsing and editing multiple sequence alignments (MSA) in FASTA, A3M, and Stockholm (`.sto` / `.stk`) formats. It provides a real-time color-coded alignment grid, designed for efficient sequence inspection directly from the command line.

## Features

- **Command-Line Interface**: Clean, bordered ANSI layouts, real-time status overlays, and interactive file selection menus.
- **Interactive Alignment Color Coding**:
  - **Nucleotides**: A (Red), T/U (Green), C (Blue), G (Yellow), Gaps (Dark Grey).
  - **Amino Acids**: ClustalX-inspired colors based on chemical properties (Acidic: Red, Basic: Blue, Polar: Green, Hydrophobic: Orange/Yellow, Cysteine: Pink, Glycine: Grey).
  - **DIFF Mode**: Selectively highlights only columns containing variable sites (mutations/gaps) to draw focus to polymorphs.
- **Dynamic Consensus and Conservation**: Real-time bottom-row ruler showing conservation levels (Bold Green for 100% identity, Bold White for >=80% conservation, lowercase for >=50%, and grey dots for polymorphic sites).
- **Active Search and Live Highlights**: Search accession names or sequence motifs (`Ctrl+F`), instantly highlighting all matches across the viewport in high-contrast cyan.
- **Synced Side-by-Side Panes**: Left-hand pane for accession names, right-hand pane for sequences. Scrolls in vertical synchronization.
- **Intuitive Keyboard Controls & ESC Menu**:
  - **ESC Menu**: Invokes a clean, two-column side-by-side modal menu with direct access to File operations, Editing tools, Display color schemes, and Bioinformatics utilities.
  - **Arrow keys**: Cell-by-cell navigation and intuitive focus swapping between panes.
  - **Direct Editing**: Overwrite or insert residues, insert gaps, delete residues, edit accession headers, add new sequences, or reorder rows.
- **Undo/Redo History**: Deep undo stack (up to 50 states) for sequences and accession edits.
- **Multiple Alignment Formats**: Seamlessly load, edit, convert, and save alignments in FASTA, A3M, and Stockholm (`.sto` / `.stk`) formats. *(Note: When loading Stockholm files, sequence alignment data and identifiers are parsed while file/column/residue annotation metadata tags such as `#=GF`, `#=GS`, `#=GC`, and `#=GR` are stripped).*
- **Overwrite Protection & Confirmation**: Prompts for confirmation `(y/N)` before saving over existing alignment files or exporting frequency CSV files to prevent accidental data loss. Defaults grid editing to **INSERT (INS)** mode to protect existing sequences from inadvertent residue overwriting.
- **Sandbox Safe**: Only reads and writes inside the workspace directory (`AligNano`).
- **Zero Dependencies**: Native cross-platform compatibility utilizing Unix `termios` and Windows `msvcrt`/`ctypes` VT.

---

## Installation and Running

Ensure you have Python 3 installed. No third-party modules or installations are required.

### 1. Launch with the Interactive Menu

To load and choose from available FASTA, A3M, or Stockholm files in the workspace (or create a new empty alignment):
```bash
python3 alignano.py
```

### 2. Launch directly with a specific file

```bash
python3 alignano.py input_examples/ubiquitin_dna.sto
```

---

## Navigation, ESC Menu & Reserved Shortcuts

AligNano uses an **`ESC`**-invoked menu to organize functions cleanly without keyboard clutter, reserving standard **Ctrl** keys only for core, high-frequency editor commands.

### The ESC Main Menu

Press **`ESC`** at any time to open the side-by-side modal menu:
- Use **`Up / Down`** to navigate items.
- Use **`Left / Right`** (or **`Enter`**) to switch between the **Categories** and **Actions** columns.
- Use **`1, 2, 3, 4`** to jump directly to categories (*1. File*, *2. Edit*, *3. Display*, *4. Tools*).
- Press **`ESC`** to return from Actions to Categories, or close the menu.

| Menu Category | Available Actions |
|---|---|
| **1. File** | Save Alignment (`Ctrl+S`), Toggle Alignment Format (FASTA / A3M / STO), Export Frequencies (CSV), Help & Overview (`?`), Quit Editor (`Ctrl+Q`) |
| **2. Edit** | Undo (`Ctrl+Z`), Redo (`Ctrl+Y`), Toggle Insert/Overwrite (`Insert`), Rename Accession Header, Add Sequence Row, Delete Sequence Row, Reorder/Move Row |
| **3. Display** | Directly select Color Scheme (*DNA/RNA*, *Protein ClustalX*, *DIFF Variable Sites*, *Monochrome*), Toggle Mouse Mode, Widen Accession Pane (`]`), Narrow Accession Pane (`[`), Page Left, Page Right |
| **4. Tools** | Search Motif or Header (`Ctrl+F`), Jump to Next Match (`Ctrl+J`), Translate DNA to Protein (6 reading frames, 26 NCBI code tables), Sort by Levenshtein distance |

### Reserved Direct Shortcuts

| Key / Shortcut | Action |
|---|---|
| **`ESC`** | Open / Close the AligNano Main Menu |
| **`Arrows`** | Move cursor in active pane (Up/Down scrolls both synchronously; Left/Right crosses panes) |
| **`Tab`** | Switch focus between Accession Names pane and Sequence Grid |
| **`[` / `]`** | Narrow / widen Accession Name pane width |
| **`Insert`** | Toggle edit mode between **INSERT (INS)** and **OVERWRITE (OVR)** |
| **`Alphanumeric`** | Insert or overwrite residue at cursor (in sequence grid) |
| **`Space` or `-`** | Insert or overwrite alignment gap (`-`) at cursor |
| **`Backspace` / `Delete`** | In Sequence Grid: delete residue left of cursor; In Accession Pane: delete highlighted sequence row (undoable) |
| **`Page Up` / `Page Down`** | Page sequences vertically by viewport height |
| **`Ctrl+F`** | Open search prompt (find accession name or sequence motif) |
| **`Ctrl+J`** | Jump to the next search match |
| **`Ctrl+Z`** | Undo last action (up to 50 historical states) |
| **`Ctrl+Y`** | Redo last undone action |
| **`Ctrl+S`** | Quick-save alignment to file |
| **`Ctrl+Q`** | Quit editor (warns if unsaved changes exist) |
| **`?`** | Open / close the interactive scrollable Help screen |

### Mouse Support (tmux-style)

AligNano includes full SGR 1006 terminal mouse tracking:
- **Click to Focus / Place Cursor**: Click directly on any residue in the sequence grid or on any accession name in the left pane.
- **Hold & Drag Sequences**:
  - **Drag Up / Down**: Grabs and moves sequence rows to reorder them in real-time (with automatic edge scrolling and `Ctrl+Z` Undo support).
  - **Drag Left / Right**: Smoothly scrolls and pans the alignment horizontally across columns.
- **Drag Divider Partition**: Click and drag the vertical border (`|`) between accessions and sequences to smoothly resize panel widths in real-time.
- **Mouse Wheel Scrolling**: Scroll the mouse wheel up/down to scroll vertically through sequences; horizontal scroll moves left/right across columns.
- **ESC Menu Interaction**: Click directly on menu categories and actions, or click outside the menu box to dismiss it.
- **Toggle Mouse Mode**: Toggle in the menu via **`[ESC] > Display > Mouse Mode`** (use `◄/►`, `Enter`, or click to toggle). You can also launch from the command line with `--no-mouse` or `--mouse`.
- **Native Clipboard Copy**: When mouse mode is active, hold **`Shift`** (or **`Option`** on macOS) while dragging to select text using your terminal's native clipboard.

---

## Sample Alignments Included

We have provided curated, biologically authentic eukaryotic ubiquitin alignments in all supported formats:
1. `input_examples/ubiquitin_dna.fasta` / `input_examples/ubiquitin_dna.a3m` / `input_examples/ubiquitin_dna.sto` - Codon-aligned mature ubiquitin DNA coding sequences (228 bp) from 20 diverse eukaryotic species in FASTA, A3M, and Stockholm formats.
2. `input_examples/ubiquitin_protein.fasta` / `input_examples/ubiquitin_protein.a3m` / `input_examples/ubiquitin_protein.sto` - Aligned mature ubiquitin protein sequences (76 AA) from the same 20 eukaryotic species in FASTA, A3M, and Stockholm formats.
