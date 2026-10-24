"""Structural public derivatives: remove unrelated argv while preserving numeric evidence."""
import json,re,hashlib
APPROVED_SELECTED_IDENTITIES=[]
def configure_selected_identities(document):
    global APPROVED_SELECTED_IDENTITIES
    expected={"name","id","image","image_id","path","args","created","started_at","compose_project","compose_service"}
    values=[]
    for row in document["services"]:
        identity=row["identity"]
        if set(identity)!=expected or hashlib.sha256(json.dumps(identity,sort_keys=True,separators=(",",":")).encode()).hexdigest()!=row["selected_role_config_sha256"]:raise RuntimeError("Selected identity schema/digest")
        values.append(identity)
    if len(values)!=3 or len({x["name"] for x in values})!=3:raise RuntimeError("Expected exact three approved selected identities")
    APPROVED_SELECTED_IDENTITIES=values
def approved_identity(value):
    if not isinstance(value,dict):return False
    candidate=dict(value)
    if "status" in candidate:
        if candidate.pop("status")!="running":return False
    return candidate in APPROVED_SELECTED_IDENTITIES
SENSITIVE_FIELDS={'full_command','Command','Labels','Env'}
SECRET=re.compile(rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|\bgh[pousr]_[A-Za-z0-9]{30,}\b|\bgithub_pat_[A-Za-z0-9_]{30,}\b|Bearer [A-Za-z0-9._~+/-]{20,}')
def process_record(value):
    return isinstance(value,dict) and (('exe_name' in value and ('pid' in value or 'cpu' in value)) or ('exe' in value and 'max_ps_cpu_percent' in value))
def raw_service_identity(value):
    # The source inspection receipt also retained compose config locations. Only
    # the three exact approved canonical dictionaries above may retain role fields.
    return isinstance(value,dict) and {'name','id','image','image_id','path','args','created','started_at'}<=set(value)
def sensitive_field(value,key):
    return key in SENSITIVE_FIELDS or (key=='command' and process_record(value)) or (raw_service_identity(value) and key in {'compose_labels','path','args'})
def collect_strings(value,pool):
    if approved_identity(value):return
    if isinstance(value,dict):
        for key,child in value.items():
            sensitive=sensitive_field(value,key)
            if sensitive:
                def harvest(x):
                    if isinstance(x,str) and x:pool.add(x)
                    elif isinstance(x,list):
                        for y in x:harvest(y)
                    elif isinstance(x,dict):
                        for y in x.values():harvest(y)
                harvest(child)
            collect_strings(child,pool)
    elif isinstance(value,list):
        for child in value:collect_strings(child,pool)
def numeric_fields(value,path=()):
    if isinstance(value,dict):
        return {p:x for k,v in value.items() for p,x in numeric_fields(v,path+(str(k),)).items()}
    if isinstance(value,list):return {p:x for i,v in enumerate(value) for p,x in numeric_fields(v,path+(str(i),)).items()}
    if isinstance(value,(int,float,bool)) or value is None:return {path:value}
    return {}
def scrub(value,pool,field=''):
    if approved_identity(value):return value
    if isinstance(value,dict):
        out={}
        for key,child in value.items():
            sensitive=sensitive_field(value,key)
            if sensitive:
                def redact(x):
                    if isinstance(x,str):return '[redacted unrelated process/container text]'
                    if isinstance(x,list):return [redact(y) for y in x]
                    if isinstance(x,dict):return {k:redact(y) for k,y in x.items()}
                    return x
                out[key]=redact(child)
            else:out[key]=scrub(child,pool,key)
        return out
    if isinstance(value,list):return [scrub(x,pool,field) for x in value]
    if isinstance(value,str):
        if field in {'exe_name','exe','comm','Name','Names','Image','ID','Id','interfering_process_names_guarded','interfering_command_patterns_guarded'}:
            return value
        # Error strings may embed a JSON/repr copy of the same process record.
        for text in sorted(pool,key=len,reverse=True):
            if len(text)<8:continue
            for spelling in [text,json.dumps(text)[1:-1],repr(text)[1:-1]]:
                value=value.replace(spelling,'[redacted unrelated process/container text]')
        return value
    return value
def public_json(original,pool,jsonl=False):
    values=[json.loads(x) for x in original.decode().splitlines()] if jsonl else [json.loads(original)]
    changed=[]
    for value in values:
        public=scrub(value,pool)
        if numeric_fields(value)!=numeric_fields(public):raise RuntimeError('Privacy derivative altered numeric evidence')
        changed.append(public)
    if changed==values:return original,False
    data=(''.join(json.dumps(x,separators=(',',':'))+'\n' for x in changed) if jsonl else json.dumps(changed[0],indent=2)+'\n').encode()
    return data,True
