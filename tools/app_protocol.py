"""CPU5 sequential 16 KiB code upload profile; never accesses hardware."""
from tools.runner_protocol import WRITE,READ,RUN,STATUS,BEGIN,WRITE_CODE,READ_CODE,decode,ProtocolError

def encode(token,op,seq,address=0,count=0,values=()):
    for name,v,limit in [('token',token,1),('opcode',op,7),('sequence',seq,65535),('address',address,8191),('count',count,8)]:
        if type(v) is not int or not 0<=v<=limit:raise ValueError('Invalid '+name)
    if op<1:raise ValueError('Invalid opcode')
    values=tuple(values)
    if any(type(v) is not int or not 0<=v<=0xffffffff for v in values):raise ValueError('Expected u32 words')
    if op in (WRITE,READ,WRITE_CODE,READ_CODE):
        if not 1<=count<=8 or address+count>(4095 if op==WRITE_CODE else 4096 if op==READ_CODE else 8192):raise ValueError('Transfer outside memory')
        if len(values)!=(count if op in (WRITE,WRITE_CODE) else 0):raise ValueError('Payload length differs')
    elif op==BEGIN:
        if address or count or len(values)!=1 or not 1<=values[0]<=4095:raise ValueError('Program needs 1..4095 words')
    elif op==STATUS:
        if count or values or address>12:raise ValueError('Invalid status page')
    elif address or count or values:raise ValueError('Unexpected RUN fields')
    payload=sum(v<<(32*i) for i,v in enumerate(values))
    return f'{(0x51<<312)|(token<<311)|(op<<308)|(seq<<292)|(address<<279)|(count<<274)|(1<<258)|payload:080X}'
