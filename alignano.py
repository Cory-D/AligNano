#!/usr/bin/env python3
# AligNano
# Software Architect : Cory Dunn
import atexit
import copy
import os
import select
import shutil
import sys
import time


class TerminalResizeException(Exception):
    pass


def supports_256_colors():
    """Detects if stdout supports 256 colors."""
    if not sys.stdout.isatty():
        return False
    # Check COLORTERM first (truecolor / 24bit)
    colorterm = os.environ.get("COLORTERM", "").lower()
    if colorterm in ("truecolor", "24bit", "yes"):
        return True
    # Check TERM
    term = os.environ.get("TERM", "").lower()
    if any(k in term for k in ("256color", "256", "kitty", "alacritty", "foot", "iterm", "wezterm")):
        return True
    # Most modern xterm/screen/tmux terminals support 256 colors even if labeled xterm
    if term in ("xterm", "screen", "tmux", "rxvt", "linux"):
        return True
    # Check Windows Terminal/VS Code environments
    if sys.platform == "win32":
        if "WT_SESSION" in os.environ or "VSCODE_GIT_IPC_HANDLE" in os.environ:
            return True
    return False


def enable_mouse_tracking():
    """Enables SGR 1006 extended mouse tracking (clicks, drags, and wheel) in the terminal."""
    if sys.stdout.isatty():
        sys.stdout.write("\x1b[?1000h\x1b[?1002h\x1b[?1006h")
        sys.stdout.flush()


def disable_mouse_tracking():
    """Disables terminal mouse tracking, restoring native terminal copy/paste selection."""
    if sys.stdout.isatty():
        sys.stdout.write("\x1b[?1000l\x1b[?1002l\x1b[?1006l")
        sys.stdout.flush()


atexit.register(disable_mouse_tracking)


def get_theme_colors():
    """Returns terminal color codes depending on 256-color support."""
    has_256 = supports_256_colors()
    if has_256:
        return {
            "accent": "\x1b[38;5;198m",
            "gold": "\x1b[38;5;220m",
            "blue": "\x1b[38;5;20m",  # Dark blue
            "dim": "\x1b[38;5;244m",
            "bold": "\x1b[1m",
            "reset": "\x1b[0m",
            "select_bg": "\x1b[48;5;198m\x1b[38;5;231m",
        }
    else:
        return {
            "accent": "\x1b[35m",  # Magenta
            "gold": "\x1b[33m",  # Yellow
            "blue": "\x1b[34m",  # Blue
            "dim": "\x1b[2m",  # Dim / faint
            "bold": "\x1b[1m",
            "reset": "\x1b[0m",
            "select_bg": "\x1b[7m",  # Inverted text
        }


# ==============================================================================
# TERMINAL ESCAPE CODES & WINDOWS COMPATIBILITY
# ==============================================================================
_terminal_resized = False

if sys.platform == "win32":
    import msvcrt
    import ctypes

    # Enable Virtual Terminal Processing for ANSI colors and controls on Windows
    kernel32 = ctypes.windll.kernel32
    mode = ctypes.c_ulong()

    # stdout VT Mode
    stdout_handle = kernel32.GetStdHandle(-11)
    if kernel32.GetConsoleMode(stdout_handle, ctypes.byref(mode)):
        mode.value |= (
            0x0004 | 0x0008
        )  # ENABLE_VIRTUAL_TERMINAL_PROCESSING | DISABLE_NEWLINE_AUTO_RETURN
        kernel32.SetConsoleMode(stdout_handle, mode)

    # stdin VT Mode
    stdin_handle = kernel32.GetStdHandle(-10)
    if kernel32.GetConsoleMode(stdin_handle, ctypes.byref(mode)):
        mode.value |= 0x0200  # ENABLE_VIRTUAL_TERMINAL_INPUT
        kernel32.SetConsoleMode(stdin_handle, mode)
else:
    import termios
    import tty
    import signal

    _terminal_resized = False

    def resize_handler(signum, frame):
        global _terminal_resized
        _terminal_resized = True

    signal.signal(signal.SIGWINCH, resize_handler)

# ==============================================================================
# ALIVIEW-INSPIRED COLOR SCHEMES (ANSI 256-color)
# ==============================================================================
# Nucleotide Colors: A (Red), T/U (Green), C (Blue), G (Yellow), Gap (Dark Grey)
NUC_COLORS = {
    "A": "\x1b[48;5;196m\x1b[38;5;231m",  # Red bg, White fg
    "T": "\x1b[48;5;40m\x1b[38;5;231m",  # Green bg, White fg
    "U": "\x1b[48;5;40m\x1b[38;5;231m",  # Green bg, White fg
    "C": "\x1b[48;5;21m\x1b[38;5;231m",  # Blue bg, White fg
    "G": "\x1b[48;5;226m\x1b[38;5;16m",  # Yellow bg, Black fg
    "-": "\x1b[48;5;234m\x1b[38;5;244m",  # Dark grey bg, Grey fg
    ".": "\x1b[48;5;234m\x1b[38;5;244m",  # Dark grey bg, Grey fg
}
DEFAULT_NUC = "\x1b[48;5;250m\x1b[38;5;16m"

# Amino Acid Colors (Static ClustalX-like properties)
AA_COLORS = {
    # Acidic (D, E): Red bg, White fg
    "D": "\x1b[48;5;160m\x1b[38;5;231m",
    "E": "\x1b[48;5;160m\x1b[38;5;231m",
    # Basic (K, R, H): Blue bg, White fg
    "K": "\x1b[48;5;27m\x1b[38;5;231m",
    "R": "\x1b[48;5;27m\x1b[38;5;231m",
    "H": "\x1b[48;5;33m\x1b[38;5;231m",
    # Polar/Uncharged (N, Q, S, T): Green bg, Black fg
    "N": "\x1b[48;5;76m\x1b[38;5;16m",
    "Q": "\x1b[48;5;76m\x1b[38;5;16m",
    "S": "\x1b[48;5;82m\x1b[38;5;16m",
    "T": "\x1b[48;5;82m\x1b[38;5;16m",
    # Hydrophobic/Aromatic (A, I, L, M, F, W, V, P, Y): Orange/Yellow bg, Black fg
    "A": "\x1b[48;5;214m\x1b[38;5;16m",
    "I": "\x1b[48;5;214m\x1b[38;5;16m",
    "L": "\x1b[48;5;220m\x1b[38;5;16m",
    "M": "\x1b[48;5;220m\x1b[38;5;16m",
    "F": "\x1b[48;5;208m\x1b[38;5;16m",
    "W": "\x1b[48;5;208m\x1b[38;5;16m",
    "V": "\x1b[48;5;214m\x1b[38;5;16m",
    "P": "\x1b[48;5;178m\x1b[38;5;16m",
    "Y": "\x1b[48;5;184m\x1b[38;5;16m",
    # Cysteine (C): Pink bg, White fg
    "C": "\x1b[48;5;201m\x1b[38;5;231m",
    # Glycine (G): Grey bg, White fg
    "G": "\x1b[48;5;244m\x1b[38;5;231m",
    # Gaps
    "-": "\x1b[48;5;234m\x1b[38;5;244m",
    ".": "\x1b[48;5;234m\x1b[38;5;244m",
}
DEFAULT_AA = "\x1b[48;5;250m\x1b[38;5;16m"


# ==============================================================================
# KEYBOARD INPUT HANDLERS
# ==============================================================================
def read_key():
    """Cross-platform keyboard reader returning clean logical strings."""
    global _terminal_resized
    if _terminal_resized:
        _terminal_resized = False
        return "TERMINAL_RESIZE"

    if sys.platform == "win32":
        # Windows keyboard input
        ch = msvcrt.getch()
        if ch in (b"\x00", b"\xe0"):
            ch2 = msvcrt.getch()
            code = f"win_{ch.hex()}_{ch2.hex()}"
            win_map = {
                "win_e0_48": "KEY_UP",
                "win_e0_50": "KEY_DOWN",
                "win_e0_4b": "KEY_LEFT",
                "win_e0_4d": "KEY_RIGHT",
                "win_e0_49": "PAGE_UP",
                "win_e0_51": "PAGE_DOWN",
                "win_e0_52": "INSERT",
                "win_e0_53": "DELETE",
                "win_e0_73": "CTRL_LEFT",
                "win_e0_74": "CTRL_RIGHT",
                "win_e0_8d": "CTRL_UP",
                "win_e0_91": "CTRL_DOWN",
            }
            return win_map.get(code, "UNKNOWN")

        try:
            k = ch.decode("utf-8")
        except UnicodeDecodeError:
            k = ch

        common_map = {
            "\x01": "ADD_ROW",  # Ctrl+A
            "\x02": "TOGGLE_MOVE",  # Ctrl+B
            "\x04": "PAGE_DOWN",  # Ctrl+D
            "\x05": "EDIT_NAME",  # Ctrl+E
            "\x06": "SEARCH",  # Ctrl+F
            "\x0b": "DELETE",  # Ctrl+K
            "\x0c": "PAGE_LEFT",  # Ctrl+L
            "\x0e": "ADD_ROW",  # Ctrl+N
            "\x0f": "INSERT",  # Ctrl+O
            "\x10": "TOGGLE_FORMAT",  # Ctrl+P
            "\x11": "QUIT",  # Ctrl+Q
            "\x12": "PAGE_RIGHT",  # Ctrl+R
            "\x13": "SAVE",  # Ctrl+S
            "\x14": "TRANSLATE",  # Ctrl+T
            "\x15": "PAGE_UP",  # Ctrl+U
            "\x16": "CYCLE_COLORS",  # Ctrl+V
            "\x17": "SORT_DIST",  # Ctrl+W
            "\x18": "DELETE_ROW",  # Ctrl+X
            "\x19": "REDO",  # Ctrl+Y
            "\x1a": "UNDO",
            "\x7f": "DELETE",
            "\x08": "DELETE",
            "\x07": "EXPORT_FREQ",
            "\r": "ENTER",
            "\n": "FIND_NEXT",  # Ctrl+J
            "\t": "TAB",
            "\x1b": "ESCAPE",
        }
        return common_map.get(k, k)
    else:
        # Unix keyboard & mouse input
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            try:
                ch = os.read(fd, 1).decode("utf-8", errors="ignore")
            except (InterruptedError, OSError):
                if _terminal_resized:
                    _terminal_resized = False
                return "TERMINAL_RESIZE"

            if _terminal_resized:
                _terminal_resized = False
                return "TERMINAL_RESIZE"

            if not ch:
                return "UNKNOWN"

            if ch == "\x1b":
                try:
                    rlist, _, _ = select.select([fd], [], [], 0.05)
                except (InterruptedError, OSError):
                    if _terminal_resized:
                        _terminal_resized = False
                    return "TERMINAL_RESIZE"

                if rlist:
                    try:
                        chunk = os.read(fd, 32).decode("utf-8", errors="ignore")
                    except (InterruptedError, OSError):
                        if _terminal_resized:
                            _terminal_resized = False
                        return "TERMINAL_RESIZE"

                    seq = ch + chunk

                    # SGR mouse tracking sequence: \x1b[<btn;col;row;[M/m]
                    if seq.startswith("\x1b[<"):
                        while not (seq.endswith("M") or seq.endswith("m")) and len(seq) < 32:
                            try:
                                r2, _, _ = select.select([fd], [], [], 0.02)
                            except (InterruptedError, OSError):
                                break
                            if not r2:
                                break
                            try:
                                seq += os.read(fd, 8).decode("utf-8", errors="ignore")
                            except (InterruptedError, OSError):
                                break

                        try:
                            content = seq[3:-1]
                            parts = content.split(";")
                            if len(parts) == 3:
                                btn = int(parts[0])
                                col = int(parts[1])
                                row = int(parts[2])
                                is_release = seq.endswith("m")
                                if is_release:
                                    return ("MOUSE_RELEASE", btn, col, row)
                                if btn == 64:
                                    return ("MOUSE_WHEEL_UP", col, row)
                                elif btn == 65:
                                    return ("MOUSE_WHEEL_DOWN", col, row)
                                elif btn == 66:
                                    return ("MOUSE_WHEEL_LEFT", col, row)
                                elif btn == 67:
                                    return ("MOUSE_WHEEL_RIGHT", col, row)
                                elif btn == 32:
                                    return ("MOUSE_DRAG", col, row)
                                elif btn == 0:
                                    return ("MOUSE_PRESS", col, row)
                                elif btn == 1:
                                    return ("MOUSE_MIDDLE", col, row)
                                elif btn == 2:
                                    return ("MOUSE_RIGHT", col, row)
                        except Exception:
                            pass
                        return "UNKNOWN"

                    # Legacy X10 mouse tracking sequence: \x1b[M followed by 3 bytes
                    if seq.startswith("\x1b[M") and len(seq) >= 6:
                        try:
                            btn_raw = ord(seq[3]) - 32
                            col = ord(seq[4]) - 32
                            row = ord(seq[5]) - 32
                            if btn_raw == 64:
                                return ("MOUSE_WHEEL_UP", col, row)
                            elif btn_raw == 65:
                                return ("MOUSE_WHEEL_DOWN", col, row)
                            elif btn_raw == 32:
                                return ("MOUSE_DRAG", col, row)
                            elif btn_raw == 0:
                                return ("MOUSE_PRESS", col, row)
                            elif btn_raw == 3:
                                return ("MOUSE_RELEASE", 0, col, row)
                        except Exception:
                            pass
                        return "UNKNOWN"

                    unix_map = {
                        "\x1b[A": "KEY_UP",
                        "\x1b[B": "KEY_DOWN",
                        "\x1b[C": "KEY_RIGHT",
                        "\x1b[D": "KEY_LEFT",
                        "\x1b[5~": "PAGE_UP",
                        "\x1b[6~": "PAGE_DOWN",
                        "\x1b[2~": "INSERT",
                        "\x1b[3~": "DELETE",
                        "\x1b[1;5A": "CTRL_UP",
                        "\x1b[1;5B": "CTRL_DOWN",
                        "\x1b[1;5C": "CTRL_RIGHT",
                        "\x1b[1;5D": "CTRL_LEFT",
                        "\x1bOA": "KEY_UP",
                        "\x1bOB": "KEY_DOWN",
                        "\x1bOC": "KEY_RIGHT",
                        "\x1bOD": "KEY_LEFT",
                    }
                    return unix_map.get(seq, "ESCAPE")
                return "ESCAPE"

            common_map = {
                "\x01": "ADD_ROW",  # Ctrl+A
                "\x02": "TOGGLE_MOVE",  # Ctrl+B
                "\x04": "PAGE_DOWN",  # Ctrl+D
                "\x05": "EDIT_NAME",  # Ctrl+E
                "\x06": "SEARCH",  # Ctrl+F
                "\x0b": "DELETE",  # Ctrl+K
                "\x0c": "PAGE_LEFT",  # Ctrl+L
                "\x0e": "ADD_ROW",  # Ctrl+N
                "\x0f": "INSERT",  # Ctrl+O
                "\x10": "TOGGLE_FORMAT",  # Ctrl+P
                "\x11": "QUIT",  # Ctrl+Q
                "\x12": "PAGE_RIGHT",  # Ctrl+R
                "\x13": "SAVE",  # Ctrl+S
                "\x14": "TRANSLATE",  # Ctrl+T
                "\x15": "PAGE_UP",  # Ctrl+U
                "\x16": "CYCLE_COLORS",  # Ctrl+V
                "\x17": "SORT_DIST",  # Ctrl+W
                "\x18": "DELETE_ROW",  # Ctrl+X
                "\x19": "REDO",  # Ctrl+Y
                "\x1a": "UNDO",
                "\x7f": "DELETE",
                "\x08": "HELP",
                "\x07": "EXPORT_FREQ",
                "\r": "ENTER",
                "\n": "FIND_NEXT",  # Ctrl+J
                "\t": "TAB",
            }
            return common_map.get(ch, ch)
        finally:
            for _ in range(3):
                try:
                    termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
                    break
                except Exception:
                    try:
                        termios.tcsetattr(fd, termios.TCSANOW, old_settings)
                        break
                    except Exception:
                        pass


