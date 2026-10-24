#!/usr/bin/env python3
"""Prospective host admission correction only; never runs live checks or benchmarks."""
import ast,hashlib,json,pathlib,shutil
A=pathlib.Path('/Users/pushparaj/projects/SwiftJLS-audit/m4-20261024')
OLD=A/'campaigns005-confirmation'; NEW=A/'campaigns005-final-services'
def sha(p):return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
def write(p,v):p.write_text(json.dumps(v,indent=2)+'\n')
def replace_func(s,name,new):
 n=next(n for n in ast.parse(s).body if isinstance(n,ast.FunctionDef) and n.name==name)
 ls=s.splitlines(keepends=True);return ''.join(ls[:n.lineno-1])+new.rstrip()+'\n'+''.join(ls[n.end_lineno:])
assert not NEW.exists()
assert sha(OLD/'campaign-freeze.json')=='71487cb4d5272ef0791e04aeeada506ec94ade2fa244f3ec2791539674b0a948'
shutil.copytree(OLD,NEW,ignore=shutil.ignore_patterns('runs','__pycache__'))
# New package is only for the two uncompleted scopes. Short proof remains in OLD.
for name in ['short1032_runner.py','short1032_analyse.py','schedules/short1032-3arms-005.json']:(NEW/name).unlink()
proof=A/'016-shared-service-admission/identities.json'
entries=[]
for service in json.loads(proof.read_text())['services']:
 identity={k:service[k] for k in ['name','id','image','image_id','path','args','created','started_at']}
 identity['compose_project']=service['compose_labels']['com.docker.compose.project']
 identity['compose_service']=service['compose_labels']['com.docker.compose.service']
 digest=hashlib.sha256(json.dumps(identity,sort_keys=True,separators=(',',':')).encode()).hexdigest()
 entries.append({'identity':identity,'selected_role_config_sha256':digest})
