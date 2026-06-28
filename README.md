# AligNano: Terminal FASTA & A3M Alignment Editor

A lightweight, dependency-free Python terminal interface for browsing and editing multiple sequence alignments (MSA) in FASTA and A3M formats. It provides a real-time color-coded alignment grid, designed for efficient sequence inspection directly from the command line.

## Features

- 🖥️ **Command-Line Interface**: Clean, bordered ANSI layouts, real-time status overlays, and interactive file selection menus.
- 🧬 **Interactive Alignment Color Coding**:
  - **Nucleotides**: A (Red), T/U (Green), C (Blue), G (Yellow), Gaps (Dark Grey).
  - **Amino Acids**: ClustalX-inspired colors based on chemical properties (Acidic: Red, Basic: Blue, Polar: Green, Hydrophobic: Orange/Yellow, Cysteine: Pink, Glycine: Grey).
  - **DIFF Mode**: Selectively highlights only columns containing variable sites (mutations/gaps) to draw focus to polymorphs.
- 📊 **Dynamic Consensus & Conservation**: Real-time bottom-row ruler showing conservation levels (Bold Green for 100% identity, Bold White for >=80% conservation, lowercase for >=50%, and grey dots for polymorphic sites).
- 🔍 **Active Search & Live Highlights**: Search accession names or sequence motifs (`Ctrl+F`), instantly highlighting all matches across the viewport in high-contrast cyan.
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
| `Ctrl+U` / `Ctrl+D` | `Page Up` / `Page Down` | Page sequences/accessions vertically |
| `Ctrl+T` | `T` (Accession Pane only) | Toggle dedicated **MOVE SEQUENCE (MOV)** mode (then use normal **Up/Down** arrows to shift it) |
| `Ctrl+O` | `Insert` | Toggle edit mode between **INSERT (INS)** and **OVERWRITE (OVR)** |
| `Alphanumeric` | | Insert or overwrite nucleotides or amino acids at cursor (in sequence pane) |
| `Space` or `-` | | Insert alignment gap (`-`) at cursor |
| `Ctrl+K` | `Delete` / `D` (Accession Pane only) | In Sequence Pane: delete base to the left of the cursor; In Accession Pane: delete current sequence row (with confirmation) |
| `Ctrl+E` | `E` (Accession Pane only) | Edit selected accession name |
| `Ctrl+N` / `Ctrl+A` | `N` / `A` (Accession Pane only) | Add a new empty sequence row |
| `Ctrl+X` | `X` (Accession Pane only) | Delete current sequence row (requires confirmation) |
| `Ctrl+V` | `V` (Accession Pane only) | Cycle color visualization modes (**DNA/RNA** ➔ **Protein** ➔ **DIFF (variable sites)** ➔ **Monochrome**) |
| `Ctrl+P` | `P` (Accession Pane only) | Toggle alignment file save format (**FASTA** ➔ **A3M** ➔ **FASTA**) |
| `Ctrl+W` | `C` (Accession Pane only) | Sort/cluster sequences by Levenshtein distance relative to the top reference sequence |
| `Ctrl+F` | | Open search prompt (find accession name or sequence motif) |
| `Ctrl+J` | | Jump to the next search match |
| `Ctrl+G` | `G` (Accession Pane only) | Export transposed character counts/frequencies (all and polymorphic-only) CSVs |
| `Ctrl+Z` | `U` (Accession Pane only) | Undo last action |
| `Ctrl+Y` | `Y` (Accession Pane only) | Redo last action |
| `Ctrl+S` | `S` (Accession Pane only) | Save current alignment to a FASTA file |
| `Ctrl+Q` | `Q` (Accession Pane only) | Quit editor (warns if there are unsaved changes) |

---

## Sample Alignments Included

We have provided four curated, biologically authentic eukaryotic ubiquitin alignments:
1. `ubiquitin_dna.fasta` / `ubiquitin_dna.a3m` - Codon-aligned mature ubiquitin DNA coding sequences (228 bp) from 20 diverse eukaryotic species in FASTA and A3M formats.
2. `ubiquitin_protein.fasta` / `ubiquitin_protein.a3m` - Aligned mature ubiquitin protein sequences (76 AA) from the same 20 eukaryotic species in FASTA and A3M formats.