# ==============================================================================
# FASTA FILE PARSING & SAVING
# ==============================================================================
def load_fasta(filepath):
    """Loads a FASTA file and returns lists of headers and padded sequences."""
    headers = []
    sequences = []
    current_seq = []

    if not os.path.exists(filepath):
        return [], []

    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            if line.startswith(">"):
                if current_seq:
                    sequences.append("".join(current_seq))
                    current_seq = []
                # Keep everything after > as the accession
                headers.append(line[1:])
            else:
                current_seq.append(line)
        if current_seq:
            sequences.append("".join(current_seq))

    # Pad sequences to max length with gaps
    if sequences:
        max_len = max(len(s) for s in sequences)
        for i in range(len(sequences)):
            if len(sequences[i]) < max_len:
                sequences[i] = sequences[i] + "-" * (max_len - len(sequences[i]))

    # If file was empty, return empty lists
    return headers, sequences


def a3m_to_fasta(a3m_seqs):
    """Converts a list of query-anchored A3M sequences to standard aligned FASTA sequences."""
    if not a3m_seqs:
        return []

    num_seqs = len(a3m_seqs)
    parsed_seqs = []
    for seq in a3m_seqs:
        match_states = []
        pre_insertions = []

        idx = 0
        while idx < len(seq) and seq[idx].islower():
            pre_insertions.append(seq[idx].upper())
            idx += 1

        current_insertions = []
        while idx < len(seq):
            c = seq[idx]
            if c.islower():
                current_insertions.append(c.upper())
            else:
                if match_states:
                    match_states[-1][1].extend(current_insertions)
                else:
                    pre_insertions.extend(current_insertions)
                current_insertions = []
                match_states.append((c, []))
            idx += 1
        if match_states:
            match_states[-1][1].extend(current_insertions)
        else:
            pre_insertions.extend(current_insertions)

        parsed_seqs.append((pre_insertions, match_states))

    max_pre = max(len(p[0]) for p in parsed_seqs) if parsed_seqs else 0
    aligned_seqs = [[] for _ in range(num_seqs)]

    for s_idx in range(num_seqs):
        pre_ins = parsed_seqs[s_idx][0]
        aligned_seqs[s_idx].extend(pre_ins)
        aligned_seqs[s_idx].extend(["-"] * (max_pre - len(pre_ins)))

    query_match_states_count = len(parsed_seqs[0][1]) if parsed_seqs else 0

    for col_idx in range(query_match_states_count):
        for s_idx in range(num_seqs):
            m_states = parsed_seqs[s_idx][1]
            if col_idx < len(m_states):
                aligned_seqs[s_idx].append(m_states[col_idx][0])
            else:
                aligned_seqs[s_idx].append("-")

        max_post = 0
        for s_idx in range(num_seqs):
            m_states = parsed_seqs[s_idx][1]
            if col_idx < len(m_states):
                max_post = max(max_post, len(m_states[col_idx][1]))

        if max_post > 0:
            for s_idx in range(num_seqs):
                m_states = parsed_seqs[s_idx][1]
                post_ins = m_states[col_idx][1] if col_idx < len(m_states) else []
                aligned_seqs[s_idx].extend(post_ins)
                aligned_seqs[s_idx].extend(["-"] * (max_post - len(post_ins)))

    return ["".join(s) for s in aligned_seqs]


def fasta_to_a3m(sequences):
    """Converts standard aligned FASTA sequences to query-anchored A3M sequences."""
    if not sequences:
        return []

    num_seqs = len(sequences)
    seq_len = len(sequences[0])

    a3m_seqs = [[] for _ in range(num_seqs)]

    for col_idx in range(seq_len):
        query_char = sequences[0][col_idx]
        if query_char == "-":
            for s_idx in range(num_seqs):
                c = sequences[s_idx][col_idx]
                if c != "-":
                    a3m_seqs[s_idx].append(c.lower())
        else:
            for s_idx in range(num_seqs):
                c = sequences[s_idx][col_idx]
                a3m_seqs[s_idx].append(c.upper())

    return ["".join(s) for s in a3m_seqs]


