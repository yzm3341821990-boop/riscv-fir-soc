"""Check generated project reproducibility and complete, byte-accurate file lists."""
import hashlib
import json
from pathlib import Path
import re
import tempfile
import unittest

from tools.prepare_de2_pipeline import PROJECT,prepare


class PipelineProjectTests(unittest.TestCase):
    def test_existing_tool_logs_are_not_project_inputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            d=Path(tmp)
            (d/'previous-build.log').write_text('old vendor output')
            manifest=prepare(d)
            self.assertNotIn('previous-build.log',manifest['generated_sha256'])

    def test_regeneration_keeps_manifest_hashes_valid(self):
        # A manifest that hashes its own previous contents fails after regeneration.
        with tempfile.TemporaryDirectory() as tmp:
            d=Path(tmp)
            prepare(d)
            manifest=prepare(d)
            for name,digest in manifest['generated_sha256'].items():
                self.assertEqual(hashlib.sha256((d/name).read_bytes()).hexdigest(),digest,name)

    def test_qsf_sources_exist_and_snapshots_match(self):
        with tempfile.TemporaryDirectory() as tmp:
            d=Path(tmp);manifest=prepare(d)
            qsf=(d/f'{PROJECT}.qsf').read_text()
            sources=re.findall(r'-name VHDL_FILE (\S+)',qsf)
            self.assertEqual(len(sources),len(set(sources)))
            self.assertTrue(all((d/name).is_file() for name in sources))
            self.assertEqual((d/'pipeline-qsf-before-build.txt').read_bytes(),(d/f'{PROJECT}.qsf').read_bytes())
            self.assertEqual(len(re.findall(r'^set_location_assignment ',qsf,re.M)),66)
            self.assertEqual(manifest['firmware_symbols']['_program_end'],300)
            self.assertFalse(manifest['physical_board_verified'])


if __name__=='__main__':unittest.main()
