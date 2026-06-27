# AligNano: Terminal FASTA Editor & Browser

*Version 1.0.10*

A retro-styled, dependency-free Python terminal utility for browsing and editing multiple sequence alignments (MSA) in FASTA format. Designed in the spirit of 1980s ANSI BBSs, tmux, and Antigravity CLI, it provides a color-coded alignment interface modeled after Aliview.

## Features

- 🎮 **BBS-Inspired Interface**: Colorful 80s ANSI ASCII frames, custom logos, and clear status overlays.
- 🧬 **Aliview-Style Color Coding**:
  - **Nucleotides**: A (Red), T/U (Green), C (Blue), G (Yellow), Gaps (Dark Grey).
  - **Amino Acids**: ClustalX-inspired colors based on chemical properties (Acidic: Red, Basic: Blue, Polar: Green, Hydrophobic: Orange/Yellow, Cysteine: Pink, Glycine: Grey).
  - **DIFF Mode**: Selectively highlights only columns containing variable sites (mutations/gaps) to draw focus to polymorphs.
- 🔀 **Synced Side-by-Side Panes**: Left-hand pane for accession names, right-hand pane for sequences. Scrolls in vertical synchronization.
- ⌨️ **Intuitive Keyboard Controls**:
  - **Arrow keys**: Cell-by-cell navigation and intuitive focus swapping between panes.
  - **CTRL keys / Pages**: Page up, down, left, or right quickly. Supports Ctrl+Arrow keys and letter mappings.
  - **Direct Editing**: Overwrite or insert characters, insert gaps, delete characters, edit accession headers, add new sequences, or delete rows.
- 🕒 **Undo/Redo History**: Deep undo stack (up to 50 states) for sequences and accession edits.
- 🛡️ **Sandbox Safe**: Only reads and writes inside the workspace directory (`AligNano`).
- 🔌 **Zero Dependencies**: Native cross-platform compatibility utilizing Unix `termios` and Windows `msvcrt`/`ctypes` VT.

---

## Installation & Running

Ensure you have Python 3 installed. No third-party modules or installations are required.

### 1. Launch with the Interactive Menu

To load and choose from available FASTA files in the workspace (or create a new empty alignment):
```bash
python3 alignano.py
```

### 2. Launch directly with a specific file

```bash
python3 alignano.py dna_sample.fasta
```

---

Every feature can be invoked using standard control (**Ctrl**) shortcuts, which is perfect for minimal keyboards lacking page, insert, or delete keys. Single-character shortcuts are also supported as fallbacks when navigating the Accession Names pane.

| Key(s) / Shortcut | Fallback / Alt Key | Action |
|---|---|---|
| `Arrows` | | Move cursor in active pane (Up/Down scrolls both synchronously) |
| `Tab` or `Ctrl+I` | | Switch focus between the Accession Names pane and the Sequence pane |
| `[` / `]` | | Decrease / increase Accession Name panel width |
| `Ctrl+Left` / `Ctrl+Right` / `Ctrl+L` / `Ctrl+R` | | Page sequences horizontally |
| `Ctrl+Up` / `Ctrl+Down` / `Ctrl+U` / `Ctrl+D` | | Page sequences/accessions vertically |
| `Ctrl+O` | `Insert` | Toggle edit mode between **INSERT (INS)** and **OVERWRITE (OVR)** |
| `Alphanumeric` | | Insert or overwrite nucleotides or amino acids at cursor (in sequence pane) |
| `Space` or `-` | | Insert alignment gap (`-`) at cursor |
| `Ctrl+K` | `Delete` / `D` (Accession Pane only) | Delete sequence character to the left of the cursor (shortens sequence) |
| `Ctrl+E` | `E` (Accession Pane only) | Edit selected accession name |
| `Ctrl+A` | `A` (Accession Pane only) | Add a new empty sequence row |
| `Ctrl+X` | `X` (Accession Pane only) | Delete current sequence row (requires confirmation) |
| `Ctrl+V` | `V` (Accession Pane only) | Cycle color visualization modes (**DNA/RNA** ➔ **Protein** ➔ **DIFF (variable sites)** ➔ **Monochrome**) |
| `Ctrl+F` | | Open search prompt (find accession name or sequence motif) |
| `Ctrl+N` | | Jump to the next search match |
| `Ctrl+G` | `G` (Accession Pane only) | Export transposed character counts/frequencies (all and polymorphic-only) CSVs |
| `Ctrl+Z` | `U` (Accession Pane only) | Undo last action |
| `Ctrl+Y` | `Y` (Accession Pane only) | Redo last action |
| `Ctrl+S` | `S` (Accession Pane only) | Save current alignment to a FASTA file |
| `Ctrl+Q` | `Q` (Accession Pane only) | Quit editor (warns if there are unsaved changes) |

---

## Sample Alignments Included

We have created two pre-loaded sample alignment files in the workspace:
1. `dna_sample.fasta` - Aligned coding DNA sequences (CDS) of mammalian alpha-synuclein (SNCA) (human, mouse, rat).
2. `protein_sample.fasta` - Aligned protein sequences of mammalian alpha-synuclein (SNCA) (human, mouse, rat).