def levenshtein_distance(s1, s2):
    """Calculates Levenshtein distance between s1 and s2 (excluding gaps and dots, case-insensitive)."""
    seq1 = s1.replace("-", "").replace(".", "").upper()
    seq2 = s2.replace("-", "").replace(".", "").upper()

    if len(seq1) < len(seq2):
        return levenshtein_distance(seq2, seq1)

    if len(seq2) == 0:
        return len(seq1)

    previous_row = range(len(seq2) + 1)
    for i, c1 in enumerate(seq1):
        current_row = [i + 1]
        for j, c2 in enumerate(seq2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row

    return previous_row[-1]


def save_fasta(filepath, headers, sequences):
    """Saves headers and sequences to FASTA format."""
    with open(filepath, "w", encoding="utf-8") as f:
        for h, s in zip(headers, sequences):
            f.write(f">{h}\n")
            f.write(s + "\n")


# ==============================================================================
# STOCKHOLM (.STO) FILE PARSING & SAVING
# ==============================================================================
def load_stockholm(filepath):
    """Loads a Stockholm (.sto/.stk) alignment file and returns headers and padded sequences."""
    seq_dict = {}
    if not os.path.exists(filepath):
        return [], []

    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            if line.startswith("#"):
                continue
            if line == "//":
                break  # End of alignment record
            parts = line.split(None, 1)
            if len(parts) == 2:
                name, chunk = parts[0], parts[1].replace(" ", "").replace(".", "-")
                if name not in seq_dict:
                    seq_dict[name] = []
                seq_dict[name].append(chunk)

    headers = list(seq_dict.keys())
    sequences = ["".join(chunks) for chunks in seq_dict.values()]

    # Pad sequences to max length with gaps
    if sequences:
        max_len = max(len(s) for s in sequences)
        for i in range(len(sequences)):
            if len(sequences[i]) < max_len:
                sequences[i] = sequences[i] + "-" * (max_len - len(sequences[i]))

    return headers, sequences


def save_stockholm(filepath, headers, sequences):
    """Saves headers and sequences to Stockholm (.sto) format."""
    with open(filepath, "w", encoding="utf-8") as f:
        f.write("# STOCKHOLM 1.0\n\n")
        max_name_len = max((len(h) for h in headers), default=10)
        for h, s in zip(headers, sequences):
            f.write(f"{h:<{max_name_len + 4}}{s}\n")
        f.write("//\n")


def load_alignment(filepath):
    """Loads an alignment from FASTA, A3M, or Stockholm format."""
    if not filepath or not os.path.exists(filepath):
        return [], [], "fasta"

    ext = os.path.splitext(filepath)[1].lower()
    if ext in (".sto", ".stk", ".stockholm"):
        headers, sequences = load_stockholm(filepath)
        return headers, sequences, "sto"

    # Check first non-empty line for Stockholm signature
    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if line:
                    if line.startswith("# STOCKHOLM") or line.startswith("#=GF"):
                        headers, sequences = load_stockholm(filepath)
                        return headers, sequences, "sto"
                    break
    except Exception:
        pass

    # Default to FASTA / A3M loader
    headers, sequences = load_fasta(filepath)
    if ext == ".a3m":
        try:
            sequences = a3m_to_fasta(sequences)
            return headers, sequences, "a3m"
        except Exception:
            return headers, sequences, "a3m"

    return headers, sequences, "fasta"


# ==============================================================================
# DNA TO PROTEIN TRANSLATION TABLES & LOGIC
# ==============================================================================
STANDARD_CODON_TABLE = {
    "TTT": "F", "TTC": "F", "TTA": "L", "TTG": "L",
    "TCT": "S", "TCC": "S", "TCA": "S", "TCG": "S",
    "TAT": "Y", "TAC": "Y", "TAA": "*", "TAG": "*",
    "TGT": "C", "TGC": "C", "TGA": "*", "TGG": "W",
    "CTT": "L", "CTC": "L", "CTA": "L", "CTG": "L",
    "CCT": "P", "CCC": "P", "CCA": "P", "CCG": "P",
    "CAT": "H", "CAC": "H", "CAA": "Q", "CAG": "Q",
    "CGT": "R", "CGC": "R", "CGA": "R", "CGG": "R",
    "ATT": "I", "ATC": "I", "ATA": "I", "ATG": "M",
    "ACT": "T", "ACC": "T", "ACA": "T", "ACG": "T",
    "AAT": "N", "AAC": "N", "AAA": "K", "AAG": "K",
    "AGT": "S", "AGC": "S", "AGA": "R", "AGG": "R",
    "GTT": "V", "GTC": "V", "GTA": "V", "GTG": "V",
    "GCT": "A", "GCC": "A", "GCA": "A", "GCG": "A",
    "GAT": "D", "GAC": "D", "GAA": "E", "GAG": "E",
    "GGT": "G", "GGC": "G", "GGA": "G", "GGG": "G",
}

GENETIC_CODE_OVERRIDES = {
    1: {},  # Standard Code
    2: {"AGA": "*", "AGG": "*", "ATA": "M", "TGA": "W"},  # Vertebrate Mitochondrial
    3: {"ATA": "M", "CTA": "T", "CTC": "T", "CTG": "T", "CTT": "T", "TGA": "W"},  # Yeast Mitochondrial
    4: {"TGA": "W"},  # Mold, Protozoan, Coelenterate Mito / Mycoplasma
    5: {"AGA": "S", "AGG": "S", "ATA": "M", "TGA": "W"},  # Invertebrate Mitochondrial
    6: {"TAA": "Q", "TAG": "Q"},  # Ciliate, Dasycladacean, Hexamita Nuclear
    9: {"AAA": "N", "AGA": "S", "AGG": "S", "TGA": "W"},  # Echinoderm and Flatworm Mito
    10: {"TGA": "C"},  # Euplotid Nuclear
    11: {},  # Bacterial, Archaeal and Plant Plastid
    12: {"CTG": "S"},  # Alternative Yeast Nuclear
    13: {"AGA": "G", "AGG": "G", "ATA": "M", "TGA": "W"},  # Ascidian Mitochondrial
    14: {"AAA": "N", "AGA": "S", "AGG": "S", "TAA": "Y", "TGA": "W"},  # Alternative Flatworm Mito
    15: {"TAG": "Q"},  # Blepharisma Nuclear
    16: {"TAG": "L"},  # Chlorophycean Mitochondrial
    21: {"AAA": "N", "AGA": "S", "AGG": "S", "ATA": "M", "TGA": "W"},  # Trematode Mito
    22: {"TCA": "*", "TAG": "L"},  # Scenedesmus obliquus Mito
    23: {"TTA": "*"},  # Thraustochytrium Mito
    24: {"AGA": "S", "AGG": "K", "TGA": "W"},  # Rhabdopleuridae Mito
    25: {"TGA": "G"},  # Candidate Division SR1 / Gracilibacteria
    26: {"CTG": "A"},  # Pachysolen tannophilus Nuclear
    27: {"TAA": "Q", "TAG": "Q", "TGA": "W"},  # Karyorelict Nuclear
    28: {"TAA": "Q", "TAG": "Q", "TGA": "W"},  # Condylostoma Nuclear
    29: {"TAA": "Y", "TAG": "Y"},  # Mesodinium Nuclear
    30: {"TAA": "E", "TAG": "E"},  # Peritrich Nuclear
    31: {"TAA": "E", "TAG": "E", "TGA": "W"},  # Blastocrithidia Nuclear
    32: {"TAG": "W"},  # Balanophoraceae Plastid
    33: {"AGA": "S", "AGG": "K", "TAA": "Y", "TGA": "W"},  # Cephalodiscidae Mito
}

GENETIC_CODE_NAMES = {
    1: "Standard Code",
    2: "Vertebrate Mitochondrial",
    3: "Yeast Mitochondrial",
    4: "Mold/Protozoan/Coelenterate Mito",
    5: "Invertebrate Mitochondrial",
    6: "Ciliate Nuclear",
    9: "Echinoderm/Flatworm Mito",
    10: "Euplotid Nuclear",
    11: "Bacterial/Archaeal/Plastid",
    12: "Alternative Yeast Nuclear",
    13: "Ascidian Mitochondrial",
    14: "Alternative Flatworm Mito",
    15: "Blepharisma Nuclear",
    16: "Chlorophycean Mito",
    21: "Trematode Mitochondrial",
    22: "Scenedesmus obliquus Mito",
    23: "Thraustochytrium Mito",
    24: "Rhabdopleuridae Mito",
    25: "Candidate Division SR1",
    26: "Pachysolen tannophilus",
    27: "Karyorelict Nuclear",
    28: "Condylostoma Nuclear",
    29: "Mesodinium Nuclear",
    30: "Peritrich Nuclear",
    31: "Blastocrithidia Nuclear",
    32: "Balanophoraceae Plastid",
    33: "Cephalodiscidae Mito",
}


def get_codon_table(code_id=1):
    """Returns codon translation table for given NCBI code ID."""
    table = STANDARD_CODON_TABLE.copy()
    overrides = GENETIC_CODE_OVERRIDES.get(code_id, {})
    table.update(overrides)
    return table


COMPLEMENT_MAP = str.maketrans(
    "ATCGURYSWKMBDHVatcguryswkmbdhv",
    "TAGCAYRSWMKVHDBtagcayrswmkvhdb",
)


def reverse_complement(seq):
    """Calculates reverse complement of a nucleotide sequence string."""
    return seq.translate(COMPLEMENT_MAP)[::-1]


def translate_alignment(sequences, frame_str="+1", code_id=1):
    """Translates a list of aligned DNA sequence strings to protein sequences."""
    frame_clean = str(frame_str).strip()
    is_reverse = frame_clean.startswith("-")
    try:
        frame_num = abs(int(frame_clean))
        if frame_num not in (1, 2, 3):
            frame_num = 1
    except ValueError:
        frame_num = 1
        is_reverse = False

    offset = frame_num - 1
    table = get_codon_table(code_id)

    translated_seqs = []
    for seq in sequences:
        s = reverse_complement(seq) if is_reverse else seq
        s_sliced = s[offset:]
        aa_list = []
        for i in range(0, len(s_sliced) - 2, 3):
            codon = s_sliced[i : i + 3].upper().replace("U", "T")
            if codon in ("---", "..."):
                aa_list.append("-")
            elif codon in table:
                aa_list.append(table[codon])
            else:
                aa_list.append("X")
        translated_seqs.append("".join(aa_list))

    return translated_seqs


def detect_vis_mode(sequences):
    """Detects whether alignment is likely nucleotide or protein."""
    if not sequences:
        return "nuc"
    # Count characters in first 1000 characters of alignment
    chars = "".join(sequences)[:1000].upper()
    nuc_chars = sum(1 for c in chars if c in "ACGUTN-")
    total = len(chars)
    if total == 0:
        return "nuc"
    # If > 80% are typical nucleotide characters, use nucleotide coloring
    if (nuc_chars / total) > 0.8:
        return "nuc"
    return "aa"


# ==============================================================================
# UNDO / REDO STATE STACK
# ==============================================================================
class StateHistory:
    def __init__(self):
        self.undo_stack = []
        self.redo_stack = []

    def push_state(self, headers, sequences):
        # Store copy of the alignment state
        self.undo_stack.append((copy.deepcopy(headers), copy.deepcopy(sequences)))
        self.redo_stack.clear()
        if len(self.undo_stack) > 50:
            self.undo_stack.pop(0)

    def undo(self, current_headers, current_sequences):
        if not self.undo_stack:
            return None
        self.redo_stack.append(
            (copy.deepcopy(current_headers), copy.deepcopy(current_sequences))
        )
        return self.undo_stack.pop()

    def redo(self, current_headers, current_sequences):
        if not self.redo_stack:
            return None
        self.undo_stack.append(
            (copy.deepcopy(current_headers), copy.deepcopy(current_sequences))
        )
        return self.redo_stack.pop()


# ==============================================================================
# SCREEN RENDERING LOOP
# ==============================================================================
# Caches for performance optimization with large alignments
_consensus_cache_state = None
_consensus_col_cache = {}

_diff_cache_state = None
_diff_col_cache = {}


def get_modal_menu_structure(current_vis_mode, alignment_format, mouse_enabled=False):
    """Returns categorized menu items and shortcuts for the modal menu."""
    radio_nuc = "(*)" if current_vis_mode == "nuc" else "( )"
    radio_aa = "(*)" if current_vis_mode == "aa" else "( )"
    radio_diff = "(*)" if current_vis_mode == "diff" else "( )"
    radio_mono = "(*)" if current_vis_mode == "mono" else "( )"

    categories = [
        (
            "File",
            [
                ("SAVE", "Save Alignment", "Ctrl+S"),
                ("TOGGLE_FORMAT", f"Format: < {alignment_format.upper()} >", "◄/►"),
                ("EXPORT_FREQ", "Export Frequencies (CSV)", ""),
                ("HELP", "Help & Overview", "?"),
                ("QUIT", "Quit Editor", "Ctrl+Q"),
            ],
        ),
        (
            "Edit",
            [
                ("UNDO", "Undo Last Action", "Ctrl+Z"),
                ("REDO", "Redo Last Action", "Ctrl+Y"),
                ("TOGGLE_INSERT", "Toggle Insert / Overwrite", "Insert"),
                ("EDIT_NAME", "Rename Accession Header", ""),
                ("ADD_ROW", "Add New Sequence Row", ""),
                ("DELETE_ROW", "Delete Current Row", ""),
                ("TOGGLE_MOVE", "Reorder / Move Sequence Row", ""),
            ],
        ),
        (
            "Display",
            [
                ("COLOR_NUC", f"{radio_nuc} DNA / RNA Mode", ""),
                ("COLOR_AA", f"{radio_aa} Protein (ClustalX)", ""),
                ("COLOR_DIFF", f"{radio_diff} DIFF (Variable Sites)", ""),
                ("COLOR_MONO", f"{radio_mono} Monochrome", ""),
                ("TOGGLE_MOUSE", f"Mouse Mode: < {'ON' if mouse_enabled else 'OFF'} >", "◄/►"),
                ("PANE_WIDEN", "Widen Accession Pane", "]"),
                ("PANE_NARROW", "Narrow Accession Pane", "["),
                ("PAGE_LEFT", "Page Sequences Left", ""),
                ("PAGE_RIGHT", "Page Sequences Right", ""),
            ],
        ),
        (
            "Tools",
            [
                ("SEARCH", "Search Motif or Header", "Ctrl+F"),
                ("FIND_NEXT", "Find Next Match", "Ctrl+J"),
                ("TRANSLATE", "Translate DNA to Protein", ""),
                ("SORT_DIST", "Sort by Levenshtein Dist", ""),
            ],
        ),
    ]
    return categories


def build_modal_menu_lines(modal_state):
    """Builds pre-formatted ANSI lines for the centered two-column modal menu."""
    active_col = modal_state["active_col"]
    cat_idx = modal_state["cat_idx"]
    act_idx = modal_state["act_idx"]
    categories = modal_state["categories"]

    colors = get_theme_colors()
    accent = colors["accent"]
    gold = colors["gold"]
    blue = colors["blue"]
    bold = colors["bold"]
    reset = colors["reset"]
    dim = colors["dim"]
    select_bg = colors["select_bg"]

    inner_w = 68
    cat_w = 20
    act_w = 47

    lines = []

    # 1. Top border
    title = " AligNano Main Menu "
    pad_left = (inner_w - len(title)) // 2
    pad_right = inner_w - pad_left - len(title)
    top_line = f"{blue}┌{'─' * pad_left}{gold}{bold}{title}{reset}{blue}{'─' * pad_right}┐{reset}"
    lines.append(top_line)

    # 2. Header column titles
    header_cat = f"  CATEGORIES".ljust(cat_w)
    header_act = f"  ACTIONS".ljust(act_w)
    hdr_line = f"{blue}│{gold}{bold}{header_cat}{reset}{blue}│{gold}{bold}{header_act}{reset}{blue}│{reset}"
    lines.append(hdr_line)

    # 3. Mid separator
    mid_sep = f"{blue}├{'─' * cat_w}┼{'─' * act_w}┤{reset}"
    lines.append(mid_sep)

    # 4. Content rows (dynamically sized to longest menu category)
    max_rows = max(len(cat[1]) for cat in categories)
    actions = categories[cat_idx][1]

    for r in range(max_rows):
        # Left column: Categories
        if r < len(categories):
            cat_num = r + 1
            cat_name = categories[r][0]
            if r == cat_idx:
                if active_col == "cat":
                    cat_cell = f"{select_bg} ► {cat_num}. {cat_name:<13} {reset}"
                else:
                    cat_cell = f"{accent}{bold} • {cat_num}. {cat_name:<13} {reset}"
            else:
                cat_cell = f"   {cat_num}. {cat_name:<13} "
        else:
            cat_cell = " " * cat_w

        # Right column: Actions
        if r < len(actions):
            act_code, act_name, act_badge = actions[r]
            badge_str = f"[{act_badge}]" if act_badge else ""
            if r == act_idx:
                if active_col == "act":
                    act_cell = f"{select_bg} ► {act_name:<33} {badge_str:>8} {reset}"
                else:
                    act_cell = f"{gold}   {act_name:<33} {badge_str:>8} {reset}"
            else:
                act_cell = f"   {act_name:<33} {dim}{badge_str:>8}{reset} "
        else:
            act_cell = " " * act_w

        lines.append(f"{blue}│{reset}{cat_cell}{blue}│{reset}{act_cell}{blue}│{reset}")

    # 5. Bottom divider
    bot_sep = f"{blue}├{'─' * inner_w}┤{reset}"
    lines.append(bot_sep)

    # 6. Hints line
    hints = " [▲/▼] Move  [◄/►] Column  [Enter] Select  [1-4] Jump  [Esc] Back "
    pad_h = max(0, inner_w - len(hints))
    hints_line = f"{blue}│{dim}{hints}{' ' * pad_h}{reset}{blue}│{reset}"
    lines.append(hints_line)

    # 7. Bottom border
    bot_line = f"{blue}└{'─' * inner_w}┘{reset}"
    lines.append(bot_line)

    return lines


def draw_screen(
    headers,
    sequences,
    cursor_row,
    cursor_col,
    row_offset,
    col_offset,
    active_pane,
    filename,
    insert_mode,
    vis_mode,
    modified,
    acc_width,
    status_msg="",
    prompt_mode=None,
    prompt_text="",
    prompt_input="",
    move_mode=False,
    search_query="",
    search_matches=None,
    alignment_format="fasta",
    modal_state=None,
):
    """Composes and renders the entire editor layout to stdout in a single write."""
    global _consensus_cache_state, _consensus_col_cache
    global _diff_cache_state, _diff_col_cache

    cols, rows = shutil.get_terminal_size((80, 24))
    num_seqs = len(sequences)
    seq_len = len(sequences[0]) if num_seqs > 0 else 0

    # Borders: left border (1), separator (1), right border (1), safety spacer (1)
    seq_width = cols - acc_width - 4
    view_height = rows - 10 if num_seqs > 0 else rows - 9

    # Fast fingerprint to detect sequence list modifications without id() recycling
    seq_state = (
        len(sequences),
        tuple(len(s) for s in sequences),
        sum(hash(s) for s in sequences),
    )
    if _consensus_cache_state != seq_state:
        _consensus_cache_state = seq_state
        _consensus_col_cache = {}
    if _diff_cache_state != seq_state:
        _diff_cache_state = seq_state
        _diff_col_cache = {}

    # Pre-process search matches for fast O(1) row lookup in the viewport
    acc_matches_by_row = {}
    seq_matches_by_row = {}
    if search_query and search_matches:
        for r, c_start, pane in search_matches:
            if row_offset <= r < row_offset + view_height:
                if pane == "acc":
                    if r not in acc_matches_by_row:
                        acc_matches_by_row[r] = []
                    acc_matches_by_row[r].append((c_start, len(search_query)))
                elif pane == "seq":
                    if r not in seq_matches_by_row:
                        seq_matches_by_row[r] = []
                    seq_matches_by_row[r].append((c_start, len(search_query)))

    # Calculate non-identical columns for DIFF visualization mode
    non_identical_cols = set()
    if vis_mode == "diff" and sequences:
        num_seqs_val = len(sequences)
        seq_len_val = len(sequences[0])
        for col_idx in range(col_offset, min(seq_len_val, col_offset + seq_width)):
            if col_idx in _diff_col_cache:
                if not _diff_col_cache[col_idx]:
                    non_identical_cols.add(col_idx)
                continue

            first_char = (
                sequences[0][col_idx].upper() if col_idx < len(sequences[0]) else "-"
            )
            is_identical = True
            for r in range(1, num_seqs_val):
                char = (
                    sequences[r][col_idx].upper()
                    if col_idx < len(sequences[r])
                    else "-"
                )
                if char != first_char:
                    is_identical = False
                    break
            _diff_col_cache[col_idx] = is_identical
            if not is_identical:
                non_identical_cols.add(col_idx)

    if view_height < 1 or seq_width < 1:
        sys.stdout.write("\x1b[H\x1b[2JTerminal too small! Please resize.\n")
        sys.stdout.flush()
        return

    has_256 = supports_256_colors()
    colors_theme = get_theme_colors()

    lines = []

    # 1. Header top border (ASCII)
    lines.append("+" + "-" * (cols - 2) + "+")

    # 2. Header Status Line
    filename_display = os.path.basename(filename) if filename else "[New Alignment]"
    mod_marker = " *" if modified else ""
    mode_marker = "MOV" if move_mode else ("INS" if insert_mode else "OVR")
    vis_name = (
        "DNA/RNA"
        if vis_mode == "nuc"
        else (
            "Protein"
            if vis_mode == "aa"
            else ("Diff (Var)" if vis_mode == "diff" else "Monochrome")
        )
    )
    format_marker = alignment_format.upper()

    header_left = f" # AligNano # File: {filename_display}{mod_marker} | Mode: {mode_marker} | Colors: {vis_name} | Format: {format_marker} | Pane: {acc_width}"
    header_right = f"Seq: {cursor_row + 1}/{num_seqs} Col: {cursor_col + 1}/{seq_len} "

    space_left = cols - 2 - len(header_left) - len(header_right)
    if space_left < 0:
        header_text = (header_left + " " + header_right)[: cols - 2]
        lines.append("|" + header_text + " " * (cols - 2 - len(header_text)) + "|")
    else:
        lines.append("|" + header_left + " " * space_left + header_right + "|")

    # 3. Header separator (ASCII)
    lines.append("+" + "-" * acc_width + "+" + "-" * (cols - acc_width - 3) + "+")

    # 3.1. Coordinates Ruler Lines
    nums_list = [" "] * seq_width
    ticks_list = [" "] * seq_width
    for col_i in range(seq_width):
        col_val = col_offset + col_i + 1
        if col_val == 1 or col_val % 10 == 0:
            val_str = str(col_val)
            for char_pos, char_val in enumerate(val_str):
                idx = col_i + char_pos
                if idx < seq_width:
                    nums_list[idx] = char_val
            ticks_list[col_i] = "|"
        elif col_val % 5 == 0:
            ticks_list[col_i] = "+"
        else:
            ticks_list[col_i] = "."

    ruler_nums_str = colors_theme["dim"] + "".join(nums_list) + colors_theme["reset"]
    ruler_ticks_str = colors_theme["dim"] + "".join(ticks_list) + colors_theme["reset"]

    acc_blank = " " * acc_width
    lines.append(f"|{acc_blank}|{ruler_nums_str}|")
    lines.append(f"|{acc_blank}+{ruler_ticks_str}|")

    # 4. Body Viewport
    for i in range(view_height):
        seq_idx = row_offset + i

        # Accession Subpane
        acc_part = ""
        if seq_idx < num_seqs:
            max_idx_len = len(str(num_seqs))
            name = f"{seq_idx + 1:>{max_idx_len}}: {headers[seq_idx]}"
            disp_name = name[:acc_width].ljust(acc_width)

            # Check if this row contains an accession search match
            row_acc_matches = acc_matches_by_row.get(seq_idx, [])

            # Render accession name
            if row_acc_matches:
                acc_part = ""
                for char_idx in range(acc_width):
                    c = disp_name[char_idx]

                    is_match_char = any(
                        c_start <= char_idx < c_start + match_len
                        for c_start, match_len in row_acc_matches
                    )
                    is_cursor = (
                        seq_idx == cursor_row
                        and active_pane == "acc"
                        and not prompt_mode
                    )

                    if is_cursor:
                        # Cursor wins: full row highlight in magenta
                        if has_256:
                            acc_part += f"\x1b[48;5;198m\x1b[38;5;231m\x1b[1m{c}\x1b[0m"
                        else:
                            acc_part += f"\x1b[7m\x1b[1m{c}\x1b[0m"
                    elif is_match_char:
                        # Highlight search match in cyan
                        if has_256:
                            acc_part += f"\x1b[48;5;45m\x1b[38;5;16m\x1b[1m{c}\x1b[0m"
                        else:
                            acc_part += f"\x1b[7m{c}\x1b[0m"
                    elif seq_idx == cursor_row:
                        if has_256:
                            acc_part += f"\x1b[48;5;238m\x1b[38;5;231m{c}\x1b[0m"
                        else:
                            acc_part += f"\x1b[2m{c}\x1b[0m"
                    else:
                        acc_part += c
            else:
                # No matches in this accession name
                if seq_idx == cursor_row:
                    if active_pane == "acc" and not prompt_mode:
                        # Inverted text for active cursor in accession list
                        acc_part = f"\x1b[7m\x1b[1m{disp_name}\x1b[0m"
                    else:
                        # Secondary highlight for cursor row alignment
                        if has_256:
                            acc_part = f"\x1b[48;5;238m\x1b[38;5;231m{disp_name}\x1b[0m"
                        else:
                            acc_part = f"\x1b[2m{disp_name}\x1b[0m"
                else:
                    acc_part = disp_name
        else:
            acc_part = " " * acc_width

        # Divider Line (ASCII)
        divider = "|"

        # Sequence Subpane
        seq_part = ""
        if seq_idx < num_seqs:
            seq_data = sequences[seq_idx]

            for col_i in range(seq_width):
                char_idx = col_offset + col_i
                if char_idx < len(seq_data):
                    c = seq_data[char_idx]
                    is_cursor = seq_idx == cursor_row and char_idx == cursor_col

                    # Formatting logic
                    color = ""
                    if vis_mode == "nuc":
                        color = NUC_COLORS.get(c.upper(), DEFAULT_NUC)
                    elif vis_mode == "aa":
                        color = AA_COLORS.get(c.upper(), DEFAULT_AA)
                    elif vis_mode == "diff":
                        if char_idx in non_identical_cols:
                            base_mode = detect_vis_mode(sequences)
                            if base_mode == "nuc":
                                color = NUC_COLORS.get(c.upper(), DEFAULT_NUC)
                            else:
                                color = AA_COLORS.get(c.upper(), DEFAULT_AA)

                    # Check search match
                    is_search_match = False
                    row_seq_matches = seq_matches_by_row.get(seq_idx, [])
                    for c_start, match_len in row_seq_matches:
                        if c_start <= char_idx < c_start + match_len:
                            is_search_match = True
                            break

                    if is_cursor:
                        if active_pane == "seq" and not prompt_mode:
                            # Highlight cursor block
                            if has_256:
                                seq_part += (
                                    f"\x1b[48;5;198m\x1b[38;5;231m\x1b[1m{c}\x1b[0m"
                                )
                            else:
                                seq_part += f"\x1b[7m\x1b[1m{c}\x1b[0m"
                        else:
                            # Secondary highlight for column alignment
                            if has_256:
                                seq_part += f"\x1b[48;5;238m\x1b[38;5;231m{c}\x1b[0m"
                            else:
                                seq_part += f"\x1b[4m{c}\x1b[0m"
                    elif is_search_match:
                        # Highlight search matches in bright cyan
                        if has_256:
                            seq_part += f"\x1b[48;5;45m\x1b[38;5;16m\x1b[1m{c}\x1b[0m"
                        else:
                            seq_part += f"\x1b[7m{c}\x1b[0m"
                    else:
                        if color and has_256 and vis_mode != "mono":
                            seq_part += f"{color}{c}\x1b[0m"
                        else:
                            seq_part += c
                else:
                    seq_part += " "
        else:
            seq_part = " " * seq_width

        lines.append(f"|{acc_part}{divider}{seq_part}|")

    # 4.1. Consensus Row
    if num_seqs > 0:
        # Accession column
        con_label = "Consensus"
        acc_part = (
            colors_theme["bold"]
            + con_label.ljust(acc_width)[:acc_width]
            + colors_theme["reset"]
        )

        # Sequence column
        seq_part = ""
        for col_i in range(seq_width):
            col_idx = col_offset + col_i
            if col_idx < seq_len:
                if col_idx in _consensus_col_cache:
                    seq_part += _consensus_col_cache[col_idx]
                    continue

                # Collect residues in this column
                col_chars = [
                    sequences[r][col_idx].upper()
                    for r in range(num_seqs)
                    if col_idx < len(sequences[r])
                ]

                from collections import Counter

                counts = Counter(col_chars)
                if counts:
                    most_common_char, most_common_count = counts.most_common(1)[0]
                    freq = most_common_count / num_seqs

                    if freq == 1.0:
                        # 100% identical: Bold Green
                        res = most_common_char.upper()
                        if has_256:
                            col_str = f"\x1b[1;38;5;46m{res}\x1b[0m"
                        else:
                            col_str = f"\x1b[1m{res}\x1b[0m"
                    elif freq >= 0.8:
                        # >=80%: Bold White
                        res = most_common_char.upper()
                        if has_256:
                            col_str = f"\x1b[1;38;5;231m{res}\x1b[0m"
                        else:
                            col_str = f"\x1b[1m{res}\x1b[0m"
                    elif freq >= 0.5:
                        # >=50%: Normal lowercase
                        res = most_common_char.lower()
                        col_str = res
                    else:
                        # <50%: Dark grey dot
                        if has_256:
                            col_str = "\x1b[38;5;242m.\x1b[0m"
                        else:
                            col_str = "."
                else:
                    col_str = " "
                
                _consensus_col_cache[col_idx] = col_str
                seq_part += col_str
            else:
                seq_part += " "
        lines.append(f"|{acc_part}|{seq_part}|")

    # 5. Footer separator (ASCII)
    lines.append("+" + "-" * acc_width + "+" + "-" * (cols - acc_width - 3) + "+")

    # 6. Status / Help / Prompt Line
    if prompt_mode:
        raw_prompt = f" * {prompt_text}{prompt_input}"
        max_prompt_len = max(5, cols - 4)
        if len(raw_prompt) > max_prompt_len:
            raw_prompt = raw_prompt[:max_prompt_len]
        space_left = max(0, cols - 2 - len(raw_prompt) - 1)
        lines.append("|" + raw_prompt + "_" + " " * space_left + "|")
    elif status_msg:
        # Show flashing warning or notification (clamped to prevent terminal line wraps)
        max_msg_len = max(5, cols - 4)
        display_msg = status_msg
        if len(display_msg) > max_msg_len:
            display_msg = display_msg[: max_msg_len - 3] + "..."
        space_left = max(0, cols - 2 - len(display_msg))
        lines.append("|" + display_msg + " " * space_left + "|")
    else:
        help_text = " [ESC] Menu   [Tab] Switch Pane   [Arrows] Navigate   [Ins] Insert/Overwrite"
        max_help_len = max(5, cols - 2)
        if len(help_text) > max_help_len:
            help_text = help_text[:max_help_len]
        space_left = max(0, cols - 2 - len(help_text))
        lines.append("|" + help_text + " " * space_left + "|")

    # 7. Navigation shortcut help line
    if move_mode:
        nav_text = " [ESC] Exit Move Mode   [Arrows Up/Down] Move sequence"
    elif not prompt_mode:
        nav_text = (
            " [Ctrl+F] Search   [Ctrl+Z] Undo   [Ctrl+Y] Redo   [Ctrl+S] Save   [Ctrl+Q] Quit"
        )
    else:
        nav_text = " [Enter] Confirm   [Escape] Cancel / Exit Prompt"
    max_nav_len = max(5, cols - 2)
    if len(nav_text) > max_nav_len:
        nav_text = nav_text[:max_nav_len]
    space_left = max(0, cols - 2 - len(nav_text))
    lines.append("|" + nav_text + " " * space_left + "|")

    # 8. Footer bottom border (ASCII)
    lines.append("+" + "-" * (cols - 2) + "+")

    # Write full viewport starting at terminal home (0,0) without trailing newline to avoid scrolling
    sys.stdout.write("\x1b[H" + "\n".join(lines))

    # If modal menu is active, overlay it directly at center coordinates
    if modal_state:
        modal_lines = build_modal_menu_lines(modal_state)
        start_row = max(1, (rows - len(modal_lines)) // 2)
        start_col = max(1, (cols - 70) // 2)
        for idx, m_line in enumerate(modal_lines):
            sys.stdout.write(f"\x1b[{start_row + idx + 1};{start_col + 1}H{m_line}")

    sys.stdout.flush()


def run_modal_menu(
    headers,
    sequences,
    cursor_row,
    cursor_col,
    row_offset,
    col_offset,
    active_pane,
    filename,
    insert_mode,
    vis_mode,
    modified,
    acc_width,
    alignment_format,
    mouse_enabled=False,
):
    """Interactive side-by-side modal dialog invoked by ESC."""
    active_col = "cat"  # 'cat' (Categories) or 'act' (Actions)
    cat_idx = 0
    act_idx = 0

    while True:
        categories = get_modal_menu_structure(vis_mode, alignment_format, mouse_enabled)
        if cat_idx < 0:
            cat_idx = 0
        if cat_idx >= len(categories):
            cat_idx = len(categories) - 1

        current_actions = categories[cat_idx][1]
        if act_idx < 0:
            act_idx = 0
        if act_idx >= len(current_actions):
            act_idx = len(current_actions) - 1

        modal_state = {
            "active_col": active_col,
            "cat_idx": cat_idx,
            "act_idx": act_idx,
            "categories": categories,
        }

        # Draw alignment grid with centered modal menu overlay
        draw_screen(
            headers,
            sequences,
            cursor_row,
            cursor_col,
            row_offset,
            col_offset,
            active_pane,
            filename,
            insert_mode,
            vis_mode,
            modified,
            acc_width,
            status_msg="",
            prompt_mode=None,
            alignment_format=alignment_format,
            modal_state=modal_state,
        )

        try:
            key = read_key()
        except (TerminalResizeException, InterruptedError, OSError):
            key = "TERMINAL_RESIZE"
        except (KeyboardInterrupt, Exception):
            return None, alignment_format, mouse_enabled

        if key == "TERMINAL_RESIZE":
            sys.stdout.write("\x1b[2J")
            sys.stdout.flush()
            continue

        # Mouse event handling inside modal menu
        if isinstance(key, tuple) and key[0].startswith("MOUSE"):
            m_event = key[0]
            if m_event == "MOUSE_PRESS":
                _, m_col, m_row = key
                cols, rows = get_terminal_size()
                modal_lines = build_modal_menu_lines(modal_state)
                start_row = max(1, (rows - len(modal_lines)) // 2)
                start_col = max(1, (cols - 70) // 2)
                inner_w = 68
                cat_w = 20
                act_w = 47

                # Click outside modal menu -> close menu
                if m_row <= start_row or m_row > start_row + len(modal_lines) or m_col <= start_col or m_col > start_col + inner_w + 2:
                    return None, alignment_format, mouse_enabled

                # Content rows start at start_row + 4
                content_start_row = start_row + 4
                max_r = max(len(cat[1]) for cat in categories)
                if content_start_row <= m_row < content_start_row + max_r:
                    r_idx = m_row - content_start_row
                    # Categories column: start_col + 2 to start_col + 1 + cat_w
                    if start_col + 2 <= m_col <= start_col + 1 + cat_w:
                        if 0 <= r_idx < len(categories):
                            cat_idx = r_idx
                            active_col = "act"
                            act_idx = 0
                            continue
                    # Actions column: start_col + 2 + cat_w + 1 to start_col + 2 + cat_w + act_w
                    elif start_col + 2 + cat_w + 1 <= m_col <= start_col + 2 + cat_w + act_w:
                        if 0 <= r_idx < len(current_actions):
                            act_idx = r_idx
                            action_code = current_actions[act_idx][0]
                            if action_code == "TOGGLE_FORMAT":
                                formats = ["fasta", "a3m", "sto"]
                                curr_i = formats.index(alignment_format) if alignment_format in formats else 0
                                alignment_format = formats[(curr_i + 1) % len(formats)]
                                continue
                            elif action_code == "TOGGLE_MOUSE":
                                mouse_enabled = not mouse_enabled
                                if mouse_enabled:
                                    enable_mouse_tracking()
                                else:
                                    disable_mouse_tracking()
                                continue
                            return action_code, alignment_format, mouse_enabled

            elif m_event == "MOUSE_WHEEL_UP":
                if active_col == "cat":
                    cat_idx = (cat_idx - 1) % len(categories)
                else:
                    act_idx = (act_idx - 1) % len(current_actions)
                continue
            elif m_event == "MOUSE_WHEEL_DOWN":
                if active_col == "cat":
                    cat_idx = (cat_idx + 1) % len(categories)
                else:
                    act_idx = (act_idx + 1) % len(current_actions)
                continue
            continue

        # Key handling inside modal menu
        if key in ("\r", "\n", "ENTER", "FIND_NEXT"):
            if active_col == "cat":
                active_col = "act"
                act_idx = 0
            else:
                action_code = current_actions[act_idx][0]
                if action_code == "TOGGLE_FORMAT":
                    formats = ["fasta", "a3m", "sto"]
                    curr_i = formats.index(alignment_format) if alignment_format in formats else 0
                    alignment_format = formats[(curr_i + 1) % len(formats)]
                    continue
                elif action_code == "TOGGLE_MOUSE":
                    mouse_enabled = not mouse_enabled
                    if mouse_enabled:
                        enable_mouse_tracking()
                    else:
                        disable_mouse_tracking()
                    continue
                return action_code, alignment_format, mouse_enabled

        elif key == "ESCAPE":
            if active_col == "act":
                active_col = "cat"
            else:
                return None, alignment_format, mouse_enabled  # Exit menu

        elif key == "KEY_UP":
            if active_col == "cat":
                cat_idx = (cat_idx - 1) % len(categories)
                act_idx = 0
            else:
                act_idx = (act_idx - 1) % len(current_actions)

        elif key == "KEY_DOWN":
            if active_col == "cat":
                cat_idx = (cat_idx + 1) % len(categories)
                act_idx = 0
            else:
                act_idx = (act_idx + 1) % len(current_actions)

        elif key in ("KEY_RIGHT", "TAB"):
            if active_col == "cat":
                active_col = "act"
                act_idx = 0
            elif active_col == "act":
                action_code = current_actions[act_idx][0]
                if action_code == "TOGGLE_FORMAT":
                    formats = ["fasta", "a3m", "sto"]
                    curr_i = formats.index(alignment_format) if alignment_format in formats else 0
                    alignment_format = formats[(curr_i + 1) % len(formats)]
                    continue
                elif action_code == "TOGGLE_MOUSE":
                    mouse_enabled = not mouse_enabled
                    if mouse_enabled:
                        enable_mouse_tracking()
                    else:
                        disable_mouse_tracking()
                    continue
                elif key == "TAB":
                    active_col = "cat"

        elif key == "KEY_LEFT":
            if active_col == "act":
                action_code = current_actions[act_idx][0]
                if action_code == "TOGGLE_FORMAT":
                    formats = ["fasta", "a3m", "sto"]
                    curr_i = formats.index(alignment_format) if alignment_format in formats else 0
                    alignment_format = formats[(curr_i - 1) % len(formats)]
                    continue
                elif action_code == "TOGGLE_MOUSE":
                    mouse_enabled = not mouse_enabled
                    if mouse_enabled:
                        enable_mouse_tracking()
                    else:
                        disable_mouse_tracking()
                    continue
                active_col = "cat"

        elif key in ("1", "2", "3", "4"):
            idx = int(key) - 1
            if 0 <= idx < len(categories):
                cat_idx = idx
                active_col = "act"
                act_idx = 0

        elif key == "QUIT" or key == "\x03":
            return None, alignment_format, mouse_enabled


def save_alignment_file(dest_file, alignment_format, headers, sequences):
    """Saves headers and sequences according to chosen alignment format."""
    if alignment_format in ("sto", "stockholm"):
        save_stockholm(dest_file, headers, sequences)
    elif alignment_format == "a3m":
        save_seqs = fasta_to_a3m(sequences)
        save_fasta(dest_file, headers, save_seqs)
    else:
        save_fasta(dest_file, headers, sequences)


def export_frequency_tables(prefix, sequences, current_dir):
    """Computes and writes 4 transposed frequency and count CSV matrices to freqs/."""
    freqs_dir = os.path.join(current_dir, "freqs")
    os.makedirs(freqs_dir, exist_ok=True)

    target_counts_all = os.path.join(freqs_dir, prefix + "_counts_all.csv")
    target_counts_changed = os.path.join(freqs_dir, prefix + "_counts_changed.csv")
    target_freq_all = os.path.join(freqs_dir, prefix + "_frequencies_all.csv")
    target_freq_changed = os.path.join(freqs_dir, prefix + "_frequencies_changed.csv")

    num_seqs = len(sequences)
    seq_len = len(sequences[0]) if num_seqs > 0 else 0

    all_chars_set = set()
    for seq in sequences:
        for c in seq:
            c_upper = c.upper()
            if c_upper.isalnum() or c_upper == "-":
                all_chars_set.add(c_upper)
    all_chars = sorted(list(all_chars_set))

    col_data_counts = {char: [] for char in all_chars}
    col_data_freq = {char: [] for char in all_chars}
    changed_col_indices = []

    from collections import Counter
    for col_idx in range(seq_len):
        col_chars = [
            sequences[r][col_idx].upper()
            for r in range(num_seqs)
            if col_idx < len(sequences[r])
        ]
        counts = Counter(col_chars)
        for char in all_chars:
            cnt = counts.get(char, 0)
            freq = cnt / num_seqs if num_seqs > 0 else 0.0
            col_data_counts[char].append(cnt)
            col_data_freq[char].append(round(freq, 3))

        if len(set(col_chars)) > 1:
            changed_col_indices.append(col_idx)

    csv_headers_all = ["Character"] + [str(col_idx + 1) for col_idx in range(seq_len)]
    csv_headers_changed = ["Character"] + [str(idx + 1) for idx in changed_col_indices]

    counts_all_rows = []
    counts_changed_rows = []
    freq_all_rows = []
    freq_changed_rows = []

    for char in all_chars:
        counts_all_rows.append([char] + col_data_counts[char])
        freq_all_rows.append([char] + col_data_freq[char])
        counts_changed_rows.append([char] + [col_data_counts[char][idx] for idx in changed_col_indices])
        freq_changed_rows.append([char] + [col_data_freq[char][idx] for idx in changed_col_indices])

    import csv
    with open(target_counts_all, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(csv_headers_all)
        writer.writerows(counts_all_rows)

    with open(target_counts_changed, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(csv_headers_changed)
        writer.writerows(counts_changed_rows)

    with open(target_freq_all, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(csv_headers_all)
        writer.writerows(freq_all_rows)

    with open(target_freq_changed, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(csv_headers_changed)
        writer.writerows(freq_changed_rows)


# ==============================================================================
# MAIN EDITOR SESSION
# ==============================================================================
def run_editor(filepath, mouse_enabled=True):
    """Main keyboard polling and state update loop for the alignment editor."""
    headers, sequences, alignment_format = load_alignment(filepath)
    filename = filepath

    # If file was not loaded or empty, initialize with placeholder values
    if not headers:
        headers = ["Sequence_1"]
        sequences = ["ACTG-ACTG-ACTG-ACTG-ACTG-ACTG-ACTG-ACTG"]
        filename = filepath if filepath else ""

    cursor_row = 0
    cursor_col = 0
    row_offset = 0
    col_offset = 0

    active_pane = "seq"  # 'acc' or 'seq'
    insert_mode = True  # True = Insert, False = Overwrite (default to Insert for safety)
    vis_mode = detect_vis_mode(sequences)
    modified = False
    acc_width_delta = 0
    move_mode = False

    mouse_dragging_divider = False
    mouse_dragging_seq_row = None
    mouse_drag_start_row = None
    mouse_drag_last_col = 0
    mouse_drag_initial_headers = []
    mouse_drag_initial_seqs = []
    mouse_drag_moved = False

    history = StateHistory()

    # Clear screen and hide cursor on start
    sys.stdout.write("\x1b[2J\x1b[?25l")
    sys.stdout.flush()

    if mouse_enabled:
        enable_mouse_tracking()

    status_msg = ""
    status_expiry = 0.0

    prompt_mode = None
    prompt_text = ""
    prompt_input = ""
    pending_frame = "+1"
    pending_save_file = ""
    pending_export_prefix = ""

    search_query = ""
    search_matches = []
    search_match_idx = -1

    while True:
        # Update dynamic dimensions
        cols, rows = shutil.get_terminal_size((80, 24))
        acc_width = min(50, max(5, int(cols * 0.22) + acc_width_delta))
        seq_width = cols - acc_width - 4
        view_height = rows - 9

        num_seqs = len(sequences)
        seq_len = len(sequences[0]) if num_seqs > 0 else 0

        # Enforce boundaries
        if cursor_row < 0:
            cursor_row = 0
        if cursor_row >= num_seqs:
            cursor_row = num_seqs - 1

        if cursor_col < 0:
            cursor_col = 0
        if cursor_col >= seq_len:
            cursor_col = max(0, seq_len - 1)

        # Manage offsets to scroll window viewports
        if cursor_row < row_offset:
            row_offset = cursor_row
        if cursor_row >= row_offset + view_height:
            row_offset = max(0, cursor_row - view_height + 1)

        if cursor_col < col_offset:
            col_offset = cursor_col
        if cursor_col >= col_offset + seq_width:
            col_offset = max(0, cursor_col - seq_width + 1)

        # Expire status messages after 3 seconds
        if status_msg and time.time() > status_expiry:
            status_msg = ""

        # Render frame
        draw_screen(
            headers,
            sequences,
            cursor_row,
            cursor_col,
            row_offset,
            col_offset,
            active_pane,
            filename,
            insert_mode,
            vis_mode,
            modified,
            acc_width,
            status_msg,
            prompt_mode,
            prompt_text,
            prompt_input,
            move_mode=move_mode,
            search_query=search_query,
            search_matches=search_matches,
            alignment_format=alignment_format,
        )

        # Read user keystroke
        try:
            key = read_key()
        except (TerminalResizeException, InterruptedError, OSError):
            key = "TERMINAL_RESIZE"

        if key == "TERMINAL_RESIZE":
            # Clear screen and force redraw on next iteration
            sys.stdout.write("\x1b[2J")
            sys.stdout.flush()
            continue

        # Move mode shortcut interceptor
        if move_mode:
            if key == "KEY_UP":
                if cursor_row > 0:
                    history.push_state(headers, sequences)
                    headers[cursor_row], headers[cursor_row - 1] = (
                        headers[cursor_row - 1],
                        headers[cursor_row],
                    )
                    sequences[cursor_row], sequences[cursor_row - 1] = (
                        sequences[cursor_row - 1],
                        sequences[cursor_row],
                    )
                    cursor_row -= 1
                    modified = True
            elif key == "KEY_DOWN":
                if cursor_row < len(sequences) - 1:
                    history.push_state(headers, sequences)
                    headers[cursor_row], headers[cursor_row + 1] = (
                        headers[cursor_row + 1],
                        headers[cursor_row],
                    )
                    sequences[cursor_row], sequences[cursor_row + 1] = (
                        sequences[cursor_row + 1],
                        sequences[cursor_row],
                    )
                    cursor_row += 1
                    modified = True
            elif key in ("ENTER", "ESCAPE", "TOGGLE_MOVE"):
                move_mode = False
                status_msg = "Exited Move Mode."
                status_expiry = time.time() + 1.5
            continue

        # Prompt mode processing
        if prompt_mode:
            if key == "ESCAPE":
                prompt_mode = None
                prompt_input = ""
                status_msg = "Command cancelled."
                status_expiry = time.time() + 2.0
            elif key in ("ENTER", "FIND_NEXT"):
                # Process confirmation/string
                if prompt_mode == "edit_name":
                    if prompt_input.strip():
                        history.push_state(headers, sequences)
                        new_name = prompt_input.strip()
                        if alignment_format in ("sto", "stockholm") and " " in new_name:
                            new_name = new_name.replace(" ", "_")
                            status_msg = "Accession name updated (spaces replaced with '_' for Stockholm format)."
                        else:
                            status_msg = "Accession name updated."
                        headers[cursor_row] = new_name
                        modified = True
                    prompt_mode = None
                    prompt_input = ""
                elif prompt_mode == "save_file":
                    dest_file = prompt_input.strip()
                    if dest_file:
                        # Auto-toggle format based on destination file extension
                        if dest_file.lower().endswith((".sto", ".stk", ".stockholm")):
                            alignment_format = "sto"
                        elif dest_file.lower().endswith(".a3m"):
                            alignment_format = "a3m"
                        elif dest_file.lower().endswith((".fasta", ".fa", ".fas")):
                            alignment_format = "fasta"

                        current_dir = os.path.abspath(os.getcwd())
                        dest_abs = os.path.abspath(dest_file)
                        if not dest_abs.startswith(current_dir):
                            status_msg = "Error: Access denied (sandbox policy: AligNano folder only)."
                            status_expiry = time.time() + 4.0
                            prompt_mode = None
                            prompt_input = ""
                        elif os.path.exists(dest_abs):
                            # Overwrite protection / confirmation
                            pending_save_file = dest_file
                            prompt_mode = "save_overwrite_confirm"
                            prompt_text = f"File '{os.path.basename(dest_file)}' already exists! Overwrite? (y/N): "
                            prompt_input = ""
                        else:
                            try:
                                save_alignment_file(dest_file, alignment_format, headers, sequences)
                                filename = dest_file
                                modified = False
                                status_msg = f"Alignment successfully saved to: {os.path.basename(dest_file)}"
                            except Exception as e:
                                status_msg = f"Save failed: {str(e)}"
                            status_expiry = time.time() + 3.0
                            prompt_mode = None
                            prompt_input = ""
                    else:
                        prompt_mode = None
                        prompt_input = ""

                elif prompt_mode == "save_overwrite_confirm":
                    if prompt_input.strip().upper().startswith("Y"):
                        dest_file = pending_save_file
                        try:
                            save_alignment_file(dest_file, alignment_format, headers, sequences)
                            filename = dest_file
                            modified = False
                            status_msg = f"File '{os.path.basename(dest_file)}' overwritten and saved successfully."
                        except Exception as e:
                            status_msg = f"Save failed: {str(e)}"
                        status_expiry = time.time() + 3.0
                    else:
                        status_msg = "Save cancelled (existing file protected)."
                        status_expiry = time.time() + 2.0
                    prompt_mode = None
                    prompt_input = ""
                    pending_save_file = ""

                elif prompt_mode == "export_freq":
                    prefix = (
                        prompt_input.strip() if prompt_input.strip() else "frequencies"
                    )
                    current_dir = os.path.abspath(os.getcwd())
                    freqs_dir = os.path.join(current_dir, "freqs")
                    paths = [
                        os.path.join(freqs_dir, prefix + "_counts_all.csv"),
                        os.path.join(freqs_dir, prefix + "_counts_changed.csv"),
                        os.path.join(freqs_dir, prefix + "_frequencies_all.csv"),
                        os.path.join(freqs_dir, prefix + "_frequencies_changed.csv"),
                    ]
                    if any(not os.path.abspath(p).startswith(current_dir) for p in paths):
                        status_msg = "Error: Access denied (sandbox policy: AligNano folder only)."
                        status_expiry = time.time() + 4.0
                        prompt_mode = None
                        prompt_input = ""
                    elif any(os.path.exists(p) for p in paths):
                        # Overwrite protection / confirmation
                        pending_export_prefix = prefix
                        prompt_mode = "export_overwrite_confirm"
                        prompt_text = f"CSV files for '{prefix}' exist in freqs/. Overwrite? (y/N): "
                        prompt_input = ""
                    else:
                        try:
                            export_frequency_tables(prefix, sequences, current_dir)
                            status_msg = f"Exported 4 CSVs for '{prefix}' to freqs/ subdirectory."
                        except Exception as e:
                            status_msg = f"Export failed: {str(e)}"
                        status_expiry = time.time() + 3.0
                        prompt_mode = None
                        prompt_input = ""

                elif prompt_mode == "export_overwrite_confirm":
                    if prompt_input.strip().upper().startswith("Y"):
                        prefix = pending_export_prefix
                        current_dir = os.path.abspath(os.getcwd())
                        try:
                            export_frequency_tables(prefix, sequences, current_dir)
                            status_msg = f"Overwrote and exported 4 CSVs for '{prefix}' to freqs/."
                        except Exception as e:
                            status_msg = f"Export failed: {str(e)}"
                        status_expiry = time.time() + 3.0
                    else:
                        status_msg = "Export cancelled (existing CSV files protected)."
                        status_expiry = time.time() + 2.0
                    prompt_mode = None
                    prompt_input = ""
                    pending_export_prefix = ""
                elif prompt_mode == "translate_frame":
                    val = prompt_input.strip()
                    if not val:
                        val = "+1"
                    if val not in ("+1", "+2", "+3", "-1", "-2", "-3", "1", "2", "3", "-1", "-2", "-3"):
                        status_msg = "Invalid reading frame! Use +1, +2, +3, -1, -2, or -3."
                        status_expiry = time.time() + 3.0
                        prompt_mode = None
                        prompt_input = ""
                    else:
                        if not val.startswith("+") and not val.startswith("-"):
                            val = "+" + val
                        pending_frame = val
                        prompt_mode = "translate_code"
                        prompt_text = "NCBI Code (1:Std 2:Vert 3:Yeast 5:Invert 11:Bact) [1]: "
                        prompt_input = ""
                elif prompt_mode == "translate_code":
                    val = prompt_input.strip()
                    if not val:
                        val = "1"
                    try:
                        code_id = int(val)
                        if code_id not in GENETIC_CODE_NAMES:
                            code_id = 1
                    except ValueError:
                        code_id = 1
                    if sequences:
                        history.push_state(headers, sequences)
                        sequences = translate_alignment(sequences, pending_frame, code_id)
                        vis_mode = "aa"
                        new_len = len(sequences[0]) if sequences else 0
                        cursor_col = max(0, min(cursor_col // 3, max(0, new_len - 1)))
                        col_offset = max(0, min(col_offset // 3, cursor_col))
                        modified = True
                        status_msg = f"Translated to Protein (Frame {pending_frame}, Code {code_id}). Press Ctrl+Z to undo."
                        sys.stdout.write("\x1b[2J")
                        sys.stdout.flush()
                    else:
                        status_msg = "No sequences to translate."
                    status_expiry = time.time() + 4.0
                    prompt_mode = None
                    prompt_input = ""
                elif prompt_mode == "add_seq":
                    name = (
                        prompt_input.strip()
                        if prompt_input.strip()
                        else f"Seq_{num_seqs + 1}"
                    )
                    history.push_state(headers, sequences)
                    headers.append(name)
                    # Add sequence matching the alignment grid width
                    sequences.append("-" * max(1, seq_len))
                    cursor_row = len(sequences) - 1
                    modified = True
                    status_msg = "New sequence row added."
                    status_expiry = time.time() + 2.0
                    prompt_mode = None
                    prompt_input = ""
                elif prompt_mode == "quit_confirm":
                    if prompt_input.upper().startswith("Y"):
                        break
                    else:
                        prompt_mode = None
                        prompt_input = ""
                elif prompt_mode == "delete_confirm":
                    if prompt_input.upper().startswith("Y"):
                        history.push_state(headers, sequences)
                        headers.pop(cursor_row)
                        sequences.pop(cursor_row)
                        modified = True
                        if cursor_row >= len(sequences):
                            cursor_row = max(0, len(sequences) - 1)
                        status_msg = "Sequence row deleted."
                    else:
                        status_msg = "Delete aborted."
                    status_expiry = time.time() + 2.0
                    prompt_mode = None
                    prompt_input = ""
                elif prompt_mode == "search":
                    query = prompt_input.strip()
                    if query:
                        search_query = query
                        matches = []
                        for r, seq in enumerate(sequences):
                            s_upper = seq.upper()
                            q_upper = query.upper()
                            pos = 0
                            while True:
                                idx = s_upper.find(q_upper, pos)
                                if idx == -1:
                                    break
                                matches.append((r, idx, "seq"))
                                pos = idx + 1
                        for r, name in enumerate(headers):
                            max_idx_len = len(str(len(headers)))
                            full_acc = f"{r + 1:>{max_idx_len}}: {name}"
                            idx = full_acc.upper().find(query.upper())
                            if idx != -1:
                                matches.append((r, idx, "acc"))
                        matches.sort(
                            key=lambda m: (m[0], m[1] if m[2] == "seq" else -1)
                        )
                        search_matches = matches
                        if matches:
                            search_match_idx = 0
                            for idx, (r, c, pane) in enumerate(matches):
                                if r > cursor_row or (
                                    r == cursor_row
                                    and (pane == "acc" or c >= cursor_col)
                                ):
                                    search_match_idx = idx
                                    break
                            r, c, pane = matches[search_match_idx]
                            cursor_row = r
                            cursor_col = c
                            active_pane = pane
                            status_msg = f"Found {len(matches)} matches. Jumped to match {search_match_idx + 1}."
                        else:
                            search_match_idx = -1
                            status_msg = f"No matches found for '{query}'"
                        status_expiry = time.time() + 3.0
                    prompt_mode = None
                    prompt_input = ""
            elif key in ("DELETE", "HELP"):
                prompt_input = prompt_input[:-1]
            elif isinstance(key, str) and len(key) == 1:
                prompt_input += key
            continue

        # Mouse Event Handler
        if isinstance(key, tuple) and key[0].startswith("MOUSE"):
            m_event = key[0]
            if m_event == "MOUSE_PRESS":
                _, m_col, m_row = key
                # 1. Divider drag grab: within 1 column of divider (divider is at acc_width + 2)
                if abs(m_col - (acc_width + 2)) <= 1 and 3 <= m_row <= (rows - 3):
                    mouse_dragging_divider = True
                    status_msg = "Dragging panel divider (move mouse left/right, release to finish)"
                    status_expiry = time.time() + 1.5
                    continue
                # 2. Viewport click (row 6 to 5 + view_height)
                elif 6 <= m_row < 6 + view_height:
                    target_row = row_offset + (m_row - 6)
                    if 0 <= target_row < num_seqs:
                        cursor_row = target_row
                        mouse_dragging_seq_row = target_row
                        mouse_drag_start_row = target_row
                        mouse_drag_last_col = m_col
                        mouse_drag_initial_headers = copy.deepcopy(headers)
                        mouse_drag_initial_seqs = copy.deepcopy(sequences)
                        mouse_drag_moved = False

                        if 2 <= m_col <= acc_width + 1:
                            active_pane = "acc"
                        elif m_col >= acc_width + 3 and m_col < cols:
                            active_pane = "seq"
                            target_col = col_offset + (m_col - (acc_width + 3))
                            cursor_col = max(0, min(seq_len - 1, target_col))
                    continue
                # 3. Bottom bar click
                elif m_row >= rows - 3:
                    if m_col <= 15:
                        key = "ESCAPE"
                    elif 16 <= m_col <= 35:
                        active_pane = "acc" if active_pane == "seq" else "seq"
                        continue
                    elif 36 <= m_col <= 55:
                        insert_mode = not insert_mode
                        status_msg = f"Edit Mode: {'INSERT' if insert_mode else 'OVERWRITE'}"
                        status_expiry = time.time() + 2.0
                        continue

            elif m_event == "MOUSE_DRAG":
                _, m_col, m_row = key
                if mouse_dragging_divider:
                    target_width = max(5, min(cols - 10, m_col - 2))
                    acc_width_delta = target_width - int(cols * 0.22)
                    continue
                elif mouse_dragging_seq_row is not None:
                    # 1. Horizontal scrolling / panning (Left / Right drag)
                    delta_x = m_col - mouse_drag_last_col
                    mouse_drag_last_col = m_col
                    if delta_x != 0:
                        # Moving mouse right (delta_x > 0) scrolls view left; moving left scrolls view right
                        col_offset = max(0, min(max(0, seq_len - 5), col_offset - delta_x))
                        cursor_col = max(0, min(max(0, seq_len - 1), cursor_col - delta_x))

                    # 2. Vertical sequence reordering (Up / Down drag)
                    if 6 <= m_row < 6 + view_height:
                        hover_row = row_offset + (m_row - 6)
                        if 0 <= hover_row < num_seqs and hover_row != mouse_dragging_seq_row:
                            if not mouse_drag_moved:
                                history.push_state(mouse_drag_initial_headers, mouse_drag_initial_seqs)
                                mouse_drag_moved = True

                            h = headers.pop(mouse_dragging_seq_row)
                            s = sequences.pop(mouse_dragging_seq_row)
                            headers.insert(hover_row, h)
                            sequences.insert(hover_row, s)

                            mouse_dragging_seq_row = hover_row
                            cursor_row = hover_row
                            modified = True
                            status_msg = f"Moving row: '{headers[cursor_row]}' (Row {cursor_row + 1}/{num_seqs})"
                            status_expiry = time.time() + 1.0

                    # Edge auto-scrolling when dragging near top/bottom
                    if m_row <= 6 and row_offset > 0:
                        row_offset -= 1
                        hover_row = max(0, mouse_dragging_seq_row - 1)
                        if hover_row != mouse_dragging_seq_row:
                            if not mouse_drag_moved:
                                history.push_state(mouse_drag_initial_headers, mouse_drag_initial_seqs)
                                mouse_drag_moved = True
                            h = headers.pop(mouse_dragging_seq_row)
                            s = sequences.pop(mouse_dragging_seq_row)
                            headers.insert(hover_row, h)
                            sequences.insert(hover_row, s)
                            mouse_dragging_seq_row = hover_row
                            cursor_row = hover_row
                            modified = True
                    elif m_row >= 5 + view_height and row_offset + view_height < num_seqs:
                        row_offset += 1
                        hover_row = min(num_seqs - 1, mouse_dragging_seq_row + 1)
                        if hover_row != mouse_dragging_seq_row:
                            if not mouse_drag_moved:
                                history.push_state(mouse_drag_initial_headers, mouse_drag_initial_seqs)
                                mouse_drag_moved = True
                            h = headers.pop(mouse_dragging_seq_row)
                            s = sequences.pop(mouse_dragging_seq_row)
                            headers.insert(hover_row, h)
                            sequences.insert(hover_row, s)
                            mouse_dragging_seq_row = hover_row
                            cursor_row = hover_row
                            modified = True
                    continue

            elif m_event == "MOUSE_RELEASE":
                if mouse_dragging_seq_row is not None:
                    if mouse_drag_moved:
                        status_msg = f"Sequence '{headers[cursor_row]}' moved to row {cursor_row + 1}. Press Ctrl+Z to undo."
                        status_expiry = time.time() + 3.0
                    mouse_dragging_seq_row = None
                    mouse_drag_start_row = None
                    mouse_drag_moved = False
                mouse_dragging_divider = False
                continue

            elif m_event == "MOUSE_WHEEL_UP":
                cursor_row = max(0, cursor_row - 3)
                continue

            elif m_event == "MOUSE_WHEEL_DOWN":
                cursor_row = min(num_seqs - 1, cursor_row + 3)
                continue

            elif m_event == "MOUSE_WHEEL_LEFT":
                cursor_col = max(0, cursor_col - 5)
                continue

            elif m_event == "MOUSE_WHEEL_RIGHT":
                cursor_col = min(seq_len - 1, cursor_col + 5)
                continue

        # Main ESC Modal Menu Handler
        if key == "ESCAPE":
            old_fmt = alignment_format
            old_mouse = mouse_enabled
            action, alignment_format, mouse_enabled = run_modal_menu(
                headers,
                sequences,
                cursor_row,
                cursor_col,
                row_offset,
                col_offset,
                active_pane,
                filename,
                insert_mode,
                vis_mode,
                modified,
                acc_width,
                alignment_format,
                mouse_enabled,
            )
            if alignment_format != old_fmt:
                status_msg = f"Alignment Format set to: {alignment_format.upper()}"
                status_expiry = time.time() + 2.0
            elif mouse_enabled != old_mouse:
                status_msg = f"Mouse Mode set to: {'ENABLED' if mouse_enabled else 'DISABLED'}"
                status_expiry = time.time() + 2.0

            if not action:
                continue

            # Process modal menu action
            if action == "SAVE":
                prompt_mode = "save_file"
                prompt_text = "Save as (FASTA/A3M/STO path): "
                prompt_input = filename if filename else "alignment.fasta"

            elif action == "TOGGLE_FORMAT":
                status_msg = f"Alignment Format set to: {alignment_format.upper()}"
                status_expiry = time.time() + 2.0

            elif action == "EXPORT_FREQ":
                prompt_mode = "export_freq"
                prompt_text = "Export prefix: "
                if filename:
                    base_name = os.path.splitext(os.path.basename(filename))[0]
                else:
                    base_name = "frequencies"
                prompt_input = base_name

            elif action == "HELP":
                display_help_screen()
                sys.stdout.write("\x1b[2J")
                sys.stdout.flush()

            elif action == "QUIT":
                if modified:
                    prompt_mode = "quit_confirm"
                    prompt_text = "Unsaved changes! Quit anyway? (y/N): "
                    prompt_input = ""
                else:
                    break

            elif action == "UNDO":
                restored = history.undo(headers, sequences)
                if restored:
                    headers, sequences = restored
                    modified = True
                    vis_mode = detect_vis_mode(sequences)
                    status_msg = "Action Undone."
                else:
                    status_msg = "Nothing to undo."
                status_expiry = time.time() + 2.0

            elif action == "REDO":
                restored = history.redo(headers, sequences)
                if restored:
                    headers, sequences = restored
                    modified = True
                    vis_mode = detect_vis_mode(sequences)
                    status_msg = "Action Redone."
                else:
                    status_msg = "Nothing to redo."
                status_expiry = time.time() + 2.0

            elif action == "TOGGLE_INSERT":
                insert_mode = not insert_mode
                status_msg = f"Edit Mode: {'INSERT' if insert_mode else 'OVERWRITE'}"
                status_expiry = time.time() + 2.0

            elif action == "EDIT_NAME":
                prompt_mode = "edit_name"
                prompt_text = "Enter accession name: "
                prompt_input = headers[cursor_row]

            elif action == "ADD_ROW":
                prompt_mode = "add_seq"
                prompt_text = "New sequence name (default Seq_N): "
                prompt_input = ""

            elif action == "DELETE_ROW":
                if num_seqs <= 1:
                    status_msg = "Cannot delete the last remaining sequence."
                    status_expiry = time.time() + 2.0
                else:
                    prompt_mode = "delete_confirm"
                    prompt_text = f"Delete sequence row '{headers[cursor_row]}'? (y/N): "
                    prompt_input = ""

            elif action == "TOGGLE_MOVE":
                move_mode = True
                status_msg = "Entered Move Mode (Use Up/Down arrows to reorder, ESC to exit)"
                status_expiry = time.time() + 3.0

            elif action == "COLOR_NUC":
                vis_mode = "nuc"
                status_msg = "Visual Mode: DNA/RNA"
                status_expiry = time.time() + 2.0

            elif action == "COLOR_AA":
                vis_mode = "aa"
                status_msg = "Visual Mode: PROTEIN (ClustalX)"
                status_expiry = time.time() + 2.0

            elif action == "COLOR_DIFF":
                vis_mode = "diff"
                status_msg = "Visual Mode: DIFF (Variable sites only)"
                status_expiry = time.time() + 2.0

            elif action == "COLOR_MONO":
                vis_mode = "mono"
                status_msg = "Visual Mode: MONOCHROME"
                status_expiry = time.time() + 2.0

            elif action == "TOGGLE_MOUSE":
                mouse_enabled = not mouse_enabled
                if mouse_enabled:
                    enable_mouse_tracking()
                    status_msg = "Mouse Mode ENABLED (Click cursor, drag partition, wheel scroll. Shift+Drag to copy text)"
                else:
                    disable_mouse_tracking()
                    status_msg = "Mouse Mode DISABLED (Native terminal text selection restored)"
                status_expiry = time.time() + 3.0

            elif action == "PANE_WIDEN":
                acc_width_delta += 2
                status_msg = "Accession panel widened."
                status_expiry = time.time() + 1.0

            elif action == "PANE_NARROW":
                acc_width_delta -= 2
                status_msg = "Accession panel narrowed."
                status_expiry = time.time() + 1.0

            elif action == "PAGE_LEFT":
                cursor_col = max(0, cursor_col - (seq_width - 5))

            elif action == "PAGE_RIGHT":
                cursor_col = min(seq_len - 1, cursor_col + (seq_width - 5))

            elif action == "SEARCH":
                prompt_mode = "search"
                prompt_text = "Search motif/name: "
                prompt_input = ""

            elif action == "FIND_NEXT":
                if search_query and search_matches:
                    search_match_idx = (search_match_idx + 1) % len(search_matches)
                    r, c, pane = search_matches[search_match_idx]
                    cursor_row = r
                    cursor_col = c
                    active_pane = pane
                    status_msg = f"Match {search_match_idx + 1}/{len(search_matches)}: Row {r + 1}, Col {c + 1}"
                else:
                    status_msg = "No active search. Press [ESC] -> Tools -> Search or Ctrl+F."
                status_expiry = time.time() + 2.0

            elif action == "TRANSLATE":
                prompt_mode = "translate_frame"
                prompt_text = "Reading Frame (+1,+2,+3,-1,-2,-3) [default: +1]: "
                prompt_input = ""

            elif action == "SORT_DIST":
                if num_seqs <= 1:
                    status_msg = "Nothing to sort."
                else:
                    history.push_state(headers, sequences)
                    ref_seq = sequences[0]
                    sub_rows = []
                    for h, s in zip(headers[1:], sequences[1:]):
                        dist = levenshtein_distance(ref_seq, s)
                        sub_rows.append((h, s, dist))
                    sub_rows.sort(key=lambda x: x[2])
                    headers = [headers[0]] + [item[0] for item in sub_rows]
                    sequences = [sequences[0]] + [item[1] for item in sub_rows]
                    modified = True
                    status_msg = "Sequences sorted by distance to top sequence. Press Ctrl+Z to undo."
                status_expiry = time.time() + 3.0
            continue

        # Reserved Direct Shortcuts
        elif key == "SAVE":
            prompt_mode = "save_file"
            prompt_text = "Save as (FASTA file path): "
            prompt_input = filename if filename else "alignment.fasta"

        elif key == "QUIT":
            if modified:
                prompt_mode = "quit_confirm"
                prompt_text = "Unsaved changes! Quit anyway? (y/N): "
                prompt_input = ""
            else:
                break

        elif key == "SEARCH":
            prompt_mode = "search"
            prompt_text = "Search motif/name: "
            prompt_input = ""

        elif key == "FIND_NEXT":
            if search_query and search_matches:
                search_match_idx = (search_match_idx + 1) % len(search_matches)
                r, c, pane = search_matches[search_match_idx]
                cursor_row = r
                cursor_col = c
                active_pane = pane
                status_msg = f"Match {search_match_idx + 1}/{len(search_matches)}: Row {r + 1}, Col {c + 1}"
            else:
                status_msg = "No active search. Press Ctrl+F to search."
            status_expiry = time.time() + 2.0

        elif key == "UNDO":
            restored = history.undo(headers, sequences)
            if restored:
                headers, sequences = restored
                modified = True
                vis_mode = detect_vis_mode(sequences)
                status_msg = "Action Undone."
            else:
                status_msg = "Nothing to undo."
            status_expiry = time.time() + 2.0

        elif key == "REDO":
            restored = history.redo(headers, sequences)
            if restored:
                headers, sequences = restored
                modified = True
                vis_mode = detect_vis_mode(sequences)
                status_msg = "Action Redone."
            else:
                status_msg = "Nothing to redo."
            status_expiry = time.time() + 2.0

        elif key in ("HELP", "?"):
            display_help_screen()
            sys.stdout.write("\x1b[2J")
            sys.stdout.flush()
            continue

        elif key == "KEY_UP":
            cursor_row -= 1
        elif key == "KEY_DOWN":
            cursor_row += 1

        elif key == "KEY_LEFT":
            if active_pane == "seq":
                if cursor_col == 0:
                    active_pane = "acc"
                else:
                    cursor_col -= 1
            else:
                pass  # Can't go further left than accession pane

        elif key == "KEY_RIGHT":
            if active_pane == "acc":
                active_pane = "seq"
                cursor_col = col_offset
            else:
                cursor_col += 1

        elif key == "PAGE_UP":
            cursor_row = max(0, cursor_row - (view_height - 2))
        elif key == "PAGE_DOWN":
            cursor_row = min(num_seqs - 1, cursor_row + (view_height - 2))

        elif key == "[":
            acc_width_delta -= 1
            status_msg = "Accession panel narrowed."
            status_expiry = time.time() + 1.0
        elif key == "]":
            acc_width_delta += 1
            status_msg = "Accession panel widened."
            status_expiry = time.time() + 1.0

        elif key == "TAB":
            active_pane = "seq" if active_pane == "acc" else "acc"

        elif key == "INSERT":
            insert_mode = not insert_mode
            status_msg = f"Edit Mode: {'INSERT' if insert_mode else 'OVERWRITE'}"
            status_expiry = time.time() + 2.0

        elif key == "DELETE":
            if active_pane == "acc":
                if num_seqs <= 1:
                    status_msg = "Cannot delete the last remaining sequence."
                    status_expiry = time.time() + 2.0
                else:
                    history.push_state(headers, sequences)
                    deleted_name = headers.pop(cursor_row)
                    sequences.pop(cursor_row)
                    modified = True
                    if cursor_row >= len(sequences):
                        cursor_row = max(0, len(sequences) - 1)
                    status_msg = f"Deleted sequence '{deleted_name}'. Press Ctrl+Z to undo."
                    status_expiry = time.time() + 3.0
            else:
                if cursor_col > 0:
                    history.push_state(headers, sequences)
                    current_seq = sequences[cursor_row]
                    sequences[cursor_row] = (
                        current_seq[: cursor_col - 1] + current_seq[cursor_col:]
                    )
                    cursor_col -= 1
                    modified = True
                    status_msg = "Deleted base (sequence shortened)."
                    status_expiry = time.time() + 1.5

        elif key == " " or key == "-":
            # Insert or overwrite Gap at cursor
            if active_pane == "seq":
                history.push_state(headers, sequences)
                current_seq = sequences[cursor_row]

                if insert_mode:
                    # Insert mode: pushes letters right and pads other sequences
                    sequences[cursor_row] = (
                        current_seq[:cursor_col] + "-" + current_seq[cursor_col:]
                    )
                    # Pad all other sequences to align with new length
                    for i in range(len(sequences)):
                        if i != cursor_row:
                            sequences[i] += "-"
                else:
                    # Overwrite mode: replaces character under cursor, maintaining length
                    if cursor_col < len(current_seq):
                        sequences[cursor_row] = (
                            current_seq[:cursor_col]
                            + "-"
                            + current_seq[cursor_col + 1 :]
                        )
                    else:
                        # Append if cursor is past end
                        sequences[cursor_row] = current_seq + "-"

                cursor_col += 1
                modified = True

        # Direct alphanumeric character insertions / replacements
        elif isinstance(key, str) and len(key) == 1 and key.isalnum():
            if active_pane == "seq":
                history.push_state(headers, sequences)
                c_char = key  # Preserve user's casing
                current_seq = sequences[cursor_row]

                if insert_mode:
                    # Insert mode: pushes letters right
                    sequences[cursor_row] = (
                        current_seq[:cursor_col] + c_char + current_seq[cursor_col:]
                    )
                    # Pad all other sequences to align with new length
                    for i in range(len(sequences)):
                        if i != cursor_row:
                            sequences[i] += "-"
                else:
                    # Overwrite mode: replaces char at cursor
                    sequences[cursor_row] = (
                        current_seq[:cursor_col]
                        + c_char
                        + current_seq[cursor_col + 1 :]
                    )

                cursor_col += 1
                modified = True

    disable_mouse_tracking()
    # Restore terminal visibility and reset cursor on quit
    sys.stdout.write("\x1b[?25h\x1b[2J\x1b[H")
    sys.stdout.flush()
    print("Alignment Editor exited cleanly.")


def display_help_screen():
    """Draws a beautiful fullscreen scrollable interactive help window."""
    # We loop until user exits
    scroll_offset = 0
    while True:
        cols, rows = shutil.get_terminal_size((80, 24))
        if rows < 10 or cols < 40:
            sys.stdout.write("\x1b[H\x1b[2JTerminal too small! Please resize.\n")
            sys.stdout.flush()
            try:
                key = read_key()
                if key == "TERMINAL_RESIZE":
                    continue
                if key in ("ESCAPE", "ENTER", "QUIT", "HELP", "Ctrl+H", "?") or (key in ("h", "H")):
                    break
            except Exception:
                continue
            continue
        colors = get_theme_colors()
        
        # Build all content lines
        content_lines = []
        
        # Section titles and keys
        help_data = [
            ("ESC MAIN MENU SYSTEM", [
                ("ESC", "Open AligNano Main Menu (File, Edit, Display, Tools)"),
                ("Arrows (Up/Down)", "Move cursor across categories or actions"),
                ("Arrows (Left/Right)", "Switch between Categories and Actions columns"),
                ("Enter", "Select focused action or open action column"),
                ("1, 2, 3, 4", "Directly jump to category (File, Edit, Display, Tools)"),
                ("ESC", "Return from Actions to Categories, or close menu"),
            ]),
            ("RESERVED SHORTCUTS", [
                ("Ctrl+S", "Save current alignment to FASTA/A3M/STO file"),
                ("Ctrl+Q", "Quit alignment editor (checks for unsaved changes)"),
                ("Ctrl+Z", "Undo last editing action (history restored)"),
                ("Ctrl+Y", "Redo last undone action"),
                ("Ctrl+F", "Search motif or accession name"),
                ("Ctrl+J", "Jump to next search match"),
                ("?", "Open / Close this interactive Help viewer"),
                ("Tab", "Switch focus between Accession Names & Sequence Grid"),
                ("[ / ]", "Decrease / Increase Accession column width"),
            ]),
            ("GRID & SEQUENCE EDITING", [
                ("Insert", "Toggle Edit Mode: INSERT (insert base/gap) vs OVERWRITE"),
                ("A-Z, a-z, 0-9", "Insert or overwrite residue at cursor"),
                ("Space / -", "Insert or overwrite gap character '-' at cursor"),
                ("Backspace / Delete", "Sequence Grid: delete residue left of cursor"),
                ("Delete", "Accession Pane: delete highlighted sequence row (undoable)"),
                ("Page Up / Page Down", "Scroll sequences vertically by screen page"),
            ]),
            ("MENU: FILE & DISPLAY", [
                ("ESC > File > Format", "Toggle alignment format: FASTA <-> A3M <-> STO"),
                ("ESC > File > Export", "Export column consensus frequencies to CSV"),
                ("ESC > Display > Scheme", "Directly select Color Scheme:"),
                ("  * DNA / RNA", "Standard 4-color nucleotide scheme (A, C, G, T/U)"),
                ("  * Protein", "ClustalX chemical property colors for amino acids"),
                ("  * DIFF", "Highlight variable polymorphic sites only"),
                ("  * Monochrome", "High-contrast monochrome scheme"),
            ]),
            ("MENU: TOOLS & BIOINFORMATICS", [
                ("ESC > Tools > Translate", "Translate DNA to Protein (frames +1..+3, -1..-3)"),
                ("  * NCBI Codon Tables", "26 genetic code tables supported"),
                ("ESC > Tools > Sort", "Cluster / Sort sequences by Levenshtein distance"),
                ("ESC > Edit > Reorder", "Enter Move Mode to reorder rows with Up/Down arrows"),
                ("ESC > Edit > Add Row", "Add new sequence row to alignment"),
                ("ESC > Edit > Rename", "Rename selected sequence accession header"),
            ]),
        ]
        
        # Format the help items
        shortcut_w = 26
        for sec_title, items in help_data:
            content_lines.append("")
            content_lines.append(f"{colors['bold']}{colors['accent']}=== {sec_title} ==={colors['reset']}")
            for shortcut, desc in items:
                sh_str = f"  {shortcut}".ljust(shortcut_w)
                content_lines.append(f"{colors['gold']}{sh_str}{colors['reset']} {desc}")
                
        content_lines.append("")
        
        # Calculate viewport
        # Header takes 4 lines, Footer takes 4 lines.
        header_height = 4
        footer_height = 4
        view_h = rows - header_height - footer_height
        if view_h < 1:
            view_h = 1
            
        # Constrain scroll offset
        max_offset = max(0, len(content_lines) - view_h)
        if scroll_offset > max_offset:
            scroll_offset = max_offset
        if scroll_offset < 0:
            scroll_offset = 0
            
        # Render frame
        lines = []
        lines.append("\x1b[H\x1b[2J")  # Clear and home
        lines.append(colors["blue"] + "=" * cols + colors["reset"])
        
        title_text = " ALIGNANO INTERACTIVE HELP "
        pad_t = max(0, (cols - len(title_text)) // 2)
        lines.append(" " * pad_t + colors["bold"] + colors["gold"] + title_text + colors["reset"])
        lines.append(colors["blue"] + "=" * cols + colors["reset"])
        
        # Add viewport lines
        for i in range(view_h):
            idx = scroll_offset + i
            if idx < len(content_lines):
                line = content_lines[idx]
                lines.append(line)
            else:
                lines.append("")
                
        # Pad empty viewport lines if needed
        for _ in range(view_h - len(lines) + header_height):
            lines.append("")
            
        # Footer
        lines.append(colors["blue"] + "=" * cols + colors["reset"])
        scroll_indicator = f" Line {scroll_offset+1}/{len(content_lines)} "
        if len(content_lines) > view_h:
            scroll_indicator += f" [Use Up/Down/PgUp/PgDn to scroll]"
        footer_text = f" Press [ESC], [ENTER], [Ctrl+H], or [?] to return "
        
        # Draw footer lines centered
        pad_f = max(0, (cols - len(footer_text)) // 2)
        lines.append(" " * pad_f + colors["bold"] + footer_text + colors["reset"])
        
        pad_s = max(0, (cols - len(scroll_indicator)) // 2)
        lines.append(" " * pad_s + colors["dim"] + scroll_indicator + colors["reset"])
        lines.append(colors["blue"] + "=" * cols + colors["reset"])
        
        sys.stdout.write("\n".join(lines))
        sys.stdout.flush()
        
        # Wait for key
        try:
            key = read_key()
        except (TerminalResizeException, InterruptedError, OSError):
            key = "TERMINAL_RESIZE"

        if key == "TERMINAL_RESIZE":
            sys.stdout.write("\x1b[2J")
            sys.stdout.flush()
            continue
            
        if key in ("ESCAPE", "ENTER", "QUIT", "HELP", "Ctrl+H", "?") or (key in ("h", "H")):
            break
        elif key == "KEY_UP":
            scroll_offset = max(0, scroll_offset - 1)
        elif key == "KEY_DOWN":
            scroll_offset = min(max_offset, scroll_offset + 1)
        elif key == "PAGE_UP":
            scroll_offset = max(0, scroll_offset - view_h)
        elif key == "PAGE_DOWN":
            scroll_offset = min(max_offset, scroll_offset + view_h)


# ==============================================================================
# MAIN ENTRY & FILES SELECTOR
# ==============================================================================
def display_retro_intro(choices, selected_idx):
    """Draws professional ANSI start screen menu."""
    cols, rows = shutil.get_terminal_size((80, 24))
    lines = []

    # Modern Block-style ASCII art for "AligNano"
    banner = [
        "     _   _ _       _   _                  ",
        "    /_\\ | (_) __ _| \\ | | __ _ _ __   ___ ",
        "   //_\\\\| | |/ _` |  \\| |/ _` | '_ \\ / _ \\",
        "  /  _  \\ | | (_| | |\\  | (_| | | | | (_) |",
        "  \\_/ \\_/_|_|\\__, |_| \\_|\\__,_|_| |_|\\___/ ",
        "             |___/                         ",
    ]

    colors = get_theme_colors()

    lines.append("\x1b[H\x1b[2J")  # Clear and home
    lines.append(colors["blue"] + "=" * cols + colors["reset"])

    # Render banner centered
    for bline in banner:
        pad = max(0, (cols - len(bline)) // 2)
        lines.append(colors["gold"] + " " * pad + bline + colors["reset"])

    lines.append(colors["blue"] + "=" * cols + colors["reset"])
    lines.append(
        colors["bold"]
        + "  Multiple Sequence Alignment Editor & Browser"
        + colors["reset"]
    )
    lines.append("  Interactive Terminal Grid Viewer & Editor\n")

    lines.append("  " + colors["bold"] + "Menu Options:" + colors["reset"] + "\n")

    # Render options list
    for idx, choice in enumerate(choices):
        if idx == selected_idx:
            # Highlight selected item
            lines.append(f"   {colors['select_bg']} * {choice} {colors['reset']}")
        else:
            lines.append(f"     - {choice}")

    lines.append("")
    lines.append(
        colors["dim"]
        + "  [Arrows] Move selection   [Enter] Confirm Selection   [Q] Quit"
        + colors["reset"]
    )
    lines.append(colors["blue"] + "=" * cols + colors["reset"])

    sys.stdout.write("\n".join(lines))
    sys.stdout.flush()


def display_file_selector(files, selected_idx, scroll_offset, view_height):
    """Draws file selection screen with scrollable viewport."""
    cols, rows = shutil.get_terminal_size((80, 24))
    if rows < 18 or cols < 40:
        sys.stdout.write("\x1b[H\x1b[2JTerminal too small! Please resize.\n")
        sys.stdout.flush()
        return
    lines = []

    # Modern Block-style ASCII art for "AligNano"
    banner = [
        "     _   _ _       _   _                  ",
        "    /_\\ | (_) __ _| \\ | | __ _ _ __   ___ ",
        "   //_\\\\| | |/ _` |  \\| |/ _` | '_ \\ / _ \\",
        "  /  _  \\ | | (_| | |\\  | (_| | | | | (_) |",
        "  \\_/ \\_/_|_|\\__, |_| \\_|\\__,_|_| |_|\\___/ ",
        "             |___/                         ",
    ]

    colors = get_theme_colors()

    lines.append("\x1b[H\x1b[2J")  # Clear and home
    lines.append(colors["blue"] + "=" * cols + colors["reset"])

    # Render banner centered
    for bline in banner:
        pad = max(0, (cols - len(bline)) // 2)
        lines.append(colors["gold"] + " " * pad + bline + colors["reset"])

    lines.append(colors["blue"] + "=" * cols + colors["reset"])
    lines.append(
        colors["bold"]
        + "  Multiple Sequence Alignment Editor & Browser"
        + colors["reset"]
    )
    lines.append("  Interactive Terminal Grid Viewer & Editor\n")

    lines.append(
        "  "
        + colors["bold"]
        + "Select Alignment File to Load:"
        + colors["reset"]
        + "\n"
    )

    # Render files list using viewport windowing
    if len(files) == 1 and files[0] == "[ Go Back ]":
        lines.append("     (No .fasta, .a3m, or .sto files found in current directory)")
        lines.append("")
    else:
        # Determine slice of files to render
        visible_files = files[scroll_offset : scroll_offset + view_height]
        
        # Show scrolling indicators if there are more files
        if scroll_offset > 0:
            lines.append(colors["dim"] + "     ▲  [More files above]  ▲" + colors["reset"])
        else:
            lines.append("")
            
        for i, f in enumerate(visible_files):
            actual_idx = scroll_offset + i
            if actual_idx == selected_idx:
                # Highlight selected item
                lines.append(f"   {colors['select_bg']} * {f} {colors['reset']}")
            else:
                lines.append(f"     - {f}")
                
        # Fill rest of visible list with empty lines if needed
        # (This keeps the height of the screen consistent)
        for _ in range(view_height - len(visible_files)):
            lines.append("")

        if scroll_offset + view_height < len(files):
            lines.append(colors["dim"] + f"     ▼  [More files below ({len(files) - (scroll_offset + view_height)} more)]  ▼" + colors["reset"])
        else:
            lines.append("")

    lines.append("")
    lines.append(
        colors["dim"]
        + "  [Arrows] Move selection   [Enter] Load File   [Esc/Q] Cancel"
        + colors["reset"]
    )
    lines.append(colors["blue"] + "=" * cols + colors["reset"])

    sys.stdout.write("\n".join(lines))
    sys.stdout.flush()


def run_file_selector():
    """Interactive menu to select a FASTA/A3M/STO file from the current directory and subdirectories."""
    # List files case-insensitively matching standard extensions
    valid_exts = (".fasta", ".fa", ".msa", ".seq", ".a3m", ".sto", ".stk", ".stockholm")
    files = []
    for root, dirs, filenames in os.walk("."):
        # Prune hidden directories (e.g. .git) and __pycache__
        dirs[:] = [d for d in dirs if not d.startswith('.') and d != '__pycache__']
        for f in filenames:
            if f.lower().endswith(valid_exts):
                rel_path = os.path.relpath(os.path.join(root, f), ".")
                files.append(rel_path)

    files = sorted(files)
    files.append("[ Go Back ]")
    selected_idx = 0
    scroll_offset = 0

    while True:
        cols, rows = shutil.get_terminal_size((80, 24))
        # 18 lines of overhead (banner, scroll indicators, margins)
        view_height = max(3, rows - 18)
        
        # Constrain selected_idx
        if selected_idx < 0:
            selected_idx = 0
        if selected_idx >= len(files):
            selected_idx = len(files) - 1

        # Adjust scroll offset
        if selected_idx < scroll_offset:
            scroll_offset = selected_idx
        elif selected_idx >= scroll_offset + view_height:
            scroll_offset = selected_idx - view_height + 1

        display_file_selector(files, selected_idx, scroll_offset, view_height)
        try:
            key = read_key()
        except (TerminalResizeException, InterruptedError, OSError):
            key = "TERMINAL_RESIZE"

        if key == "TERMINAL_RESIZE":
            sys.stdout.write("\x1b[2J")
            sys.stdout.flush()
            continue

        if key == "KEY_UP":
            selected_idx = max(0, selected_idx - 1)
        elif key == "KEY_DOWN":
            selected_idx = min(len(files) - 1, selected_idx + 1)
        elif key == "ENTER":
            choice = files[selected_idx]
            if choice == "[ Go Back ]":
                return None
            else:
                return choice
        elif key in ("ESCAPE", "Q", "q"):
            return None


def main():
    args = sys.argv[1:]
    mouse_arg = True
    filepath = None
    for arg in args:
        if arg in ("--no-mouse", "--nomouse", "-M"):
            mouse_arg = False
        elif arg in ("--mouse", "-m"):
            mouse_arg = True
        elif not filepath and not arg.startswith("-"):
            filepath = arg

    if filepath:
        run_editor(filepath, mouse_enabled=mouse_arg)
        return

    choices = ["Load Alignment (FASTA, A3M, or STO)", "Create New Empty Alignment", "Exit"]

    selected_idx = 0
    valid_exts = (".fasta", ".fa", ".msa", ".seq", ".a3m", ".sto", ".stk", ".stockholm")

    # Hide cursor
    sys.stdout.write("\x1b[?25l")
    sys.stdout.flush()

    try:
        while True:
            display_retro_intro(choices, selected_idx)
            try:
                key = read_key()
            except (TerminalResizeException, InterruptedError, OSError):
                key = "TERMINAL_RESIZE"

            if key == "TERMINAL_RESIZE":
                sys.stdout.write("\x1b[2J")
                sys.stdout.flush()
                continue

            if key == "KEY_UP":
                selected_idx = max(0, selected_idx - 1)
            elif key == "KEY_DOWN":
                selected_idx = min(len(choices) - 1, selected_idx + 1)
            elif key == "ENTER":
                choice = choices[selected_idx]
                if choice == "Exit":
                    break
                elif choice == "Create New Empty Alignment":
                    # Prompt for file name
                    sys.stdout.write("\x1b[?25h\n Enter name for new FASTA/A3M/STO file: ")
                    sys.stdout.flush()
                    new_filename = sys.stdin.readline().strip()
                    sys.stdout.write("\x1b[?25l")

                    if not new_filename:
                        new_filename = "new_alignment.fasta"
                    if not new_filename.lower().endswith(valid_exts):
                        new_filename += ".fasta"

                    # Respect sandbox
                    full_path = os.path.abspath(new_filename)
                    current_dir = os.path.abspath(os.getcwd())
                    if not full_path.startswith(current_dir):
                        print(
                            "\n Access denied (sandbox policy: AligNano folder only)."
                        )
                        time.sleep(2)
                        continue

                    # Initialize empty alignment
                    if new_filename.lower().endswith((".sto", ".stk", ".stockholm")):
                        save_stockholm(new_filename, ["Seq_1"], ["ACTG-ACTG-ACTG-ACTG"])
                    else:
                        save_fasta(new_filename, ["Seq_1"], ["ACTG-ACTG-ACTG-ACTG"])
                    run_editor(new_filename, mouse_enabled=mouse_arg)
                    break
                elif choice == "Load Alignment (FASTA, A3M, or STO)":
                    selected_file = run_file_selector()
                    if selected_file:
                        run_editor(selected_file, mouse_enabled=mouse_arg)
                        break
            elif key == "Q" or key == "ESCAPE":
                break
    finally:
        disable_mouse_tracking()
        # Show cursor and reset screen on exit
        sys.stdout.write("\x1b[?25h\x1b[H\x1b[2J")
        sys.stdout.flush()

        sys.stdout.flush()

if __name__ == "__main__":
    main()
