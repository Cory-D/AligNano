#!/usr/bin/env python3
# AligNano Version: 1.0.10
import os
import sys
import time
import shutil
import select
import copy

class TerminalResizeException(Exception):
    pass

def supports_256_colors():
    """Detects if stdout supports 256 colors."""
    if not sys.stdout.isatty():
        return False
    # Check COLORTERM first
    colorterm = os.environ.get("COLORTERM", "").lower()
    if colorterm in ("truecolor", "24bit"):
        return True
    # Check TERM
    term = os.environ.get("TERM", "").lower()
    if "256color" in term or "256" in term:
        return True
    # Check Windows Terminal/VS Code environments
    if sys.platform == "win32":
        if "WT_SESSION" in os.environ or "VSCODE_GIT_IPC_HANDLE" in os.environ:
            return True
    return False

def get_theme_colors():
    """Returns terminal color codes depending on 256-color support."""
    has_256 = supports_256_colors()
    if has_256:
        return {
            'accent': '\x1b[38;5;198m',
            'gold': '\x1b[38;5;220m',
            'dim': '\x1b[38;5;244m',
            'bold': '\x1b[1m',
            'reset': '\x1b[0m',
            'select_bg': '\x1b[48;5;198m\x1b[38;5;231m',
        }
    else:
        return {
            'accent': '\x1b[35m',      # Magenta
            'gold': '\x1b[33m',        # Yellow
            'dim': '\x1b[2m',          # Dim / faint
            'bold': '\x1b[1m',
            'reset': '\x1b[0m',
            'select_bg': '\x1b[7m',    # Inverted text
        }

# ==============================================================================
# TERMINAL ESCAPE CODES & WINDOWS COMPATIBILITY
# ==============================================================================
if sys.platform == "win32":
    import msvcrt
    import ctypes
    # Enable Virtual Terminal Processing for ANSI colors and controls on Windows
    kernel32 = ctypes.windll.kernel32
    mode = ctypes.c_ulong()
    
    # stdout VT Mode
    stdout_handle = kernel32.GetStdHandle(-11)
    if kernel32.GetConsoleMode(stdout_handle, ctypes.byref(mode)):
        mode.value |= 0x0004 | 0x0008  # ENABLE_VIRTUAL_TERMINAL_PROCESSING | DISABLE_NEWLINE_AUTO_RETURN
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
    
    def resize_handler(signum, frame):
        raise TerminalResizeException()
        
    signal.signal(signal.SIGWINCH, resize_handler)

# ==============================================================================
# ALIVIEW-INSPIRED COLOR SCHEMES (ANSI 256-color)
# ==============================================================================
# Nucleotide Colors: A (Red), T/U (Green), C (Blue), G (Yellow), Gap (Dark Grey)
NUC_COLORS = {
    'A': '\x1b[48;5;196m\x1b[38;5;231m', # Red bg, White fg
    'T': '\x1b[48;5;40m\x1b[38;5;231m',  # Green bg, White fg
    'U': '\x1b[48;5;40m\x1b[38;5;231m',  # Green bg, White fg
    'C': '\x1b[48;5;21m\x1b[38;5;231m',  # Blue bg, White fg
    'G': '\x1b[48;5;226m\x1b[38;5;16m',  # Yellow bg, Black fg
    '-': '\x1b[48;5;234m\x1b[38;5;244m', # Dark grey bg, Grey fg
    '.': '\x1b[48;5;234m\x1b[38;5;244m', # Dark grey bg, Grey fg
}
DEFAULT_NUC = '\x1b[48;5;250m\x1b[38;5;16m'

# Amino Acid Colors (Static ClustalX-like properties)
AA_COLORS = {
    # Acidic (D, E): Red bg, White fg
    'D': '\x1b[48;5;160m\x1b[38;5;231m',
    'E': '\x1b[48;5;160m\x1b[38;5;231m',
    # Basic (K, R, H): Blue bg, White fg
    'K': '\x1b[48;5;27m\x1b[38;5;231m',
    'R': '\x1b[48;5;27m\x1b[38;5;231m',
    'H': '\x1b[48;5;33m\x1b[38;5;231m',
    # Polar/Uncharged (N, Q, S, T): Green bg, Black fg
    'N': '\x1b[48;5;76m\x1b[38;5;16m',
    'Q': '\x1b[48;5;76m\x1b[38;5;16m',
    'S': '\x1b[48;5;82m\x1b[38;5;16m',
    'T': '\x1b[48;5;82m\x1b[38;5;16m',
    # Hydrophobic/Aromatic (A, I, L, M, F, W, V, P, Y): Orange/Yellow bg, Black fg
    'A': '\x1b[48;5;214m\x1b[38;5;16m',
    'I': '\x1b[48;5;214m\x1b[38;5;16m',
    'L': '\x1b[48;5;220m\x1b[38;5;16m',
    'M': '\x1b[48;5;220m\x1b[38;5;16m',
    'F': '\x1b[48;5;208m\x1b[38;5;16m',
    'W': '\x1b[48;5;208m\x1b[38;5;16m',
    'V': '\x1b[48;5;214m\x1b[38;5;16m',
    'P': '\x1b[48;5;178m\x1b[38;5;16m',
    'Y': '\x1b[48;5;184m\x1b[38;5;16m',
    # Cysteine (C): Pink bg, White fg
    'C': '\x1b[48;5;201m\x1b[38;5;231m',
    # Glycine (G): Grey bg, White fg
    'G': '\x1b[48;5;244m\x1b[38;5;231m',
    # Gaps
    '-': '\x1b[48;5;234m\x1b[38;5;244m',
    '.': '\x1b[48;5;234m\x1b[38;5;244m',
}
DEFAULT_AA = '\x1b[48;5;250m\x1b[38;5;16m'

