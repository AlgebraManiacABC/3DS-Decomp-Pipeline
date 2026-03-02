import sys
import csv
from files import gather_bearings
from ELF import *

EXIT_SUCCESS=0
EXIT_FAILURE=1

def main(argv: list[str]) -> int:
    """
    Main function
    :param argv: sys.argv
    :return: exit code
    """

    (compiled_objects,
     binary_file,
     symbol_file,
     split_dir) = gather_bearings(argv)
    print(f"Compiled objects located in: {compiled_objects[0].parent}")
    print(f"Binary to split: {binary_file}")
    print(f"Symbol file: {symbol_file}")
    print(f"Directory to output split objects: {split_dir}")

    # Locations of matching binaries within the main binary
    address_matches = []
    # Symbols imported by compiled binaries
    #  (must be exported by a split binary)
    undefined_symbols = []

    binary_bytes = binary_file.read_bytes()
    for o_file in compiled_objects:
        o = ELF.from_path(o_file)
        found = find_all_bytes(binary_bytes, o.data, o.mask)
        undefined_symbols += o.imported_symbols
        if not found:
            raise Exception(f"Binary file {o_file} was not found in {binary_file}!")

        print(f"Found {len(found)} {'matches' if len(found) > 1 else 'match'} for {o_file}!")
        for start_addr in found:
            end_addr = start_addr + len(o.data) - 1
            address_matches.append((start_addr, end_addr))

    # Calculate interstitial space (bytes which were not user-compiled)
    to_objectify = []
    address_matches.sort(key=lambda a: a[0])
    start_addr = 0
    while address_matches:
        next_obj = address_matches.pop(0)
        if next_obj[0] > start_addr:
            # Plan new object ending just before next start
            to_objectify.append((start_addr, next_obj[0]-1))
        start_addr = next_obj[1] + 1
    # Plan trailing bytes as final object
    if start_addr < len(binary_bytes):
        to_objectify.append((start_addr, len(binary_bytes)))

    # TODO: Create object files from interstitial space, exporting symbols which are imported by user-compiled objects

    return EXIT_SUCCESS


if __name__ == '__main__':
    try:
        sys.exit(main(sys.argv))
    except Exception as e:
        print(f"An issue occurred while running {sys.argv[0]}:")
        print(e)
        print("Program aborted.")
        sys.exit(EXIT_FAILURE)
