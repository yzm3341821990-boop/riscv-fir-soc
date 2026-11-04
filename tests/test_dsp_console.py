import importlib.util,hashlib,json,tempfile,threading,unittest,urllib.request,urllib.error
from pathlib import Path
from tools.dsp_console import Controller,server_for
from tools.dsp_program import anchor
class ConsoleTests(unittest.TestCase):
    def test_initialization_is_offline_and_rejects_bad_count(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);(p/'firmware').mkdir();(p/'firmware/program.elf').write_bytes(b'ELF fixture')
            (p/'dsp-project-manifest.json').write_text(json.dumps(dict(firmware_elf_sha256=hashlib.sha256(b'ELF fixture').hexdigest())))
            called=[];c=Controller(p,lambda *_:called.append('hardware'))
            self.assertEqual(c.snapshot()['connection'],'disconnected');self.assertEqual(called,[])
            for n in (0,262145,True,1.5):
                with self.assertRaises(ValueError):c.run_samples(dict(samples=n))
            with self.assertRaises(ValueError):c.run_samples(dict(samples=65536))
            self.assertEqual(called,[])
    def test_changed_elf_fails_before_connection(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);(p/'firmware').mkdir();(p/'firmware/program.elf').write_bytes(b'changed')
            (p/'dsp-project-manifest.json').write_text(json.dumps(dict(firmware_elf_sha256='0'*64)))
            with self.assertRaisesRegex(ValueError,'ELF differs'):Controller(p)
    @unittest.skipUnless(importlib.util.find_spec('numpy'), 'DSP6 NumPy reference dependency is optional for the standard-library gate')
    def test_anchor_tail_and_large_counts(self):
        for n in (1,224,225,226,451,65536,262144):
            v=anchor(n);self.assertEqual(v[:2],[n,(n+224)//225]);self.assertEqual(v[2],v[3]);self.assertEqual(v[3],v[4]);self.assertEqual(len(v),7+min(n,96))
        for n in (0,True,262145):
            with self.assertRaises(ValueError):anchor(n)
    def test_http_cannot_start_without_local_token(self):
        class C:
            def snapshot(self):return dict(connection='disconnected')
        s=server_for(C(),0);t=threading.Thread(target=s.serve_forever,daemon=True);t.start()
        try:
            request=urllib.request.Request(f'http://127.0.0.1:{s.server_port}/api/connect',data=b'{}',headers={'Content-Type':'application/json'})
            with self.assertRaises(urllib.error.HTTPError) as e:urllib.request.urlopen(request)
            self.assertEqual(e.exception.code,403)
        finally:s.shutdown();s.server_close();t.join()
if __name__=='__main__':unittest.main()
