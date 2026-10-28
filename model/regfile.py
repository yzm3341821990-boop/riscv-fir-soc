"""Edge-based reference for regfile32-rv32i-v1; no assumed power-on data."""


def _port(value, bits, name):
    if not isinstance(value, int) or isinstance(value, bool):
        raise TypeError(f"{name} must be an integer port value")
    if not 0 <= value < 1 << bits:
        raise ValueError(f"{name} does not fit {bits} bits")
    return value


class RegisterFileReference:
    def __init__(self):
        self._words = [None] * 32
        self._words[0] = 0

    def read(self, address):
        address = _port(address, 5, "read address")
        value = self._words[address]
        if value is None:
            raise RuntimeError("ordinary register has not been reset or written")
        return value

    def edge(self, reset, write_enable, write_address, write_data):
        """Apply one rising edge; reads between edge calls observe saved data."""
        reset = _port(reset, 1, "reset")
        write_enable = _port(write_enable, 1, "write enable")
        write_address = _port(write_address, 5, "write address")
        write_data = _port(write_data, 32, "write data")
        if reset:
            self._words = [0] * 32
        elif write_enable and write_address:
            self._words[write_address] = write_data
