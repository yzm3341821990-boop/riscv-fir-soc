"""CPU0 bounded full-word upload protocol; no hardware access on import."""
from tools.live_protocol import ProtocolError,decode_response

WRITE,READ,RUN,STATUS,BEGIN,WRITE_CODE,READ_CODE=range(1,8)
def encode(token,op,seq,address=0,count=0,values=()):
    for name,v,limit in [('token',token,1),('opcode',op,7),('sequence',seq,65535),('address',address,8191),('count',count,8)]:
        if type(v) is not int or not 0<=v<=limit:raise ValueError('Invalid '+name)
    if op<1:raise ValueError('Invalid opcode')
    values=tuple(values)
    if any(type(v) is not int or not 0<=v<=0xffffffff for v in values):raise ValueError('Expected raw 32-bit words')
    if op in (WRITE,READ,WRITE_CODE,READ_CODE):
        if not 1<=count<=8 or address+count>(256 if op in (WRITE_CODE,READ_CODE) else 8192):raise ValueError('Transfer outside memory')
        if len(values)!=(count if op in (WRITE,WRITE_CODE) else 0):raise ValueError('Payload length mismatch')
    elif op==BEGIN:
        if address or count or len(values)!=1 or not 1<=values[0]<=255:raise ValueError('Invalid program length')
    elif op==STATUS:
        if count or values or address>2:raise ValueError('Invalid status page')
    elif address or count or values:raise ValueError('Unexpected RUN fields')
    payload=sum(v<<(32*i) for i,v in enumerate(values))
    return f'{(0x51<<312)|(token<<311)|(op<<308)|(seq<<292)|(address<<279)|(count<<274)|(1<<258)|payload:080X}'

def decode(reply,request):
    if not isinstance(reply,str) or not 1<=len(reply)<=80:raise ProtocolError('Malformed CPU0 reply')
    try:value=int(reply,16)
    except ValueError as exc:raise ProtocolError('Malformed CPU0 hexadecimal reply') from exc
    error=(value>>270)&15
    result=decode_response(f'{value&~(15<<270):080X}',request)
    if error:
        labels={1:'malformed request',2:'device busy or wrong state',3:'stale sequence',4:'memory range',5:'instruction upload incomplete',7:'link reset',9:'unknown operation'}
        raise ProtocolError(f'CPU0 error {error}: '+labels.get(error,'unknown'))
    return result
