from pathlib import Path

from ctrtype import CRO, CTRBinary
from util import subp_run, BinaryWriter


def generate_objdiff_unit(name: str, working_dir: Path, compiled: list[Path], targets: list[tuple[int, Path]]) -> tuple[list, list[Path]]:
    # Generate objdiff json units
    objdiff_units = []
    target_dict: dict[int, Path] = {addr: path for addr, path in targets}
    compiled_dict = {path.stem: path for path in compiled}
    to_link = []
    for t_addr, t_path in sorted(target_dict.items()):
        base_path = compiled_dict.get(t_path.stem, None)
        if base_path:
            to_link.append(base_path)
        else:
            to_link.append(t_path)
        objdiff_units.append({
            "name": f'{name}/{t_path.stem}',
            "target_path": str(t_path.relative_to(working_dir)),
            "base_path": str(base_path.relative_to(working_dir)) if base_path else None,
            "metadata": {
                "progress_categories": [name],
                "complete": False if base_path is None else None
            }
        })
    return objdiff_units, to_link


def link_by_seriatum(name: str, to_link: list[Path], out_dir: Path, ld: str, verbose: bool) -> Path:
    # Link (in groups of files, so we can see progress)
    link_by = 100
    response_file = out_dir / f'{name}.txt'
    link_bounds = [(i, i + link_by) for i in range(0, len(to_link), link_by)]
    temp_links: list[Path] = []
    for i, bounds in enumerate(link_bounds):
        linked = out_dir / f'{name}_linked_{bounds[0]}'
        response_file.write_text('\n'.join('"' + str(o).replace('\\', '/') + '"' for o in to_link[bounds[0]:bounds[1]]))
        cmd = [ld, '--entry=0', '--no-warn-mismatch', '-r', f'@{response_file}', '-o', str(linked)]
        print(f"[LINKER PROGRESS] {link_by * i / len(link_bounds):.1f}%")
        subp_run(cmd, verbose, "Linker error!")
        temp_links.append(linked)

    linked = out_dir / f'{name}_linked'
    print("[LINKER PROGRESS] Performing final link...")
    response_file.write_text('\n'.join(str(o).replace('\\', '/') for o in temp_links))
    cmd = [ld, '--entry=0', '--no-warn-mismatch',
           f'@{response_file}', '-o', str(linked)]
    subp_run(cmd, True, "Linker error!")
    for link in temp_links:
        link.unlink()
    response_file.unlink()
    return linked


def link_all(name: str, to_link: list[Path], out_dir: Path, ld: str) -> Path:
    response_file = out_dir / f'{name}.txt'
    linked = out_dir / f'{name}_linked'
    print("[LINKER PROGRESS] Performing final link...")
    response_file.write_text('\n'.join(str(o).replace('\\', '/') for o in to_link))
    cmd = [ld, '--entry=0', '--no-warn-mismatch',
           f'@{response_file}', '-o', str(linked)]
    subp_run(cmd, True, "Linker error!")
    response_file.unlink()
    return linked


def recreate_binary(name: str, out_dir: Path, objcopy: str, linked: Path, in_binary: CTRBinary):
    # Objcopy
    final_binary = out_dir / name
    if '.cro' in name:
        final_binary = out_dir / f'{name}.temp'
    cmd = [objcopy, str(linked), '-O', 'binary', str(final_binary)]
    subp_run(cmd, True, "Objcopy error!")

    # .cro modules need recreated
    if '.cro' in name:
        cro = CRO.from_cro(in_binary.binary, final_binary.read_bytes())
        final_cro = out_dir / name
        writer = BinaryWriter()
        cro.write(writer)
        writer.flush(final_cro)
        final_binary.unlink()
        final_binary = final_cro

    return final_binary