# ==============================================================================
# KEYBOARD INPUT HANDLERS
# ==============================================================================
def read_key():
    """Cross-platform keyboard reader returning clean logical strings."""
    if sys.platform == "win32":
        # Windows keyboard input
        ch = msvcrt.getch()
        if ch in (b'\x00', b'\xe0'):
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
            k = ch.decode('utf-8')
        except UnicodeDecodeError:
            k = ch
            
        common_map = {
            "\x01": "ADD_ROW",       # Ctrl+A
            "\x04": "PAGE_DOWN",     # Ctrl+D
            "\x05": "EDIT_NAME",     # Ctrl+E
            "\x0b": "DELETE",        # Ctrl+K
            "\x0c": "PAGE_LEFT",     # Ctrl+L
            "\x0f": "INSERT",        # Ctrl+O
            "\x11": "QUIT",          # Ctrl+Q
            "\x12": "PAGE_RIGHT",    # Ctrl+R
            "\x13": "SAVE",          # Ctrl+S
            "\x15": "PAGE_UP",       # Ctrl+U
            "\x16": "CYCLE_COLORS",  # Ctrl+V
            "\x18": "DELETE_ROW",    # Ctrl+X
            "\x19": "REDO",          # Ctrl+Y
            "\x1a": "UNDO",
            "\x7f": "DELETE",
            "\x08": "DELETE",
            "\x07": "EXPORT_FREQ",
            "\r": "ENTER",
            "\n": "ENTER",
            "\t": "TAB",
            "\x1b": "ESCAPE",
        }
        return common_map.get(k, k)
    else:
        # Unix keyboard input
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            ch = os.read(fd, 1).decode('utf-8', errors='ignore')
            if ch == '\x1b':
                rlist, _, _ = select.select([fd], [], [], 0.05)
                if rlist:
                    seq = ch + os.read(fd, 7).decode('utf-8', errors='ignore')
                    
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
                "\x01": "ADD_ROW",       # Ctrl+A
                "\x04": "PAGE_DOWN",     # Ctrl+D
                "\x05": "EDIT_NAME",     # Ctrl+E
                "\x0b": "DELETE",        # Ctrl+K
                "\x0c": "PAGE_LEFT",     # Ctrl+L
                "\x0f": "INSERT",        # Ctrl+O
                "\x11": "QUIT",          # Ctrl+Q
                "\x12": "PAGE_RIGHT",    # Ctrl+R
                "\x13": "SAVE",          # Ctrl+S
                "\x15": "PAGE_UP",       # Ctrl+U
                "\x16": "CYCLE_COLORS",  # Ctrl+V
                "\x18": "DELETE_ROW",    # Ctrl+X
                "\x19": "REDO",          # Ctrl+Y
                "\x1a": "UNDO",
                "\x7f": "DELETE",
                "\x08": "DELETE",
                "\x07": "EXPORT_FREQ",
                "\r": "ENTER",
                "\n": "ENTER",
                "\t": "TAB",
            }
            return common_map.get(ch, ch)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

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
        
    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            if line.startswith('>'):
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
                sequences[i] = sequences[i] + '-' * (max_len - len(sequences[i]))
    
    # If file was empty, return empty lists
    return headers, sequences

def save_fasta(filepath, headers, sequences):
    """Saves headers and sequences to FASTA format."""
    with open(filepath, 'w', encoding='utf-8') as f:
        for h, s in zip(headers, sequences):
            f.write(f">{h}\n")
            # Write sequence in standard 80-char block width or single line
            # Aliview saves single line or block width, we'll write in 80-char chunks
            for i in range(0, len(s), 80):
                f.write(s[i:i+80] + "\n")

