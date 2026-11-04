"""Bounded LIV0 mailbox packets and continuous-history digital signal frames."""
from dataclasses import dataclass
import math
import re
from model.fixed_fir import fir_block

SAMPLES=256
HISTORY=31
VALID_SAMPLES=SAMPLES-HISTORY
INPUT_WORD,COEFF_WORD,FIR_WORD,EXPECTED_WORD,SAVED_WORD=512,768,800,1056,4096
WRITE,READ,RUN,STATUS,BEGIN=1,2,3,4,5
ERRORS={1:'malformed command',2:'device busy',3:'stale frame sequence',4:'invalid range',
        5:'missing frame data',6:'RAM value is not signed Q15',7:'link reset',
        8:'CPU/FIR execution failed',9:'unsupported command'}


class ProtocolError(ValueError):
    pass


def _integer(value,maximum,label):
    if type(value) is not int or not 0<=value<=maximum:
        raise ValueError('Invalid '+label)
    return value


def encode_request(token,opcode,seq,address=0,count=0,values=()):
    _integer(token,1,'token');_integer(opcode,5,'opcode');_integer(seq,65535,'sequence')
    _integer(address,8191,'address');_integer(count,16,'count')
    if opcode not in (WRITE,READ,RUN,STATUS,BEGIN):raise ValueError('Invalid opcode')
    values=tuple(values)
    if opcode in (WRITE,READ):
        if count<1 or address+count>8192:raise ValueError('Invalid RAM range')
    elif count or (opcode!=STATUS and address):raise ValueError('Invalid control fields')
    if opcode==STATUS and address>2:raise ValueError('Invalid status page')
    if opcode==WRITE:
        if len(values)!=count or any(type(v) is not int or not -32768<=v<=32767 for v in values):
            raise ValueError('Invalid Q15 write payload')
    elif values:raise ValueError('Unexpected payload')
    payload=sum((v&65535)<<(16*i) for i,v in enumerate(values))
    value=(0x51<<312)|(token<<311)|(opcode<<308)|(seq<<292)|(address<<279)|(count<<274)|(1<<258)|payload
    return f'{value:080X}'


@dataclass(frozen=True)
class Reply:
    state:int
    words:tuple
    u32:tuple
    seq:int
    opcode:int
    address:int
    count:int


def decode_response(text,request):
    if not isinstance(text,str) or not re.fullmatch(r'[0-9A-Fa-f]{1,80}',text):
        raise ProtocolError('Malformed 320-bit probe')
    value=int(text,16);sent=int(request,16)
    if value>>312!=0x4c or (value>>258)&255!=1 or (value>>256)&3:
        raise ProtocolError('Wrong LIV0 image, signature or protocol version')
    mask=((1<<38)-1)<<274
    if value&mask != sent&mask:raise ProtocolError('Response token/sequence/opcode/address/count mismatch')
    error=(value>>270)&15
    if error:raise ProtocolError(f'FPGA error {error}: '+ERRORS.get(error,'unknown error'))
    words=tuple((value>>(16*i))&65535 for i in range(16))
    return Reply(state=(value>>266)&15,words=tuple(v-65536 if v>=32768 else v for v in words),
                 u32=tuple((value>>(32*i))&0xffffffff for i in range(8)),seq=(value>>292)&65535,
                 opcode=(value>>308)&7,address=(value>>279)&8191,count=(value>>274)&31)


@dataclass(frozen=True)
class SignalConfig:
    low_hz:float=1000
    high_hz:float=11000
    amplitude:float=.45
    high_amplitude:float=.35

    def __post_init__(self):
        for value in (self.low_hz,self.high_hz,self.amplitude,self.high_amplitude):
            if type(value) not in (float,int) or not math.isfinite(value):raise ValueError('Signal parameters must be finite numbers')
        if not 200<=self.low_hz<=3000 or not 6500<=self.high_hz<=18000:
            raise ValueError('Signal frequency outside the supported range')
        if min(self.amplitude,self.high_amplitude)<0 or self.amplitude+self.high_amplitude>.95:
            raise ValueError('Combined signal amplitude must be between 0 and 0.95')


@dataclass
class SignalFrame:
    samples:list
    expected:list
    coefficients:list
    valid_start:int
    sample_offset:int
    config:SignalConfig


class SignalSource:
    def __init__(self,coefficients):
        if len(coefficients)!=32 or any(type(v) is not int or not -32768<=v<=32767 for v in coefficients):
            raise ValueError('Expected 32 signed Q15 coefficients')
        self.coefficients=list(coefficients);self.history=[0]*HISTORY
        self.low_phase=0.;self.high_phase=0.;self.offset=0

    def next_frame(self,config):
        if not isinstance(config,SignalConfig):raise ValueError('Invalid signal configuration')
        fresh=[]
        for unused in range(VALID_SAMPLES):
            sample=(config.amplitude*math.sin(self.low_phase)+config.high_amplitude*math.sin(self.high_phase))*32768
            fresh.append(max(-32768,min(32767,math.floor(sample+.5) if sample>=0 else math.ceil(sample-.5))))
            self.low_phase=(self.low_phase+2*math.pi*config.low_hz/48000)%(2*math.pi)
            self.high_phase=(self.high_phase+2*math.pi*config.high_hz/48000)%(2*math.pi)
        values=self.history+fresh
        result=SignalFrame(values,list(fir_block(values,self.coefficients).outputs),
                           self.coefficients.copy(),HISTORY,self.offset,config)
        self.history=values[-HISTORY:];self.offset+=VALID_SAMPLES
        return result