write(NEW/'persistent-service-identities.json',{'schema':1,'source_receipt_sha256':sha(proof),'services':entries,'scope':'Exact three running shared services; selected fields only, no environment or private compose paths. Missing, restarted, recreated or changed identity fails. No host-idleness claim.'})
s=(NEW/'diag72_runner.py').read_text()
marker='def evaluate_colima_containers('
pos=s.index(marker)
helpers='''PERSISTENT_SERVICE_IDENTITIES = json.loads(
    (pathlib.Path(__file__).resolve().parent / "persistent-service-identities.json").read_text()
)
PERSISTENT_SERVICE_BY_NAME = {
    x["identity"]["name"]: x for x in PERSISTENT_SERVICE_IDENTITIES["services"]
}
PERSISTENT_INSPECT_FORMAT = (
    '{"name":{{json .Name}},"id":{{json .Id}},"image":{{json .Config.Image}},'
    '"image_id":{{json .Image}},"path":{{json .Path}},"args":{{json .Args}},'
    '"created":{{json .Created}},"started_at":{{json .State.StartedAt}},'
    '"status":{{json .State.Status}},'
    '"compose_project":{{json (index .Config.Labels "com.docker.compose.project")}},'
    '"compose_service":{{json (index .Config.Labels "com.docker.compose.service")}}}'
)


def persistent_identity_result(container: dict) -> tuple[bool, str]:
    name = str(container.get("Names", "")).strip()
    expected = PERSISTENT_SERVICE_BY_NAME.get(name)
    actual = container.get("persistent_service_identity")
    if expected is None or not isinstance(actual, dict):
        return False, "missing exact selected identity"
    actual = dict(actual)
    if actual.pop("status", None) != "running":
        return False, "service is not running"
    ps_id = str(container.get("ID", ""))
    if not re.fullmatch(r"[0-9a-f]{12,64}", ps_id) or not str(actual.get("id", "")).startswith(ps_id):
        return False, "inspection does not match docker ps ID"
    if actual.get("name") != name or actual.get("image") != container.get("Image"):
        return False, "inspection does not match docker ps name/image"
    if actual != expected["identity"]:
        return False, "selected identity changed"
    digest = hashlib.sha256(json.dumps(actual, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    if digest != expected["selected_role_config_sha256"]:
        return False, "selected identity digest differs"
    return True, "exact identity admitted; no CPU-idleness claim"


def inspect_persistent_services(containers: list[dict], env: dict[str, str]) -> dict:
    started = datetime.datetime.now(datetime.timezone.utc).isoformat()
    tick = time.monotonic()
    results = []
    for container in containers:
        name = str(container.get("Names", "")).strip()
        if name not in PERSISTENT_SERVICE_BY_NAME:
            continue
        # Inspect the ps ID, not a name which can race a replacement. Never emit full inspect/Env.
        ps_id = str(container.get("ID", ""))
        item = {"name": name, "ps_id": ps_id}
        try:
            require(re.fullmatch(r"[0-9a-f]{12,64}", ps_id) is not None, "Invalid docker ps ID")
            proc = subprocess.run(
                ["docker", "container", "inspect", "--format", PERSISTENT_INSPECT_FORMAT, ps_id],
                capture_output=True, text=True, env=env, timeout=10,
            )
            require(proc.returncode == 0, "Selected service inspection failed")
            selected = json.loads(proc.stdout)
            require(isinstance(selected, dict), "Selected service inspection must be one object")
            selected["name"] = str(selected.get("name", "")).removeprefix("/")
            container["persistent_service_identity"] = selected
            ok, reason = persistent_identity_result(container)
            item.update(identity=selected, identity_matches=ok, reason=reason)
        except (ValueError, RuntimeError, OSError, subprocess.SubprocessError) as error:
            container.pop("persistent_service_identity", None)
            item.update(identity_matches=False, reason=type(error).__name__ + ": selected inspection unavailable or invalid")
        results.append(item)
    return {"started_utc": started, "completed_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "inspection_seconds": time.monotonic() - tick, "services": results,
            "scope": "Selected identity checks outside timed Consumer; no environment/private config paths captured"}


def self_test_persistent_services() -> dict:
    import copy
    checked = []
    for name, entry in PERSISTENT_SERVICE_BY_NAME.items():
        identity = dict(entry["identity"], status="running")
        row = {"ID": identity["id"][:12], "Names": name, "Image": identity["image"],
               "Command": " ".join([identity["path"], *identity["args"]]), "Status": "Up", "persistent_service_identity": identity}
        require(not evaluate_colima_containers([row]), "Exact persistent identity rejected")
        for field, value in [("id", "0"*64), ("image_id", "sha256:"+"0"*64), ("image", "lookalike"),
                             ("compose_project", "test"), ("compose_service", "test"), ("path", "pytest"),
                             ("args", ["ng", "test"]), ("created", "changed"), ("started_at", "changed"), ("status", "exited")]:
            bad = copy.deepcopy(row); bad["persistent_service_identity"][field] = value
            require(evaluate_colima_containers([bad]), "Changed identity admitted: " + field)
        for field in ["ID", "Image", "Names"]:
            bad = copy.deepcopy(row); bad[field] = "lookalike"
            require(evaluate_colima_containers([bad]), "Wrong ps row admitted: " + field)
        bad = copy.deepcopy(row); bad.pop("persistent_service_identity")
        require(evaluate_colima_containers([bad]), "Name-only service admitted")
        bad = copy.deepcopy(row); bad["Command"] = "pytest -q"
        require(evaluate_colima_containers([bad]), "Active test command admitted despite exact identity")
        checked.append(name)
    return {"passed": True, "services": checked, "controls": "exact positive; ten identity mutations; three ps-row mutations; missing inspection; active test command"}


'''
s=s[:pos]+helpers+s[pos:]
s=replace_func(s,'evaluate_colima_containers','''def evaluate_colima_containers(containers: list[dict]) -> list[dict]:
    interfering = []
    for c in containers:
        name = str(c.get("Names", "")).strip()
        image = str(c.get("Image", "")).strip()
        command = str(c.get("Command", "")).strip()
        status = str(c.get("Status", "")).strip()
        identity = c.get("persistent_service_identity", {})
        selected_command = " ".join([str(identity.get("path", "")), *[str(x) for x in identity.get("args", [])]]) if isinstance(identity, dict) else ""
        active = ACTIVE_CONTAINER_PATTERN.search(f"{name} {image} {command} {selected_command}")
        admitted = name in SHARED_QUIESCENT_COLIMA_CONTAINERS
        reason = "unknown container"
        if name in PERSISTENT_SERVICE_BY_NAME:
            admitted, reason = persistent_identity_result(c)
        if not admitted or active:
            interfering.append({"rule": "active_colima_container_workload", "container_name": name,
                                "image": image, "command": command, "status": status,
                                "identity_admission_reason": reason if not active else "active workload pattern"})
    return interfering''')
