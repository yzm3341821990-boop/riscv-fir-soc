"""Run explicitly to access the board; import only has no side effects."""
from pathlib import Path
from tools.cpu5_sdk import CPU5,Program

def main():
    source=Path(__file__).with_name('square.c').read_text(encoding='utf-8')
    program=Program.compile(source,Path('F:/CodexWorkspace/outputs/riscv-fir-soc/my-python-cpu-app'))
    cpu=CPU5()
    try:
        cpu.connect() # Explicit board access. Disconnect the browser's CPU5 first.
        result=cpu.run(program,[2,-3,8])
        print(result['output'])
        print(result['console'])
        print('CPU cycles:',result['cycles'])
    finally:cpu.close()

if __name__=='__main__':main()