def detect_vis_mode(sequences):
    """Detects whether alignment is likely nucleotide or protein."""
    if not sequences:
        return 'nuc'
    # Count characters in first 1000 characters of alignment
    chars = "".join(sequences)[:1000].upper()
    nuc_chars = sum(1 for c in chars if c in 'ACGUTN-')
    total = len(chars)
    if total == 0:
        return 'nuc'
    # If > 80% are typical nucleotide characters, use nucleotide coloring
    if (nuc_chars / total) > 0.8:
        return 'nuc'
    return 'aa'

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
        self.redo_stack.append((copy.deepcopy(current_headers), copy.deepcopy(current_sequences)))
        return self.undo_stack.pop()
        
    def redo(self, current_headers, current_sequences):
        if not self.redo_stack:
            return None
        self.undo_stack.append((copy.deepcopy(current_headers), copy.deepcopy(current_sequences)))
        return self.redo_stack.pop()

# ==============================================================================
# SCREEN RENDERING LOOP
# ==============================================================================
def draw_screen(headers, sequences, cursor_row, cursor_col, row_offset, col_offset, 
                active_pane, filename, insert_mode, vis_mode, modified, acc_width,
                status_msg="", prompt_mode=None, prompt_text="", prompt_input=""):
    """Composes and renders the entire editor layout to stdout in a single write."""
    cols, rows = shutil.get_terminal_size((80, 24))
    
    # Borders: left border (1), separator (1), right border (1), safety spacer (1)
    seq_width = cols - acc_width - 4
    view_height = rows - 9 # 3 lines header, 2 lines ruler, 4 lines footer
    
    # Calculate non-identical columns for DIFF visualization mode
    non_identical_cols = set()
    if vis_mode == 'diff' and sequences:
        num_seqs_val = len(sequences)
        seq_len_val = len(sequences[0])
        for col_idx in range(col_offset, min(seq_len_val, col_offset + seq_width)):
            first_char = sequences[0][col_idx].upper() if col_idx < len(sequences[0]) else '-'
            is_identical = True
            for r in range(1, num_seqs_val):
                char = sequences[r][col_idx].upper() if col_idx < len(sequences[r]) else '-'
                if char != first_char:
                    is_identical = False
                    break
            if not is_identical:
                non_identical_cols.add(col_idx)
    
    if view_height < 1 or seq_width < 1:
        sys.stdout.write("\x1b[H\x1b[2JTerminal too small! Please resize.\n")
        sys.stdout.flush()
        return

    num_seqs = len(sequences)
    seq_len = len(sequences[0]) if num_seqs > 0 else 0
    has_256 = supports_256_colors()
    colors_theme = get_theme_colors()
    
    lines = []
    
    # 1. Header top border (ASCII)
    lines.append("+" + "-" * (cols - 2) + "+")
    
    # 2. Header Status Line
    filename_display = os.path.basename(filename) if filename else "[New Alignment]"
    mod_marker = " *" if modified else ""
    mode_marker = "INS" if insert_mode else "OVR"
    vis_name = "DNA/RNA" if vis_mode == 'nuc' else ("Protein" if vis_mode == 'aa' else ("Diff (Var)" if vis_mode == 'diff' else "Monochrome"))
    
    header_left = f" # AligNano # File: {filename_display}{mod_marker} | Mode: {mode_marker} | Colors: {vis_name} | Pane: {acc_width}"
    header_right = f"Seq: {cursor_row+1}/{num_seqs} Col: {cursor_col+1}/{seq_len} "
    
    space_left = cols - 2 - len(header_left) - len(header_right)
    if space_left < 0:
        header_text = (header_left + " " + header_right)[:cols-2]
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
            
    ruler_nums_str = colors_theme['dim'] + "".join(nums_list) + colors_theme['reset']
    ruler_ticks_str = colors_theme['dim'] + "".join(ticks_list) + colors_theme['reset']
    
    acc_blank = " " * acc_width
    lines.append(f"|{acc_blank}|{ruler_nums_str}|")
    lines.append(f"|{acc_blank}+{ruler_ticks_str}|")
    
    # 4. Body Viewport
    for i in range(view_height):
        seq_idx = row_offset + i
        
        # Accession Subpane
        acc_part = ""
        if seq_idx < num_seqs:
            name = headers[seq_idx]
            disp_name = name[:acc_width]
            disp_name = disp_name + " " * (acc_width - len(disp_name))
            
            if seq_idx == cursor_row:
                if active_pane == 'acc' and not prompt_mode:
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
                    is_cursor = (seq_idx == cursor_row and char_idx == cursor_col)
                    
                    # Formatting logic
                    color = ""
                    if vis_mode == 'nuc':
                        color = NUC_COLORS.get(c.upper(), DEFAULT_NUC)
                    elif vis_mode == 'aa':
                        color = AA_COLORS.get(c.upper(), DEFAULT_AA)
                    elif vis_mode == 'diff':
                        if char_idx in non_identical_cols:
                            base_mode = detect_vis_mode(sequences)
                            if base_mode == 'nuc':
                                color = NUC_COLORS.get(c.upper(), DEFAULT_NUC)
                            else:
                                color = AA_COLORS.get(c.upper(), DEFAULT_AA)
                    
                    if is_cursor:
                        if active_pane == 'seq' and not prompt_mode:
                            # Highlight cursor block
                            if has_256:
                                seq_part += f"\x1b[48;5;198m\x1b[38;5;231m\x1b[1m{c}\x1b[0m"
                            else:
                                seq_part += f"\x1b[7m\x1b[1m{c}\x1b[0m"
                        else:
                            # Secondary highlight for column alignment
                            if has_256:
                                seq_part += f"\x1b[48;5;238m\x1b[38;5;231m{c}\x1b[0m"
                            else:
                                seq_part += f"\x1b[4m{c}\x1b[0m"
                    else:
                        if color and has_256 and vis_mode != 'mono':
                            seq_part += f"{color}{c}\x1b[0m"
                        else:
                            seq_part += c
                else:
                    seq_part += " "
        else:
            seq_part = " " * seq_width
            
        lines.append(f"|{acc_part}{divider}{seq_part}|")
        
    # 5. Footer separator (ASCII)
    lines.append("+" + "-" * acc_width + "+" + "-" * (cols - acc_width - 3) + "+")
    
    # 6. Status / Help / Prompt Line
    if prompt_mode:
        raw_prompt = f" * {prompt_text}{prompt_input}"
        space_left = cols - 2 - len(raw_prompt) - 1 # 1 for cursor char
        lines.append("|" + raw_prompt + "_" + " " * max(0, space_left) + "|")
    elif status_msg:
        # Show flashing warning or successful saving notification
        space_left = cols - 2 - len(status_msg)
        lines.append("|" + status_msg + " " * max(0, space_left) + "|")
    else:
        # Static instructions line
        help_text = " [Arrows] Move  [Tab] Swap  [Del] Del  [[/]] Pane  [Ctrl+V] Col  [Ctrl+O] Mode"
        space_left = cols - 2 - len(help_text)
        lines.append("|" + help_text + " " * max(0, space_left) + "|")
        
    # 7. Navigation shortcut help line
    if not prompt_mode:
        nav_text = " [Ctrl+E] Name  [Ctrl+F] Find  [Ctrl+G] Freq  [Ctrl+S] Save  [Ctrl+Q] Quit"
    else:
        nav_text = " [Enter] Confirm  [Escape] Cancel / Exit Prompt"
    space_left = cols - 2 - len(nav_text)
    lines.append("|" + nav_text + " " * max(0, space_left) + "|")
    
    # 8. Footer bottom border (ASCII)
    lines.append("+" + "-" * (cols - 2) + "+")
    
    # Write full viewport starting at terminal home (0,0) without trailing newline to avoid scrolling
    sys.stdout.write("\x1b[H" + "\n".join(lines))
    sys.stdout.flush()

