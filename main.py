import hashlib
import subprocess
import sys
import json
from files import gather_bearings
from pipeline import link_by_seriatum, generate_objdiff_unit, recreate_binary
from split import split_by_symbols
from util import subp_run, EXIT_SUCCESS, EXIT_FAILURE


def main(argv: list[str]) -> int:
    """
    Main function
    :param argv: sys.argv
    :return: exit code
    """

    info = gather_bearings(argv)
    print(f"Source file count: {len(info.sources)}")
    print(f"Binaries to split:")
    for binary in info.binaries:
        print(f"\t{binary}")
    print(f"Symbol files loaded:")
    for sym_file, sym_list in info.symbols.items():
        print(f"\t{sym_file} ({len(sym_list)} symbols)")
    print(f"Build directory: {info.build_dir}")
    print(f"Split directory: {info.split_dir}")
    print(f"Final output directory: {info.out_dir}")

    ld = str((info.tool_dir / 'ld').resolve())
    objcopy = str((info.tool_dir / 'objcopy').resolve())

    objdiff_units = []

    for name in info.binaries.keys():
        # Compile
        to_compile = info.sources.get(name,[])
        compiled = []
        default = info.cc_info.get('default', None)
        ignore_list = info.cc_info.get(name,{}).get('ignored', [])
        errored = []
        num_to_compile = len(to_compile)
        for i, c in enumerate(to_compile):
            if info.args['progress_reports'] and i % int(num_to_compile / 100) == 0:
                print(f"[COMPILER PROGRESS] {i/num_to_compile:.1f}%")
            if c.name in ignore_list:
                continue
            bld = info.build_dir / name / (c.stem + '.o')
            bld.parent.mkdir(parents=True, exist_ok=True)
            d = info.cc_info[name].get(c.name, None)
            if not d:
                d = default
            cc = d['cc']
            flags = d['flags']
            cmd = [str(info.tool_dir / cc), *flags, str(c), '-c', '-o', str(bld)]
            print(" ".join(cmd))
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != EXIT_SUCCESS:
                if info.args['ignore_compiler_errors']:
                    print(f"Error compiling {c}! Skipping!")
                    errored.append(c)
                    continue
                else:
                    raise Exception(f"Compiler error!\nstdout:\n{result.stdout}\n\nstderr:\n{result.stderr}")
            # Since armcc doesn't globalize the symbol (and we might need it for linking), globalize with objcopy
            cmd = [objcopy, f'--globalize-symbol={c.name}', str(bld)]
            subp_run(cmd, False, f"Objcopy error on {c}!")
            compiled.append(bld)
        if info.args['progress_reports']:
            print("[COMPILER PROGRESS] 100%")

        if errored:
            print(f"Error compiling {len(errored)} functions!! First 10:")
            for e in errored[0:10]:
                print(e)

        if info.args['compile_only']:
            if info.args['progress_reports']:
                print(f"COMPILATION OF {name.upper()} COMPLETE!")
            continue

        # Split
        print(f"Splitting {name}")
        (info.split_dir / name).mkdir(parents=True, exist_ok=True)
        targets = split_by_symbols(info.binaries[name], info.split_dir / name, info.symbols.get(name, []))

        # Generate objdiff json units
        units, to_link = generate_objdiff_unit(name, info.working_dir, compiled, targets)
        objdiff_units += units

        if info.recreating_binaries:
            # Link
            linked = link_by_seriatum(name, to_link, info.out_dir, ld, False, info)

            # Objcopy
            final_binary = recreate_binary(name, info.out_dir, objcopy, linked, info.binaries[name])
            linked.unlink()

            # Hash check - did we create an identical binary?
            de_novo = hashlib.sha256(final_binary.read_bytes()).digest()
            original_file = next(p for p in info.originals if p.name == name)
            existing = hashlib.sha256(original_file.read_bytes()).digest()
            if de_novo != existing:
                raise Exception(f"Binary {name} was created, but does not match original!")

            if info.args['progress_reports']:
                print(f"ROUND TRIP DECOMP COMPLETE FOR {name.upper()}!!")
        else:
            if info.args['progress_reports']:
                print(f"OBJECT CREATION COMPLETE FOR {name.upper()}!!")

    if not info.args['compile_only']:
        objdiff = {
            "$schema": "https://raw.githubusercontent.com/encounter/objdiff/main/config.schema.json",
            "build_target": False,
            "build_base": False,
            "units": objdiff_units,
            "progress_categories": [{"id": n, "name": n} for n in info.binaries.keys()]
        }
        objdiff_path = info.working_dir / 'objdiff.json'
        objdiff_path.write_text(json.dumps(objdiff, indent=2))

    return EXIT_SUCCESS


if __name__ == '__main__':
    # try:
    sys.exit(main(sys.argv))
    # except Exception as e:
    #     print(f"An issue occurred while running {sys.argv[0]}:")
    #     print(e)
    #     print("Program aborted.")
    #     sys.exit(EXIT_FAILURE)
