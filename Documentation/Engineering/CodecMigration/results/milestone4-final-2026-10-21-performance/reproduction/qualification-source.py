"""Capture the exact working source; a base commit is never a dirty source label."""
import hashlib, json, pathlib, subprocess
ROOT = pathlib.Path(__file__).resolve().parents[2]
OUT = pathlib.Path(__file__).resolve().parent
def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()
def source():
    files = [ROOT / 'Package.swift', ROOT / 'VERSION']
    for name in ['Sources', 'Tests']:
        files += [p for p in (ROOT/name).rglob('*') if p.is_file()]
    hashes = {str(p.relative_to(ROOT)): sha(p) for p in sorted(files)}
    head = subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    dirty = subprocess.check_output(['git','status','--porcelain','--untracked-files=all','--','Sources','Tests','Package.swift','VERSION'],cwd=ROOT,text=True)
    return dict(base_head=head, source_commit=head if not dirty else None,
                working_tree_changes=dirty, files=hashes)
def write(path, value):
    path.write_text(json.dumps(value,indent=2)+'\n')
def unchanged(before):
    if source()['files'] != before['files']:
        raise RuntimeError('Source/test/package contents changed during qualification')