# ==============================================================================
# MAIN EDITOR SESSION
# ==============================================================================
def run_editor(filepath):
    """Main keyboard polling and state update loop for the FASTA editor."""
    headers, sequences = load_fasta(filepath)
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
    
    active_pane = 'seq' # 'acc' or 'seq'
    insert_mode = False # False = Overwrite, True = Insert
    if not supports_256_colors():
        vis_mode = 'mono'
    else:
        vis_mode = detect_vis_mode(sequences)
    modified = False
    acc_width_delta = 0
    
    history = StateHistory()
    
    # Clear screen and hide cursor on start
    sys.stdout.write("\x1b[2J\x1b[?25l")
    sys.stdout.flush()
    
    status_msg = ""
    status_expiry = 0.0
    
    prompt_mode = None
    prompt_text = ""
    prompt_input = ""
    
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
            headers, sequences, cursor_row, cursor_col, row_offset, col_offset,
            active_pane, filename, insert_mode, vis_mode, modified, acc_width,
            status_msg, prompt_mode, prompt_text, prompt_input
        )
        
        # Read user keystroke
        try:
            key = read_key()
        except TerminalResizeException:
            # Clear screen and force redraw on next iteration
            sys.stdout.write("\x1b[2J")
            sys.stdout.flush()
            continue
        
        # Prompt mode processing
        if prompt_mode:
            if key == 'ESCAPE':
                prompt_mode = None
                prompt_input = ""
                status_msg = "Command cancelled."
                status_expiry = time.time() + 2.0
            elif key == 'ENTER':
                # Process confirmation/string
                if prompt_mode == 'edit_name':
                    if prompt_input.strip():
                        history.push_state(headers, sequences)
                        headers[cursor_row] = prompt_input.strip()
                        modified = True
                        status_msg = "Accession name updated."
                    prompt_mode = None
                    prompt_input = ""
                elif prompt_mode == 'save_file':
                    dest_file = prompt_input.strip()
                    if dest_file:
                        # Restrict reads/writes within the sandbox AligNano (or child directories)
                        # Normalize path
                        full_path = os.path.abspath(dest_file)
                        current_dir = os.path.abspath(os.getcwd())
                        if not full_path.startswith(current_dir):
                            status_msg = "Error: Access denied (sandbox policy: AligNano folder only)."
                            status_expiry = time.time() + 4.0
                        else:
                            try:
                                save_fasta(dest_file, headers, sequences)
                                filename = dest_file
                                modified = False
                                status_msg = f"Alignment successfully saved to: {os.path.basename(dest_file)}"
                            except Exception as e:
                                status_msg = f"Save failed: {str(e)}"
                            status_expiry = time.time() + 3.0
                    prompt_mode = None
                    prompt_input = ""
                elif prompt_mode == 'export_freq':
                    prefix = prompt_input.strip() if prompt_input.strip() else "frequencies"
                    
                    # Compute output filenames
                    counts_all_path = prefix + "_counts_all.csv"
                    counts_changed_path = prefix + "_counts_changed.csv"
                    freq_all_path = prefix + "_frequencies_all.csv"
                    freq_changed_path = prefix + "_frequencies_changed.csv"
                    
                    target_counts_all = os.path.abspath(counts_all_path)
                    target_counts_changed = os.path.abspath(counts_changed_path)
                    target_freq_all = os.path.abspath(freq_all_path)
                    target_freq_changed = os.path.abspath(freq_changed_path)
                    
                    current_dir = os.path.abspath(os.getcwd())
                    paths = [target_counts_all, target_counts_changed, target_freq_all, target_freq_changed]
                    
                    if any(not p.startswith(current_dir) for p in paths):
                        status_msg = "Error: Access denied (sandbox policy: AligNano folder only)."
                        status_expiry = time.time() + 4.0
                    else:
                        try:
                            num_seqs = len(sequences)
                            seq_len = len(sequences[0]) if num_seqs > 0 else 0
                            
                            # Dynamically build standard set of unique characters (alphanumeric and gaps)
                            all_chars_set = set()
                            for seq in sequences:
                                for c in seq:
                                    c_upper = c.upper()
                                    if c_upper.isalnum() or c_upper == '-':
                                        all_chars_set.add(c_upper)
                            all_chars = sorted(list(all_chars_set))
                            
                            # Precompute counts and frequencies for all columns
                            col_data_counts = {char: [] for char in all_chars}
                            col_data_freq = {char: [] for char in all_chars}
                            changed_col_indices = []
                            
                            for col_idx in range(seq_len):
                                col_chars = [sequences[r][col_idx].upper() for r in range(num_seqs) if col_idx < len(sequences[r])]
                                from collections import Counter
                                counts = Counter(col_chars)
                                
                                for char in all_chars:
                                    cnt = counts.get(char, 0)
                                    freq = cnt / num_seqs if num_seqs > 0 else 0.0
                                    col_data_counts[char].append(cnt)
                                    col_data_freq[char].append(round(freq, 4))
                                    
                                if len(set(col_chars)) > 1:
                                    changed_col_indices.append(col_idx)
                                    
                            # CSV Headers (Transposed: Characters on left, 1-indexed positions as columns)
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
                                
                            # Write counts_all
                            import csv
                            with open(target_counts_all, 'w', newline='', encoding='utf-8') as f:
                                writer = csv.writer(f)
                                writer.writerow(csv_headers_all)
                                writer.writerows(counts_all_rows)
                                
                            # Write counts_changed
                            with open(target_counts_changed, 'w', newline='', encoding='utf-8') as f:
                                writer = csv.writer(f)
                                writer.writerow(csv_headers_changed)
                                writer.writerows(counts_changed_rows)
                                
                            # Write frequencies_all
                            with open(target_freq_all, 'w', newline='', encoding='utf-8') as f:
                                writer = csv.writer(f)
                                writer.writerow(csv_headers_all)
                                writer.writerows(freq_all_rows)
                                
                            # Write frequencies_changed
                            with open(target_freq_changed, 'w', newline='', encoding='utf-8') as f:
                                writer = csv.writer(f)
                                writer.writerow(csv_headers_changed)
                                writer.writerows(freq_changed_rows)
                                
                            status_msg = f"Exported 4 frequency/count CSVs successfully."
                            status_expiry = time.time() + 3.0
                        except Exception as e:
                            status_msg = f"Export failed: {str(e)}"
                            status_expiry = time.time() + 3.0
                    prompt_mode = None
                    prompt_input = ""
                elif prompt_mode == 'add_seq':
                    name = prompt_input.strip() if prompt_input.strip() else f"Seq_{num_seqs + 1}"
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
                elif prompt_mode == 'quit_confirm':
                    if prompt_input.upper().startswith('Y'):
                        break
                    else:
                        prompt_mode = None
                        prompt_input = ""
                elif prompt_mode == 'delete_confirm':
                    if prompt_input.upper().startswith('Y'):
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
                elif prompt_mode == 'search':
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
                                matches.append((r, idx, 'seq'))
                                pos = idx + 1
                        for r, name in enumerate(headers):
                            if query.upper() in name.upper():
                                matches.append((r, 0, 'acc'))
                        matches.sort(key=lambda m: (m[0], m[1] if m[2] == 'seq' else -1))
                        search_matches = matches
                        if matches:
                            search_match_idx = 0
                            for idx, (r, c, pane) in enumerate(matches):
                                if r > cursor_row or (r == cursor_row and (pane == 'acc' or c >= cursor_col)):
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
            elif key == 'DELETE':
                prompt_input = prompt_input[:-1]
            elif isinstance(key, str) and len(key) == 1:
                prompt_input += key
            continue
            
        # Normal command controls
        is_cmd_mode = (active_pane == 'acc')
        
        if key == 'QUIT' or (is_cmd_mode and key == 'Q'):
            if modified:
                prompt_mode = 'quit_confirm'
                prompt_text = "Unsaved changes! Quit anyway? (y/N): "
                prompt_input = ""
            else:
                break
                
        elif key == 'SEARCH':
            prompt_mode = 'search'
            prompt_text = "Search motif/name: "
            prompt_input = ""
            
        elif key == 'FIND_NEXT':
            if search_query and search_matches:
                search_match_idx = (search_match_idx + 1) % len(search_matches)
                r, c, pane = search_matches[search_match_idx]
                cursor_row = r
                cursor_col = c
                active_pane = pane
                status_msg = f"Match {search_match_idx + 1}/{len(search_matches)}: Row {r+1}, Col {c+1}"
            else:
                status_msg = "No active search. Press Ctrl+F to search."
            status_expiry = time.time() + 2.0
                
        elif key == 'KEY_UP':
            cursor_row -= 1
        elif key == 'KEY_DOWN':
            cursor_row += 1
            
        elif key == 'KEY_LEFT':
            if active_pane == 'seq':
                if cursor_col == 0:
                    active_pane = 'acc'
                else:
                    cursor_col -= 1
            else:
                pass # Can't go further left than accession pane
                
        elif key == 'KEY_RIGHT':
            if active_pane == 'acc':
                active_pane = 'seq'
                cursor_col = col_offset
            else:
                cursor_col += 1
                
        # Scrolling Pages
        elif key == 'PAGE_UP' or key == 'CTRL_UP':
            # Page up sequences/accessions (rows)
            cursor_row = max(0, cursor_row - (view_height - 2))
        elif key == 'PAGE_DOWN' or key == 'CTRL_DOWN':
            # Page down sequences/accessions (rows)
            cursor_row = min(num_seqs - 1, cursor_row + (view_height - 2))
        elif key == 'PAGE_LEFT' or key == 'CTRL_LEFT':
            # Page sequence left (columns)
            cursor_col = max(0, cursor_col - (seq_width - 5))
        elif key == 'PAGE_RIGHT' or key == 'CTRL_RIGHT':
            # Page sequence right (columns)
            cursor_col = min(seq_len - 1, cursor_col + (seq_width - 5))
            
        elif key == '[':
            acc_width_delta -= 1
            status_msg = "Accession panel narrowed."
            status_expiry = time.time() + 1.0
        elif key == ']':
            acc_width_delta += 1
            status_msg = "Accession panel widened."
            status_expiry = time.time() + 1.0
            
        elif key == 'TAB':
            # Switch pane focus
            active_pane = 'seq' if active_pane == 'acc' else 'acc'
            
        elif key == 'INSERT':
            # Toggle edit mode
            insert_mode = not insert_mode
            status_msg = f"Edit Mode: {'INSERT' if insert_mode else 'OVERWRITE'}"
            status_expiry = time.time() + 2.0
            
        elif key == 'CYCLE_COLORS' or (is_cmd_mode and key == 'V'):
            # Toggle visualization mode
            if not supports_256_colors():
                vis_mode = 'mono'
                status_msg = "Visual Mode: MONOCHROME (256-color not supported)"
            else:
                if vis_mode == 'nuc':
                    vis_mode = 'aa'
                    status_msg = "Visual Mode: PROTEIN (ClustalX)"
                elif vis_mode == 'aa':
                    vis_mode = 'diff'
                    status_msg = "Visual Mode: DIFF (Only highlight variable sites)"
                elif vis_mode == 'diff':
                    vis_mode = 'mono'
                    status_msg = "Visual Mode: MONOCHROME"
                else:
                    vis_mode = 'nuc'
                    status_msg = "Visual Mode: DNA/RNA"
            status_expiry = time.time() + 2.0
            
        elif key == 'UNDO' or (is_cmd_mode and key == 'U'):
            restored = history.undo(headers, sequences)
            if restored:
                headers, sequences = restored
                modified = True
                status_msg = "Action Undone."
            else:
                status_msg = "Nothing to undo."
            status_expiry = time.time() + 2.0
            
        elif key == 'REDO' or (is_cmd_mode and key == 'Y'):
            restored = history.redo(headers, sequences)
            if restored:
                headers, sequences = restored
                modified = True
                status_msg = "Action Redone."
            else:
                status_msg = "Nothing to redo."
            status_expiry = time.time() + 2.0
            
        elif key == 'EDIT_NAME' or (is_cmd_mode and key == 'E'):
            # Edit name
            prompt_mode = 'edit_name'
            prompt_text = "Enter accession name: "
            prompt_input = headers[cursor_row]
            
        elif key == 'ADD_ROW' or (is_cmd_mode and key == 'A'):
            # Add new row
            prompt_mode = 'add_seq'
            prompt_text = "New sequence name (default Seq_N): "
            prompt_input = ""
            
        elif key == 'DELETE_ROW' or (is_cmd_mode and key == 'X'):
            # Delete current row
            if num_seqs <= 1:
                status_msg = "Cannot delete the last remaining sequence."
                status_expiry = time.time() + 2.0
            else:
                prompt_mode = 'delete_confirm'
                prompt_text = f"Delete sequence row '{headers[cursor_row]}'? (y/N): "
                prompt_input = ""
                
        elif key == 'SAVE' or (is_cmd_mode and key == 'S'):
            # Save Alignment
            prompt_mode = 'save_file'
            prompt_text = "Save as (FASTA file path): "
            prompt_input = filename
            
        elif key == 'EXPORT_FREQ' or (is_cmd_mode and key == 'G'):
            # Export frequencies
            prompt_mode = 'export_freq'
            prompt_text = "Export prefix: "
            if filename:
                base_name = os.path.splitext(os.path.basename(filename))[0]
            else:
                base_name = "frequencies"
            prompt_input = base_name
            
        elif key == 'DELETE' or (is_cmd_mode and key == 'D'):
            # Delete character to the left of the cursor and shorten sequence
            if cursor_col > 0:
                history.push_state(headers, sequences)
                current_seq = sequences[cursor_row]
                sequences[cursor_row] = current_seq[:cursor_col-1] + current_seq[cursor_col:]
                cursor_col -= 1
                modified = True
                status_msg = "Deleted base (sequence shortened)."
                status_expiry = time.time() + 1.5
                
        elif key == ' ' or key == '-':
            # Insert or overwrite Gap at cursor
            if active_pane == 'seq':
                history.push_state(headers, sequences)
                current_seq = sequences[cursor_row]
                
                if insert_mode:
                    # Insert mode: pushes letters right and pads other sequences
                    sequences[cursor_row] = current_seq[:cursor_col] + "-" + current_seq[cursor_col:]
                    # Check new max length and pad all others
                    max_len = max(len(s) for s in sequences)
                    for i in range(len(sequences)):
                        if len(sequences[i]) < max_len:
                            sequences[i] = sequences[i] + '-' * (max_len - len(sequences[i]))
                else:
                    # Overwrite mode: replaces character under cursor, maintaining length
                    if cursor_col < len(current_seq):
                        sequences[cursor_row] = current_seq[:cursor_col] + "-" + current_seq[cursor_col+1:]
                    else:
                        # Append if cursor is past end
                        sequences[cursor_row] = current_seq + "-"
                        
                cursor_col += 1
                modified = True
                
        # Direct alphanumeric character insertions / replacements
        elif isinstance(key, str) and len(key) == 1 and key.isalnum():
            if active_pane == 'seq':
                history.push_state(headers, sequences)
                c_char = key  # Preserve user's casing
                current_seq = sequences[cursor_row]
                
                if insert_mode:
                    # Insert mode: pushes letters right
                    sequences[cursor_row] = current_seq[:cursor_col] + c_char + current_seq[cursor_col:]
                    # Pad all other sequences to align with new length
                    max_len = max(len(s) for s in sequences)
                    for i in range(len(sequences)):
                        if len(sequences[i]) < max_len:
                            sequences[i] = sequences[i] + '-' * (max_len - len(sequences[i]))
                else:
                    # Overwrite mode: replaces char at cursor
                    sequences[cursor_row] = current_seq[:cursor_col] + c_char + current_seq[cursor_col+1:]
                    
                cursor_col += 1
                modified = True

    # Restore terminal visibility and reset cursor on quit
    sys.stdout.write("\x1b[?25h\x1b[2J\x1b[H")
    sys.stdout.flush()
    print("Alignment Editor exited cleanly.")

