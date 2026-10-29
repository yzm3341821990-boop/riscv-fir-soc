"""Pair only matching CPU, firmware, input and timing-boundary measurements."""
from collections import defaultdict

MODES=('software','hardware_cold','hardware_resident')
LANES=(1,2,4)


def compare_lanes(measurements):
    groups=defaultdict(dict)
    for row in measurements:
        lane,mode=row['lanes'],row['mode']
        if lane not in LANES or mode not in MODES:raise ValueError('invalid lane or mode')
        if type(row['cycles']) is not int or row['cycles']<=0:raise ValueError('invalid cycle interval')
        key=(row['case'],row['wait_policy']);slot=(lane,mode)
        if slot in groups[key]:raise ValueError('duplicate lane/mode measurement')
        groups[key][slot]=row
    if not groups:raise ValueError('no lane measurements')
    result=[]
    for (case,wait),rows in sorted(groups.items()):
        if set(rows)!={(p,m) for p in LANES for m in MODES}:raise ValueError('missing lane/mode')
        for key in ['initial_memory_sha256','compiler_configuration','layout_sha256','cpu_sha256']:
            if len({r[key] for r in rows.values()})!=1:raise ValueError('cross-lane mismatch: '+key)
        for mode in MODES:
            if len({rows[p,mode]['firmware_sha256'] for p in LANES})!=1:
                raise ValueError('cross-lane mismatch: firmware_sha256')
        sw={rows[p,'software']['cycles'] for p in LANES}
        if len(sw)!=1:raise ValueError('software baseline cycles differ between lanes')
        software=sw.pop()
        for p in LANES:
            cold,resident=rows[p,'hardware_cold'],rows[p,'hardware_resident']
            result.append(dict(case=case,wait_policy=wait,lanes=p,software_cycles=software,
                hardware_cold_cycles=cold['cycles'],hardware_resident_cycles=resident['cycles'],
                cold_kernel_cycles=cold['hardware_cycles'],resident_kernel_cycles=resident['hardware_cycles'],
                cold_software_ratio=software/cold['cycles'],resident_software_ratio=software/resident['cycles'],
                cold_vs_single_lane=rows[1,'hardware_cold']['cycles']/cold['cycles'],
                resident_vs_single_lane=rows[1,'hardware_resident']['cycles']/resident['cycles']))
    return result
