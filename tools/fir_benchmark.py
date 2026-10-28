"""Build matched benchmark inputs and reject unfair/incomplete cycle comparisons."""
import hashlib
import json
from pathlib import Path
import struct

from model.fixed_fir import fir_block
from tools.build_fir_benchmark import LAYOUT, MODES, load_firmware
from tools.software_fir import fir_inputs, load_fir


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode('ascii')).hexdigest()


def compiler_configuration(manifest):
    fields=('zig_version','clang_version','compiler_sha256','compiler_cpu','abi','compiler_flags')
    return fingerprint({key:manifest[key] for key in fields})


def matched_cases():
    """Identical complete RAM images for each runtime dataset and all three modes."""
    firmwares={mode:load_firmware(mode) for mode in MODES}
    if len({image.memory_words for image,_ in firmwares.values()})!=1:
        raise ValueError('benchmark initial RAM differs between modes')
    if len({compiler_configuration(m) for _,m in firmwares.values()})!=1:
        raise ValueError('benchmark compiler configurations differ')
    if len({fingerprint(m['layout']) for _,m in firmwares.values()})!=1:
        raise ValueError('benchmark data layouts differ')
    image=firmwares['software'][0]
    _,old=load_fir()
    result=[]
    for old_name,memory in fir_inputs().items():
        raw=struct.pack('<256I',*memory)
        x=struct.unpack_from('<8h',raw,old['symbols']['samples'])
        h=struct.unpack_from('<32h',raw,old['symbols']['coefficients'])
        initial=bytearray(struct.pack('<256I',*image.memory_words))
        struct.pack_into('<8i',initial,LAYOUT['samples'],*x)
        struct.pack_into('<32i',initial,LAYOUT['coefficients'],*h)
        golden=fir_block(x,h)
        result.append({'name':old_name.replace('software_fir','base'),
                       'samples':list(x),'coefficients':list(h),
                       'initial_memory':list(struct.unpack('<256I',initial)),
                       'initial_memory_sha256':hashlib.sha256(initial).hexdigest(),
                       'outputs':list(golden.outputs)})
    return result,firmwares


def pair_measurements(measurements):
    grouped={}
    for row in measurements:
        key=(row['case'],row['wait_policy']);mode=row['mode']
        if mode not in MODES: raise ValueError('unknown benchmark mode')
        cycles=row['cycles']
        if type(cycles) is not int or cycles<=0: raise ValueError('invalid completed-call cycle measurement')
        group=grouped.setdefault(key,{})
        if mode in group: raise ValueError('duplicate benchmark measurement')
        group[mode]=row
    if not grouped: raise ValueError('no benchmark measurements')
    results=[]
    for (case,wait),group in sorted(grouped.items()):
        if set(group)!=set(MODES): raise ValueError('missing matched benchmark mode')
        for field in ('initial_memory_sha256','compiler_configuration','layout_sha256','platform_sha256'):
            if len({row[field] for row in group.values()})!=1:
                raise ValueError('unfair benchmark comparison: '+field)
        sw,cold,resident=(group[name] for name in MODES)
        results.append({'case':case,'wait_policy':wait,'software_cycles':sw['cycles'],
                        'hardware_cold_cycles':cold['cycles'],'hardware_resident_cycles':resident['cycles'],
                        'cold_cycle_ratio':sw['cycles']/cold['cycles'],
                        'resident_cycle_ratio':sw['cycles']/resident['cycles'],
                        'cold_kernel_cycles':cold['hardware_cycles'],
                        'resident_kernel_cycles':resident['hardware_cycles']})
    return results
