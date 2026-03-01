from tkinter import filedialog

def gather_bearings():
    """

    :return:
    """

    compiled_dir = filedialog.askdirectory(
        initialdir='.',
        mustexist=True,
        title="User-compiled objects directory"
    )
    if not compiled_dir:
        raise Exception("Did not pick a user-compiled object directory!")

    binary_file = filedialog.askopenfilename(
        filetypes=[("3DS Executable Binary", "*.cro code.bin"), ("All files", "*")],
        title="Binary to Split"
    )
    if not binary_file:
        raise Exception("Did not pick the binary to split!")

    symbol_file = filedialog.askopenfilename(
        filetypes=[("All files", "*")],
        title="Symbol file"
    )
    if not symbol_file:
        raise Exception("Did not pick the symbol file!")

    split_dir = filedialog.askdirectory(
        mustexist=False,
        title="Split object output directory"
    )
    if not split_dir:
        raise Exception("Did not pick the output directory!")

    return compiled_dir, binary_file, symbol_file, split_dir