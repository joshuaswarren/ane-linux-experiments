import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).parent.parent
SPEC = importlib.util.spec_from_file_location(
    'hwx_check', Path(__file__).with_name('hwx_check.py')
)
assert SPEC is not None
assert SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class HWXCheckTests(unittest.TestCase):
    def test_reloc_against_kern0_accepted(self):
        # zin_ane_compiler writes the relocation's target section ordinal
        # (__kern_0) in the info word's low 24 bits. The kernel's
        # ane_h16_relocations_validate compares that field to
        # p->info.kernel.ordinal; a replica that compares it to the task
        # section's ordinal refuses every object the kernel accepts.
        # This fixture has text ordinal 3, kernel ordinal 5, and
        # reloc info 0x07000005.
        info = MODULE.validate(str(ROOT / 'tools/add64-h16.hwx.sample'))
        self.assertEqual(info.kernel.ordinal, 5)
        self.assertNotEqual(info.kernel.ordinal, info.text.ordinal)
        self.assertEqual(info.surface_count, 2)
        self.assertEqual(info.tasks, 2)

    def test_report_is_info_on_pass(self):
        info = MODULE.validate(str(ROOT / 'tools/add64-h16.hwx.sample'))
        self.assertEqual(info.subtype, MODULE.ANE_HWX_SUBTYPE_H16)


if __name__ == '__main__':
    unittest.main()
