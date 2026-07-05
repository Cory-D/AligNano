import subprocess
import os

def main():
    # troff/groff layout content
    troff_content = """.pl 7.0i
.po 0.3i
.ll 4.4i
.fam C
.ps 8
.vs 10
.nh
.nf
.LP
.ce 3
\\fB\\s[+4]ALIGNANO CHEAT-SHEET\\s[-4]\\fR
.sp 0.1
\\fICommand & Keyboard Reference\\fR
.sp 0.1
\\fB============================================\\fR
.sp 0.3
.ta 1.3i
\\fB[ NAVIGATION ]\\fR
.sp 0.1
Arrows\tMove cursor / Swap pane focus
Ctrl+U / Ctrl+D\tPage viewport Up / Down
Ctrl+L / Ctrl+R\tPage viewport Left / Right
Ctrl+H / ?\tOpen / Close Help menu
.sp 0.3
\\fB[ GRID EDITING ]\\fR
.sp 0.1
A-Z / a-z\tInsert / overwrite residue
Space / -\tInsert gap character (-)
Delete / Ctrl+K\tDelete base (in sequence pane)
.sp 0.3
\\fB[ ROW OPERATIONS ]\\fR
.sp 0.1
Delete / Ctrl+K\tDelete highlighted row (in names pane)
Ctrl+N / Ctrl+A\tAdd new empty sequence row
Ctrl+E / E\tEdit highlighted accession name
Ctrl+T / T\tToggle row move mode (re-order)
.sp 0.3
\\fB[ ALIGNMENT CONTROLS ]\\fR
.sp 0.1
Ctrl+V / V\tCycle colors (DNA -> AA -> DIFF -> Mono)
Ctrl+P / P\tToggle format (FASTA -> A3M)
Ctrl+W / C\tSort/cluster by Levenshtein distance
Ctrl+F / Ctrl+J\tSearch motif or name / Jump to next
.sp 0.3
\\fB[ FILE & HISTORY ]\\fR
.sp 0.1
Ctrl+S / S\tSave alignment to file
Ctrl+Z / U\tUndo last action (up to 50 states)
Ctrl+Y / Y\tRedo last action
Ctrl+Q / Q\tQuit editor (warns if unsaved)
.sp 0.3
\\fB============================================\\fR
.sp 0.2
.ce 1
\\fIAligNano terminal editor (c) 2026\\fR
"""

    with open('instruction_sheet.tr', 'w', encoding='utf-8') as f:
        f.write(troff_content)

    print("Compiling troff to PostScript...")
    with open('instruction_sheet.ps', 'w') as ps_out:
        subprocess.run(['groff', '-Tps', '-P-p5i,7i', 'instruction_sheet.tr'], stdout=ps_out, check=True)

    print("Converting PostScript to PDF...")
    subprocess.run([
        'ps2pdf', 
        '-dDEVICEWIDTHPOINTS=360', 
        '-dDEVICEHEIGHTPOINTS=504', 
        'instruction_sheet.ps', 
        'instruction_sheet.pdf'
    ], check=True)

    # Clean up temp files
    os.remove('instruction_sheet.tr')
    os.remove('instruction_sheet.ps')
    print("Complete. Generated instruction_sheet.pdf successfully!")

if __name__ == "__main__":
    main()