s=s.replace('    containers = []\n    docker_ps_res =', '    containers = []\n    persistent_inspection = {"services": [], "scope": "docker ps unavailable"}\n    docker_ps_res =',1)
s=s.replace('        interfering.extend(evaluate_colima_containers(containers))','        persistent_inspection = inspect_persistent_services(containers, env)\n        interfering.extend(evaluate_colima_containers(containers))',1)
s=s.replace('        "running_containers": containers,','        "running_containers": containers,\n        "persistent_service_inspection": persistent_inspection,',1)
s=s.replace('PID 987 is the resident shared Colima Virtualization.Framework VM hosting only the persistent multi-day shared dev stack; never killed per host policy.','Resident shared Colima services admitted by the existing policy or exact selected identities; services remain running per user policy. This label records guard admission, not host or VM idleness.')
s=s.replace('        "host_guard_self_test_passed": True,','        "host_guard_self_test_passed": True,\n        "persistent_service_identity_controls": self_test_persistent_services(),',1)
(NEW/'diag72_runner.py').write_text(s)
helper=sha(NEW/'diag72_runner.py')
for filename in ['larger15_runner.py','rss528_runner.py']:
 s=(NEW/filename).read_text()
 if filename=='larger15_runner.py':
  s=s.replace('SHARED_HELPER_SHA = "41d857d93c6442ad31c446a2ee82ce86bcd3730bf5f3989f5a1e721108e1b5ea"',f'SHARED_HELPER_SHA = "{helper}"')
  s=s.replace('["campaign_identity.py", "identity.json", "campaign-freeze.json"]','["campaign_identity.py", "identity.json", "campaign-freeze.json", "persistent-service-identities.json"]')
 else:
  s=s.replace("'identity.json','campaign-freeze.json']","'identity.json','campaign-freeze.json','persistent-service-identities.json']")
 (NEW/filename).write_text(s)
# Only the plan location changes; every trial/order/value is preserved.
p=NEW/'schedules/larger15-guard-005.json';text=p.read_text();assert str(OLD) in text
p.write_text(text.replace(str(OLD),str(NEW)))
write(NEW/'host-admission-amendment.json',{'schema':1,'decided_before_any_new_larger_or_rss_measurements':True,'parent_package_freeze_sha256':sha(OLD/'campaign-freeze.json'),'change':'Exact selected-identity exception for dev_php82/dev_php71/dev_apache, including creation and start times; ACTIVE_CONTAINER_PATTERN and all existing process/VM/simulator/AC/thermal guards unchanged.','identity_receipt_sha256':sha(proof),'sanitized_identity_sha256':sha(NEW/'persistent-service-identities.json'),'host_scope':'Shared services remain running; neither identity admission nor low CPU snapshots prove host idleness.','unchanged':['candidate and baseline sources/binaries','original Consumer','all timed boundaries and 5+5 observations','larger15: 120 processes and 60 descriptive ratios','RSS528: 2112 processes, original four contrasts/maxima gate and 50000 bootstrap','5 percent gate and all existing inference criteria'],'short_scope':{'package':str(OLD),'run':'runs/short1032-002','unchanged':True,'no_short_collection_authorised_in_this_package':True},'retained_interrupted_larger_attempts':{'larger15-001':'initial AC admission, zero processes','larger15-002':'initial transient test workload admission, zero processes'},'planned_outputs':{'larger':str(NEW/'runs/larger15-003'),'rss':str(NEW/'runs/rss528-001')},'root_authorisation':'pending fresh preflight and independent method review; this preparation launches nothing'})
frozen=json.loads((OLD/'campaign-freeze.json').read_text())
frozen.update(prior_package_freeze_sha256=sha(OLD/'campaign-freeze.json'),amendment='Identity-pinned persistent shared-service admission only; completed short remains in prior package',preparation_script_sha256=sha(__file__),collection_authorised=False)
frozen['files']={str(p.relative_to(NEW)):sha(p) for p in sorted(NEW.rglob('*')) if p.is_file() and p.name!='campaign-freeze.json'}
write(NEW/'campaign-freeze.json',frozen)
write(A/'016-shared-service-admission/package-preparation.json',{'new_package':str(NEW),'freeze_sha256':sha(NEW/'campaign-freeze.json'),'helper_sha256':helper,'prior_freeze_unchanged':sha(OLD/'campaign-freeze.json'),'source_identity_unchanged':sha(NEW/'identity.json')==sha(OLD/'identity.json'),'rss_schedule_byte_equal':sha(NEW/'schedules/rss528-4arms-005.json')==sha(OLD/'schedules/rss528-4arms-005.json'),'larger_schedule_only_package_path_changed':(NEW/'schedules/larger15-guard-005.json').read_text().replace(str(NEW),str(OLD))==(OLD/'schedules/larger15-guard-005.json').read_text(),'measurement_launched':False})
print(sha(NEW/'campaign-freeze.json'),helper)
