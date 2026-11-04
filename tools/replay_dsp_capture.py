"""Recheck the saved DSP6 board capture offline against the packaged ELF."""
import argparse
import hashlib
import json
from pathlib import Path

from tools.dsp_session import DspSession


class RecordedTransport:
    source_kind = 'fpga_jtag'

    def __init__(self, transcript):
        self.initial_token = transcript['ready']['token']
        self.device_info = {key: value for key, value in transcript['ready'].items() if key != 'token'}
        self.pairs = iter(transcript['pairs'])

    def exchange(self, packet):
        request, reply = next(self.pairs)
        if packet != request:
            raise ValueError('Request differs from the saved JTAG exchange')
        return reply


def replay(record, transcript, elf):
    if record['source_kind'] != 'fpga_jtag' or transcript['format'] != 'dsp6-jtag-replay-v1':
        raise ValueError('Expected a saved DSP6 board capture')
    if hashlib.sha256(elf).hexdigest() != record['elf_sha256']:
        raise ValueError('ELF differs from the saved capture')
    transport = RecordedTransport(transcript)
    session = DspSession(transport, record['elf_sha256'])
    session.initialize()
    result = session.run(elf, record['input'])
    if next(transport.pairs, None) is not None:
        raise ValueError('Unused exchanges remain after replay')
    excluded = {'captured_at_utc', 'host_ms'}
    if {k: v for k, v in result.items() if k not in excluded} != {k: v for k, v in record.items() if k not in excluded}:
        raise ValueError('Replayed result differs from the saved board result')
    return {'status': 'passed', 'method': 'offline_replay', 'saved_source_kind': record['source_kind'],
            'samples': result['input'][0], 'blocks': result['blocks'], 'exchanges': len(transcript['pairs']),
            'profile_cycles': result['profile_cycles'], 'output_mismatches': result['output'][5]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    evidence = Path(__file__).resolve().parents[1] / 'reports/step36-dsp-c'
    parser.add_argument('--record', type=Path, default=evidence / 'observed-65536.json')
    parser.add_argument('--transcript', type=Path, default=evidence / 'jtag-exchanges-65536.json')
    parser.add_argument('--elf', type=Path, default=Path(__file__).resolve().parents[1] / 'programs/dsp6/program.elf')
    args = parser.parse_args()
    print(json.dumps(replay(json.loads(args.record.read_bytes()), json.loads(args.transcript.read_bytes()), args.elf.read_bytes())))


if __name__ == '__main__':
    main()