# ==============================================================================
# MAIN ENTRY & FILES SELECTOR
# ==============================================================================
def display_retro_intro(files, selected_idx):
    """Draws retro ANSI BBS style menu."""
    cols, rows = shutil.get_terminal_size((80, 24))
    lines = []
    
    # Retro Title Banner (Plain ASCII art using slash/backslash for absolute font safety)
    banner = [
        "    ___    _  _          _   _                        ",
        "   /   |  | |(_)        | \\ | |                       ",
        "  / /| |  | | _   __ _  |  \\| |  __ _  _ __    ___    ",
        " / ___ |  | || | / _` | | . ` | / _` || '_ \\  / _ \\   ",
        "/_/  |_|  |_||_|| (_| | |_|\\__|\\__,_||_| |_|\\___/    ",
        "                 \\__, |                               ",
        "                 |___/                                "
    ]
    
    colors = get_theme_colors()
    
    lines.append("\x1b[H\x1b[2J") # Clear and home
    lines.append(colors['accent'] + "=" * cols + colors['reset'])
    
    # Render banner centered
    for bline in banner:
        pad = max(0, (cols - len(bline)) // 2)
        lines.append(colors['gold'] + " " * pad + bline + colors['reset'])
        
    lines.append(colors['accent'] + "=" * cols + colors['reset'])
    lines.append(colors['bold'] + "  Multiple Sequence Alignment Editor & Browser" + colors['reset'])
    lines.append("  Inspired by ANSI BBSs (80s), tmux, and Antigravity CLI\n")
    
    lines.append("  " + colors['bold'] + "Select a FASTA file from the current workspace or create a new alignment:" + colors['reset'] + "\n")
    
    # Render file selector list
    for idx, f in enumerate(files):
        if idx == selected_idx:
            # Highlight selected item
            lines.append(f"   {colors['select_bg']} * {f} {colors['reset']}")
        else:
            lines.append(f"     - {f}")
            
    lines.append("")
    lines.append(colors['dim'] + "  [Arrows] Move selection   [Enter] Open Selection   [Q] Quit" + colors['reset'])
    lines.append(colors['accent'] + "=" * cols + colors['reset'])
    
    sys.stdout.write("\n".join(lines))
    sys.stdout.flush()

def main():
    if len(sys.argv) > 1:
        filepath = sys.argv[1]
        run_editor(filepath)
        return
        
    # Interactive menu for workspace directories
    # Only look inside workspace (current directory AligNano)
    workspace_files = []
    # Create lists of files matching standard extensions
    valid_exts = ('.fasta', '.fa', '.msa', '.seq')
    for f in sorted(os.listdir('.')):
        if os.path.isfile(f) and f.lower().endswith(valid_exts):
            workspace_files.append(f)
            
    # Add options for new files and quitting
    workspace_files.append("[Create New Empty Alignment]")
    workspace_files.append("[Exit]")
    
    selected_idx = 0
    
    # Hide cursor
    sys.stdout.write("\x1b[?25l")
    sys.stdout.flush()
    
    try:
        while True:
            display_retro_intro(workspace_files, selected_idx)
            try:
                key = read_key()
            except TerminalResizeException:
                sys.stdout.write("\x1b[2J")
                sys.stdout.flush()
                continue
            
            if key == 'KEY_UP':
                selected_idx = max(0, selected_idx - 1)
            elif key == 'KEY_DOWN':
                selected_idx = min(len(workspace_files) - 1, selected_idx + 1)
            elif key == 'ENTER':
                choice = workspace_files[selected_idx]
                if choice == "[Exit]":
                    break
                elif choice == "[Create New Empty Alignment]":
                    # Prompt for file name
                    sys.stdout.write("\x1b[?25h\n Enter name for new FASTA file: ")
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
                        print("Access denied (sandbox policy: AligNano folder only).")
                        time.sleep(2)
                        continue
                        
                    # Initialize empty alignment
                    save_fasta(new_filename, ["Seq_1"], ["ACTG-ACTG-ACTG-ACTG"])
                    run_editor(new_filename)
                    break
                else:
                    run_editor(choice)
                    break
            elif key == 'Q' or key == 'ESCAPE':
                break
    finally:
        # Show cursor and reset screen on exit
        sys.stdout.write("\x1b[?25h\x1b[H\x1b[2J")
        sys.stdout.flush()

if __name__ == "__main__":
    main()
